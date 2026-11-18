# -*- coding: utf-8 -*-
"""virtu_omni/models/operator_optimizer.py — Operator optimization + attributable measurement.

Measurement Constitution (AGENTS.md §8) compliance notes
---------------------------------------------------------
The previous implementation had three defects that made its report unusable:

1. ``passed = diff <= tolerance or math.isnan(diff) is False`` is a tautology
   for every finite diff, so the numerical-equivalence gate could never fail.
   It also compared only ``y[0]`` of tuple outputs (the RoPE k branch was never
   checked). Both are fixed: all output tensors are checked, non-finite outputs
   are an explicit FAIL, and the gate is ``diff <= tolerance and finite``.
2. ``run_id = f"opt_ops_{int(time.time())}"`` is a wall-clock label, not a
   content fingerprint. Two different kernels could share a run id. run_id now
   comes from ``RunIdentity`` over the hashes of the measured sources, config,
   runtime and device; ``drift()`` at the end invalidates the leg if any source
   moved mid-run.
3. The report printed a "综合端到端加速比" that was actually the sum of four
   micro-benchmarks, and a "峰值显存降幅" built only from the attention rows.
   Every number now carries ``basis``, ``n`` and ``evidence_path``; CPU memory
   figures are reported as 未测 rather than 0.0%; regressions are listed instead
   of being folded into an average.

Timing uses perf_counter, CUDA synchronize, no_grad and interleaved AB/BA
repeats with a median estimator, so a single thermal or scheduling spike does
not decide a speedup claim.
"""

from __future__ import annotations

import gc
import json
import logging
import math
import statistics
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import torch
import torch.nn.functional as F

from virtu_eval.provenance import RunIdentity
from virtu_omni.config import ModelConfig
from virtu_omni.models.architecture import (
    LoopTransformerBlock,
    UniRoPE,
    VirtuAttention,
    VirtuOmni10B,
    VirtuRMSNorm,
    VirtuSwiGLU,
)

logger = logging.getLogger("virtu_omni.models.operator_optimizer")

# Bytes that are allowed to decide the numbers in this report.
SOURCE_FILES: Tuple[str, ...] = (
    "virtu_omni/models/architecture.py",
    "virtu_omni/models/operator_optimizer.py",
    "virtu_omni/config.py",
    "virtu_eval/provenance.py",
)


@dataclass
class OperatorMetric:
    """Benchmark metrics for a single operator execution."""
    operator_name: str
    stage: str                  # "baseline" or "optimized"
    batch_size: int
    seq_len: int
    hidden_dim: int
    device: str
    dtype: str
    latency_ms: float
    throughput_tokens_per_sec: float
    peak_memory_mb: float
    max_numerical_diff: float = 0.0
    passed_precision: bool = True
    basis: str = "measured"
    n: int = 0
    evidence_path: str = ""


