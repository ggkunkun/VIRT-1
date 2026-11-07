#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/build_virtu_dense_ties.py — 把 4 个领域 LoRA 合成「一个」稠密 Qwen3-8B（低内存两遍式）。

为什么要稠密化（2026-11-06 实测依据）：
  - virtu-moe-14b 的两个专家增量近乎正交（cos=0.0068），分工是真的；
  - 但门控 `ffn_gate_inp.weight` 是 ±ones/sqrt(4096)+N(0,0.01)，从未训练，
    决策≈隐状态全局符号 → 逐 token 随机挑一个正交更新；
  - 结果：13.63B 稀疏体在 6GB 卡上只有 ~10 tok/s，而同族稠密 8.2B 能 100% 上卡 ~37 tok/s。

合并口径（与 build_virtu_franken_moe.py 对齐，便于对照）：
  attention: base + 0.25*cad + 0.35*tool + 0.25*conv + 0.15*ug
  expert_e0 = base + 0.60*cad + 0.40*tool
  expert_e1 = base + 0.65*conv + 0.35*ug
  ffn      = base + 0.5*(prune_r(d_e0) + prune_r(d_e1))

两遍式设计（本机实测可用内存仅 ~3.7GB）：
  Pass 1  只读各分片 header，规划输出张量、按字节切成 ≤shard-gb 的分片，写出 header 骨架；
  Pass 2  逐分片逐张量写数据：未改动的张量按 32MB 块从源文件流式拷贝，改动的张量按张量合并后写入。
  峰值内存 ≈ 单张量(fp32 增量 2 份 + bf16 结果) ≈ 700MB。

Windows 注意：safetensors 的 mmap 路径在本机会段错误（实测 09:05），故读写全部裸字节实现。

用法：
  .venv/Scripts/python.exe scripts/build_virtu_dense_ties.py \
      --base checkpoints/_base_qwen3_8b --out checkpoints/virtu_dense_ties_hf \
      --density 0.7 --shard-gb 1.6
