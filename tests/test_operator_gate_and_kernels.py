# -*- coding: utf-8 -*-
"""Counter-evidence tests for the operator measurement gate and the new kernels.

The 2026-11-05 measurement incident had three roots: numbers with no byte
provenance, a mutable shared object under test, and a gate that could spin
without rejecting anything. These tests exist so that a gate that always
returns PASS, or a run_id that is just a clock label, fails the suite.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
# torch 是可选训练依赖：无 torch 的推理主机上跳过本模块，而不是让收集阶段中断。
pytest.importorskip("torch")
import torch

from virtu_omni.config import ModelConfig
from virtu_omni.models.architecture import (
    UniRoPE,
    VirtuAttention,
    VirtuRMSNorm,
    VirtuSwiGLU,
)
from virtu_omni.models.operator_optimizer import (
    SOURCE_FILES,
    OperatorOptimizationReport,
    VirtuOperatorOptimizer,
    _collect_tensors,
)

DEV = "cuda" if torch.cuda.is_available() else "cpu"


@pytest.fixture(scope="module")
def optimizer():
    return VirtuOperatorOptimizer()


# ---------------------------------------------------------------------------
# 1. The gate must be fail-closed (regression for the tautology bug)
# ---------------------------------------------------------------------------

def test_gate_rejects_nonfinite_and_divergent_outputs(optimizer):
    ones = torch.ones(8)
    cases = [
        ("nan_output", torch.tensor([1.0, float("nan")]), torch.ones(2), 1e-4, "nonfinite_output"),
        ("huge_diff", torch.zeros(8), torch.ones(8) * 10, 1e-4, "diff_exceeds_tolerance"),
        ("shape_mismatch", torch.zeros(3), torch.zeros(4), 1e-4, "shape_mismatch"),
        ("dtype_mismatch", torch.zeros(4), torch.zeros(4, dtype=torch.float64), 1e-4, "dtype_mismatch"),
        ("tensor_count", (ones, ones), (ones,), 1e-4, "tensor_count_mismatch"),
    ]
    for label, base, opt, tol, reason in cases:
        res = optimizer.check_equivalence(base, opt, tol)
        assert res["precision_pass"] is False, f"{label} must FAIL"
        assert res["failure_reason"] == reason, label


def test_gate_checks_every_tuple_element_not_just_first(optimizer):
    # The old implementation only compared y[0]; a broken RoPE k branch passed.
    base = (torch.zeros(8), torch.zeros(8))
    opt = (torch.zeros(8), torch.ones(8))
    res = optimizer.check_equivalence(base, opt, 1e-6)
    assert res["equivalence_checks"] == 2
    assert res["precision_pass"] is False
    assert res["failure_reason"] == "diff_exceeds_tolerance"


def test_gate_accepts_true_equivalence(optimizer):
    x = torch.randn(16)
    assert optimizer.check_equivalence((x, x.clone()), (x.clone(), x.clone()), 1e-6)["precision_pass"]


def test_benchmark_pair_propagates_a_broken_optimized_operator(optimizer):
    """End-to-end counter-evidence: a wrong kernel must not be reported as PASS."""
    x = torch.ones(8, device=DEV)
    res = optimizer.benchmark_operator_pair(
        "deliberately_wrong",
        lambda t: t,
        lambda t: t + 1.0,
        (x,),
        num_warmup=1, num_trials=2, repeats=1, tolerance=1e-6,
    )
    assert res["precision_pass"] is False
    assert res["failure_reason"] == "diff_exceeds_tolerance"
    assert res["max_diff"] >= 1.0
    assert res["basis"] == "measured" and res["n"] == 2


def test_collect_tensors_flattens_nested_structures():
    a, b = torch.zeros(2), torch.ones(2)
    assert len(_collect_tensors({"x": (a, [b]), "y": a})) == 3


# ---------------------------------------------------------------------------
# 2. Kernel equivalence and real optimisation behaviour
# ---------------------------------------------------------------------------

def test_rmsnorm_fused_kernel_is_exact():
    norm = VirtuRMSNorm(128).to(DEV).eval()
    x = torch.randn(2, 64, 128, device=DEV)
    diff = (norm._forward_unopt(x) - norm(x)).abs().max().item()
    assert diff <= 1e-6
    assert torch.isfinite(norm(x)).all()


def test_rope_cache_is_on_demand_and_covers_both_branches():
    rope = UniRoPE(dim=64, max_seq_len=8192).to(DEV)
    q = torch.randn(2, 128, 8, 64, device=DEV)
    k = torch.randn(2, 128, 4, 64, device=DEV)
    pos = torch.arange(128, device=DEV)
    base = rope._apply_1d_rope_unopt(q, k, pos)
    opt = rope.apply_1d_rope(q, k, pos, max_pos_hint=128)
    sliced = rope.apply_1d_rope(q, k, pos, max_pos_hint=128, contiguous_slice=(0, 128))
    for left, right in ((base[0], opt[0]), (base[1], opt[1]),
                        (base[0], sliced[0]), (base[1], sliced[1])):
        assert (left - right).abs().max().item() <= 1e-6
    # Old code always built an 8192-row table even for 128 tokens.
    assert rope._cached_seq_len < 512

    # Offset slice covers the KV-cache / past_key_value path.
    pos_off = torch.arange(100, 164, device=DEV)
    q2 = torch.randn(2, 64, 8, 64, device=DEV)
    k2 = torch.randn(2, 64, 4, 64, device=DEV)
    ref = rope._apply_1d_rope_unopt(q2, k2, pos_off)
    off = rope.apply_1d_rope(q2, k2, pos_off, max_pos_hint=164,
                             contiguous_slice=(100, 164))
    assert (ref[0] - off[0]).abs().max().item() <= 1e-6
    assert (ref[1] - off[1]).abs().max().item() <= 1e-6


def test_rope_2d_cache_is_reused_without_changing_output():
    rope = UniRoPE(dim=64).to(DEV)
    q = torch.randn(2, 16, 8, 64, device=DEV)
    k = torch.randn(2, 16, 4, 64, device=DEV)
    first = rope.apply_2d_rope(q, k, 4, 4)
    assert rope._grid_cached is not None
    cached_grid = rope._grid_cached
    second = rope.apply_2d_rope(q, k, 4, 4)
    assert rope._grid_cached == cached_grid
    assert (first[0] - second[0]).abs().max().item() == 0.0
    assert (first[1] - second[1]).abs().max().item() == 0.0


def test_attention_sdpa_and_fused_qkv_match_manual():
    cfg = ModelConfig(hidden_dim=256, intermediate_dim=768,
                      num_attention_heads=8, num_kv_heads=4, head_dim=64)
    attn = VirtuAttention(cfg).to(DEV).eval()
    rope = UniRoPE(dim=64).to(DEV)
    x = torch.randn(2, 128, 256, device=DEV)
    with torch.no_grad():
        manual = attn._forward_manual(x, rope_engine=rope)
        sdpa = attn(x, rope_engine=rope)
    assert torch.isfinite(sdpa).all()
    assert (manual - sdpa).abs().max().item() <= 2e-4

    n_before = sum(p.numel() for p in attn.parameters())
    attn.fuse_projections()
    assert sum(p.numel() for p in attn.parameters()) == n_before
    with torch.no_grad():
        fused = attn(x, rope_engine=rope)
    assert (sdpa - fused).abs().max().item() <= 1e-5

    # Training mode must fall back to the real (trainable) projections.
    attn.train()
    out = attn(x, rope_engine=rope).sum()
    out.backward()
    assert all(p.grad is not None and torch.isfinite(p.grad).all()
               for p in attn.parameters())


def test_swiglu_fusion_preserves_params_output_and_gradients():
    cfg = ModelConfig(hidden_dim=128, intermediate_dim=384)
    mlp = VirtuSwiGLU(cfg).to(DEV).eval()
    x = torch.randn(2, 32, 128, device=DEV)
    n_before = sum(p.numel() for p in mlp.parameters())
    with torch.no_grad():
        reference = mlp._forward_unopt(x)
    mlp.fuse_projections()
    assert sum(p.numel() for p in mlp.parameters()) == n_before
    with torch.no_grad():
        fused = mlp(x)
    assert (reference - fused).abs().max().item() <= 1e-5

    # Training mode must never use derived (gradient-less) weights.
    mlp.train()
    assert mlp.fused_gate_up is True
    out = mlp(x).sum()
    out.backward()
    assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in mlp.parameters())
    mlp.unfuse_projections()
    assert mlp._fused_gate_up_weight.numel() == 0


# ---------------------------------------------------------------------------
# 3. Provenance / report contract
# ---------------------------------------------------------------------------

def _mini_cycle(**kwargs):
    opt = VirtuOperatorOptimizer()
    params = dict(seq_lens=[64], hidden_dim=128, num_heads=4,
                  num_kv_heads=2, head_dim=32, num_warmup=1,
                  num_trials=2, repeats=1)
    params.update(kwargs)
    return opt, opt.run_full_optimization_cycle(**params)


def test_run_id_is_content_fingerprint_not_clock_label():
    _, r1 = _mini_cycle()
    _, r2 = _mini_cycle()
    _, r3 = _mini_cycle(seq_lens=[128])
    assert r1.run_id == r2.run_id
    assert r1.run_id != r3.run_id
    assert not r1.run_id.startswith("opt_ops_")
    assert set(SOURCE_FILES) == set(r1.identity["ruler"].keys())


def test_source_drift_invalidates_the_leg():
    import virtu_eval.provenance as prov
    ident = prov.RunIdentity.capture(ruler_files=SOURCE_FILES, extra={"probe": 1})
    assert ident.drift() == []
    original = prov.sha256_file
    prov.sha256_file = lambda _p: "0" * 64      # simulate source edited mid-leg
    try:
        assert ident.drift(), "a changed ruler must invalidate the leg"
    finally:
        prov.sha256_file = original


def test_report_carries_basis_n_evidence_and_regressions(tmp_path):
    opt, report = _mini_cycle()
    assert isinstance(report, OperatorOptimizationReport)
    assert report.all_invariants_passed is True
    assert report.invalidated_legs == []
    for b in report.operator_benchmarks:
        assert b["basis"] == "measured"
        assert b["n"] > 0
        assert b["precision_pass"] is True
    json_path, md_path = opt.export_report(report, out_dir=tmp_path / "benchmarks")
    doc = json.loads(Path(json_path).read_text(encoding="utf-8"))
    assert doc["run_id"] == report.run_id
    assert doc["evidence_path"]
    assert all(b["evidence_path"] == doc["evidence_path"] for b in doc["operator_benchmarks"])
    assert doc["summary"]["total_timing_samples"] > 0
    md = Path(md_path).read_text(encoding="utf-8")
    assert "basis=measured" in md
    assert "非整模型端到端" in md
    assert "退化算子" in md
