#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/hf_to_gguf_q4.py — 把合成好的稠密 HF 目录转成 Q4_0 GGUF。

背景：本机 Ollama 0.40.14 的 `create --quantize` 只支持 int4/int8/nvfp4/mxfp4/mxfp8，
其中 int4 走 MLX（Windows 不可用），故改用 gguf 库自带 quants.quantize 离线做 Q4_0。

做法：
  - KV 元数据直接沿用参考的 qwen3 稠密 GGUF（virtu-comprehensive-q4_0.gguf），保证 tokenizer /
    rope / head_count 等与既有 Virtu 模型完全一致，只改 general.name/description/file_type；
  - 张量按 llama.cpp 命名映射（token_embd / blk.N.attn_q / ...）；
  - 2D 权重按行分块量化为 Q4_0（峰值内存 ~几十 MB），1D norm 保留 F32。

用法：
  .venv/Scripts/python.exe scripts/hf_to_gguf_q4.py \
      --src checkpoints/virtu_dense_ties_hf --ref checkpoints/virtu-comprehensive-q4_0.gguf \
      --out checkpoints/virtu-dense-ties-q4_0.gguf
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gguf
from gguf import GGMLQuantizationType as QT
from gguf import quants

ROOT = Path(__file__).resolve().parent.parent
CH_ROWS = 2048         # 每次量化的行数（4096 列时约 32 MB fp32）

_DT = {"BF16": np.uint16, "F16": np.float16, "F32": np.float32}


def hf_header(path: Path):
    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        hdr = json.loads(f.read(n))
    return hdr, 8 + n


def read_hf_tensor(path: Path, hdr, key: str, data_start: int) -> np.ndarray:
    h = hdr[key]
    st, en = h["data_offsets"]
    with open(path, "rb") as f:
        f.seek(data_start + st)
        raw = f.read(en - st)
    if h["dtype"] == "BF16":
        u = np.frombuffer(raw, dtype=np.uint16).astype(np.uint32) << 16
        return u.view(np.float32).reshape(h["shape"])
    if h["dtype"] == "F16":
        return np.frombuffer(raw, dtype=np.float16).astype(np.float32).reshape(h["shape"])
    return np.frombuffer(raw, dtype=np.float32).reshape(h["shape"])


MAP_FIXED = {
    "model.embed_tokens.weight": "token_embd.weight",
    "model.norm.weight": "output_norm.weight",
    "lm_head.weight": "output.weight",
}
MAP_SUFFIX = {
    "input_layernorm.weight": "attn_norm.weight",
    "post_attention_layernorm.weight": "ffn_norm.weight",
    "self_attn.q_proj.weight": "attn_q.weight",
    "self_attn.k_proj.weight": "attn_k.weight",
    "self_attn.v_proj.weight": "attn_v.weight",
    "self_attn.o_proj.weight": "attn_output.weight",
    "self_attn.q_norm.weight": "attn_q_norm.weight",
    "self_attn.k_norm.weight": "attn_k_norm.weight",
    "mlp.gate_proj.weight": "ffn_gate.weight",
    "mlp.up_proj.weight": "ffn_up.weight",
    "mlp.down_proj.weight": "ffn_down.weight",
}


def gguf_name(hf_name: str) -> str | None:
    if hf_name in MAP_FIXED:
        return MAP_FIXED[hf_name]
    if ".layers." not in hf_name:
        return None
    layer = hf_name.split(".layers.")[1].split(".")[0]
    tail = hf_name.split(f".layers.{layer}.", 1)[1]
    if tail in MAP_SUFFIX:
        return f"blk.{layer}.{MAP_SUFFIX[tail]}"
    return None


def quantize_rows(t: np.ndarray) -> np.ndarray:
    """按行分块做 Q4_0，返回打包后的 uint8（形状 [rows, in//32*18]）。"""
    rows, cols = t.shape
    if cols % 32:
        raise ValueError(f"Q4_0 需要列数是 32 的倍数，得到 {cols}")
    parts = []
    for s in range(0, rows, CH_ROWS):
        chunk = np.ascontiguousarray(t[s:s + CH_ROWS], dtype=np.float32)
        parts.append(quants.quantize(chunk, QT.Q4_0))
    return np.concatenate(parts, axis=0)


