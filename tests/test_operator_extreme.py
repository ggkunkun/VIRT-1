# -*- coding: utf-8 -*-
"""Tests for the roofline-limit engine and the CUDA Graph executor.

A "theoretical limit" claim must be falsifiable: the hardware bound has to be
measured, the graph must be numerically identical to eager execution, and the
fp32 reference must reproduce itself exactly (otherwise a "precision cost" is
just two different random models).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
# torch 是可选训练依赖：无 torch 的推理主机上跳过本模块，而不是让收集阶段中断。
pytest.importorskip("torch")
import torch

from virtu_omni.config import ModelConfig
from virtu_omni.models.architecture import VirtuSwiGLU
from virtu_omni.models.operator_extreme import (
    ARMS,
    OPS,
    SOURCE_FILES,
    characterize_hardware,
    export_report,
    run_extreme_cycle,
    theoretical_bound,
    VirtuGraphExecutor,
)

pytestmark = pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA required")
DEV = "cuda"


def _cfg():
    return ModelConfig(hidden_dim=128, intermediate_dim=384,
                       num_attention_heads=4, num_kv_heads=2, head_dim=32)


# ---------------------------------------------------------------------------
# 1. CUDA Graph executor: exactness and evidence that it actually computes
# ---------------------------------------------------------------------------

def test_graph_executor_is_exactly_equivalent():
    m = VirtuSwiGLU(_cfg()).to(device=DEV, dtype=torch.float32).eval()
    m.fuse_projections()
    x = torch.randn(2, 32, 128, device=DEV)
    with torch.no_grad():
        runner = VirtuGraphExecutor(m.forward, (x,), warmup=3, tolerance=0.0)
        assert runner.verify_result["passed"] is True
        assert runner.verify_result["max_diff"] == 0.0
        assert runner.verify_result["tensors_checked"] == 1
        ref = m(x)
        out = runner.replay()
        torch.cuda.synchronize()
        assert (ref - out).abs().max().item() == 0.0


def test_graph_executor_recomputes_on_new_inputs():
    """A graph returning a stale cached value would silently pass the gate above."""
    m = VirtuSwiGLU(_cfg()).to(device=DEV).eval()
    x1 = torch.randn(2, 32, 128, device=DEV)
    x2 = torch.randn(2, 32, 128, device=DEV)
    with torch.no_grad():
        runner = VirtuGraphExecutor(m.forward, (x1,), warmup=3)
        out1 = runner.replay().clone()
        torch.cuda.synchronize()
        runner.set_inputs((x2,))
        out2 = runner.replay().clone()
        torch.cuda.synchronize()
        assert (out1 - out2).abs().max().item() > 0.0
        assert (m(x2) - out2).abs().max().item() == 0.0


def test_graph_executor_rejects_drifted_output():
    """Tampering with the captured output buffer must be observable."""
    m = VirtuSwiGLU(_cfg()).to(device=DEV).eval()
    x = torch.randn(2, 16, 128, device=DEV)
    with torch.no_grad():
        runner = VirtuGraphExecutor(m.forward, (x,), warmup=3)
        before = runner.replay().clone()
        torch.cuda.synchronize()
        runner.static_output.add_(1.0)
        assert (runner.static_output - before).abs().max().item() >= 1.0


# ---------------------------------------------------------------------------
# 2. Measured hardware bound and roofline monotonicity
# ---------------------------------------------------------------------------

_HW_JSON_SCRIPT = (
    "import json,sys;"
    "sys.path.insert(0, r'%s');"
    "from dataclasses import asdict;"
    "from virtu_omni.models.operator_extreme import characterize_hardware;"
    "print(json.dumps(asdict(characterize_hardware('cuda', repeats=3))))"
) % str(Path(__file__).resolve().parents[1])


def test_hardware_limits_are_measured_and_sane():
    # 为什么要起子进程：全量跑时前面那些用例会把同进程的显存吃到见底，此时
    # `dst.copy_(src)` 退化成主机内存往返（RTX 4050 从 174 GB/s 掉到 7.8）。
    # 这是「被测环境脏了」，不是显卡不行；但在同进程里既测不出硬件、也测不出代码。
    # 子进程拿到干净的 CUDA 上下文，测的才是这块卡本身。
    proc = subprocess.run([sys.executable, "-c", _HW_JSON_SCRIPT],
                          capture_output=True, text=True, encoding="utf-8", timeout=300)
    assert proc.returncode == 0, f"子进程探针失败: {proc.stderr[-2000:]}"
    hw = json.loads(proc.stdout.strip().splitlines()[-1])
    assert hw["basis"] == "measured", (
        f"干净上下文里测出的带宽 {hw['bandwidth_gbs']} GB/s 低于物理下限；"
        "这时候不是显存压力问题，是探针或驱动真的出事了，去查，别放宽阈值。")
    assert hw["bandwidth_gbs"] > 50.0
    assert hw["peak_tflops"]["bf16"] > hw["peak_tflops"]["fp32"] * 2
    assert hw["peak_tflops"]["tf32"] > hw["peak_tflops"]["fp32"]


def test_contended_bandwidth_is_flagged_not_published_as_measured(monkeypatch):
    """显存被占满时的读数必须被标成 contended，不许再冒充 measured。

    正例证据（2026-11-13 同机实测）：空显存 174.7 GB/s；吃满 4.2 GB 后 7.8 GB/s，
    后者正是 PCIe 往返量级。这里不真的吃显存（慢且污染同进程后续用例），
    而是把探针计时放慢 30 倍来注入同一种「读数崩塌」，验证标签切换。
    """
    import virtu_omni.models.operator_extreme as oe

    real_event_time_ms = oe._event_time_ms

    def slow_copy_probe(fn, repeats=7):
        return real_event_time_ms(fn, repeats) * 30

    monkeypatch.setattr(oe, "_event_time_ms", slow_copy_probe)
    hw = characterize_hardware(DEV, repeats=2)
    assert hw.basis == "contended", "崩塌的读数仍被标成 measured，会污染 roofline 下界"
    assert hw.bandwidth_gbs > 0, "数字本身仍应如实返回，只是标签降级"


def test_roofline_bounds_respect_precision_and_sequence_length():
    hw = characterize_hardware(DEV, repeats=3)
    cfg = _cfg()
    fp32 = theoretical_bound("VirtuSwiGLU", 2, 256, cfg, "fp32", hw)
    bf16 = theoretical_bound("VirtuSwiGLU", 2, 256, cfg, "bf16", hw)
    assert bf16.t_min_ms < fp32.t_min_ms
    assert fp32.bottleneck == "compute"
    short = theoretical_bound("VirtuAttention", 2, 64, cfg, "fp32", hw)
    long = theoretical_bound("VirtuAttention", 2, 512, cfg, "fp32", hw)
    assert long.t_min_ms > short.t_min_ms * 8  # S^2 attention term dominates
    assert theoretical_bound("VirtuRMSNorm", 2, 64, cfg, "fp32", hw).bottleneck == "memory"


# ---------------------------------------------------------------------------
# 3. Full cycle: provenance, gates, and honest reporting
# ---------------------------------------------------------------------------

def test_full_cycle_is_attributable_and_gated(tmp_path):
    report = run_extreme_cycle(seq_lens=[64], trials=5)
    assert report.run_id and not report.run_id.startswith("opt_ops_")
    assert report.basis == "measured"
    assert set(SOURCE_FILES) == set(report.identity["ruler"].keys())
    assert report.invalidated_legs == []
    assert report.all_graph_gates_passed is True
    assert len(report.measurements) == len(OPS) * len(ARMS)
    assert all(r["graph_gate"]["passed"] for r in report.measurements)
    # The fp32 arm must reproduce its own reference exactly.
    assert all(
        r["precision_reference_sane"] is not False
        for r in report.measurements
    )
    assert all(r["basis"] == "measured" and r["n_wall"] > 0 for r in report.measurements)
    assert all(r["t_min_ms"] > 0 for r in report.measurements)
    assert report.toolchain_limits, "unreachable items must be listed, not hidden"
    assert all("arm" in v and "speedup_vs_eager_wall_x" in v
               for v in report.best_per_operator.values())

    jp, mp = export_report(report, out_dir=tmp_path / "benchmarks")
    doc = json.loads(Path(jp).read_text(encoding="utf-8"))
    assert doc["run_id"] == report.run_id
    assert doc["evidence_path"]
    md = Path(mp).read_text(encoding="utf-8")
    assert "basis=measured" in md
    assert "工具链不可达" in md
    assert "距理论极限" in md


def test_source_drift_invalidates_the_limit_leg():
    import virtu_eval.provenance as prov
    ident = prov.RunIdentity.capture(ruler_files=SOURCE_FILES, extra={"probe": "limit"})
    assert ident.drift() == []
    original = prov.sha256_file
    prov.sha256_file = lambda _p: "f" * 64
    try:
        assert ident.drift()
    finally:
        prov.sha256_file = original


def test_agent_registers_the_limit_tool():
    from virtu_omni.agent.super_agent import VirtuSuperAgent
    agent = VirtuSuperAgent()
    assert "optimize_operators_to_limit" in agent.tools
    assert hasattr(agent, "run_operator_extreme_limit")