@dataclass
class OperatorOptimizationReport:
    """Full self-optimization provenance report."""
    run_id: str
    timestamp: float
    device_name: str
    pytorch_version: str
    cuda_available: bool
    flash_attention_available: bool
    summary: Dict[str, Any]
    diagnostics: List[Dict[str, Any]]
    operator_benchmarks: List[Dict[str, Any]]
    overall_speedup: float
    memory_reduction_pct: float
    all_invariants_passed: bool
    identity: Dict[str, Any] = field(default_factory=dict)
    evidence_path: str = ""
    invalidated_legs: List[str] = field(default_factory=list)
    regressions: List[str] = field(default_factory=list)
    measurement_notes: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def summary_markdown(self) -> str:
        rows = []
        for b in self.operator_benchmarks:
            gate = "PASS" if b["precision_pass"] else f"FAIL({b.get('failure_reason', 'diff')})"
            mem_cell = (
                f"{b['memory_reduction_pct']:+.1f}%"
                if b.get("memory_basis") == "measured" else "未测"
            )
            rows.append(
                f"| `{b['operator']}` | {b['seq_len']} | {b['baseline_ms']:.3f} | "
                f"{b['optimized_ms']:.3f} | {b['speedup']:.2f}x | "
                f"{mem_cell} | `{b['max_diff']:.2e}` | {gate} | "
                f"{b['n']} |"
            )
        table = "\n".join(rows)
        diag_lines = "\n".join(
            f"- **{d['operator']}**: {d['diagnosis']} -> *{d['action']}* "
            f"(`basis={d.get('basis', 'inferred')}`)"
            for d in self.diagnostics
        )
        hashes = "\n".join(
            f"  - `{rel}` = `{digest[:16]}`"
            for rel, digest in sorted(self.identity.get("ruler", {}).items())
        ) or "  - (无)"
        drift = self.invalidated_legs or []
        drift_text = (
            "无（起腿与收腿的源码哈希一致）"
            if not drift
            else "**有漂移，本轮测量作废**：" + "; ".join(drift)
        )
        regressions = (
            "无" if not self.regressions else "; ".join(f"`{r}`" for r in self.regressions)
        )
        gate_verdict = "[PASS] 全部等价性闸门通过" if self.all_invariants_passed else "[FAIL] 存在未通过项"
        basis = self.measurement_notes.get("basis", "measured")
        n_total = self.summary.get("total_timing_samples", "未测")
        evidence = self.evidence_path or "（尚未导出）"
        mem_note = self.measurement_notes.get("memory", "未测")

        return (
            f"# Virtu 模型算子优化与核验报告（可归因版）\n\n"
            f"- **run_id（内容指纹）**: `{self.run_id}`\n"
            f"- **硬件 / 引擎**: `{self.device_name}` / PyTorch `{self.pytorch_version}`"
            f"（CUDA={self.cuda_available}, SDPA 接口可用={self.flash_attention_available}）\n"
            f"- **口径**: 所有耗时与显存数字 `basis={basis}`，来自本机实际计时；"
            f"计时样本总量 `n={n_total}`；证据文件 `{evidence}`\n"
            f"- **瓶颈诊断**: 以下为静态源码审查结论（`basis=inferred`），**非实测**\n\n"
            f"## 0. 归因与漂移\n\n"
            f"被测字节（sha256 前缀）:\n{hashes}\n\n"
            f"收腿漂移: {drift_text}\n\n"
            f"## 1. 算子瓶颈诊断（静态推断）\n{diag_lines}\n\n"
            f"## 2. 配对实测结果\n\n"
            f"计时方法：`{self.measurement_notes.get('timing', '未声明')}`；"
            f"等价性闸门：`{self.measurement_notes.get('equivalence_gate', '未声明')}`\n\n"
            f"| 算子 | seq | 基线 ms | 优化 ms | 加速比 | 显存降幅 | max_abs_diff | 闸门 | n |\n"
            f"| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :---: | ---: |\n"
            f"{table}\n\n"
            f"- **四算子微基准合计耗时比（非整模型端到端）**: **{self.overall_speedup:.2f}x**\n"
            f"- **峰值显存降幅**: **{self.memory_reduction_pct:.1f}%** — {mem_note}\n"
            f"- **数值等价性核验**: `{gate_verdict}`\n"
            f"- **退化算子（speedup < 1.00x，不做平均掩盖）**: {regressions}\n\n"
            f"> 说明：`overall_speedup` = 本表所有配对的 `基线 ms 之和 / 优化 ms 之和`，"
            f"仅代表这四个微基准，不代表 Ollama/GGUF 部署模型的端到端生成速度。"
            f"显存列负值表示优化后占用增加，未做截断。\n"
        )


def _collect_tensors(output: Any) -> List[torch.Tensor]:
    """Flatten any supported operator output into an ordered tensor list."""
    if isinstance(output, torch.Tensor):
        return [output]
    if isinstance(output, (tuple, list)):
        out: List[torch.Tensor] = []
        for item in output:
            out.extend(_collect_tensors(item))
        return out
    if isinstance(output, dict):
        out = []
        for key in sorted(output):
            out.extend(_collect_tensors(output[key]))
        return out
    raise TypeError(f"Unsupported operator output type: {type(output)!r}")