"""

from __future__ import annotations

import argparse
import gc
import json
import logging
import os
import shutil
import struct
import sys
import time
from pathlib import Path

import torch

torch.set_num_threads(6)

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger("dense_ties")

ROOT = Path(__file__).resolve().parent.parent

LORAS = {
    "cad":  ("checkpoints/cad_cam_six_software_lora", 0.25),
    "tool": ("checkpoints/virtu_toolcall_lora", 0.35),
    "conv": ("checkpoints/turing_conversational_lora", 0.25),
    "ug":   ("checkpoints/ug_teacher_guided_agent_lora", 0.15),
}
EXPERT0 = {"cad": 0.60, "tool": 0.40}
EXPERT1 = {"conv": 0.65, "ug": 0.35}
ATTN_PROJ = ("q_proj", "k_proj", "v_proj", "o_proj")
FFN_PROJ = ("gate_proj", "up_proj", "down_proj")

_DT = {"BF16": torch.bfloat16, "F16": torch.float16, "F32": torch.float32}
_TAG = {torch.bfloat16: "BF16", torch.float16: "F16", torch.float32: "F32"}
_ISZ = {"BF16": 2, "F16": 2, "F32": 4}
CHUNK = 32 << 20


class Header:
    """只读 header，不读数据。"""

    def __init__(self, path: Path):
        self.path = path
        with open(path, "rb") as f:
            n = struct.unpack("<Q", f.read(8))[0]
            self.header = json.loads(f.read(n))
        self.data_start = 8 + n


def read_tensor(path: Path, hdr: Header, key: str) -> torch.Tensor:
    h = hdr.header[key]
    st, en = h["data_offsets"]
    with open(path, "rb") as f:
        f.seek(hdr.data_start + st)
        raw = bytearray(f.read(en - st))
    return torch.frombuffer(raw, dtype=_DT[h["dtype"]]).reshape(tuple(h["shape"]))


def write_header(f, tensors: list[tuple[str, str, list[int]]]) -> int:
    """写 safetensors header，返回 data_start。tensors: [(name, dtype, shape)]"""
    header, off = {}, 0
    for name, dt, shape in tensors:
        nbytes = _ISZ[dt]
        for d in shape:
            nbytes *= d
        header[name] = {"dtype": dt, "shape": shape, "data_offsets": [off, off + nbytes]}
        off += nbytes
    hj = json.dumps(header, separators=(",", ":")).encode("utf-8")
    hj += b" " * ((-len(hj)) % 8)
    f.write(struct.pack("<Q", len(hj)))
    f.write(hj)
    return 8 + len(hj), off


class Lora:
    def __init__(self, key: str, directory: Path):
        cfg = json.loads((directory / "adapter_config.json").read_text(encoding="utf-8"))
        self.key = key
        self.scaling = float(cfg["lora_alpha"]) / int(cfg["r"])
        self.path = directory / "adapter_model.safetensors"
        self.hdr = Header(self.path)
        self.keys = set(self.hdr.header)

    def delta_into(self, layer: int, proj: str, acc: torch.Tensor, weight: float) -> bool:
        """acc += weight * scaling * (B @ A)，全程 fp32，复用 acc 缓冲。"""
        if proj in ATTN_PROJ:
            p = f"base_model.model.model.layers.{layer}.self_attn.{proj}"
        else:
            p = f"base_model.model.model.layers.{layer}.mlp.{proj}"
        ka, kb = f"{p}.lora_A.weight", f"{p}.lora_B.weight"
        if ka not in self.keys or kb not in self.keys:
            return False
        A = read_tensor(self.path, self.hdr, ka).float()
        B = read_tensor(self.path, self.hdr, kb).float()
        tmp = B @ A
        del A, B
        tmp.mul_(weight * self.scaling)
        acc.add_(tmp)
        del tmp
        return True


def prune_(t: torch.Tensor, density: float) -> torch.Tensor:
    """就地幅度裁剪（采样估阈值），返回同一张量。"""
    if density >= 1.0:
        return t
    flat = t.abs().flatten()
    step = max(1, flat.numel() // 2_000_000)
    sample = flat[::step]
    k = max(1, min(sample.numel(), int(sample.numel() * density)))
    thresh = torch.topk(sample, k, largest=True).values.min()
    t.masked_fill_(t.abs() < thresh, 0.0)
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="checkpoints/_base_qwen3_8b")
    ap.add_argument("--out", default="checkpoints/virtu_dense_ties_hf")
    ap.add_argument("--density", type=float, default=0.7)
    ap.add_argument("--shard-gb", type=float, default=1.6)
    ap.add_argument("--layers", type=int, default=36)
    ap.add_argument("--plan-only", action="store_true")
    args = ap.parse_args()

    base_dir = Path(args.base) if Path(args.base).is_absolute() else ROOT / args.base
    out_dir = Path(args.out) if Path(args.out).is_absolute() else ROOT / args.out

    index = json.loads((base_dir / "model.safetensors.index.json").read_text(encoding="utf-8"))
    weight_map: dict[str, str] = index["weight_map"]

    # ---------- Pass 1: 规划 ----------
    src_hdr: dict[str, Header] = {}
    plan = []          # [(name, dtype, shape, kind, src_shard, nbytes)]
    for name, shard in weight_map.items():
        if shard not in src_hdr:
            src_hdr[shard] = Header(base_dir / shard)
        h = src_hdr[shard].header[name]
        nbytes = _ISZ[h["dtype"]]
        for d in h["shape"]:
            nbytes *= d
        kind = "copy"
        if ".layers." in name:
            layer = int(name.split(".layers.")[1].split(".")[0])
            tail = name.split(f".layers.{layer}.", 1)[1]
            if layer < args.layers and tail.endswith(".weight"):
                if tail.startswith("self_attn.") and tail.split(".")[1] in ATTN_PROJ:
                    kind = "merge"
                if tail.startswith("mlp.") and tail.split(".")[1] in FFN_PROJ:
                    kind = "merge"
        plan.append((name, h["dtype"], list(h["shape"]), kind, shard, nbytes))

    total_bytes = sum(p[5] for p in plan)
    total_params = sum(p[5] // 2 for p in plan)
    log.info(f"plan: {len(plan)} tensors, {total_bytes/1e9:.2f} GB, "
             f"merge={sum(1 for p in plan if p[3]=='merge')}")

    max_bytes = int(args.shard_gb * 1024 ** 3)
    shards: list[list[tuple]] = [[]]
    cur = 0
    for p in plan:
        if cur + p[5] > max_bytes and shards[-1]:
            shards.append([])
            cur = 0
        shards[-1].append(p)
        cur += p[5]
    log.info(f"shards: {len(shards)}")

    if args.plan_only:
        for i, s in enumerate(shards, 1):
            log.info(f"  #{i}: {len(s)} tensors, {sum(x[5] for x in s)/1e9:.2f} GB")
        return

    if out_dir.exists():
        log.info(f"清理已有输出 {out_dir}")
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    loras = {k: Lora(k, Path(v[0]) if Path(v[0]).is_absolute() else ROOT / v[0])
             for k, v in LORAS.items()}
    weights = {k: v[1] for k, v in LORAS.items()}
    for k, l in loras.items():
        log.info(f"LoRA {k}: scale={l.scaling:.4f}")

    # ---------- Pass 2: 写数据 ----------
    t0 = time.time()
    n = len(shards)
    final_map: dict[str, str] = {}
    for si, shard_plan in enumerate(shards, 1):
        fname = f"model-{si:05d}-of-{n:05d}.safetensors"
        out_path = out_dir / fname
        with open(out_path, "wb") as out:
            data_start, expect = write_header(out, [(p[0], p[1], p[2]) for p in shard_plan])
            written = 0
            for name, dt, shape, kind, src_shard, nbytes in shard_plan:
                final_map[name] = fname
                if kind == "copy":
                    with open(base_dir / src_shard, "rb") as src:
                        src.seek(src_hdr[src_shard].data_start + src_hdr[src_shard].header[name]["data_offsets"][0])
                        left = nbytes
                        while left:
                            buf = src.read(min(CHUNK, left))
                            if not buf:
                                raise IOError(f"short read on {name}")
                            out.write(buf)
                            left -= len(buf)
                else:
                    layer = int(name.split(".layers.")[1].split(".")[0])
                    tail = name.split(f".layers.{layer}.", 1)[1]
                    proj = tail.split(".")[1]
                    base_t = read_tensor(base_dir / src_shard, src_hdr[src_shard], name)
                    acc0 = torch.zeros(base_t.shape, dtype=torch.float32)
                    acc1 = torch.zeros(base_t.shape, dtype=torch.float32)
                    if proj in ATTN_PROJ:
                        for k, w in weights.items():
                            loras[k].delta_into(layer, proj, acc0, w)
                        merged = base_t.float() + acc0
                        del acc1
                    else:
                        for k, w in EXPERT0.items():
                            loras[k].delta_into(layer, proj, acc0, w)
                        for k, w in EXPERT1.items():
                            loras[k].delta_into(layer, proj, acc1, w)
                        merged = base_t.float() + 0.5 * (prune_(acc0, args.density) + prune_(acc1, args.density))
                        del acc1
                    del acc0, base_t
                    out.write(merged.to(torch.bfloat16).contiguous()
                              .view(torch.uint8).reshape(-1).numpy().tobytes())
                    del merged
                    gc.collect()
                written += nbytes
            if written != expect:
                raise IOError(f"size mismatch in {fname}: {written} != {expect}")
        log.info(f"[{si}/{n}] {fname}  {expect/1e9:.2f} GB  ({time.time()-t0:.0f}s)")

    cfg = json.loads((base_dir / "config.json").read_text(encoding="utf-8"))
    cfg["architectures"] = ["Qwen3ForCausalLM"]
    cfg["model_type"] = "qwen3"
    for k in ("num_experts", "num_experts_per_tok", "moe_intermediate_size",
              "shared_expert_intermediate_size", "decoder_sparse_step", "norm_topk_prob"):
        cfg.pop(k, None)
    cfg["_merge_note"] = ("dense TIES-style merge of 4 domain LoRAs; "
                          "scripts/build_virtu_dense_ties.py 2026-11-06")
    (out_dir / "config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "model.safetensors.index.json").write_text(json.dumps({
        "metadata": {"total_size": total_bytes, "total_parameters": total_params,
                     "merge": "dense-ties", "density": args.density},
        "weight_map": final_map,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    for f in ("tokenizer.json", "tokenizer_config.json", "vocab.json", "merges.txt",
              "generation_config.json", "configuration.json"):
        if (base_dir / f).exists():
            shutil.copy2(base_dir / f, out_dir / f)

    log.info("=" * 66)
    log.info(f"完成 {total_params/1e9:.3f}B / {n} 分片 / {(time.time()-t0)/60:.1f} min -> {out_dir}")
    log.info("=" * 66)


if __name__ == "__main__":
    main()
