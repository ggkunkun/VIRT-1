#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/verify_dense_merge.py — 结构校验：稠密 FFN 是否同时继承了两位专家的增量方向。

对指定层/投影，按行分块累加，计算
  Δe0 = E0 − W_base, Δe1 = E1 − W_base, Δdense = W_dense − W_base
报告 cos(Δdense,Δe0)、cos(Δdense,Δe1)、cos(Δe0,Δe1) 与 ‖Δ‖/‖W_base‖。
判据：两条余弦均在 0.55~0.95（正交混合理论值 ≈0.71），且专家间余弦接近 0。
内存：每块 rows×in×4B×4 ≈ 64MB（chunk=1024 行 gate_proj），与张量大小无关。
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = ROOT / "checkpoints/_base_qwen3_8b"
MOE = ROOT / "checkpoints/virtu_moe_14b_hf"
DENSE = ROOT / "checkpoints/virtu_dense_merged_hf"


class Rows:
    def __init__(self, d: Path):
        idx = json.loads((d / "model.safetensors.index.json").read_text(encoding="utf-8"))
        self.d, self.wmap, self.files = d, idx["weight_map"], {}

    def _open(self, name):
        sh = self.wmap[name]
        if sh not in self.files:
            f = open(self.d / sh, "rb")
            n = struct.unpack("<Q", f.read(8))[0]
            hdr = json.loads(f.read(n))
            self.files[sh] = (f, hdr, 8 + n)
        return self.files[sh]

    def shape(self, name):
        return list(self._open(name)[1][name]["shape"])

    def get(self, name, r0, r1) -> np.ndarray:
        f, hdr, base = self._open(name)
        st, en = hdr[name]["data_offsets"]
        shape = hdr[name]["shape"]
        row_bytes = (en - st) // int(shape[0])
        f.seek(base + st + r0 * row_bytes)
        buf = f.read((r1 - r0) * row_bytes)
        u = np.frombuffer(buf, dtype=np.uint16).reshape(r1 - r0, int(shape[1]))
        return (u.astype(np.uint32) << 16).view(np.float32)


def main() -> int:
    layers = [int(x) for x in (sys.argv[1].split(",") if len(sys.argv) > 1 else ["0", "18", "35"])]
    chunk = 1024
    base, moe, dense = Rows(BASE), Rows(MOE), Rows(DENSE)
    out = []
    for L in layers:
        for p in ("gate_proj", "down_proj"):
            n_b = f"model.layers.{L}.mlp.{p}.weight"
            n0 = f"model.layers.{L}.mlp.experts.0.{p}.weight"
            n1 = f"model.layers.{L}.mlp.experts.1.{p}.weight"
            rows = base.shape(n_b)[0]
            acc = {k: 0.0 for k in ("wb", "d0", "d1", "dd", "dd_d0", "dd_d1", "d0_d1")}
            for r0 in range(0, rows, chunk):
                r1 = min(rows, r0 + chunk)
                wb = base.get(n_b, r0, r1)
                d0 = moe.get(n0, r0, r1) - wb
                d1 = moe.get(n1, r0, r1) - wb
                dd = dense.get(n_b, r0, r1) - wb
                acc["wb"] += float((wb * wb).sum())
                acc["d0"] += float((d0 * d0).sum())
                acc["d1"] += float((d1 * d1).sum())
                acc["dd"] += float((dd * dd).sum())
                acc["dd_d0"] += float((dd * d0).sum())
                acc["dd_d1"] += float((dd * d1).sum())
                acc["d0_d1"] += float((d0 * d1).sum())
                del wb, d0, d1, dd
            n_wb, n0_, n1_ = acc["wb"] ** 0.5, acc["d0"] ** 0.5, acc["d1"] ** 0.5
            nd = acc["dd"] ** 0.5
            rec = {
                "layer": L, "proj": p,
                "rel_delta_e0": round(n0_ / n_wb, 5),
                "rel_delta_e1": round(n1_ / n_wb, 5),
                "rel_delta_dense": round(nd / n_wb, 5),
                "cos_dense_e0": round(acc["dd_d0"] / (nd * n0_), 4),
                "cos_dense_e1": round(acc["dd_d1"] / (nd * n1_), 4),
                "cos_e0_e1": round(acc["d0_d1"] / (n0_ * n1_), 4),
            }
            out.append(rec)
            print(json.dumps(rec, ensure_ascii=False), flush=True)
    ok = all(0.55 <= r["cos_dense_e0"] <= 0.95 and 0.55 <= r["cos_dense_e1"] <= 0.95 for r in out)
    print("\n判定:", "PASS 两专家方向均被继承" if ok else "FAIL 有一侧方向丢失")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
