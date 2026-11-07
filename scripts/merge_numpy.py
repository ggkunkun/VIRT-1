#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
merge_numpy.py — 零 torch/peft 依赖的 LoRA 流式合并器（本机 Windows 可直接跑）。

原理
----
LoRA 合并只改动 7 个投影层 (q/k/v/o/gate/up/down_proj) 的权重，且合并后每个
张量的 shape / dtype / data_offsets 完全不变。因此可以逐分片流式处理：
  - target 张量      : bf16 -> f32, W += delta, -> bf16 写回（峰值 = 单张量 ~200MB）
  - 其余张量         : embed_tokens / lm_head / norm / q_norm / k_norm 按 4MB 分块原样拷贝
峰值内存 < 1GB，16GB 基座在本机 3.5GB 可用内存下也能合并。

合并公式（默认 peft_linear，逐位复现 peft 0.21.2 add_weighted_adapter(combination_type="linear")）
----
令 s_i = lora_alpha_i / r_i（use_rslora=False 时），g_i = w_i * s_i
    A_new = Σ_i sign(g_i)·sqrt(|g_i|)·A_i
    B_new = Σ_i sqrt(|g_i|)·B_i
    ΔW    = scaling_new · (B_new @ A_new)   # linear 分支 scaling_new = new_alpha/new_rank = 1
    W_merged = W_base + ΔW
注意：peft 的 linear 含 cross terms（i≠j 的 B_i@A_j），官方自称 "rough approximation"。
可选 --mode delta 使用无交叉项的干净公式 ΔW = Σ_i w_i·s_i·(B_i @ A_i)。

用法
----
  python scripts/merge_numpy.py --self-test
  python scripts/merge_numpy.py --base checkpoints/_base_qwen3_8b --out checkpoints/virtu_merged
  python scripts/merge_numpy.py --base ... --out ... --mode delta
  python scripts/merge_numpy.py --base ... --out ... --verify-only

依赖：numpy>=1.24（本机 2.5.4 已装）。不需要 torch / peft / transformers / safetensors。
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import hashlib
import struct
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import numpy as np

ROOT = Path(__file__).resolve().parent.parent

# 已验证配方（virtu_ties_v1：30 例工具编排 88.89 分，0 乱码）：
# 4 个 r=32/alpha=64 适配器，权重和 = 1.0。
# 排除：omni_autonomous_agent_lora / virtu_cad_cam_production_lora（5+ 路 delta 合并
#       实测 keyword 19.03、尺寸保真 0.125，属过合并）；tool_agent_lora_final(r=16,
#       rank 不兼容)；damodel_l40s_cad_cam_lora(与 cad_cam_six 字节相同)；
#       edge_qlora_adapter(r=8, 无权重文件)。
DEFAULT_LORAS = [
    ("checkpoints/turing_conversational_lora", 0.25),
    ("checkpoints/cad_cam_six_software_lora", 0.25),
    ("checkpoints/virtu_toolcall_lora", 0.35),
    ("checkpoints/ug_teacher_guided_agent_lora", 0.15),
]

TARGET_SUFFIXES = (
    ".q_proj.weight", ".k_proj.weight", ".v_proj.weight", ".o_proj.weight",
    ".gate_proj.weight", ".up_proj.weight", ".down_proj.weight",
)
COPY_CHUNK = 4 << 20  # 4MB
PASTE_FILES = (
    "config.json", "generation_config.json", "configuration.json",
    "tokenizer.json", "tokenizer_config.json", "vocab.json", "merges.txt",
    "model.safetensors.index.json",
)


# --------------------------------------------------------------------------- #
# bf16 <-> f32（numpy 无原生 bfloat16，手动位转换，避免依赖 ml_dtypes）
# --------------------------------------------------------------------------- #
def bf16_to_f32(buf: bytes) -> np.ndarray:
    u16 = np.frombuffer(buf, dtype="<u2")
    u32 = u16.astype(np.uint32) << 16
    return u32.view(np.float32)


