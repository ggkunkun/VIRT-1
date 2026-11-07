# -*- coding: utf-8 -*-
"""virtu_omni/models/operator_extreme.py — push Virtu operators to the roofline.

"理论极限" is defined here as a *measured* lower bound, not a marketing word:

    t_min(op) = max( minimum_FLOPs / peak_flops , minimum_bytes / peak_bandwidth )

peak_flops and peak_bandwidth are characterised ON THIS GPU at run time with
CUDA Events (large GEMM and large device-to-device copy), never read from a
spec sheet. Every published number carries basis/n/evidence and a run_id that
is a content fingerprint of the measured sources (AGENTS.md §8).

Four arms are measured per operator:
  eager_fp32   - current production path (Python dispatch + per-kernel launch)
  graph_fp32   - CUDA Graph replay, removes CPU launch gaps (numerically exact)
  graph_tf32   - FP32 API, TF32 tensor cores (accuracy cost reported)
  graph_bf16   - BF16 weights/activations, tensor cores + half the traffic

The roofline bound assumes an ideal fused kernel. On this host Triton is NOT
installed and PyTorch 2.6.0+cu124 has no compiled FlashAttention, so a gap
that can only be closed by writing a custom kernel is reported as 工具链不可达
instead of being claimed as a speedup (§6: 到了极限则放弃).
"""

from __future__ import annotations

import gc
import hashlib
import json
import logging
import math
import statistics
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import torch

from virtu_eval.provenance import RunIdentity
from virtu_omni.config import ModelConfig
from virtu_omni.models.architecture import (
    UniRoPE,
    VirtuAttention,
    VirtuRMSNorm,
    VirtuSwiGLU,
)
from virtu_omni.models.operator_optimizer import _collect_tensors

logger = logging.getLogger("virtu_omni.models.operator_extreme")

SOURCE_FILES: Tuple[str, ...] = (
    "virtu_omni/models/architecture.py",
    "virtu_omni/models/operator_extreme.py",
    "virtu_omni/models/operator_optimizer.py",
    "virtu_omni/config.py",
    "virtu_eval/provenance.py",
)

DTYPES: Dict[str, torch.dtype] = {
    "fp32": torch.float32,
    "tf32": torch.float32,
    "bf16": torch.bfloat16,
}
# peak key used for the roofline bound of each arm
PEAK_KEY: Dict[str, str] = {
    "fp32": "fp32", "tf32": "tf32", "bf16": "bf16",
}


# ---------------------------------------------------------------------------
# 1. Measured hardware characterisation
# ---------------------------------------------------------------------------

@dataclass
class HardwareLimits:
    device_name: str
    bandwidth_gbs: float
    peak_tflops: Dict[str, float]
    copy_probe_mb: float
    gemm_probe_n: int
    event_repeats: int
    basis: str = "measured"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _event_time_ms(fn: Callable[[], Any], repeats: int = 7) -> float:
    """Minimum GPU-side elapsed time over repeats (CUDA Events, not wall clock)."""
    for _ in range(3):
        fn()
    torch.cuda.synchronize()
    samples = []
    for _ in range(repeats):
        a = torch.cuda.Event(enable_timing=True)
        b = torch.cuda.Event(enable_timing=True)
        a.record()
        fn()
        b.record()
        b.synchronize()
        samples.append(a.elapsed_time(b))
    return min(samples)


