#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hf_to_gguf_numpy.py — 零 torch 依赖，把 Qwen3 的 HF safetensors 转成 GGUF v3 (Q4_0)。

背景：本机无 torch、无 peft、可用内存仅 ~3.6GB、且 llama.cpp 预编译包下载被
限速不可用。Ollama 0.35.1 从 safetensors 导入的模型运行时强依赖 MLX（Windows
不可用），但 Ollama 加载标准 GGUF 是稳定能力 —— 所以这里直接产出 GGUF。

用法:
  python scripts/hf_to_gguf_numpy.py \
      --model checkpoints/virtu_merged \
      --out checkpoints/virtu-q4_0.gguf

特点:
  - 纯 numpy 流式读写，峰值内存 < 200MB，不需要 torch / transformers / peft
  - Q4_0 量化（llama.cpp block_q4_0 语义），2D 权重量化，1D norm 保留 F32
  - 完整 GGUF metadata：qwen3 架构 + gpt2 tokenizer + chat_template
  - 张量名按 llama.cpp Qwen3 映射；dims 按 GGUF 规约反转写入
  - 支持 --check 只做结构自测（量化精度、张量名映射、header 解析）
"""

from __future__ import annotations

import argparse
import json
import os
import re
import struct
import sys
from pathlib import Path

import numpy as np

# --------------------------------------------------------------------------- #
# GGUF v3 常量
# --------------------------------------------------------------------------- #
GGUF_MAGIC = b"GGUF"
GGUF_VERSION = 3
GGUF_DEFAULT_ALIGNMENT = 32

# metadata value types
VT_UINT8, VT_INT8, VT_UINT16, VT_INT16 = 0, 1, 2, 3
VT_UINT32, VT_INT32, VT_FLOAT32, VT_BOOL = 4, 5, 6, 7
VT_STRING, VT_ARRAY, VT_UINT64, VT_INT64, VT_FLOAT64 = 8, 9, 10, 11, 12

# ggml tensor types
TT_F32, TT_F16, TT_Q4_0 = 0, 1, 2

# llama.cpp llama_ftype：MOSTLY_F16 = 1, MOSTLY_Q4_0 = 2
FILE_TYPE_F16 = 1
FILE_TYPE_Q4_0 = 2
GGML_QNT_VERSION = 2

# Q4_0 block: 32 weights -> 2 bytes fp16 scale + 16 bytes packed nibble = 18 bytes
Q4_0_BLOCK = 32
Q4_0_BYTES = 18

# 每次流式处理的元素数（必须是 32 的倍数），控制峰值内存
CHUNK_ELEMS = 32 * 8192  # 262144 elems -> bf16 512KB / f32 1MB


# --------------------------------------------------------------------------- #
# 基础二进制编码
# --------------------------------------------------------------------------- #
def _s(x: str) -> bytes:
    b = x.encode("utf-8")
    return struct.pack("<Q", len(b)) + b


def _u32(x: int) -> bytes:
    return struct.pack("<I", x)


def _i32(x: int) -> bytes:
    return struct.pack("<i", x)


def _u64(x: int) -> bytes:
    return struct.pack("<Q", x)


def _f32(x: float) -> bytes:
    return struct.pack("<f", float(x))


def _bool(x: bool) -> bytes:
    return struct.pack("<B", 1 if x else 0)


def kv_str(k: str, v: str) -> bytes:
    return _s(k) + _u32(VT_STRING) + _s(v)


def kv_u32(k: str, v: int) -> bytes:
    return _s(k) + _u32(VT_UINT32) + _u32(v)


def kv_i32(k: str, v: int) -> bytes:
    return _s(k) + _u32(VT_INT32) + _i32(v)


def kv_f32(k: str, v: float) -> bytes:
    return _s(k) + _u32(VT_FLOAT32) + _f32(v)


def kv_bool(k: str, v: bool) -> bytes:
    return _s(k) + _u32(VT_BOOL) + _bool(v)


def kv_u64(k: str, v: int) -> bytes:
    return _s(k) + _u32(VT_UINT64) + _u64(v)


def kv_arr_str(k: str, arr: list[str]) -> bytes:
    return (_s(k) + _u32(VT_ARRAY) + _u32(VT_STRING) + _u64(len(arr))
            + b"".join(_s(x) for x in arr))


def kv_arr_i32(k: str, arr: list[int]) -> bytes:
    return (_s(k) + _u32(VT_ARRAY) + _u32(VT_INT32) + _u64(len(arr))
            + b"".join(_i32(x) for x in arr))


# --------------------------------------------------------------------------- #
# dtype 转换
# --------------------------------------------------------------------------- #
def bf16_to_f32(a: np.ndarray) -> np.ndarray:
    """uint16 (bf16 位模式) -> float32"""
    return (a.astype(np.uint32) << 16).view(np.float32)


def f16_to_f32(a: np.ndarray) -> np.ndarray:
    """uint16 (fp16 位模式) -> float32"""
    return a.astype(np.uint16).view(np.float16).astype(np.float32)


RAW_DTYPE_NBYTES = {"F32": 4, "F16": 2, "BF16": 2}


def raw_to_f32(buf: bytes, dtype: str) -> np.ndarray:
    if dtype == "BF16":
        return bf16_to_f32(np.frombuffer(buf, dtype=np.uint16))
    if dtype == "F16":
        return f16_to_f32(np.frombuffer(buf, dtype=np.uint16))
    if dtype == "F32":
        return np.frombuffer(buf, dtype=np.float32).copy()
    raise ValueError(f"不支持的 dtype: {dtype}")


# --------------------------------------------------------------------------- #
# Q4_0 量化（向量化）
# --------------------------------------------------------------------------- #
def quantize_q4_0(arr: np.ndarray) -> bytes:
    """
    arr: 1D float32，长度必须是 32 的倍数。
    返回 Q4_0 block 字节流：每 32 权重 -> fp16 d (2B) + 16B packed nibbles。

    与 llama.cpp quantize_row_q4_0 一致：
        amax = max(|x|); d = amax / -8   (fp16 存储)
        q_i  = clip(round(x_i / d), -8, 7) + 8   (0..15)
    反量化： x_hat = (q - 8) * d
    """
    if arr.ndim != 1:
        arr = arr.reshape(-1)
    if arr.size % Q4_0_BLOCK != 0:
        raise ValueError(f"Q4_0 要求元素数为 32 倍数，得到 {arr.size}")
    blocks = arr.reshape(-1, Q4_0_BLOCK)
    amax = np.max(np.abs(blocks), axis=1)
    # d 必须按 fp16 精度存储，量化时用该精度反算（与 llama.cpp 一致）
    d16 = (amax / -8.0).astype(np.float16)
    d = d16.astype(np.float32)
    d = np.where(d == 0, np.float32(-1e-5), d)
    q = np.rint(blocks / d[:, None])
    q = np.clip(q, -8, 7).astype(np.int8) + 8  # 0..15
    lo = q[:, :16].astype(np.uint8)
    hi = q[:, 16:].astype(np.uint8) << 4
    qs = lo | hi
    out = np.empty((blocks.shape[0], Q4_0_BYTES), dtype=np.uint8)
    out[:, 0:2] = d16.view(np.uint8).reshape(-1, 2)
    out[:, 2:18] = qs
    return out.tobytes()


def dequantize_q4_0(buf: bytes, n: int) -> np.ndarray:
    """自测用：把 Q4_0 字节流还原成 float32，用于验证误差。"""
    a = np.frombuffer(buf, dtype=np.uint8).reshape(-1, Q4_0_BYTES)
    d = a[:, 0:2].copy().view(np.float16).reshape(-1).astype(np.float32)
    qs = a[:, 2:18]
    lo = (qs & 0x0F).astype(np.int16)
    hi = (qs >> 4).astype(np.int16)
    q = np.concatenate([lo, hi], axis=1).reshape(-1).astype(np.float32) - 8.0
    return (q * np.repeat(d, Q4_0_BLOCK))[:n]


# --------------------------------------------------------------------------- #
# safetensors 读取
# --------------------------------------------------------------------------- #
class SafeTensorReader:
    def __init__(self, path: Path):
        self.path = path
        with open(path, "rb") as f:
            hlen = struct.unpack("<Q", f.read(8))[0]
            self.header = json.loads(f.read(hlen))
        self.data_start = 8 + hlen
        self.entries = {k: v for k, v in self.header.items() if k != "__metadata__"}
        # 常驻句柄：8.19B 元素分 3 万块读取，避免反复 open/close
        self.f = open(path, "rb")

    def close(self):
        if getattr(self, "f", None):
            self.f.close()
            self.f = None

    def info(self, name: str):
        e = self.entries[name]
        return tuple(e["shape"]), e["dtype"], e["data_offsets"]

    def read_range(self, name: str, start_elem: int, count_elem: int) -> bytes:
        shape, dtype, (beg, _end) = self.info(name)
        nbytes = RAW_DTYPE_NBYTES[dtype]
        off = self.data_start + beg + start_elem * nbytes
        size = count_elem * nbytes
        self.f.seek(off)
        data = self.f.read(size)
        if len(data) != size:
            raise IOError(f"{self.path.name}:{name} 读取 {size}B 失败，实际 {len(data)}B")
        return data


# --------------------------------------------------------------------------- #
# HF -> GGUF 张量名映射（llama.cpp Qwen3Model）
# --------------------------------------------------------------------------- #
LAYER_MAP = {
    "input_layernorm.weight": "attn_norm.weight",
    "post_attention_layernorm.weight": "ffn_norm.weight",
    "self_attn.q_norm.weight": "attn_q_norm.weight",
    "self_attn.k_norm.weight": "attn_k_norm.weight",
    "self_attn.q_proj.weight": "attn_q.weight",
    "self_attn.k_proj.weight": "attn_k.weight",
    "self_attn.v_proj.weight": "attn_v.weight",
    "self_attn.o_proj.weight": "attn_output.weight",
    "mlp.gate_proj.weight": "ffn_gate.weight",
    "mlp.up_proj.weight": "ffn_up.weight",
    "mlp.down_proj.weight": "ffn_down.weight",
}


def map_name(hf: str) -> str | None:
    if hf == "model.embed_tokens.weight":
        return "token_embd.weight"
    if hf == "model.norm.weight":
        return "output_norm.weight"
    if hf == "lm_head.weight":
        return "output.weight"
    m = re.match(r"model\.layers\.(\d+)\.(.+)", hf)
    if m:
        idx, rest = m.groups()
        if rest in LAYER_MAP:
            return f"blk.{idx}.{LAYER_MAP[rest]}"
    return None


def gguf_dims(hf_shape: tuple) -> tuple:
    """GGUF tensor info 的 dims 按 GGML 规约反转（ne0 为最快变化维）。"""
    return tuple(reversed(hf_shape))


# --------------------------------------------------------------------------- #
# metadata 构造
# --------------------------------------------------------------------------- #
def build_metadata(model: Path, cfg: dict, tokcfg: dict, tokenizer: dict, out_dtype: str = "q4_0") -> bytes:
    h = cfg["hidden_size"]
    nl = cfg["num_hidden_layers"]
    nh = cfg["num_attention_heads"]
    nkv = cfg["num_key_value_heads"]
    hd = cfg.get("head_dim", h // nh)
    ffn = cfg["intermediate_size"]
    vocab = cfg["vocab_size"]
    ctx = cfg.get("max_position_embeddings", 40960)
    rope = cfg.get("rope_theta", 1_000_000.0)
    eps = cfg.get("rms_norm_eps", 1e-6)

    # tokenizer：按 id 排序还原 token 表，special token 标 CONTROL(3)
    tmodel = tokenizer["model"]
    tvocab: dict[str, int] = tmodel["vocab"]
    # 关键：HF Qwen3 的 embed/lm_head 按 config.vocab_size(151936) 对齐存储，
    # 但 tokenizer 实际只有 151643 个 token。GGUF 的 tokens 数组必须与 embed
    # 行数一致，否则 llama.cpp check_tensor_dims 会报
    # "expected 4096,151643, got 4096,151936" 而拒绝加载。
    n = max(len(tvocab), (max(tvocab.values()) + 1 if tvocab else 0), vocab)
    tokens = [""] * n
    for tok, i in tvocab.items():
        if i < n:
            tokens[i] = tok
    ttypes = [1] * n  # NORMAL
    # 关键修复：added_tokens（含 <|im_end|> 等所有特殊 token）必须写入真实 content，
    # 否则这些 id 会被写成 "[PAD<id>]" 字面量，llama.cpp 输出时原样吐出 -> [PAD151667]
    # 这类碎片。不在 vocab、也不在 added_tokens 的补位 id（padding 到 vocab_size）保持
    # 空串，渲染时什么都不输出，避免污染纯文本输出。
    for at in tokenizer.get("added_tokens", []):
        i = at.get("id")
        if i is not None and i < n:
            content = at.get("content")
            if content:
                tokens[i] = content
            ttypes[i] = 3 if at.get("special") else 4  # CONTROL / USER_DEFINED

    merges_raw = tmodel.get("merges", [])
    merges: list[str] = []
    for m in merges_raw:
        merges.append(" ".join(m) if isinstance(m, list) else str(m))

    bos = cfg.get("bos_token_id", 151643)
    eos = cfg.get("eos_token_id", 151645)
    pad = 151643
    chat_tpl = tokcfg.get("chat_template") or ""

    ftype = FILE_TYPE_F16 if out_dtype == "f16" else FILE_TYPE_Q4_0
    qlabel = "F16" if out_dtype == "f16" else "Q4_0"

    parts = [
        kv_str("general.architecture", "qwen3"),
        kv_str("general.name", model.name.replace("_", "-")),
        kv_str("general.description",
               f"Qwen3 architecture checkpoint, {qlabel} GGUF"),
        kv_u32("general.quantization_version", GGML_QNT_VERSION),
        kv_u32("general.file_type", ftype),
        kv_u32("general.alignment", GGUF_DEFAULT_ALIGNMENT),
        kv_u32("qwen3.block_count", nl),
        kv_u32("qwen3.context_length", ctx),
        kv_u32("qwen3.embedding_length", h),
        kv_u32("qwen3.feed_forward_length", ffn),
        kv_u32("qwen3.attention.head_count", nh),
        kv_u32("qwen3.attention.head_count_kv", nkv),
        kv_u32("qwen3.attention.key_length", hd),
        kv_u32("qwen3.attention.value_length", hd),
        kv_f32("qwen3.attention.layer_norm_rms_epsilon", eps),
        kv_u32("qwen3.rope.dimension_count", hd),
        kv_f32("qwen3.rope.freq_base", rope),
        kv_u32("qwen3.vocab_size", vocab),
        kv_str("tokenizer.ggml.model", "gpt2"),
        kv_str("tokenizer.ggml.pre", "qwen2"),
        kv_arr_str("tokenizer.ggml.tokens", tokens),
        kv_arr_i32("tokenizer.ggml.token_type", ttypes),
        kv_arr_str("tokenizer.ggml.merges", merges),
        kv_u32("tokenizer.ggml.bos_token_id", bos),
        kv_u32("tokenizer.ggml.eos_token_id", eos),
        kv_u32("tokenizer.ggml.padding_token_id", pad),
        kv_bool("tokenizer.ggml.add_bos_token", False),
        kv_bool("tokenizer.ggml.add_eos_token", False),
        kv_str("tokenizer.chat_template", chat_tpl),
    ]
    return b"".join(parts), len(parts), n, len(merges)


# --------------------------------------------------------------------------- #
# 主转换
# --------------------------------------------------------------------------- #
def convert(model: Path, out: Path, out_dtype: str = "q4_0") -> dict:
    if out_dtype not in ("q4_0", "f16"):
        raise ValueError(f"不支持的 out_dtype: {out_dtype}")
    cfg = json.loads((model / "config.json").read_text(encoding="utf-8"))
    tokcfg = json.loads((model / "tokenizer_config.json").read_text(encoding="utf-8"))
    tokenizer = json.loads((model / "tokenizer.json").read_text(encoding="utf-8"))
    
    idx_file = model / "model.safetensors.index.json"
    if idx_file.exists():
        index = json.loads(idx_file.read_text(encoding="utf-8"))
        wmap: dict[str, str] = index["weight_map"]
    else:
        single_file = model / "model.safetensors"
        if not single_file.exists():
            raise FileNotFoundError(f"未在 {model} 找到 safetensors 文件")
        reader = SafeTensorReader(single_file)
        wmap = {k: "model.safetensors" for k in reader.entries.keys()}
        reader.close()

    meta_bytes, n_kv, n_tokens, n_merges = build_metadata(model, cfg, tokcfg, tokenizer, out_dtype=out_dtype)

    # 按 GGUF 友好顺序排列：embed -> blk.0..N -> output_norm -> output
    def sort_key(name):
        gg = map_name(name)
        if gg is None:
            return (9, name)
        if gg == "token_embd.weight":
            return (0, "")
        if gg.startswith("blk."):
            i = int(gg.split(".")[1])
            return (1, f"{i:04d}" + gg)
        if gg == "output_norm.weight":
            return (7, "")
        if gg == "output.weight":
            return (8, "")
        return (5, gg)

    names = sorted(wmap.keys(), key=sort_key)
    readers: dict[str, SafeTensorReader] = {}

    # 第一遍：收集 tensor info 并计算 offsets
    tensor_infos = []  # (gguf_name, dims, ggml_type, nbytes, hf_name, hf_shape, dtype)
    offset = 0
    unaligned = []
    for hf in names:
        gg = map_name(hf)
        if gg is None:
            unaligned.append(hf)
            continue
        shard = wmap[hf]
        if shard not in readers:
            readers[shard] = SafeTensorReader(model / shard)
        shape, dtype, _ = readers[shard].info(hf)
        nelem = 1
        for d in shape:
            nelem *= d
        if len(shape) >= 2:
            if out_dtype == "f16":
                gtype = TT_F16
                nbytes = nelem * 2
            else:
                if nelem % Q4_0_BLOCK != 0:
                    raise ValueError(f"{hf} 元素数 {nelem} 不是 32 倍数，无法 Q4_0")
                gtype = TT_Q4_0
                nbytes = nelem // Q4_0_BLOCK * Q4_0_BYTES
        else:
            gtype = TT_F32
            nbytes = nelem * 4
        tensor_infos.append((gg, gguf_dims(shape), gtype, nbytes, hf, shape, dtype))
        offset += nbytes
        # 每个张量起始按 alignment 对齐
        pad = (-offset) % GGUF_DEFAULT_ALIGNMENT
        offset += pad

    data_size = offset
    # tensor info 区
    ti = bytearray()
    cur = 0
    for gg, dims, gtype, nbytes, hf, shape, dtype in tensor_infos:
        ti += _s(gg)
        ti += _u32(len(dims))
        for d in dims:
            ti += _u64(d)
        ti += _u32(gtype)
        ti += _u64(cur)
        cur += nbytes
        cur += (-cur) % GGUF_DEFAULT_ALIGNMENT

    header = bytearray()
    header += GGUF_MAGIC
    header += _u32(GGUF_VERSION)
    header += _u64(len(tensor_infos))
    header += _u64(n_kv)
    header += meta_bytes
    header += ti
    header += b"\x00" * ((-len(header)) % GGUF_DEFAULT_ALIGNMENT)
    data_start = len(header)

    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"[convert] 张量 {len(tensor_infos)} 个, metadata {n_kv} 项, "
          f"token {n_tokens}, merges {n_merges}", flush=True)
    print(f"[convert] header {data_start/1e6:.2f}MB, 数据区 {data_size/1e9:.2f}GB, "
          f"预计产物 {(data_start+data_size)/1e9:.2f}GB", flush=True)
    if unaligned:
        print(f"[convert] 警告：{len(unaligned)} 个张量未映射，已跳过: {unaligned[:5]}",
              flush=True)

    written = 0
    with open(out, "wb") as of:
        of.write(header)
        for gi, (gg, dims, gtype, nbytes, hf, shape, dtype) in enumerate(tensor_infos):
            shard = wmap[hf]
            r = readers[shard]
            nelem = 1
            for d in shape:
                nelem *= d
            if gtype == TT_Q4_0:
                pos = 0
                while pos < nelem:
                    cnt = min(CHUNK_ELEMS, nelem - pos)
                    raw = r.read_range(hf, pos, cnt)
                    f32 = raw_to_f32(raw, dtype)
                    of.write(quantize_q4_0(f32))
                    pos += cnt
            elif gtype == TT_F16:
                pos = 0
                while pos < nelem:
                    cnt = min(CHUNK_ELEMS, nelem - pos)
                    raw = r.read_range(hf, pos, cnt)
                    f32 = raw_to_f32(raw, dtype)
                    f16 = f32.astype(np.float16)
                    if not np.all(np.isfinite(f16)):
                        raise ValueError(f"{hf} 转 F16 出现溢出或非有限值")
                    of.write(f16.tobytes())
                    pos += cnt
            else:
                pos = 0
                while pos < nelem:
                    cnt = min(CHUNK_ELEMS, nelem - pos)
                    raw = r.read_range(hf, pos, cnt)
                    f32 = raw_to_f32(raw, dtype)
                    of.write(f32.astype(np.float32).tobytes())
                    pos += cnt
            # 精确对齐：当前文件偏移相对数据区起点，补 0 到 32 字节边界
            rel = of.tell() - data_start
            pad = (-rel) % GGUF_DEFAULT_ALIGNMENT
            if pad:
                of.write(b"\x00" * pad)
            written += nbytes
            if (gi + 1) % 60 == 0 or gi + 1 == len(tensor_infos):
                print(f"  [{gi+1}/{len(tensor_infos)}] {gg} "
                      f"{nbytes/1e6:.1f}MB  累计 {written/1e9:.2f}GB", flush=True)

    for r in readers.values():
        r.close()
    actual = out.stat().st_size
    expected = data_start + data_size
    if actual != expected:
        raise IOError(f"产物大小不符: 实际 {actual} vs 预期 {expected}")
    return {
        "status": "ok",
        "out": str(out),
        "tensors": len(tensor_infos),
        "metadata_kv": n_kv,
        "tokens": n_tokens,
        "merges": n_merges,
        "header_bytes": data_start,
        "data_bytes": data_size,
        "file_bytes": actual,
        "quantization": "F16" if out_dtype == "f16" else "Q4_0",
        "architecture": "qwen3",
        "unmapped": unaligned,
    }


# --------------------------------------------------------------------------- #
# 自测
# --------------------------------------------------------------------------- #
def self_test() -> None:
    rng = np.random.default_rng(42)
    x = rng.normal(0, 0.02, size=32 * 100).astype(np.float32)
    enc = quantize_q4_0(x)
    dec = dequantize_q4_0(enc, x.size)
    err = float(np.max(np.abs(dec - x)))
    rel = float(np.sqrt(np.mean((dec - x) ** 2)) / (np.sqrt(np.mean(x ** 2)) + 1e-12))
    print(f"[self-test] Q4_0 往返: max_abs_err={err:.6f} rel_rms={rel:.4%} "
          f"bytes={len(enc)} (期望 {x.size//32*Q4_0_BYTES})")
    assert len(enc) == x.size // 32 * Q4_0_BYTES
    assert err < 0.01, f"量化误差过大: {err}"

    # bf16 位操作
    a = np.array([0x3F80, 0x4000, 0xBF80], dtype=np.uint16)  # 1.0, 2.0, -1.0
    f = bf16_to_f32(a)
    print(f"[self-test] bf16->f32: {f.tolist()}")
    assert abs(float(f[0]) - 1.0) < 1e-6 and abs(float(f[2]) + 1.0) < 1e-6

    # 张量名映射覆盖
    cases = {
        "model.embed_tokens.weight": "token_embd.weight",
        "model.layers.0.self_attn.q_proj.weight": "blk.0.attn_q.weight",
        "model.layers.35.mlp.down_proj.weight": "blk.35.ffn_down.weight",
        "model.layers.7.self_attn.q_norm.weight": "blk.7.attn_q_norm.weight",
        "model.norm.weight": "output_norm.weight",
        "lm_head.weight": "output.weight",
    }
    for k, v in cases.items():
        assert map_name(k) == v, f"{k} -> {map_name(k)} != {v}"
    assert gguf_dims((4096, 4096)) == (4096, 4096)
    assert gguf_dims((12288, 4096)) == (4096, 12288)
    print("[self-test] 张量名映射 / dims 反转 OK")
    print("[self-test] ALL PASS")


def main() -> None:
    p = argparse.ArgumentParser(description="纯 numpy HF safetensors -> GGUF Q4_0")
    p.add_argument("--model", default="checkpoints/virtu_merged")
    p.add_argument("--out", default="checkpoints/virtu-q4_0.gguf")
    p.add_argument("--dtype", choices=["q4_0", "f16"], default="q4_0",
                   help="输出权重类型：默认 q4_0，或 f16 供 llama-quantize 量化")
    p.add_argument("--check", action="store_true", help="只跑自测，不转换")
    args = p.parse_args()
    if args.check:
        self_test()
        return
    model = Path(args.model)
    out = Path(args.out)
    if not model.is_dir():
        raise SystemExit(f"[convert] 模型目录不存在: {model}")
    self_test()
    print()
    receipt = convert(model, out, out_dtype=args.dtype)
    print("\n[convert] 完成:", json.dumps(receipt, ensure_ascii=False, indent=2))
    receipt_path = out.with_suffix(".gguf.receipt.json")
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[convert] 回执: {receipt_path}")


if __name__ == "__main__":
    main()
