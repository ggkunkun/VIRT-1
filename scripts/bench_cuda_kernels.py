# -*- coding: utf-8 -*-
"""bench_cuda_kernels.py — 定制 CUDA 算子 vs torch 生产路径的卡上实测

口径与 `benchmarks/model_operator_theoretical_limit_report.md` 对齐：
  batch=2, hidden=512, heads=8, head_dim=64, seq ∈ {128, 512, 1024}
  intermediate=1536；计时用 CUDA Event（warmup=5, repeats=20, 取 min/median）

产出：
  benchmarks/wm_cuda_kernels_2026-11-08.json  （basis=measured, run_id 内容指纹）
  benchmarks/wm_cuda_kernels_2026-11-08.md    （人读摘要）

用法： python scripts/bench_cuda_kernels.py [--out-prefix benchmarks/wm_cuda_kernels_2026-11-08]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import time

import torch
import torch.nn.functional as F

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from virtu_omni.models import cuda_ops as K  # noqa: E402
from virtu_omni.models.architecture import UniRoPE  # noqa: E402

B, HEADS, HEAD_DIM = 2, 8, 64
HIDDEN = HEADS * HEAD_DIM
INTER = HIDDEN * 3
SEQLENS = [128, 512, 1024]
DTS = [("fp32", torch.float32), ("bf16", torch.bfloat16), ("fp16", torch.float16)]


def _time_gpu(fn, warmup=5, repeats=20):
    for _ in range(warmup):
        fn()
    torch.cuda.synchronize()
    xs = []
    for _ in range(repeats):
        a = torch.cuda.Event(enable_timing=True)
        b = torch.cuda.Event(enable_timing=True)
        a.record()
        fn()
        b.record()
        torch.cuda.synchronize()
        xs.append(a.elapsed_time(b))
    return {"min_ms": min(xs), "median_ms": statistics.median(xs), "n": len(xs)}


def _time_wall(fn, repeats=3):
    xs = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        xs.append((time.perf_counter() - t0) * 1e3)
    return {"min_ms": min(xs), "median_ms": statistics.median(xs), "n": len(xs)}


def bench_swiglu(results):
    for S in SEQLENS:
        n = B * S * INTER
        for dname, dt in DTS[:2]:
            g = torch.randn(n, device="cuda", dtype=dt)
            u = torch.randn(n, device="cuda", dtype=dt)
            rows = [
                ("torch_silu_mul", lambda: F.silu(g).mul_(u)),
                ("cuda_ops", lambda: K.swiglu(g, u)),
            ]
            for arm, fn in rows:
                t = _time_gpu(fn)
                results.append({"op": "swiglu", "seq": S, "dtype": dname, "arm": arm, **t})


def bench_rmsnorm(results):
    for S in SEQLENS:
        rows_n, cols = B * S, HIDDEN
        for dname, dt in DTS[:2]:
            x = torch.randn(rows_n, cols, device="cuda", dtype=dt)
            w = torch.randn(cols, device="cuda", dtype=dt)
            eps = 1e-6
            arms = [
                ("torch_F.rms_norm", lambda: F.rms_norm(x, (cols,), w, eps=eps)),
                ("cuda_ops", lambda: K.rmsnorm(x, w, eps)),
            ]
            for arm, fn in arms:
                t = _time_gpu(fn)
                results.append({"op": "rmsnorm", "seq": S, "dtype": dname, "arm": arm, **t})


def bench_rope(results):
    rope = UniRoPE(HEAD_DIM, max_seq_len=2048).cuda()
    for S in SEQLENS:
        for dname, dt in DTS[:2]:
            q = torch.randn(B, S, HEADS, HEAD_DIM, device="cuda", dtype=dt)
            k = q.clone()
            rope._build_cache(S, q.device, q.dtype)
            cos = rope._cos_cached[:S]
            sin = rope._sin_cached[:S]
            pos = torch.arange(S, device="cuda")
            # 与 VirtuAttention 生产调用点一致（带 max_pos_hint）；torch 臂显式关掉
            # 快路径，否则接线后两臂都在跑同一个内核，等于自己比自己。
            orig_avail = K.available
            K.available = lambda: False
            t_off = _time_gpu(lambda: rope.apply_1d_rope(
                q, k, pos, max_pos_hint=S, contiguous_slice=(0, S)))
            K.available = orig_avail
            t_on = _time_gpu(lambda: (K.rope1d(q, cos, sin), K.rope1d(k, cos, sin)))
            results.append({"op": "rope1d", "seq": S, "dtype": dname,
                            "arm": "unirope_apply_1d", "min_ms": t_off["min_ms"],
                            "median_ms": t_off["median_ms"], "n": t_off["n"]})
            results.append({"op": "rope1d", "seq": S, "dtype": dname,
                            "arm": "cuda_ops", "min_ms": t_on["min_ms"],
                            "median_ms": t_on["median_ms"], "n": t_on["n"]})


def bench_rope2d(results):
    """视觉 2D RoPE：q/k[B,N,H,D]，N=grid_h*grid_w；对比模块路径与定制内核。"""
    rope = UniRoPE(HEAD_DIM, max_seq_len=2048).cuda()
    for gh, gw in ((16, 16), (32, 32)):
        N = gh * gw
        q = torch.randn(B, N, HEADS, HEAD_DIM, device="cuda")
        k = q.clone()
        rope.apply_2d_rope(q, k, gh, gw)          # 填充三角表缓存
        cy, cx = rope._cos_2d
        sy, sx = rope._sin_2d
        cy2, sy2 = cy.squeeze(0).squeeze(1), sy.squeeze(0).squeeze(1)
        cx2, sx2 = cx.squeeze(0).squeeze(1), sx.squeeze(0).squeeze(1)
        orig_avail = K.available
        K.available = lambda: False
        t_off = _time_gpu(lambda: rope.apply_2d_rope(q, k, gh, gw))
        K.available = orig_avail
        t_on = _time_gpu(lambda: (K.rope2d(q, cy2, sy2, cx2, sx2),
                                  K.rope2d(k, cy2, sy2, cx2, sx2)))
        for arm, t in (("unirope_apply_2d", t_off), ("cuda_ops", t_on)):
            results.append({"op": "rope2d", "seq": f"{gh}x{gw}", "dtype": "fp32",
                            "arm": arm, **t})


def bench_physics(results):
    import wm_verifier

    rng = torch.Generator(device="cuda").manual_seed(11)
    for n in (1_000, 100_000, 1_000_000):
        sx = torch.rand(n, device="cuda", generator=rng) * 180 + 20
        sy = torch.rand(n, device="cuda", generator=rng) * 120 + 10
        tau = torch.rand(n, device="cuda", generator=rng) * 40
        Sy = torch.rand(n, device="cuda", generator=rng) * 600 + 200
        torch_arm = _time_gpu(lambda: (
            lambda vm: (vm, Sy / vm, (Sy / vm) >= 1.5))(
            (sx * sx - sx * sy + sy * sy + 3 * tau * tau).clamp_min(0).sqrt()))
        cuda_arm = _time_gpu(lambda: K.fea_batch(sx, sy, tau, Sy))
        entry = {"op": "fea_batch", "n": n, "dtype": "fp32",
                 "torch_gpu_ms": torch_arm["min_ms"], "cuda_ops_ms": cuda_arm["min_ms"],
                 "speedup_vs_torch": torch_arm["min_ms"] / cuda_arm["min_ms"],
                 "n_samples": cuda_arm["n"]}
        if n <= 10_000:
            scenarios = [
                {"task": "fea_fos", "inputs": {"Sy": float(Sy[i]), "sigma": float(sx[i])}}
                for i in range(min(n, 1_000))
            ]
            py = _time_wall(lambda: [wm_verifier.recompute(s) for s in scenarios])
            entry["python_loop_n"] = len(scenarios)
            entry["python_loop_ms"] = py["min_ms"]
            entry["speedup_vs_python_per_scenario"] = (
                (py["min_ms"] / len(scenarios)) / (cuda_arm["min_ms"] / n))
        results.append(entry)

    for n in (1_000, 100_000, 1_000_000):
        zs = torch.rand(n, device="cuda", generator=rng) * 60 + 10
        zm = torch.rand(n, device="cuda", generator=rng) * 80 - 10
        zt = torch.rand(n, device="cuda", generator=rng) * 60
        torch_arm = _time_gpu(lambda: (
            ((zm < zs) & (zm < zt + 1.0)) | (zm < zt)))
        cuda_arm = _time_gpu(lambda: K.collision_batch(zs, zm, zt))
        results.append({"op": "collision_batch", "n": n, "dtype": "fp32",
                        "torch_gpu_ms": torch_arm["min_ms"], "cuda_ops_ms": cuda_arm["min_ms"],
                        "speedup_vs_torch": torch_arm["min_ms"] / cuda_arm["min_ms"],
                        "n_samples": cuda_arm["n"]})


def bench_modules(results):
    """模块级：真实 VirtuRMSNorm / VirtuSwiGLU / UniRoPE 开/关定制算子的端到端差异。

    「关」= 把 cuda_ops.available 临时置假（*_or_none 内部的显式回退判定点），
    同一份权重、同一份输入，只差快路径开关。
    """
    from virtu_omni.config import ModelConfig
    from virtu_omni.models.architecture import VirtuRMSNorm, VirtuSwiGLU

    orig = K.available

    def _run(fn):
        with torch.no_grad():
            return _time_gpu(fn)

    torch.manual_seed(9)
    cfg = ModelConfig(num_layers=2, hidden_dim=HIDDEN, intermediate_dim=INTER,
                      vocab_size=1000, num_attention_heads=HEADS,
                      num_kv_heads=HEADS, head_dim=HEAD_DIM)
    for S in SEQLENS:
        norm = VirtuRMSNorm(HIDDEN).to("cuda").eval()
        x = torch.randn(B, S, HIDDEN, device="cuda")
        ffn = VirtuSwiGLU(cfg).to("cuda").eval()
        ffn.fuse_projections()
        rope = UniRoPE(HEAD_DIM, max_seq_len=2048).cuda()
        q = torch.randn(B, S, HEADS, HEAD_DIM, device="cuda")
        k = q.clone()
        pos = torch.arange(S, device="cuda")
        arms = [
            ("rmsnorm", lambda: norm(x)),
            ("swiglu", lambda: ffn(x)),
            ("rope1d", lambda: rope.apply_1d_rope(
                q, k, pos, max_pos_hint=S, contiguous_slice=(0, S))),
        ]
        for name, fn in arms:
            K.available = orig
            on = _run(fn)
            K.available = lambda: False
            off = _run(fn)
            K.available = orig
            results.append({"op": f"module:{name}", "seq": S, "dtype": "fp32",
                            "torch_gpu_ms": off["min_ms"], "cuda_ops_ms": on["min_ms"],
                            "speedup_vs_torch": off["min_ms"] / on["min_ms"],
                            "n_samples": on["n"]})
    K.available = orig


def bench_full_model(results):
    """完整 VirtuOmni10B 前向（小配置：2 层/hidden 128），开/关定制算子。"""
    from virtu_omni.config import ModelConfig
    from virtu_omni.models.architecture import VirtuOmni10B

    torch.manual_seed(12)
    cfg = ModelConfig(num_layers=2, hidden_dim=128, intermediate_dim=384,
                      num_attention_heads=4, num_kv_heads=2, head_dim=32,
                      vocab_size=1000, max_position_embeddings=128)
    model = VirtuOmni10B(cfg).to("cuda").eval()
    ids = torch.randint(0, 1000, (2, 24), device="cuda")
    orig = K.available
    with torch.no_grad():
        K.available = orig
        on = _time_gpu(lambda: model(ids), repeats=50)
        K.available = lambda: False
        off = _time_gpu(lambda: model(ids), repeats=50)
        K.available = orig
    results.append({"op": "module:model_forward", "seq": 24, "dtype": "fp32",
                    "torch_gpu_ms": off["min_ms"], "cuda_ops_ms": on["min_ms"],
                    "speedup_vs_torch": off["min_ms"] / on["min_ms"],
                    "n_samples": on["n"],
                    "config": "2 layers / hidden 128 / 4 heads / loop-steps default"})


def _run_id(cfg: dict, source_sha: str) -> str:
    blob = json.dumps({"cfg": cfg, "src": source_sha}, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-prefix", default=os.path.join(ROOT, "benchmarks",
                                                         "wm_cuda_kernels_2026-11-08"))
    args = ap.parse_args()

    caps = K.capabilities()
    if not caps.get("available"):
        raise SystemExit(f"cuda_ops unavailable: {caps.get('error')}")
    print("[caps]", json.dumps(caps, ensure_ascii=False))

    results = []
    # 完整模型先跑（冷显存/冷分配器），避免物理批算子的 6GB 显存碎片污染端到端数字
    bench_full_model(results)
    bench_swiglu(results)
    bench_rmsnorm(results)
    bench_rope(results)
    bench_rope2d(results)
    bench_physics(results)
    bench_modules(results)

    cfg = {"batch": B, "hidden": HIDDEN, "heads": HEADS, "head_dim": HEAD_DIM,
           "inter": INTER, "seqs": SEQLENS,
           "timing": {"warmup": 5, "repeats": 20, "clock": "cuda_event"}}
    run_id = _run_id(cfg, caps["source_sha256"])
    payload = {"run_id": run_id, "basis": "measured", "config": cfg,
               "capabilities": caps, "results": results}
    with open(args.out_prefix + ".json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    lines = ["# 定制 CUDA 算子实测（2026-11-08）", "",
             f"- run_id: `{run_id}`（内容指纹：配置+内核源码 sha）",
             f"- 硬件: `{caps['device']}`，驱动 {caps['cuda_driver']}，torch {caps['torch']}",
             f"- 内核编译: {caps['build']['kind']} {caps['build']['bytes']}B @ {caps['build']['arch']}，"
             f"源 sha256 `{caps['source_sha256'][:16]}…`",
             f"- 口径: basis=measured；CUDA Event 计时 warmup=5/repeats=20 取 min",
             "", "## 结果（ms，min）", "",
             "| op | seq/n | dtype | torch | cuda_ops | speedup |", "|---|---|---|---:|---:|---:|"]
    for r in results:
        if "torch_gpu_ms" in r:
            size = r.get("n", r.get("seq"))
            lines.append(f"| {r['op']} | {size} | {r['dtype']} | {r['torch_gpu_ms']:.4f} | "
                         f"{r['cuda_ops_ms']:.4f} | {r['speedup_vs_torch']:.2f}x |")
        elif r.get("arm") == "cuda_ops":
            torch_arm = next(x for x in results if x["op"] == r["op"] and
                             x.get("seq") == r.get("seq") and x["dtype"] == r["dtype"] and
                             x.get("arm") not in (None, "cuda_ops"))
            lines.append(f"| {r['op']} | {r['seq']} | {r['dtype']} | {torch_arm['min_ms']:.4f} "
                         f"({torch_arm['arm']}) | {r['min_ms']:.4f} | "
                         f"{torch_arm['min_ms'] / r['min_ms']:.2f}x |")
    lines += ["", "> 跨臂形状与既有《理论极限》报告同源（B=2, hidden=512, heads=8, "
              "head_dim=64, inter=1536）。未做跨 dtype 精度判据：精度由 "
              "`tests/test_cuda_kernels.py` 对 fp64 参照判定。"]
    with open(args.out_prefix + ".md", "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[ok] {args.out_prefix}.json / .md")
    for r in results:
        if "speedup_vs_torch" in r:
            size = r.get("n", r.get("seq"))
            print(f"  {r['op']:18s} n={size:>8} torch={r['torch_gpu_ms']:.4f}ms "
                  f"cuda={r['cuda_ops_ms']:.4f}ms  {r['speedup_vs_torch']:.2f}x")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