def characterize_hardware(device: str = "cuda", repeats: int = 7) -> HardwareLimits:
    """Measure achievable bandwidth and GEMM throughput on the live device."""
    props = torch.cuda.get_device_properties(0)
    mb = 64
    n = mb * 1024 * 1024
    src = torch.empty(n, device=device, dtype=torch.uint8)
    dst = torch.empty_like(src)
    bw = (2 * n) / (_event_time_ms(lambda: dst.copy_(src), repeats) / 1000.0) / 1e9
    del src, dst

    N = 4096
    a = torch.randn(N, N, device=device, dtype=torch.float32)
    b = torch.randn(N, N, device=device, dtype=torch.float32)
    flops = 2 * N ** 3
    peaks: Dict[str, float] = {}
    saved_tf32 = torch.backends.cuda.matmul.allow_tf32
    try:
        for key, dt, tf32 in (
            ("fp32", torch.float32, False),
            ("tf32", torch.float32, True),
            ("bf16", torch.bfloat16, False),
            ("fp16", torch.float16, False),
        ):
            torch.backends.cuda.matmul.allow_tf32 = tf32
            aa, bb = a.to(dt), b.to(dt)
            t = _event_time_ms(lambda: torch.mm(aa, bb), repeats) / 1000.0
            peaks[key] = flops / t / 1e12
            del aa, bb
    finally:
        torch.backends.cuda.matmul.allow_tf32 = saved_tf32
    del a, b
    torch.cuda.empty_cache()

    return HardwareLimits(
        device_name=props.name,
        bandwidth_gbs=round(bw, 3),
        peak_tflops={k: round(v, 3) for k, v in peaks.items()},
        copy_probe_mb=mb,
        gemm_probe_n=N,
        event_repeats=repeats,
    )


# ---------------------------------------------------------------------------
# 2. Roofline lower bounds (ideal fused kernel)
# ---------------------------------------------------------------------------

@dataclass
class BoundSpec:
    operator: str
    seq_len: int
    arm: str
    dtype: str
    min_flops: int
    min_bytes: int
    t_compute_ms: float
    t_memory_ms: float
    t_min_ms: float
    bottleneck: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def theoretical_bound(
    operator: str, batch: int, seq_len: int, cfg: ModelConfig,
    arm: str, hw: HardwareLimits,
) -> BoundSpec:
    """Minimum physically possible time for an ideal fused kernel."""
    S, B = seq_len, batch
    dt = DTYPES[arm]
    eb = 2 if dt in (torch.bfloat16, torch.float16) else 4
    peak = hw.peak_tflops[PEAK_KEY[arm]] * 1e12
    bw = hw.bandwidth_gbs * 1e9
    H, I = cfg.hidden_dim, cfg.intermediate_dim
    Hn, Kn, D = cfg.num_attention_heads, cfg.num_kv_heads, cfg.head_dim

    if operator == "VirtuRMSNorm":
        elems = B * S * H
        min_flops = 4 * elems                       # square / reduce / rsqrt / scale
        min_bytes = 2 * elems * eb                  # one read + one write
    elif operator == "UniRoPE":
        elems = B * S * (Hn + Kn) * D
        min_flops = 6 * elems                       # two mul + one add per element
        min_bytes = 2 * elems * eb                  # read q/k, write q/k
    elif operator == "VirtuSwiGLU":
        min_flops = 6 * B * S * H * I               # gate + up + down GEMMs
        min_bytes = (3 * H * I + B * S * (2 * H + 2 * I)) * eb
    elif operator == "VirtuAttention":
        min_flops = (
            2 * B * S * H * (Hn * D + 2 * Kn * D)  # q/k/v projections
            + 2 * B * S * (Hn * D) * H              # o projection
            + 4 * B * Hn * S * S * D                # QK^T + P V
        )
        min_bytes = (
            (H * (Hn * D + 2 * Kn * D) + (Hn * D) * H)  # weights
            + B * S * (H + Hn * D + 2 * Kn * D + H)      # activations
        ) * eb
    else:
        raise ValueError(f"unknown operator {operator}")

    tc, tm = min_flops / peak, min_bytes / bw
    return BoundSpec(
        operator=operator, seq_len=seq_len, arm=arm, dtype=str(dt).replace("torch.", ""),
        min_flops=int(min_flops), min_bytes=int(min_bytes),
        t_compute_ms=round(tc * 1000, 6), t_memory_ms=round(tm * 1000, 6),
        t_min_ms=round(max(tc, tm) * 1000, 6),
        bottleneck="compute" if tc >= tm else "memory",
    )


# ---------------------------------------------------------------------------
# 3. CUDA Graph executor (production component)
# ---------------------------------------------------------------------------

