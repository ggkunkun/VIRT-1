# -*- coding: utf-8 -*-
"""Compare expert DELTAS (expert - base) instead of raw weights.

Raw weight cosine is meaningless for LoRA merges (base dominates). What matters:
  1) ||delta|| / ||base||            how strong each expert's update is
  2) cos(delta_e0, delta_e1)         do both experts move in the same direction?
  3) ||delta_e0 - delta_e1|| / ||delta_e0||   how distinguishable they are
"""
import glob
import json
import os
import struct

import numpy as np

CK = r"D:\Virtu模型\checkpoints"
MOE = os.path.join(CK, "virtu-moe-14b-bf16.gguf")
BASE_DIR = os.path.join(CK, "_base_qwen3_8b")


# ---------- safetensors header reader ----------
def st_header(path):
    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        hdr = json.loads(f.read(n).decode("utf-8"))
        return hdr, 8 + n


def read_bf16(path, name):
    hdr, data_start = st_header(path)
    meta = hdr[name]
    assert meta["dtype"] == "BF16", meta["dtype"]
    a, b = meta["data_offsets"]
    with open(path, "rb") as f:
        f.seek(data_start + a)
        u = np.frombuffer(f.read(b - a), dtype=np.uint16)
    w = (u.astype(np.uint32) << 16).view(np.float32)
    return w.reshape(meta["shape"])


shards = sorted(glob.glob(os.path.join(BASE_DIR, "*.safetensors")))
locate = {}
for s in shards:
    hdr, _ = st_header(s)
    for k in hdr:
        if k != "__metadata__":
            locate[k] = s


# ---------- GGUF expert reader (reuse minimal parser) ----------
class R:
    def __init__(self, f):
        self.f = f

    def u32(self):
        return struct.unpack("<I", self.f.read(4))[0]

    def u64(self):
        return struct.unpack("<Q", self.f.read(8))[0]

    def s(self):
        n = self.u64()
        return self.f.read(n).decode("utf-8", "replace")

    def skip(self, t):
        if t == 8:
            self.s()
        elif t in (0, 1, 7):
            self.f.read(1)
        elif t in (2, 3):
            self.f.read(2)
        elif t in (4, 5, 6):
            self.f.read(4)
        elif t in (10, 11, 12):
            self.f.read(8)
        elif t == 9:
            et = self.u32()
            for _ in range(self.u64()):
                self.skip(et)


with open(MOE, "rb") as f:
    f.read(4)
    r = R(f)
    r.u32()
    nt = r.u64()
    nkv = r.u64()
    align = 32
    for _ in range(nkv):
        k = r.s()
        t = r.u32()
        if k == "general.alignment" and t == 4:
            align = struct.unpack("<I", f.read(4))[0]
            continue
        r.skip(t)
    infos = {}
    for _ in range(nt):
        name = r.s()
        nd = r.u32()
        dims = [r.u64() for _ in range(nd)]
        ty = r.u32()
        off = r.u64()
        infos[name] = (dims, ty, off)
    data_start = (f.tell() + align - 1) // align * align

    def experts(L, key):
        name = f"blk.{L}.{key}.weight"
        dims, ty, off = infos[name]
        n = int(np.prod(dims))
        f.seek(data_start + off)
        u = np.frombuffer(f.read(n * 2), dtype=np.uint16)
        w = (u.astype(np.uint32) << 16).view(np.float32).reshape(dims, order="F")
        return w[..., 0], w[..., 1]     # each [in, out]

    print(f"{'layer':>5} {'proj':>9} {'||d0||/||W||':>13} {'||d1||/||W||':>13} "
          f"{'cos(d0,d1)':>11} {'||d0-d1||/||d0||':>17}")
    rows = []
    for L in (0, 12, 24, 35):
        for key, src in (("ffn_gate_exps", "gate_proj"), ("ffn_down_exps", "down_proj")):
            hf = f"model.layers.{L}.mlp.{src}.weight"
            if hf not in locate:
                print(f"{L:>5} {src:>9}   (base shard not found)")
                continue
            W = read_bf16(locate[hf], hf).astype(np.float32)      # [out, in]
            e0, e1 = experts(L, key)                             # [in, out]
            Wt = W.T.copy()
            d0, d1 = e0 - Wt, e1 - Wt
            nW = np.linalg.norm(Wt)
            n0, n1 = np.linalg.norm(d0), np.linalg.norm(d1)
            cos = float(d0.ravel() @ d1.ravel() / (n0 * n1 + 1e-12))
            dist = float(np.linalg.norm(d0 - d1) / (n0 + 1e-12))
            print(f"{L:>5} {src:>9} {n0/nW*100:>12.3f}% {n1/nW*100:>12.3f}% "
                  f"{cos:>11.4f} {dist:>16.4f}")
            rows.append((cos, dist))
            del W, Wt, d0, d1

cs = [r[0] for r in rows]
print(f"\ncos(delta0, delta1): mean = {np.mean(cs):+.4f} | min = {min(cs):+.4f} | max = {max(cs):+.4f}")
print("判读：cos≈1 表示两专家朝同一方向更新（路由无信息量）；cos 低表示确有分工")
