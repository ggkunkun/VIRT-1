#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/write_dense_gguf.py — 把稠密 HF 目录写成 GGUF（Q4_0），供 ollama create 导入。

为什么需要它：本机 Ollama 0.40.14 的 `create --quantize` 只接受 MLX 量化类型
（int4/int8/nvfp4/mxfp4/mxfp8），HTTP API 明确拒绝 q4_K_M；本机也没有 llama.cpp
的 convert/quantize 二进制；gguf-py 的 quants 只实现了 Q4_0/Q4_1/Q5_0/Q5_1/Q8_0
（k-quants 全部 NotImplementedError，实测）。故采用 Q4_0 —— 与在役基线
virtu-comprehensive 同一量化方案（4.5 bit/权重），A/B 的唯一变量是「FFN 来源」。

实现要点（内存恒定，不随张量大小增长）：
1. 模板 = 在役 `virtu-comprehensive-q4_0.gguf`（同架构/同形状/同类型），
   直接复用其**整个头部字节**（KV + tensor info + offset 全部有效）。
2. 输出文件先 truncate 到模板大小（稀疏），再按 offset 顺序逐块写入量化数据，
   块大小 = chunk_rows × row_bytes，峰值 ≈ 一个 chunk（16MB 量级）。
3. bf16 → fp32 用 numpy 位运算完成（不 import torch，省 1GB+ CUDA 上下文）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import struct
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gguf_depth_upscale import read_header  # noqa: E402
from gguf.quants import quantize  # noqa: E402
from gguf import GGMLQuantizationType as QT, GGML_QUANT_SIZES  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MAP_LAYER = {
    "attn_norm.weight": "input_layernorm.weight",
    "ffn_norm.weight": "post_attention_layernorm.weight",
    "attn_q.weight": "self_attn.q_proj.weight",
    "attn_k.weight": "self_attn.k_proj.weight",
    "attn_v.weight": "self_attn.v_proj.weight",
    "attn_output.weight": "self_attn.o_proj.weight",
    "attn_q_norm.weight": "self_attn.q_norm.weight",
    "attn_k_norm.weight": "self_attn.k_norm.weight",
    "ffn_gate.weight": "mlp.gate_proj.weight",
    "ffn_up.weight": "mlp.up_proj.weight",
    "ffn_down.weight": "mlp.down_proj.weight",
}


def gguf_to_hf(name: str):
    if name == "token_embd.weight":
        return "model.embed_tokens.weight"
    if name == "output.weight":
        return "lm_head.weight"
    if name == "output_norm.weight":
        return "model.norm.weight"
    m = re.fullmatch(r"blk\.(\d+)\.(.+)", name)
    if m and m.group(2) in MAP_LAYER:
        return f"model.layers.{m.group(1)}.{MAP_LAYER[m.group(2)]}"
    return None