def copy_kv(ref: "gguf.GGUFReader", w: "gguf.GGUFWriter", name: str, desc: str):
    f = ref.fields
    w.add_name(name)
    w.add_description(desc)
    _qv = f["general.quantization_version"].contents()
    _qv = _qv[0] if isinstance(_qv, (list, tuple, np.ndarray)) else _qv
    w.add_quantization_version(int(_qv))
    w.add_file_type(2)                        # 2 = MOSTLY_Q4_0 (Ollama 0.40.14 验证可用；与 merged 模型一致)
    w.add_alignment(int(f["general.alignment"].contents()[0]))

    for k, fld in f.items():
        if k.startswith("GGUF.") or k in ("general.architecture", "general.name",
                                         "general.description", "general.quantization_version",
                                         "general.file_type", "general.alignment"):
            continue
        if k == "tokenizer.ggml.model":
            w.add_tokenizer_model(str(fld.contents()[0]))
        elif k == "tokenizer.ggml.pre":
            w.add_key_value(k, str(fld.contents()[0]))
        elif k == "tokenizer.ggml.tokens":
            w.add_token_list([str(x) for x in fld.contents()])
        elif k == "tokenizer.ggml.token_type":
            w.add_token_types([int(x) for x in fld.contents()])
        elif k == "tokenizer.ggml.merges":
            w.add_token_merges([str(x) for x in fld.contents()])
        elif k == "tokenizer.ggml.bos_token_id":
            w.add_bos_token_id(int(fld.contents()[0]))
        elif k == "tokenizer.ggml.eos_token_id":
            w.add_eos_token_id(int(fld.contents()[0]))
        elif k == "tokenizer.ggml.padding_token_id":
            w.add_padding_token_id(int(fld.contents()[0]))
        elif k == "tokenizer.ggml.add_bos_token":
            w.add_add_bos_token(bool(fld.contents()[0]))
        elif k == "tokenizer.ggml.add_eos_token":
            w.add_add_eos_token(bool(fld.contents()[0]))
        elif k == "tokenizer.chat_template":
            w.add_chat_template(str(fld.contents()[0]))
        else:
            c = fld.contents()
            val = c[0] if len(c) == 1 else c
            if isinstance(val, np.generic):
                val = val.item()
            w.add_key_value(k, val)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="checkpoints/virtu_dense_ties_hf")
    ap.add_argument("--ref", default="checkpoints/virtu-comprehensive-q4_0.gguf")
    ap.add_argument("--out", default="checkpoints/virtu-dense-ties-q4_0.gguf")
    ap.add_argument("--name", default="Virtu-Dense-TIES-8B")
    ap.add_argument("--desc", default="dense TIES-style merge of 4 domain LoRAs (2026-11-06)")
    args = ap.parse_args()

    src = Path(args.src) if Path(args.src).is_absolute() else ROOT / args.src
    ref_p = Path(args.ref) if Path(args.ref).is_absolute() else ROOT / args.ref
    out = Path(args.out) if Path(args.out).is_absolute() else ROOT / args.out

    index = json.loads((src / "model.safetensors.index.json").read_text(encoding="utf-8"))
    weight_map: dict[str, str] = index["weight_map"]
    hdrs = {}
    for shard in sorted(set(weight_map.values())):
        hdrs[shard] = hf_header(src / shard)

    ref = gguf.GGUFReader(str(ref_p))
    w = gguf.GGUFWriter(str(out), "qwen3")
    copy_kv(ref, w, args.name, args.desc)

    t0 = time.time()
    n_q = n_f32 = 0
    total_bytes = 0
    for hf_name in sorted(weight_map):
        gname = gguf_name(hf_name)
        if gname is None:
            print(f"  skip {hf_name}")
            continue
        shard = weight_map[hf_name]
        hdr, ds = hdrs[shard]
        t = read_hf_tensor(src / shard, hdr, hf_name, ds)
        if t.ndim == 2:
            packed = quantize_rows(t)
            w.add_tensor(gname, packed, raw_shape=tuple(t.shape), raw_dtype=QT.Q4_0)
            n_q += 1
            total_bytes += packed.nbytes
        else:
            arr = np.ascontiguousarray(t, dtype=np.float32)
            w.add_tensor(gname, arr)
            n_f32 += 1
            total_bytes += arr.nbytes
        del t
        if (n_q + n_f32) % 48 == 0:
            print(f"  {n_q + n_f32} tensors, {total_bytes/1e9:.2f} GB, {time.time()-t0:.0f}s", flush=True)

    w.write_header_to_file()
    w.write_kv_data_to_file()
    w.write_tensors_to_file()
    w.close()

    size = out.stat().st_size
    print("=" * 60)
    print(f"done: {n_q} quantized(Q4_0) + {n_f32} f32 tensors")
    print(f"file: {out}  {size/1e9:.2f} GB  {(time.time()-t0)/60:.1f} min")


if __name__ == "__main__":
    main()