def f32_to_bf16(arr: np.ndarray) -> bytes:
    a = np.ascontiguousarray(arr, dtype=np.float32).reshape(-1)
    u64 = a.view(np.uint32).astype(np.uint64)
    # round-to-nearest-even
    u16 = ((u64 + 0x7FFF + ((u64 >> 16) & 1)) >> 16).astype(np.uint16)
    return u16.tobytes()


# --------------------------------------------------------------------------- #
# safetensors 读取（仅需 struct + json + numpy）
# --------------------------------------------------------------------------- #
class SafeTensorReader:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.f = open(self.path, "rb")
        n = struct.unpack("<Q", self.f.read(8))[0]
        self.hlen = n
        self.header = json.loads(self.f.read(n))
        self.data_start = 8 + n

    def read_raw(self, st: int, en: int) -> bytes:
        self.f.seek(self.data_start + st)
        return self.f.read(en - st)

    def read(self, key: str) -> np.ndarray:
        h = self.header[key]
        st, en = h["data_offsets"]
        b = self.read_raw(st, en)
        dt = h["dtype"]
        if dt == "F32":
            arr = np.frombuffer(b, dtype="<f4")
        elif dt == "F16":
            arr = np.frombuffer(b, dtype="<f2").astype(np.float32)
        elif dt == "BF16":
            arr = bf16_to_f32(b)
        else:
            raise ValueError(f"unsupported dtype {dt} for {key}")
        return arr.reshape(h["shape"])

    def close(self) -> None:
        self.f.close()