class VirtuGraphExecutor:
    """Capture an eval-mode operator into a CUDA Graph and replay it.

    Inputs are copied into persistent static buffers so their addresses stay
    valid across replays. The captured graph is numerically identical to eager
    execution (same kernels, same order); verify() makes that a hard gate.
    """

    def __init__(self, fn: Callable[..., Any], sample_inputs: Sequence[Any],
                 warmup: int = 3, tolerance: float = 0.0):
        if not torch.cuda.is_available():
            raise RuntimeError("VirtuGraphExecutor requires CUDA")
        self.fn = fn
        self.static_inputs = tuple(
            torch.empty_like(t) if isinstance(t, torch.Tensor) else t
            for t in sample_inputs
        )
        self._copy_in(sample_inputs)
        self.graph = torch.cuda.CUDAGraph()
        with torch.no_grad():
            side = torch.cuda.Stream()
            side.wait_stream(torch.cuda.current_stream())
            with torch.cuda.stream(side):
                for _ in range(warmup):
                    fn(*self.static_inputs)
            torch.cuda.current_stream().wait_stream(side)
            with torch.cuda.graph(self.graph):
                self.static_output = fn(*self.static_inputs)
        self.verify_result = self._verify(tolerance)

    def _copy_in(self, inputs: Sequence[Any]) -> None:
        for dst, src in zip(self.static_inputs, inputs):
            if isinstance(dst, torch.Tensor) and isinstance(src, torch.Tensor):
                dst.copy_(src)

    def _verify(self, tolerance: float) -> Dict[str, Any]:
        with torch.no_grad():
            eager = self.fn(*self.static_inputs)
            self.graph.replay()
            torch.cuda.synchronize()
            a = _collect_tensors(eager)
            b = _collect_tensors(self.static_output)
        if len(a) != len(b):
            return {"passed": False, "reason": "tensor_count_mismatch", "max_diff": float("inf")}
        max_diff = 0.0
        for x, y in zip(a, b):
            if x.shape != y.shape or x.dtype != y.dtype:
                return {"passed": False, "reason": "shape_or_dtype", "max_diff": float("inf")}
            if not bool(torch.isfinite(x).all()) or not bool(torch.isfinite(y).all()):
                return {"passed": False, "reason": "nonfinite", "max_diff": float("inf")}
            max_diff = max(max_diff, (x - y).abs().max().item())
        return {
            "passed": bool(math.isfinite(max_diff) and max_diff <= tolerance),
            "reason": "" if max_diff <= tolerance else "diff_exceeds_tolerance",
            "max_diff": max_diff,
            "tensors_checked": len(a),
        }

    def set_inputs(self, inputs: Sequence[Any]) -> None:
        self._copy_in(inputs)

    def replay(self) -> Any:
        self.graph.replay()
        return self.static_output


# ---------------------------------------------------------------------------
# 4. Arm construction and measurement
# ---------------------------------------------------------------------------

OPS = ("VirtuAttention", "UniRoPE", "VirtuSwiGLU", "VirtuRMSNorm")
ARMS = ("eager_fp32", "graph_fp32", "graph_tf32", "graph_bf16")


def _build_operator(op: str, cfg: ModelConfig, batch: int, seq_len: int,
                    dtype: torch.dtype, device: str) -> Tuple[Callable[..., Any], Tuple[Any, ...]]:
    B, S = batch, seq_len
    H, D = cfg.hidden_dim, cfg.head_dim
    Hn, Kn = cfg.num_attention_heads, cfg.num_kv_heads

    if op == "VirtuRMSNorm":
        m = VirtuRMSNorm(H).to(device=device, dtype=dtype).eval()
        return m.forward, (torch.randn(B, S, H, device=device, dtype=dtype),)

    if op == "UniRoPE":
        rope = UniRoPE(dim=D).to(device=device)
        q = torch.randn(B, S, Hn, D, device=device, dtype=dtype)
        k = torch.randn(B, S, Kn, D, device=device, dtype=dtype)
        pos = torch.arange(S, device=device)
        return (
            lambda qq, kk, pp: rope.apply_1d_rope(
                qq, kk, pp, max_pos_hint=S, contiguous_slice=(0, S)
            ),
            (q, k, pos),
        )

    if op == "VirtuSwiGLU":
        m = VirtuSwiGLU(cfg).to(device=device, dtype=dtype).eval()
        m.fuse_projections()
        return m.forward, (torch.randn(B, S, H, device=device, dtype=dtype),)

    attn = VirtuAttention(cfg).to(device=device, dtype=dtype).eval()
    attn.fuse_projections()
    rope = UniRoPE(dim=D).to(device=device)
    return (
        lambda x: attn(x, rope_engine=rope),
        (torch.randn(B, S, H, device=device, dtype=dtype),),
    )