class VirtuOperatorOptimizer:
    """Agentic engine for operator optimization and attributable verification."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = Path(workspace_root) if workspace_root else Path(__file__).resolve().parents[2]
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"
        self.sdpa_available = hasattr(F, "scaled_dot_product_attention")

    # =========================================================================
    # Step 1: Diagnostics (static source review, basis=inferred)
    # =========================================================================

    def diagnose_bottlenecks(self) -> List[Dict[str, Any]]:
        diagnostics = [
            {
                "operator": "VirtuAttention",
                "bottleneck_type": "Quadratic Memory & Compute Churn (O(N^2))",
                "diagnosis": "显式 torch.matmul(q, k.T) + softmax 会分配 BxHxSxS 稠密矩阵；原 GQA 路径还用 expand().reshape() 实体复制 KV 两次。",
                "action": "单次融合 QKV GEMM + SDPA 融合注意力内核；实测本运行时 enable_gqa=True 会退到 math 后端（2.4x 退化），故保留实体展开 KV 的 SDPA 路径。",
                "basis": "inferred",
            },
            {
                "operator": "UniRoPE",
                "bottleneck_type": "Redundant Trigonometric Recomputation + Host Sync",
                "diagnosis": "原实现每次 forward 都按 max_seq_len(8192) 建表，并调用 positions.max().item() 造成设备到主机同步；2D 视觉网格三角表完全未缓存。",
                "action": "按需几何扩容缓存 + max_pos_hint 消除同步 + 连续位置零拷贝切片替代 gather；2D 网格 cos/sin 表按 (grid, device, dtype) 缓存。",
                "basis": "inferred",
            },
            {
                "operator": "VirtuSwiGLU",
                "bottleneck_type": "Two Independent GEMMs per Feed-Forward",
                "diagnosis": "gate_proj 与 up_proj 是两次独立 GEMM；旧 mul_ 优化只是省掉一个乘积中间张量，未减少 kernel 启动。",
                "action": "推理态 fuse_projections() 将两路权重拼成单次 GEMM 再 chunk；权重为派生 buffer，参数量/梯度契约不变，训练态自动走原路径。",
                "basis": "inferred",
            },
            {
                "operator": "VirtuRMSNorm",
                "bottleneck_type": "Multi-Kernel Dispatched Layer Normalization",
                "diagnosis": "旧 forward 只是把 _forward_unopt 内联，仍是 pow->mean->rsqrt->mul->cast->mul 六次 kernel 启动。",
                "action": "CUDA 上调 F.rms_norm 单次融合内核（CPU/混合精度回退原累加顺序）。",
                "basis": "inferred",
            },
        ]
        return diagnostics

    # =========================================================================
    # Step 2: Strict equivalence gate and paired measurement
    # =========================================================================

    def check_equivalence(
        self, baseline_output: Any, optimized_output: Any, tolerance: float
    ) -> Dict[str, Any]:
        """Fail-closed numerical gate over EVERY output tensor.

        A non-finite value on either side, a shape/dtype/count mismatch, or a
        max absolute difference above tolerance returns precision_pass=False.
        """
        try:
            a = _collect_tensors(baseline_output)
            b = _collect_tensors(optimized_output)
        except TypeError as exc:
            return {
                "max_diff": float("inf"), "precision_pass": False,
                "equivalence_checks": 0, "failure_reason": f"unsupported_output:{exc}",
            }
        if len(a) != len(b) or not a:
            return {
                "max_diff": float("inf"), "precision_pass": False,
                "equivalence_checks": min(len(a), len(b)),
                "failure_reason": "tensor_count_mismatch",
            }
        max_diff = 0.0
        for ta, tb in zip(a, b):
            if ta.shape != tb.shape:
                return {
                    "max_diff": float("inf"), "precision_pass": False,
                    "equivalence_checks": len(a), "failure_reason": "shape_mismatch",
                }
            if ta.dtype != tb.dtype:
                return {
                    "max_diff": float("inf"), "precision_pass": False,
                    "equivalence_checks": len(a), "failure_reason": "dtype_mismatch",
                }
            if not bool(torch.isfinite(ta).all()) or not bool(torch.isfinite(tb).all()):
                return {
                    "max_diff": float("inf"), "precision_pass": False,
                    "equivalence_checks": len(a), "failure_reason": "nonfinite_output",
                }
            diff = (ta.detach() - tb.detach()).abs().max().item()
            if not math.isfinite(diff):
                return {
                    "max_diff": float("inf"), "precision_pass": False,
                    "equivalence_checks": len(a), "failure_reason": "nonfinite_diff",
                }
            max_diff = max(max_diff, diff)
        return {
            "max_diff": max_diff,
            "precision_pass": bool(max_diff <= tolerance),
            "equivalence_checks": len(a),
            "failure_reason": "" if max_diff <= tolerance else "diff_exceeds_tolerance",
        }

    def _timed(self, fn, sample_inputs: Sequence[Any], num_trials: int) -> float:
        t0 = time.perf_counter()
        for _ in range(num_trials):
            fn(*sample_inputs)          # deliberately discard: no live output tensors
        if self.device == "cuda":
            torch.cuda.synchronize()
        return (time.perf_counter() - t0) / num_trials * 1000.0

    def _peak_memory_mb(self, fn, sample_inputs: Sequence[Any]) -> Optional[float]:
        """Peak *additional* allocation of one call, not the absolute watermark.

        reset_peak_memory_stats() seeds the watermark at the already-live
        tensors, so the raw max_memory_allocated() is contaminated by every
        surviving input/parameter from earlier legs. Subtracting the baseline
        makes two operators (and two sequence lengths) comparable.
        """
        if self.device != "cuda":
            return None                # 未测, not 0.0
        torch.cuda.synchronize()
        before = torch.cuda.memory_allocated()
        torch.cuda.reset_peak_memory_stats()
        fn(*sample_inputs)
        torch.cuda.synchronize()
        return max(0.0, (torch.cuda.max_memory_allocated() - before) / (1024 * 1024))

    def benchmark_operator_pair(
        self,
        name: str,
        baseline_fn,
        optimized_fn,
        sample_inputs: Tuple[Any, ...],
        num_warmup: int = 15,
        num_trials: int = 50,
        tolerance: float = 1e-4,
        repeats: int = 3,
    ) -> Dict[str, Any]:
        """Paired A/B measurement with a fail-closed equivalence gate."""
        repeats = max(1, int(repeats))
        num_trials = max(1, int(num_trials))
        with torch.no_grad():
            for _ in range(max(0, num_warmup)):
                baseline_fn(*sample_inputs)
                optimized_fn(*sample_inputs)
            if self.device == "cuda":
                torch.cuda.synchronize()

            y_base = baseline_fn(*sample_inputs)
            y_opt = optimized_fn(*sample_inputs)
            equivalence = self.check_equivalence(y_base, y_opt, tolerance)
            del y_base, y_opt

            samples: Dict[str, List[float]] = {"baseline": [], "optimized": []}
            for r in range(repeats):
                order = (("baseline", baseline_fn), ("optimized", optimized_fn))
                if r % 2:
                    order = tuple(reversed(order))
                for tag, fn in order:
                    samples[tag].append(self._timed(fn, sample_inputs, num_trials))

            mem_base = self._peak_memory_mb(baseline_fn, sample_inputs)
            mem_opt = self._peak_memory_mb(optimized_fn, sample_inputs)

        b_ms = statistics.median(samples["baseline"])
        o_ms = statistics.median(samples["optimized"])
        speedup = b_ms / max(o_ms, 1e-9)
        if mem_base is None or mem_opt is None:
            mem_reduction = 0.0
            mem_basis = "unmeasured"
        else:
            # Keep the sign: a memory increase must not be hidden as "0.0%".
            mem_reduction = (mem_base - mem_opt) / max(mem_base, 1.0) * 100.0
            mem_basis = "measured"

        return {
            "operator": name,
            "baseline_ms": round(b_ms, 4),
            "optimized_ms": round(o_ms, 4),
            "speedup": round(speedup, 4),
            "baseline_spread_ms": round(max(samples["baseline"]) - min(samples["baseline"]), 4),
            "optimized_spread_ms": round(max(samples["optimized"]) - min(samples["optimized"]), 4),
            "baseline_mem_mb": round(mem_base, 2) if mem_base is not None else None,
            "optimized_mem_mb": round(mem_opt, 2) if mem_opt is not None else None,
            "memory_reduction_pct": round(mem_reduction, 2),
            "memory_basis": mem_basis,
            "max_diff": equivalence["max_diff"],
            "precision_pass": equivalence["precision_pass"],
            "equivalence_checks": equivalence["equivalence_checks"],
            "failure_reason": equivalence["failure_reason"],
            "tolerance": tolerance,
            "n": repeats * num_trials,
            "repeats": repeats,
            "trials_per_repeat": num_trials,
            "basis": "measured",
            "evidence_path": "",
        }

    # =========================================================================
    # Step 3: Full cycle with content-addressed identity and drift check
    # =========================================================================

    def run_full_optimization_cycle(
        self,
        batch_size: int = 2,
        seq_lens: Optional[List[int]] = None,
        hidden_dim: int = 512,
        num_heads: int = 8,
        num_kv_heads: int = 4,
        head_dim: int = 64,
        num_warmup: int = 10,
        num_trials: int = 30,
        repeats: int = 3,
    ) -> OperatorOptimizationReport:
        seq_lens = list(seq_lens or [128, 512, 1024])
        diagnostics = self.diagnose_bottlenecks()
        benchmarks: List[Dict[str, Any]] = []

        identity = RunIdentity.capture(
            ruler_files=SOURCE_FILES,
            extra={
                "batch_size": batch_size,
                "seq_lens": seq_lens,
                "hidden_dim": hidden_dim,
                "num_heads": num_heads,
                "num_kv_heads": num_kv_heads,
                "head_dim": head_dim,
                "num_warmup": num_warmup,
                "num_trials": num_trials,
                "repeats": repeats,
                "device": self.device_name,
                "torch": torch.__version__,
            },
        )

        cfg = ModelConfig(
            hidden_dim=hidden_dim,
            intermediate_dim=hidden_dim * 3,
            num_attention_heads=num_heads,
            num_kv_heads=num_kv_heads,
            head_dim=head_dim,
        )

        total_base = 0.0
        total_opt = 0.0
        mem_pairs: List[Tuple[float, float]] = []
        regressions: List[str] = []
        all_passed = True

        for s_len in seq_lens:
            x = torch.randn(batch_size, s_len, hidden_dim, device=self.device)

            # 1. Attention: manual quadratic vs fused-QKV SDPA with materialised GQA
            attn = VirtuAttention(cfg).to(device=self.device, dtype=torch.float32).eval()
            rope = UniRoPE(dim=head_dim).to(device=self.device)
            attn.fuse_projections()   # optimized arm only; _forward_manual stays unfused

            def manual_forward(x_in):
                return attn._forward_manual(x_in, rope_engine=rope)

            def fast_forward(x_in):
                return attn.forward(x_in, rope_engine=rope)

            res_attn = self.benchmark_operator_pair(
                "VirtuAttention (fused QKV + SDPA)", manual_forward, fast_forward, (x,),
                num_warmup=num_warmup, num_trials=num_trials, repeats=repeats, tolerance=2e-4,
            )

            # 2. UniRoPE: recompute vs on-demand cache (both q and k are gated)
            q = torch.randn(batch_size, s_len, num_heads, head_dim, device=self.device)
            k = torch.randn(batch_size, s_len, num_kv_heads, head_dim, device=self.device)
            pos = torch.arange(s_len, device=self.device)

            def rope_base(q_in, k_in, p_in):
                return rope._apply_1d_rope_unopt(q_in, k_in, p_in)

            def rope_opt(q_in, k_in, p_in):
                return rope.apply_1d_rope(
                    q_in, k_in, p_in,
                    max_pos_hint=s_len,
                    contiguous_slice=(0, s_len),
                )

            # 3. SwiGLU: two GEMMs vs fused single GEMM (eval only)
            mlp = VirtuSwiGLU(cfg).to(device=self.device).eval()

            def swiglu_base(x_in):
                return mlp._forward_unopt(x_in)

            mlp.fuse_projections()

            def swiglu_opt(x_in):
                return mlp.forward(x_in)

            # 4. RMSNorm: 6 kernels vs fused F.rms_norm
            norm = VirtuRMSNorm(hidden_dim).to(device=self.device).eval()

            def norm_base(x_in):
                return norm._forward_unopt(x_in)

            def norm_opt(x_in):
                return norm.forward(x_in)

            specs = [
                (res_attn, None, None, None, None),
                (None, "UniRoPE (1D cached)", rope_base, rope_opt, (q, k, pos)),
                (None, "VirtuSwiGLU (fused gate/up GEMM)", swiglu_base, swiglu_opt, (x,)),
                (None, "VirtuRMSNorm (fused kernel)", norm_base, norm_opt, (x,)),
            ]
            # 容差按算子实际数值路径定，不是一律 1e-5：
            # - attention: SDPA 与手写实现分块不同 → 2e-4
            # - UniRoPE / RMSNorm: 逐元素运算，无累加重排 → 1e-5
            # - SwiGLU: 融合把 gate/up 两次 GEMM 合成一次，cuBLAS 的 tile 划分与
            #   累加顺序随之改变；同一数学结果在不同算法选择下实测 max_abs 可达
            #   3e-5（本机 CUDA 实测 2.94e-5）。1e-5 会把合法快速路径判红，
            #   而 TF32 级破坏（~1e-3）仍会被 1e-4 拦住。
            tolerances = [2e-4, 1e-5, 1e-4, 1e-5]
            for idx, (prepared, op_name, base_fn, opt_fn, args) in enumerate(specs):
                if prepared is None:
                    prepared = self.benchmark_operator_pair(
                        op_name, base_fn, opt_fn, args,
                        num_warmup=num_warmup, num_trials=num_trials,
                        repeats=repeats, tolerance=tolerances[idx],
                    )
                prepared["seq_len"] = s_len
                benchmarks.append(prepared)
                if not prepared["precision_pass"]:
                    all_passed = False
                if prepared["speedup"] < 1.0:
                    regressions.append(f"{prepared['operator']}@{s_len}={prepared['speedup']:.2f}x")
                total_base += prepared["baseline_ms"]
                total_opt += prepared["optimized_ms"]
                if prepared["baseline_mem_mb"] is not None:
                    mem_pairs.append((prepared["baseline_mem_mb"], prepared["optimized_mem_mb"] or 0.0))

            # Closures keep the modules alive across sequence lengths; drop them
            # explicitly so the memory watermark of the next leg is not polluted.
            del (manual_forward, fast_forward, rope_base, rope_opt,
                 swiglu_base, swiglu_opt, norm_base, norm_opt,
                 specs, tolerances, res_attn, prepared)
            del attn, rope, mlp, norm, x, q, k, pos
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        drift = identity.drift()
        if drift:
            all_passed = False           # 该腿作废，不得改称"某标签的结果"

        total_mem_base = sum(a for a, _ in mem_pairs)
        total_mem_opt = sum(b for _, b in mem_pairs)
        mem_reduction = (
            (total_mem_base - total_mem_opt) / max(total_mem_base, 1.0) * 100.0
            if mem_pairs else 0.0
        )
        overall_speedup = total_base / max(total_opt, 1e-9)
        n_total = sum(b["n"] for b in benchmarks)

        report = OperatorOptimizationReport(
            run_id=identity.run_id,
            timestamp=time.time(),
            device_name=self.device_name,
            pytorch_version=torch.__version__,
            cuda_available=torch.cuda.is_available(),
            flash_attention_available=self.sdpa_available,
            summary={
                "overall_speedup": round(overall_speedup, 4),
                "memory_reduction_pct": round(mem_reduction, 2),
                "total_operators_optimized": 4,
                "benchmarked_sequence_lengths": seq_lens,
                "invariants_verified": all_passed,
                "total_timing_samples": n_total,
                "regression_count": len(regressions),
                "basis": "measured",
            },
            diagnostics=diagnostics,
            operator_benchmarks=benchmarks,
            overall_speedup=round(overall_speedup, 4),
            memory_reduction_pct=round(mem_reduction, 2),
            all_invariants_passed=all_passed,
            identity=identity.to_dict(),
            invalidated_legs=drift,
            regressions=regressions,
            measurement_notes={
                "basis": "measured",
                "timing": "perf_counter + CUDA synchronize + no_grad + interleaved AB/BA repeats, median of per-repeat means",
                "equivalence_gate": "all output tensors, finite check, shape/dtype/count match, max_abs_diff <= tolerance (fail-closed)",
                "memory": (
                    "各算子独立隔离测得的峰值显存之和的降幅（非整模型峰值显存）"
                    if mem_pairs else "未测（CPU 环境无 CUDA 显存计数）"
                ),
            },
        )
        return report

    def export_report(
        self, report: OperatorOptimizationReport, out_dir: Optional[Path] = None
    ) -> Tuple[Path, Path]:
        """Write JSON + Markdown; the JSON is the evidence file referenced by both."""
        target_dir = Path(out_dir) if out_dir else (self.workspace_root / "benchmarks")
        target_dir.mkdir(parents=True, exist_ok=True)
        json_path = target_dir / "model_operator_optimization_report.json"
        md_path = target_dir / "model_operator_optimization_report.md"

        try:
            evidence = str(json_path.resolve().relative_to(self.workspace_root.resolve()))
        except ValueError:
            evidence = str(json_path.resolve())
        report.evidence_path = evidence
        report.summary["evidence_path"] = evidence
        for b in report.operator_benchmarks:
            b["evidence_path"] = evidence

        json_path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        md_path.write_text(report.summary_markdown(), encoding="utf-8")
        logger.info("Exported attributable operator report: %s", json_path)
        return json_path, md_path
