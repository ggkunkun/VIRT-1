"""Comprehensive numerical equivalence, gradient flow, and regression test suite

Verifies Loop Transformer implementation against production acceptance criteria:
1. Numerical equivalence with baseline standard Transformer (FP32 < 1e-6, FP16 < 1e-3).
2. Forward pass tensor flow shape & dimension validity.
3. Backward pass full-path gradient propagation & health (no vanishing/exploding/NaN/Inf).
4. Runtime dynamic loop step adjustment and telemetry observability.
5. Dynamic convergence early-exit decision branch.
6. Cross-loop state cache and memory reuse.
"""

from typing import Dict, Any
import torch

from virtu_omni.config import ModelConfig
from virtu_omni.models.architecture import (
    VirtuOmni10B,
    LoopTransformerBlock,
    UniRoPE,
)


def _build_test_config(**kwargs: Any) -> ModelConfig:
    """Build lightweight ModelConfig for fast unit verification."""
    defaults: Dict[str, Any] = {
        "num_layers": 2,
        "hidden_dim": 256,
        "intermediate_dim": 512,
        "num_attention_heads": 8,
        "num_kv_heads": 2,
        "head_dim": 32,
        "vocab_size": 1000,
        "vision_codebook_size": 512,
        "image_resolution": 28,
        "patch_size": 14,
        "max_loop_steps": 1,
        "convergence_threshold": 1e-4,
        "enable_state_cache": True,
        "loop_gating": True,
        "adaptive_loop": True,
    }
    defaults.update(kwargs)
    return ModelConfig(**defaults)