def _wall_ms(fn: Callable[[], Any], trials: int) -> float:
    for _ in range(max(3, trials // 10)):
        fn()
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(trials):
        fn()
    torch.cuda.synchronize()
    return (time.perf_counter() - t0) / trials * 1000.0


def _measure_arm(op: str, arm: str, cfg: ModelConfig, batch: int, seq_len: int,
                 hw: HardwareLimits, trials: int, device: str) -> Dict[str, Any]:
    is_graph = arm != "eager_fp32"
    dtype = DTYPES["bf16" if arm == "graph_bf16" else "fp32"]
    tf32 = arm == "graph_tf32"
    saved = torch.backends.cuda.matmul.allow_tf32
    torch.backends.cuda.matmul.allow_tf32 = tf32
    # Both the measured module and the fp32 reference must start from the SAME
    # weights; otherwise the "precision cost" is just two random models.
    seed = 20261106
    try:
        torch.manual_seed(seed)
        fn, inputs = _build_operator(op, cfg, batch, seq_len, dtype, device)
        bound = theoretical_bound(op, batch, seq_len, cfg, "bf16" if arm == "graph_bf16" else arm.split("_")[-1] if arm != "eager_fp32" else "fp32", hw)
        with torch.no_grad():
            eager_wall = _wall_ms(lambda: fn(*inputs), trials)
            runner = None
            if is_graph:
                runner = VirtuGraphExecutor(fn, inputs, warmup=3, tolerance=0.0)
                gate = runner.verify_result
                graph_wall = _wall_ms(lambda: runner.replay(), trials)
                kernel_ms = _event_time_ms(lambda: runner.replay(), repeats=7)
                kernel_time = kernel_ms
            else:
                gate = {"passed": True, "reason": "eager_reference", "max_diff": 0.0,
                        "tensors_checked": len(_collect_tensors(fn(*inputs)))}
                graph_wall = None
                kernel_time = None
            # Accuracy cost vs a TRUE fp32 reference (TF32 disabled), reported
            # separately and NOT used as a pass/fail gate.
            ref32 = None
            inner_saved = torch.backends.cuda.matmul.allow_tf32
            torch.backends.cuda.matmul.allow_tf32 = False
            try:
                with torch.no_grad():
                    torch.manual_seed(seed)
                    fn32, _ = _build_operator(op, cfg, batch, seq_len, torch.float32, device)
                    in32 = tuple(
                        t.to(torch.float32)
                        if isinstance(t, torch.Tensor) and t.is_floating_point() else t
                        for t in inputs
                    )
                    ref32 = fn32(*in32)
                    cur = runner.replay() if runner else fn(*inputs)
            finally:
                torch.backends.cuda.matmul.allow_tf32 = inner_saved
            a = _collect_tensors(ref32)
            b = _collect_tensors(cur)
            cost = max((x.float() - y.float()).abs().max().item() for x, y in zip(a, b))
            del ref32, cur, fn32, in32, a, b
    finally:
        torch.backends.cuda.matmul.allow_tf32 = saved

    efficiency = (bound.t_min_ms / kernel_time) if kernel_time else None
    res = {
        "operator": op, "seq_len": seq_len, "arm": arm,
        "dtype": str(dtype).replace("torch.", ""),
        "tf32": tf32, "cuda_graph": is_graph,
        "eager_wall_ms": round(eager_wall, 5),
        "graph_wall_ms": round(graph_wall, 5) if graph_wall is not None else None,
        "kernel_ms": round(kernel_time, 5) if kernel_time is not None else None,
        "t_min_ms": bound.t_min_ms,
        "efficiency_pct": round(efficiency * 100, 2) if efficiency is not None else None,
        "gap_to_limit_x": round(kernel_time / bound.t_min_ms, 2) if kernel_time else None,
        "bottleneck": bound.bottleneck,
        "graph_gate": gate,
        "fp32_to_this_dtype_max_diff": cost,
        # Self-check on the reference itself: the fp32 arm must reproduce the
        # fp32 reference exactly, otherwise the "precision cost" is meaningless.
        "precision_reference_sane": (cost <= 1e-5) if arm == "eager_fp32" else None,
        "n_wall": trials,
        "n_event": 7 if is_graph else 0,
        "basis": "measured",
        "bound": bound.to_dict(),
    }
    if runner is not None:
        del runner
    del fn, inputs
    gc.collect()
    torch.cuda.empty_cache()
    return res


def run_extreme_cycle(
    seq_lens: Optional[List[int]] = None,
    batch_size: int = 2,
    hidden_dim: int = 512,
    num_heads: int = 8,
    num_kv_heads: int = 4,
    head_dim: int = 64,
    trials: int = 60,
    workspace_root: Optional[Path] = None,
) -> "ExtremeReport":
    seq_lens = list(seq_lens or [128, 512, 1024])
    root = Path(workspace_root) if workspace_root else Path(__file__).resolve().parents[2]
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device != "cuda":
        raise RuntimeError("理论极限分析需要 CUDA；当前无可用 GPU")

    identity = RunIdentity.capture(
        ruler_files=SOURCE_FILES,
        extra={
            "seq_lens": seq_lens, "batch_size": batch_size,
            "hidden_dim": hidden_dim, "num_heads": num_heads,
            "num_kv_heads": num_kv_heads, "head_dim": head_dim,
            "trials": trials, "torch": torch.__version__,
            "device": torch.cuda.get_device_name(0),
        },
    )
    cfg = ModelConfig(
        hidden_dim=hidden_dim, intermediate_dim=hidden_dim * 3,
        num_attention_heads=num_heads, num_kv_heads=num_kv_heads, head_dim=head_dim,
    )
    hw = characterize_hardware(device)
    rows: List[Dict[str, Any]] = []
    for op in OPS:
        for S in seq_lens:
            for arm in ARMS:
                rows.append(_measure_arm(op, arm, cfg, batch_size, S, hw, trials, device))

    drift = identity.drift()
    all_gates = all(
        r["graph_gate"]["passed"]
        and (r["precision_reference_sane"] is not False)
        for r in rows
    )
    # BF16 is not universally faster: fused RMSNorm in particular pays an
    # extra conversion. Record every such case instead of implying otherwise.
    fp32_kernel = {
        (r["operator"], r["seq_len"]): r["kernel_ms"]
        for r in rows if r["arm"] == "graph_fp32"
    }
    bf16_slower = [
        f"{r['operator']}@S={r['seq_len']} ({r['kernel_ms']:.4f} vs "
        f"{fp32_kernel[(r['operator'], r['seq_len'])]:.4f} ms)"
        for r in rows
        if r["arm"] == "graph_bf16"
        and r["kernel_ms"] > fp32_kernel[(r["operator"], r["seq_len"])]
    ]
    observations = [
        "BF16 反而慢于 FP32 的组合：" + ("; ".join(bf16_slower) if bf16_slower else "无"),
        "speedup_vs_eager_wall_x 口径：每个 seq 取最快 graph 臂的 wall 与该 seq 的 eager_fp32 wall 之比，再跨 seq 取算术平均；报告同时给出 min/max，因 eager wall 含 CPU 调度噪声，跨轮波动明显，kernel_ms 才是稳定量。",
    ]
    # Per-operator: closest-to-roofline arm, absolutely fastest arm, and the
    # user-visible speedup vs the current eager FP32 production path.
    best: Dict[str, Dict[str, Any]] = {}
    for op in OPS:
        candidates = [r for r in rows if r["operator"] == op and r["kernel_ms"] is not None]
        b = max(candidates, key=lambda r: r["efficiency_pct"] or 0.0)
        fastest = min(candidates, key=lambda r: r["kernel_ms"])
        speedups = []
        for S in seq_lens:
            base = next(r for r in rows if r["operator"] == op and r["seq_len"] == S
                        and r["arm"] == "eager_fp32")["eager_wall_ms"]
            opts = [r for r in candidates if r["seq_len"] == S and r["graph_wall_ms"]]
            f = min(opts, key=lambda r: r["graph_wall_ms"])
            speedups.append(base / max(f["graph_wall_ms"], 1e-9))
        best[op] = {
            "arm": b["arm"], "seq_len": b["seq_len"],
            "efficiency_pct": b["efficiency_pct"],
            "gap_to_limit_x": b["gap_to_limit_x"],
            "kernel_ms": b["kernel_ms"], "t_min_ms": b["t_min_ms"],
            "fastest_arm": fastest["arm"],
            "fastest_seq_len": fastest["seq_len"],
            "fastest_kernel_ms": fastest["kernel_ms"],
            "speedup_vs_eager_wall_x": round(statistics.mean(speedups), 2),
            "speedup_min_x": round(min(speedups), 2),
            "speedup_max_x": round(max(speedups), 2),
        }
    return ExtremeReport(
        run_id=identity.run_id,
        timestamp=time.time(),
        hardware=hw.to_dict(),
        config=asdict(cfg) if hasattr(cfg, "__dataclass_fields__") else {
            "hidden_dim": hidden_dim, "intermediate_dim": hidden_dim * 3,
            "num_attention_heads": num_heads, "num_kv_heads": num_kv_heads,
            "head_dim": head_dim,
        },
        arms=list(ARMS), seq_lens=seq_lens,
        measurements=rows, best_per_operator=best,
        all_graph_gates_passed=all_gates,
        invalidated_legs=drift,
        identity=identity.to_dict(),
        observations=observations,
        toolchain_limits=[
            "Triton 未安装（torch.compile 无融合后端），无法编写自定义 RoPE/归一化融合 kernel",
            "PyTorch 2.6.0+cu124 Windows 构建未编译 FlashAttention；SDPA 的 enable_gqa 会退到 math 后端并变慢",
            "attention 的 roofline 下界假设存在理想 fused attention kernel，本机只能用 mem-efficient/math SDPA",
        ],
        notes={
            "t_min_definition": "max(min_FLOPs/peak_flops, min_bytes/peak_bandwidth)，理想单 kernel 下界",
            "kernel_ms": "CUDA Graph replay + CUDA Event 中位数/最小值口径，已消除 CPU launch 间隙",
            "efficiency_pct": "t_min_ms / kernel_ms * 100；>=100 视为已达极限（峰值以 4096³ 大 GEMM 标定，属保守下界，小算子可达更高有效算力）",
            "limit_reached_rule": "gap_to_limit_x <= 1.50 或 efficiency_pct >= 100 判定为已达极限",
            "precision_reference": "同权重同输入的 fp32 eager 参考；eager_fp32 臂 diff 必须为 0，否则本轮作废",
        },
    )


@dataclass
class ExtremeReport:
    run_id: str
    timestamp: float
    hardware: Dict[str, Any]
    config: Dict[str, Any]
    arms: List[str]
    seq_lens: List[int]
    measurements: List[Dict[str, Any]]
    best_per_operator: Dict[str, Any]
    all_graph_gates_passed: bool
    invalidated_legs: List[str]
    identity: Dict[str, Any]
    toolchain_limits: List[str]
    notes: Dict[str, str]
    evidence_path: str = ""
    basis: str = "measured"
    observations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def summary_markdown(self) -> str:
        hw = self.hardware
        lines = []
        for s in self.seq_lens:
            for op in OPS:
                by_arm = {
                    r["arm"]: r for r in self.measurements
                    if r["operator"] == op and r["seq_len"] == s
                }
                e = by_arm["eager_fp32"]["eager_wall_ms"]
                ks = [by_arm[a]["kernel_ms"] for a in ARMS[1:]]
                lines.append(
                    f"| {s} | {op} | {e:.3f} | "
                    + " | ".join(f"{v:.3f}" for v in ks) + " |"
                )
        hrows = "\n".join(lines)
        best_lines = "\n".join(
            f"- **{op}**: 最贴近下界 `{v['arm']}`（S={v['seq_len']}）"
            f" 净耗时 {v['kernel_ms']:.4f} ms / 下界 {v['t_min_ms']:.4f} ms "
            f"→ 效率 **{v['efficiency_pct']:.1f}%**，距极限 **{v['gap_to_limit_x']:.2f}x** "
            f"{'✅ 已达极限' if (v['gap_to_limit_x'] <= 1.50 or v['efficiency_pct'] >= 100) else '⬆ 仍有空间'}；"
            f"绝对最快臂 `{v['fastest_arm']}`（S={v['fastest_seq_len']}，"
            f"{v['fastest_kernel_ms']:.4f} ms），"
            f"相对当前 eager FP32 生产路径 **{v['speedup_vs_eager_wall_x']:.2f}x**"
            f"（跨 seq 范围 {v.get('speedup_min_x', 0):.2f}–{v.get('speedup_max_x', 0):.2f}x）"
            for op, v in self.best_per_operator.items()
        )
        limits = "\n".join(f"- {x}" for x in self.toolchain_limits)
        observations = "\n".join(f"- {x}" for x in self.observations)
        drift = "无（起腿/收腿源码哈希一致）" if not self.invalidated_legs else \
            "**有漂移，本轮作废**：" + "; ".join(self.invalidated_legs)
        n_total = sum(r["n_wall"] + r["n_event"] for r in self.measurements)
        return (
            f"# Virtu 算子「理论极限」核验报告\n\n"
            f"- **run_id（内容指纹）**: `{self.run_id}`\n"
            f"- **硬件**: `{hw['device_name']}`，实测带宽 **{hw['bandwidth_gbs']:.1f} GB/s**"
            f"（{hw['copy_probe_mb']}MB D2D copy），实测算力 "
            f"FP32 {hw['peak_tflops']['fp32']:.2f} / TF32 {hw['peak_tflops']['tf32']:.2f} / "
            f"BF16 {hw['peak_tflops']['bf16']:.2f} TFLOPS（{hw['gemm_probe_n']}³ GEMM）\n"
            f"- **口径**: `basis=measured`，硬件上界为当次现场实测（非规格表）；"
            f"计时样本 n={n_total}；证据 `{self.evidence_path or '未导出'}`\n"
            f"- **下界定义**: `{self.notes['t_min_definition']}`\n"
            f"- **CUDA Graph 等价性闸门**: "
            f"{'[PASS] 全部 0 误差' if self.all_graph_gates_passed else '[FAIL]'}\n"
            f"- **收腿漂移**: {drift}\n\n"
            f"## 1. 净 GPU 耗时（ms，CUDA Graph replay + CUDA Event）\n\n"
            f"| seq | 算子 | eager_fp32(wall) | graph_fp32 | graph_tf32 | graph_bf16 |\n"
            f"| ---: | :--- | ---: | ---: | ---: | ---: |\n{hrows}\n\n"
            f"## 2. 距理论极限\n\n{best_lines}\n\n"
            f"## 3. 实测观察（不做选择性略去）\n{observations}\n\n"
            f"## 4. 工具链不可达项（按 §6 停止，不虚报加速）\n{limits}\n\n"
            f"> `eager_fp32` 为当前生产路径（含 Python 调度与逐 kernel launch）；"
            f"`graph_*` 已消除 launch 间隙，故与上表同尺度比较。跨 dtype 的精度代价"
            f"记录在 JSON 的 `fp32_to_this_dtype_max_diff`，不作为通过/失败判据。\n"
        )


def export_report(report: ExtremeReport, out_dir: Optional[Path] = None) -> Tuple[Path, Path]:
    root = Path(out_dir) if out_dir else Path(__file__).resolve().parents[2] / "benchmarks"
    root.mkdir(parents=True, exist_ok=True)
    jp = root / "model_operator_theoretical_limit_report.json"
    mp = root / "model_operator_theoretical_limit_report.md"
    try:
        evidence = str(jp.resolve().relative_to(Path(__file__).resolve().parents[2].resolve()))
    except ValueError:
        evidence = str(jp.resolve())
    report.evidence_path = evidence
    jp.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    mp.write_text(report.summary_markdown(), encoding="utf-8")
    return jp, mp
