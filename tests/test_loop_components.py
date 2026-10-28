"""Unit tests for independent Loop Transformer components."""

import torch
from virtu_omni.config import ModelConfig
from virtu_omni.models.loop import (
    LoopRMSNorm,
    LoopStateGate,
    LoopStepController,
    LoopConvergenceCriterion,
    LoopStateCache,
)


def test_loop_rms_norm() -> None:
    dim = 256
    norm = LoopRMSNorm(dim=dim)
    x = torch.randn(2, 10, dim)
    out = norm(x)

    assert out.shape == x.shape
    # Check RMS scale close to 1
    rms = torch.sqrt(torch.mean(out.pow(2), dim=-1))
    assert torch.allclose(rms, torch.ones_like(rms), atol=1e-2)


def test_loop_state_gate_identity_initialization() -> None:
    dim = 256
    gate = LoopStateGate(hidden_dim=dim, bias_init=10.0)
    h_tilde = torch.randn(2, 5, dim)
    h_prev = torch.randn(2, 5, dim)

    # Initialized with bias=10.0 => gate ~ 1.0 => output should closely match h_tilde
    out = gate(h_tilde, h_prev)
    assert out.shape == h_tilde.shape
    assert torch.allclose(out, h_tilde, atol=1e-3)


def test_loop_step_controller() -> None:
    cfg = ModelConfig(max_loop_steps=3)
    controller = LoopStepController(cfg)
    assert controller.max_loop_steps == 3

    controller.set_max_steps(5)
    assert controller.max_loop_steps == 5

    controller.record_step(step_idx=0, delta=0.05, converged=False, layer_idx=0)
    controller.record_step(step_idx=1, delta=0.00005, converged=True, layer_idx=0)

    summary = controller.get_summary()
    assert summary["total_steps"] == 2
    assert summary["converged_steps"] == 1
    assert summary["max_configured_steps"] == 5

    controller.reset()
    assert controller.get_summary()["total_steps"] == 0


def test_loop_convergence_criterion_relative_l2() -> None:
    criterion = LoopConvergenceCriterion(threshold=1e-3, metric="relative_l2")
    h_prev = torch.ones(2, 4, 128)
    # Tiny difference
    h_curr_converged = h_prev + 1e-5 * torch.randn_like(h_prev)
    converged, delta = criterion.evaluate(h_curr_converged, h_prev)
    assert converged is True
    assert delta < 1e-3

    # Large difference
    h_curr_diverged = h_prev * 2.5
    converged2, delta2 = criterion.evaluate(h_curr_diverged, h_prev)
    assert converged2 is False
    assert delta2 > 1e-3


def test_loop_convergence_criterion_cosine() -> None:
    criterion = LoopConvergenceCriterion(threshold=1e-3, metric="cosine")
    h_prev = torch.randn(2, 4, 128)
    # Aligned vector
    h_curr = h_prev * 1.5
    converged, delta = criterion.evaluate(h_curr, h_prev)
    assert converged is True
    assert delta < 1e-4


def test_loop_state_cache() -> None:
    cache = LoopStateCache(enabled=True)
    t1 = torch.randn(2, 10, 64)
    cache.set_state("h_prev", t1)
    retrieved = cache.get_state("h_prev")
    assert retrieved is not None
    assert torch.equal(retrieved, t1)

    k = torch.randn(2, 4, 10, 32)
    v = torch.randn(2, 4, 10, 32)
    cache.set_kv(layer_idx=0, step_idx=1, k=k, v=v)
    cached_kv = cache.get_kv(layer_idx=0, step_idx=1)
    assert cached_kv is not None
    assert torch.equal(cached_kv[0], k)
    assert torch.equal(cached_kv[1], v)

    cache.clear()
    assert len(cache) == 0
    assert cache.get_state("h_prev") is None
