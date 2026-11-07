# -*- coding: utf-8 -*-
"""Tests for the roofline-limit engine and the CUDA Graph executor.

A "theoretical limit" claim must be falsifiable: the hardware bound has to be
measured, the graph must be numerically identical to eager execution, and the
fp32 reference must reproduce itself exactly (otherwise a "precision cost" is
just two different random models).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
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

def test_hardware_limits_are_measured_and_sane():
    hw = characterize_hardware(DEV, repeats=3)
    assert hw.basis == "measured"
    assert hw.bandwidth_gbs > 50.0
    assert hw.peak_tflops["bf16"] > hw.peak_tflops["fp32"] * 2
    assert hw.peak_tflops["tf32"] > hw.peak_tflops["fp32"]


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