class ShardCache:
    """按需打开 safetensors 分片，纯 numpy 行切片读取（bf16→fp32 位扩展）。"""

    def __init__(self, src: Path, wmap: dict):
        self.src, self.wmap, self.files = src, wmap, {}

    def _open(self, hf_name: str):
        sh = self.wmap[hf_name]
        if sh not in self.files:
            f = open(self.src / sh, "rb")
            n = struct.unpack("<Q", f.read(8))[0]
            hdr = json.loads(f.read(n))
            self.files[sh] = (f, hdr, 8 + n)
        return self.files[sh]

    def shape(self, hf_name: str):
        return list(self._open(hf_name)[1][hf_name]["shape"])

    def rows(self, hf_name: str, r0: int, r1: int) -> np.ndarray:
        f, hdr, base = self._open(hf_name)
        h = hdr[hf_name]
        st, en = h["data_offsets"]
        shape = list(h["shape"])
        row_bytes = (en - st) // int(shape[0])
        f.seek(base + st + r0 * row_bytes)
        buf = f.read((r1 - r0) * row_bytes)
        u = np.frombuffer(buf, dtype=np.uint16).reshape(r1 - r0, int(shape[1]))
        return (u.astype(np.uint32) << 16).view(np.float32)

    def flat(self, hf_name: str) -> np.ndarray:
        f, hdr, base = self._open(hf_name)
        h = hdr[hf_name]
        st, en = h["data_offsets"]
        f.seek(base + st)
        buf = f.read(en - st)
        if h.get("dtype") == "F32":
            return np.frombuffer(buf, dtype=np.float32).astype(np.float32)
        u = np.frombuffer(buf, dtype=np.uint16)
        return (u.astype(np.uint32) << 16).view(np.float32)

    def close(self):
        for f, _h, _b in self.files.values():
            try:
                f.close()
            except Exception:
                pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", default="checkpoints/virtu-comprehensive-q4_0.gguf")
    ap.add_argument("--src", default="checkpoints/virtu_dense_merged_hf")
    ap.add_argument("--out", default="checkpoints/virtu-dense-merged-q4_0.gguf")
    ap.add_argument("--chunk-rows", type=int, default=2048)
    ap.add_argument("--max-tensors", type=int, default=0, help="冒烟用：只写前 N 个张量")
    args = ap.parse_args()

    tpl = ROOT / args.template if not Path(args.template).is_absolute() else Path(args.template)
    src = ROOT / args.src if not Path(args.src).is_absolute() else Path(args.src)
    out = ROOT / args.out if not Path(args.out).is_absolute() else Path(args.out)
    t0 = time.time()

    version, metadata, infos, data_offset, alignment = read_header(tpl)
    tpl_size = os.path.getsize(tpl)
    idx = json.loads((src / "model.safetensors.index.json").read_text(encoding="utf-8"))
    cache = ShardCache(src, idx["weight_map"])
    print(f"[tpl] v{version} 张量 {len(infos)} 元数据 {len(metadata)} 数据起点 {data_offset} "
          f"对齐 {alignment} 总长 {tpl_size/1024**3:.2f}GB", flush=True)

    order = sorted(infos, key=lambda x: x["offset"])
    if args.max_tensors:
        order = order[: args.max_tensors]

    with open(tpl, "rb") as ft, open(out, "wb") as fo:
        fo.write(ft.read(data_offset))          # 头部（含 KV 与 tensor info）逐字节复用
        fo.truncate(tpl_size)                   # 稀疏预分配，保持 offset 不变
        n_2d = n_1d = 0
        for info in order:
            gname, qtype = info["name"], QT(info["type"])
            hf_name = gguf_to_hf(gname)
            if hf_name is None:
                raise SystemExit(f"无法映射张量 {gname}")
            dims = [int(d) for d in info["dims"]]          # ne 顺序：ne0 = in
            hf_shape = cache.shape(hf_name)
            nelem = 1
            for d in dims:
                nelem *= d
            blk, tsize = GGML_QUANT_SIZES[qtype]
            nbytes = nelem // blk * tsize
            fo.seek(data_offset + info["offset"])
            if len(dims) == 1:
                if list(reversed(hf_shape)) != dims:
                    raise SystemExit(f"{gname} 形状不匹配 {hf_shape} vs {dims}")
                fo.write(cache.flat(hf_name).astype(np.float32).tobytes())
                n_1d += 1
                continue
            out_dim, in_dim = hf_shape
            if [in_dim, out_dim] != dims:
                raise SystemExit(f"{gname} 形状不匹配 HF={hf_shape} vs GGUF ne={dims}")
            row_bytes = in_dim // blk * tsize
            written = 0
            for r0 in range(0, out_dim, args.chunk_rows):
                r1 = min(out_dim, r0 + args.chunk_rows)
                q = quantize(cache.rows(hf_name, r0, r1), qtype)
                fo.write(q.tobytes())
                written += q.nbytes
                del q
            if written != nbytes:
                raise SystemExit(f"{gname} 字节数不符 {written} vs {nbytes}")
            n_2d += 1
            if n_2d == 1 or n_2d % 40 == 0:
                print(f"  ...{n_2d} 个二维张量 ({time.time()-t0:.0f}s)", flush=True)
        fo.flush()
    cache.close()

    size = out.stat().st_size
    print(f"[done] {out.name}: {size/1024**3:.2f} GB  2D={n_2d} 1D={n_1d}  {time.time()-t0:.0f}s",
          flush=True)
    receipt = {
        "kind": "dense_gguf", "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "template": tpl.name, "template_bytes": tpl_size, "src": str(src),
        "qtype_2d": "Q4_0", "qtype_1d": "F32",
        "tensors_2d": n_2d, "tensors_1d": n_1d, "bytes": size,
        "note": "头部逐字节复用模板；数据按 offset 流式写入；Ollama 0.40.14 不支持 create --quantize k-quants",
        "basis": "measured", "elapsed_s": round(time.time() - t0, 1),
    }
    out.with_suffix(".receipt.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False),
                                                encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