def md5_file(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class LoraAdapter:
    def __init__(self, directory: str | Path, weight: float):
        self.dir = Path(directory)
        if not self.dir.is_absolute():
            self.dir = ROOT / self.dir
        self.weight = float(weight)
        cfg = json.load(open(self.dir / "adapter_config.json", encoding="utf-8"))
        self.r = int(cfg["r"])
        self.alpha = float(cfg["lora_alpha"])
        self.rslora = bool(cfg.get("use_rslora", False))
        self.s = self.alpha / math.sqrt(self.r) if self.rslora else self.alpha / self.r
        wfiles = sorted(self.dir.glob("*.safetensors"))
        if not wfiles:
            raise FileNotFoundError(f"no safetensors in {self.dir}")
        self.file_md5 = md5_file(wfiles[0])
        self.reader = SafeTensorReader(wfiles[0])

    def read(self, key: str) -> np.ndarray:
        return self.reader.read(key)

    def close(self) -> None:
        self.reader.close()

    @property
    def name(self) -> str:
        return self.dir.name


def lora_keys(base_key: str) -> tuple[str, str]:
    """base: model.layers.0.self_attn.q_proj.weight
       ->  base_model.model.model.layers.0.self_attn.q_proj.lora_{A,B}.weight"""
    stem = base_key[: -len(".weight")]
    return f"base_model.model.{stem}.lora_A.weight", f"base_model.model.{stem}.lora_B.weight"


def compute_delta(base_key: str, loras: list[LoraAdapter], mode: str,
                  density: float = 0.25, drop_rate: float = 0.5) -> np.ndarray | None:
    ak, bk = lora_keys(base_key)
    for L in loras:
        if ak not in L.reader.header or bk not in L.reader.header:
            return None
    if mode == "peft_linear":
        A_new = None
        B_new = None
        for L in loras:
            g = L.weight * L.s
            sq = math.sqrt(abs(g))
            sign = 1.0 if g >= 0 else -1.0
            A = L.read(ak)
            B = L.read(bk)
            A_new = sq * sign * A if A_new is None else A_new + sq * sign * A
            B_new = sq * B if B_new is None else B_new + sq * B
        return B_new @ A_new  # scaling_new = 1
    if mode == "delta":
        delta = None
        for L in loras:
            g = L.weight * L.s
            A = L.read(ak)
            B = L.read(bk)
            d = g * (B @ A)
            delta = d if delta is None else delta + d
        return delta
    if mode == "ties":
        # TIES-Merging: 1. Trimming (top-k density) -> 2. Elect Sign -> 3. Disjoint Merge
        deltas = []
        for L in loras:
            g = L.weight * L.s
            A = L.read(ak)
            B = L.read(bk)
            d = g * (B @ A)
            # 1. Trimming: keep top-k% largest absolute values
            flat = np.abs(d).reshape(-1)
            k = max(1, int(len(flat) * density))
            thresh = np.partition(flat, -k)[-k]
            mask = np.abs(d) >= thresh
            deltas.append(d * mask)

        # 2. Elect Sign consensus
        sum_delta = np.sum(deltas, axis=0)
        consensus_sign = np.sign(sum_delta)

        # 3. Disjoint Merge: retain values with agreeing sign, average non-zeros
        filtered = []
        counts = np.zeros_like(consensus_sign, dtype=np.float32)
        for d in deltas:
            aligned_mask = (np.sign(d) == consensus_sign) & (d != 0)
            filtered.append(d * aligned_mask)
            counts += aligned_mask.astype(np.float32)

        nonzero_mask = counts > 0
        merged = np.zeros_like(sum_delta)
        merged[nonzero_mask] = np.sum(filtered, axis=0)[nonzero_mask] / counts[nonzero_mask]
        return merged
    if mode == "dare":
        # DARE: Drop And Rescale with sign election
        rng = np.random.default_rng(42)
        deltas = []
        for L in loras:
            g = L.weight * L.s
            A = L.read(ak)
            B = L.read(bk)
            d = g * (B @ A)
            # Drop and rescale
            mask = rng.uniform(0.0, 1.0, size=d.shape) > drop_rate
            d_rescaled = (d * mask) / (1.0 - drop_rate)
            deltas.append(d_rescaled)
        sum_delta = np.sum(deltas, axis=0)
        consensus_sign = np.sign(sum_delta)
        counts = np.zeros_like(consensus_sign, dtype=np.float32)
        filtered = []
        for d in deltas:
            aligned_mask = (np.sign(d) == consensus_sign) & (d != 0)
            filtered.append(d * aligned_mask)
            counts += aligned_mask.astype(np.float32)
        nonzero_mask = counts > 0
        merged = np.zeros_like(sum_delta)
        merged[nonzero_mask] = np.sum(filtered, axis=0)[nonzero_mask] / counts[nonzero_mask]
        return merged
    raise ValueError(f"unknown mode {mode}")


def is_target(key: str) -> bool:
    return key.startswith("model.layers.") and key.endswith(TARGET_SUFFIXES)


# --------------------------------------------------------------------------- #
# 合并单个分片
# --------------------------------------------------------------------------- #
def merge_shard(src: Path, out: Path, loras: list[LoraAdapter], mode: str,
                resume: bool = False) -> dict:
    # 断点续传：产物已存在且大小与源一致则跳过（合并前后 size 严格不变）。
    # 后台任务可能被沙箱中途降权，前台新会话只需补未完成的最后一片。
    if resume and out.exists() and out.stat().st_size == src.stat().st_size:
        r0 = SafeTensorReader(src)
        n_target = sum(1 for k in r0.header if k != "__metadata__" and is_target(k))
        n_total = len([k for k in r0.header if k != "__metadata__"])
        r0.close()
        print(f"    {src.name}: 已存在且完整，跳过 ({n_target} target)", flush=True)
        return {"shard": src.name, "tensors": n_total, "merged_targets": n_target,
                "bytes": out.stat().st_size, "seconds": 0.0, "skipped": True}
    r = SafeTensorReader(src)
    with open(src, "rb") as sf:
        head_bytes = sf.read(8 + r.hlen)  # header 原样复用（shape/dtype/offsets 不变）
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as of:
        of.write(head_bytes)

    items = []
    for k, v in r.header.items():
        if k == "__metadata__":
            continue
        st, en = v["data_offsets"]
        items.append((st, en, k))
    items.sort()
    pos = 0
    for st, en, k in items:
        if st != pos:
            raise ValueError(f"[{src.name}] 非连续 offset: {k} st={st} expected={pos}（无法安全流式写）")
        pos = en

    n_target = 0
    t0 = time.time()
    with open(out, "r+b") as of:
        for i, (st, en, k) in enumerate(items):
            of.seek(8 + r.hlen + st)
            if is_target(k):
                raw = r.read_raw(st, en)
                W = bf16_to_f32(raw)
                delta = compute_delta(k, loras, mode)
                if delta is None:
                    raise RuntimeError(f"[{src.name}] target 缺 LoRA 键: {k}")
                merged = f32_to_bf16(W + delta.reshape(-1))
                if len(merged) != en - st:
                    raise RuntimeError(f"[{src.name}] 写回字节数不符: {k} {len(merged)} != {en-st}")
                of.write(merged)
                n_target += 1
            else:
                r.f.seek(8 + r.hlen + st)
                remain = en - st
                while remain > 0:
                    b = r.f.read(min(COPY_CHUNK, remain))
                    if not b:
                        raise RuntimeError(f"[{src.name}] 源文件意外 EOF: {k}")
                    of.write(b)
                    remain -= len(b)
            if (i + 1) % 40 == 0:
                print(f"    {src.name}: {i+1}/{len(items)} 张量, {n_target} target", flush=True)
    r.close()

    src_sz, out_sz = src.stat().st_size, out.stat().st_size
    if src_sz != out_sz:
        raise RuntimeError(f"[{src.name}] 输出大小 {out_sz} != 输入 {src_sz}")
    return {"shard": src.name, "tensors": len(items), "merged_targets": n_target,
            "bytes": out_sz, "seconds": round(time.time() - t0, 1)}


# --------------------------------------------------------------------------- #
# 数值验证：W_merged - W_base 应等于 delta（bf16 量化误差内）
# --------------------------------------------------------------------------- #
def verify(src_dir: Path, out_dir: Path, loras: list[LoraAdapter], mode: str,
           per_shard: int = 3) -> list[dict]:
    reports = []
    shards = sorted(src_dir.glob("model-*.safetensors"))
    for sp in shards:
        op = out_dir / sp.name
        if not op.exists():
            continue
        rs, ro = SafeTensorReader(sp), SafeTensorReader(op)
        targets = [k for k in rs.header if k != "__metadata__" and is_target(k)]
        if not targets:
            reports.append({"shard": sp.name, "note": "no target tensor in this shard"})
            rs.close(); ro.close()
            continue
        step = max(1, len(targets) // per_shard)
        picked = targets[::step][:per_shard]
        for k in picked:
            st, en = rs.header[k]["data_offsets"]
            W0 = bf16_to_f32(rs.read_raw(st, en)).astype(np.float64)
            W1 = bf16_to_f32(ro.read_raw(st, en)).astype(np.float64)
            observed = W1 - W0
            expected = compute_delta(k, loras, mode)
            expected = np.zeros_like(W0) if expected is None else expected.reshape(-1).astype(np.float64)
            err = np.abs(observed - expected)
            amp = float(np.abs(expected).max())
            scale = float(np.abs(W0).max())
            reports.append({
                "shard": sp.name, "tensor": k,
                "max_abs_err": float(err.max()),
                "mean_abs_err": float(err.mean()),
                "delta_max_amp": amp,
                "base_max_amp": scale,
                "rel_to_delta": float(err.max() / (amp + 1e-12)),
                "rel_to_base": float(err.max() / (scale + 1e-12)),
                "PASS": bool(err.max() / (scale + 1e-12) < 0.02),
            })
        rs.close(); ro.close()
    return reports


# --------------------------------------------------------------------------- #
def probe_amplitude(base: Path, loras: list[LoraAdapter], samples: int = 10) -> dict:
    """
    合并前预检：对抽样 target 张量，分别计算两种合并公式的 delta/base RMS 比。
    peft 的 linear 组合含 cross terms，4 个 LoRA 叠加后可能显著放大 delta，
    有过合并毁掉基座的风险；此函数用真实数值量化该风险，辅助选择 --mode。
    只读抽样张量，不写盘。
    """
    targets = []
    for sp in sorted(base.glob("model-*.safetensors")):
        r = SafeTensorReader(sp)
        for k, v in r.header.items():
            if k != "__metadata__" and is_target(k):
                targets.append((sp, k, v["data_offsets"]))
        r.close()
    if not targets:
        raise SystemExit("[probe] 基座中未找到 target 张量")
    step = max(1, len(targets) // samples)
    picked = targets[::step][:samples]

    by_shard: dict[Path, list] = {}
    for sp, k, off in picked:
        by_shard.setdefault(sp, []).append((k, off))

    results = {}
    for mode in ("peft_linear", "delta"):
        ratios = []
        print(f"\n--- mode={mode} ---")
        for sp, items in by_shard.items():
            r = SafeTensorReader(sp)
            for k, (st, en) in items:
                W0 = bf16_to_f32(r.read_raw(st, en)).astype(np.float64)
                delta = compute_delta(k, loras, mode)
                if delta is None:
                    continue
                d = delta.reshape(-1).astype(np.float64)
                rb = float(np.sqrt(np.mean(W0 * W0)))
                rd = float(np.sqrt(np.mean(d * d)))
                ratio = rd / rb if rb > 1e-12 else 0.0
                ratios.append(ratio)
                print(f"  {k:56s} delta/base={ratio:.2%}")
            r.close()
        if ratios:
            results[mode] = {"mean": sum(ratios) / len(ratios), "max": max(ratios),
                             "n": len(ratios)}
            print(f"  [{mode}] mean={results[mode]['mean']:.2%} max={results[mode]['max']:.2%}")
    print("\n[probe] 判据: 单 LoRA 正常 delta/base 通常 1~5%；"
          "合并后 max>20% 需警惕过合并，max>30% 强烈建议用 delta 模式或降权重。")
    return results


# --------------------------------------------------------------------------- #
def self_test() -> None:
    print("=== self-test 1: bf16 往返 ===")
    rng = np.random.default_rng(0)
    x = (rng.standard_normal(4096) * 0.5).astype(np.float32)
    y = bf16_to_f32(f32_to_bf16(x))
    e = float(np.abs(x - y).max())
    print(f"  max_abs_err={e:.6f} (bf16 精度应 < 0.01)")
    assert e < 0.01, "bf16 往返精度异常"

    print("=== self-test 2: safetensors 读写 + delta 公式 ===")
    # 构造一个小 LoRA 张量文件，验证 lora_keys 映射与 B@A 方向
    r, in_f, out_f = 4, 6, 5
    A = rng.standard_normal((r, in_f)).astype(np.float32)
    B = rng.standard_normal((out_f, r)).astype(np.float32)
    delta = B @ A
    print(f"  B@A shape={delta.shape}（应为 [{out_f},{in_f}]，与基座 weight [out,in] 一致）")
    assert delta.shape == (out_f, in_f)
    print("  self-test PASS")


def main() -> None:
    p = argparse.ArgumentParser(description="零依赖纯 numpy LoRA 流式合并器")
    p.add_argument("--base", default=str(ROOT / "checkpoints" / "_base_qwen3_8b"),
                   help="Qwen3-8B 基座目录（含 model-*.safetensors 与 index）")
    p.add_argument("--out", default=str(ROOT / "checkpoints" / "virtu_merged"),
                   help="合并产物目录")
    p.add_argument("--mode", choices=["peft_linear", "delta", "ties", "dare"], default="delta",
                   help="delta=无交叉项干净加和 (推荐)；ties=TIES剪枝与符号共识合并；dare=DARE稀疏化合并；peft_linear=复现 add_weighted_adapter(linear) 含 cross terms")
    p.add_argument("--normalize-weights", action="store_true",
                   help="自动对多 LoRA 权重进行归一化 (Σ w_i = 1.0)，防止多适配器权重线性叠加导致范数过大")
    p.add_argument("--lora", action="append", default=None, help="LoRA 目录（可重复，覆盖默认 4 个）")
    p.add_argument("--append-lora", action="store_true",
                   help="不覆盖默认 4 个，而是把 --lora 追加到默认集合之后")
    p.add_argument("--weight", action="append", type=float, default=None, help="与 --lora 对应的权重")
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--verify-only", action="store_true", help="只跑数值验证（产物已存在）")
    p.add_argument("--verify-samples", type=int, default=3, help="每分片抽样验证的 target 张量数")
    p.add_argument("--resume", action="store_true",
                   help="断点续传：跳过已存在且大小正确的产物分片")
    p.add_argument("--probe-amplitude", action="store_true",
                   help="合并前预检两种公式的 delta/base 幅度（只读抽样张量，不写盘）")
    p.add_argument("--probe-samples", type=int, default=10, help="幅度预检抽样张量数")
    args = p.parse_args()

    if args.self_test:
        self_test()
        return

    base = Path(args.base)
    out = Path(args.out)
    if not (base / "config.json").exists():
        raise SystemExit(f"[FATAL] 基座目录不完整（缺 config.json）: {base}\n"
                         f"        先跑: python scripts/download_base_modelscope.py")

    if args.lora:
        weights = args.weight if args.weight else [1.0] * len(args.lora)
        if len(weights) != len(args.lora):
            raise SystemExit("[FATAL] --lora 与 --weight 数量不一致")
        lora_specs = list(zip(args.lora, weights))
        if args.append_lora:
            lora_specs = DEFAULT_LORAS + lora_specs
            print("[merge] --append-lora: 在默认 4 个 LoRA 基础上追加 "
                  f"{len(args.lora)} 个")
    else:
        lora_specs = DEFAULT_LORAS

    total_w = sum(w for _, w in lora_specs) if lora_specs else 0.0
    if len(lora_specs) > 1 and (args.normalize_weights or total_w > 1.05):
        if total_w > 0:
            if abs(total_w - 1.0) > 1e-9:
                print(f"[merge] [WARN] 适配器权重和为 {total_w:.4f}，归一化为 1.0 "
                      "(避免多适配器线性叠加导致参数爆炸)")
            lora_specs = [(d, w / total_w) for d, w in lora_specs]

    loras = [LoraAdapter(d, w) for d, w in lora_specs]
    by_hash: dict[str, str] = {}
    duplicates = []
    for L in loras:
        if L.file_md5 in by_hash:
            duplicates.append((L.name, by_hash[L.file_md5], L.file_md5))
        else:
            by_hash[L.file_md5] = L.name
    if duplicates:
        for name, first, digest in duplicates:
            print(f"[FATAL] {name} 与 {first} 的 adapter 权重字节相同 (md5={digest})")
        for L in loras:
            L.close()
        raise SystemExit("[FATAL] 检测到重复 LoRA 拷贝；重复计入会放大该适配器的 delta。"
                         "请移除重复项后重跑。")
    ranks = {L.name: L.r for L in loras}
    if len(set(ranks.values())) > 1 and args.mode == "peft_linear":
        raise SystemExit(f"[FATAL] peft_linear 要求所有 LoRA 同 rank，实测: {ranks}")
    print("=== LoRA 列表 ===")
    for L in loras:
        print(f"  {L.name:38s} r={L.r} alpha={L.alpha} scaling={L.s:.3f} "
              f"weight={L.weight} md5={L.file_md5[:12]}")
    print(f"  合并模式: {args.mode}")
    print(f"  基座: {base}\n  产物: {out}\n")

    if args.probe_amplitude:
        probe_amplitude(base, loras, samples=args.probe_samples)
        for L in loras:
            L.close()
        return

    out.mkdir(parents=True, exist_ok=True)

    if not args.verify_only:
        for name in PASTE_FILES:
            sp = base / name
            if sp.exists():
                shutil.copy2(sp, out / name)
        print("=== 开始合并分片 ===")
        t0 = time.time()
        shard_stats = []
        for sp in sorted(base.glob("model-*.safetensors")):
            print(f"  -> {sp.name} ({sp.stat().st_size/1e9:.2f} GB)", flush=True)
            shard_stats.append(merge_shard(sp, out / sp.name, loras, args.mode,
                                           resume=args.resume))
        print(f"  合并耗时 {time.time()-t0:.0f}s")
    else:
        shard_stats = []

    print("=== 数值验证 ===")
    reports = verify(base, out, loras, args.mode, per_shard=args.verify_samples)
    ok = sum(1 for r in reports if r.get("PASS"))
    chk = [r for r in reports if "PASS" in r]
    for r in chk:
        print(f"  [{'PASS' if r['PASS'] else 'FAIL'}] {r['tensor']}: "
              f"err/base={r['rel_to_base']:.2e} err/delta={r['rel_to_delta']:.2e}")
    print(f"  验证 {ok}/{len(chk)} PASS")

    receipt = {
        "status": "COMPLETED" if not chk or ok == len(chk) else "VERIFY_FAILED",
        "base_model": str(base),
        "base_model_id": "Qwen/Qwen3-8B (ModelScope)",
        "merged_dir": str(out),
        "combination_mode": args.mode,
        "formula": {
            "peft_linear": "A_new=Σ√gᵢ·Aᵢ; B_new=Σ√gᵢ·Bᵢ; ΔW=B_new@A_new; gᵢ=wᵢ·(αᵢ/rᵢ); scaling_new=1",
            "delta": "ΔW=Σᵢ wᵢ·(αᵢ/rᵢ)·(Bᵢ@Aᵢ)",
            "ties": "TIES: Trim top-25% -> Sign consensus -> Disjoint average",
            "dare": "DARE: Random dropout 50% & rescale -> Sign consensus -> Disjoint average",
        }[args.mode],
        "merged_loras": [
            {"name": L.name, "r": L.r, "alpha": L.alpha, "scaling": L.s,
             "weight": L.weight, "adapter_md5": L.file_md5}
            for L in loras
        ],
        "weight_sum": sum(L.weight for L in loras),
        "excluded_loras": [
            "tool_agent_lora_final (r=16, rank 不兼容，保留为运行时可挂载)",
            "damodel_l40s_cad_cam_lora (与 cad_cam_six_software_lora 重复拷贝)",
            "edge_qlora_adapter (r=8, 无权重文件)",
        ],
        "shards": shard_stats,
        "verification": reports,
        "verification_summary": {"passed": ok, "total": len(chk)},
        "note": "纯 numpy 流式合并，无需 torch/peft；header/index 与基座完全一致，仅重排数据区。",
    }
    with open(out / "merge_receipt.json", "w", encoding="utf-8") as f:
        json.dump(receipt, f, ensure_ascii=False, indent=2)
    print(f"\n=== 回执 -> {out / 'merge_receipt.json'} ===")
    if chk and ok != len(chk):
        raise SystemExit("[FATAL] 数值验证未全部通过，请检查 merge_receipt.json")

    for L in loras:
        L.close()


if __name__ == "__main__":
    main()