def test_forward_tensor_flow_dimensions() -> None:
    """Verify input/output tensor dimensions for all operational modes."""
    cfg = _build_test_config(max_loop_steps=2)
    model = VirtuOmni10B(cfg)

    batch_size = 2
    seq_len = 16
    input_ids = torch.randint(0, cfg.vocab_size, (batch_size, seq_len))
    images = torch.randn(batch_size, 3, cfg.image_resolution, cfg.image_resolution)

    # 1. Text generation mode
    out_text = model(input_ids=input_ids, mode="text_gen")
    assert "logits" in out_text
    assert out_text["logits"].shape == (batch_size, seq_len, cfg.vocab_size)
    assert out_text["hidden_states"].shape == (batch_size, seq_len, cfg.hidden_dim)
    assert "loop_stats" in out_text

    # 2. Image generation mode
    out_img = model(images=images, mode="image_gen")
    assert "image_logits" in out_img
    num_patches = (cfg.image_resolution // cfg.patch_size) ** 2
    assert out_img["image_logits"].shape == (batch_size, num_patches, cfg.vision_codebook_size)

    # 3. Interleaved multimodal understanding
    labels = torch.randint(0, cfg.vocab_size, (batch_size, seq_len))
    out_mm = model(input_ids=input_ids, images=images, labels=labels, mode="multimodal_eval")
    assert "logits" in out_mm
    assert "loss" in out_mm
    assert out_mm["loss"].item() > 0.0


def test_numerical_equivalence_fp32() -> None:
    """Requirement: Under identical inputs and seeds, numerical error < 1e-6 in FP32."""
    torch.manual_seed(42)
    cfg = _build_test_config(max_loop_steps=1)

    block = LoopTransformerBlock(cfg, layer_idx=0)
    rope = UniRoPE(dim=cfg.head_dim, max_seq_len=512)

    x = torch.randn(2, 10, cfg.hidden_dim, dtype=torch.float32)

    # 1. Baseline standard single-pass computation
    with torch.no_grad():
        norm_attn = block.input_layernorm(x)
        attn_out = block.self_attn(norm_attn, rope_engine=rope)
        mid = x + attn_out
        norm_mlp = block.post_attention_layernorm(mid)
        mlp_out = block.mlp(norm_mlp)
        expected_out = mid + mlp_out

    # 2. Loop Transformer execution with max_loop_steps=1
    with torch.no_grad():
        actual_out = block(x, rope_engine=rope, loop_steps=1)

    max_diff_fp32 = torch.max(torch.abs(actual_out - expected_out)).item()
    print(f"\n[Test] FP32 Max Absolute Difference: {max_diff_fp32:.10e}")
    assert max_diff_fp32 < 1e-6, f"FP32 difference {max_diff_fp32} exceeds 1e-6 threshold"
    assert torch.allclose(actual_out, expected_out, atol=1e-6, rtol=1e-5)


def test_numerical_equivalence_fp16() -> None:
    """Requirement: Numerical error < 1e-3 in FP16."""
    torch.manual_seed(42)
    cfg = _build_test_config(max_loop_steps=1)

    block = LoopTransformerBlock(cfg, layer_idx=0).half()
    rope = UniRoPE(dim=cfg.head_dim, max_seq_len=512)

    x = torch.randn(2, 10, cfg.hidden_dim, dtype=torch.float16)

    with torch.no_grad():
        norm_attn = block.input_layernorm(x)
        attn_out = block.self_attn(norm_attn, rope_engine=rope)
        mid = x + attn_out
        norm_mlp = block.post_attention_layernorm(mid)
        mlp_out = block.mlp(norm_mlp)
        expected_out = mid + mlp_out

    with torch.no_grad():
        actual_out = block(x, rope_engine=rope, loop_steps=1)

    max_diff_fp16 = torch.max(torch.abs(actual_out - expected_out)).item()
    print(f"\n[Test] FP16 Max Absolute Difference: {max_diff_fp16:.6e}")
    assert max_diff_fp16 < 1e-3, f"FP16 difference {max_diff_fp16} exceeds 1e-3 threshold"
    assert torch.allclose(actual_out, expected_out, atol=1e-3, rtol=1e-3)


def test_gradient_propagation_full_path() -> None:
    """Requirement: Full-path gradient backpropagation without vanishing or NaN/Inf."""
    torch.manual_seed(123)
    cfg = _build_test_config(max_loop_steps=2, adaptive_loop=False)
    model = VirtuOmni10B(cfg)

    input_ids = torch.randint(0, cfg.vocab_size, (2, 8))
    labels = torch.randint(0, cfg.vocab_size, (2, 8))

    outputs = model(input_ids=input_ids, labels=labels, loop_steps=2)
    loss = outputs["loss"]
    assert torch.isfinite(loss), f"Loss is not finite: {loss.item()}"

    loss.backward()

    # Verify gradients across every critical module
    critical_tensors = [
        ("embed_tokens", model.embed_tokens.weight),
        ("layer0.q_proj", model.layers[0].self_attn.q_proj.weight),
        ("layer0.o_proj", model.layers[0].self_attn.o_proj.weight),
        ("layer0.mlp_down", model.layers[0].mlp.down_proj.weight),
        ("layer0.loop_norm", model.layers[0].loop_norm.weight),
        ("layer0.gate_w", model.layers[0].state_gate.w_gate.weight),
        ("final_norm", model.final_norm.weight),
        ("lm_head", model.lm_head.lm_head.weight),
    ]

    for name, param in critical_tensors:
        assert param.grad is not None, f"Gradient is None for {name}"
        assert not torch.isnan(param.grad).any(), f"NaN in gradient of {name}"
        assert not torch.isinf(param.grad).any(), f"Inf in gradient of {name}"
        grad_norm = torch.linalg.norm(param.grad).item()
        assert grad_norm > 0.0, f"Gradient vanished (norm=0) for {name}"


def test_dynamic_convergence_early_exit() -> None:
    """Verify loop convergence detector triggers early exit when threshold is satisfied."""
    cfg = _build_test_config(
        max_loop_steps=5,
        convergence_threshold=0.5,  # Generous threshold to force convergence
        adaptive_loop=True,
    )
    model = VirtuOmni10B(cfg)
    input_ids = torch.randint(0, cfg.vocab_size, (2, 8))

    out = model(input_ids=input_ids, loop_steps=5)
    stats = out["loop_stats"]

    assert stats["total_steps"] > 0
    assert stats["converged_steps"] > 0, "Expected at least one layer step to trigger convergence"


def test_runtime_dynamic_step_adjustment() -> None:
    """Verify runtime dynamic modification of loop step budget."""
    cfg = _build_test_config(max_loop_steps=1)
    model = VirtuOmni10B(cfg)
    input_ids = torch.randint(0, cfg.vocab_size, (1, 6))

    # Step budget = 1
    model.set_loop_steps(1)
    out1 = model(input_ids=input_ids)
    assert out1["loop_stats"]["max_configured_steps"] == 1

    # Step budget dynamically changed to 3
    model.set_loop_steps(3)
    out2 = model(input_ids=input_ids)
    assert out2["loop_stats"]["max_configured_steps"] == 3


def test_cross_step_state_cache_reuse() -> None:
    """Verify cross-loop-step hidden state caching and retrieval."""
    cfg = _build_test_config(max_loop_steps=3, enable_state_cache=True, adaptive_loop=False)
    model = VirtuOmni10B(cfg)
    input_ids = torch.randint(0, cfg.vocab_size, (1, 4))

    _ = model(input_ids=input_ids, loop_steps=3)
    # Check that state cache contains recorded layer iterations
    s0 = model.state_cache.get_state("L0_S0")
    s1 = model.state_cache.get_state("L0_S1")
    s2 = model.state_cache.get_state("L0_S2")

    assert s0 is not None
    assert s1 is not None
    assert s2 is not None
    assert s0.shape == s1.shape == s2.shape
