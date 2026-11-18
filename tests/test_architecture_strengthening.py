# -*- coding: utf-8 -*-
"""Regression and Rule-4 falsifiable mutation probes for the strengthened Virtu-Omni architecture.

Covers:
1. ModelConfig validation & parameter accounting for Hybrid MoE / Geometry / MTP / Value / YaRN / Softcap.
2. UniRoPE 3D spatial sensitivity & YaRN/NTK long-context frequency scaling.
3. VirtuAttention logit softcapping bounds & stability.
4. LoopTransformerBlock + Hybrid DeepSeek-MoE + Loss-Free Dynamic Bias Balancing.
5. Tri-modal (Vision + 3D CAD Geometry + Text) BHCM causal isolation, gradient flow, MTP, & PRM Value Head.
6. Tri-modal KV-cached vs uncached generate() / generate_stream() exact equivalence.
"""

from __future__ import annotations

import pytest
# torch 是可选训练依赖：无 torch 的推理主机上跳过本模块，而不是让收集阶段中断。
pytest.importorskip("torch")
import torch

from virtu_omni.config import ModelConfig
from virtu_omni.errors import ModelError
from virtu_omni.models import (
    MultiTokenPredictionModule,
    PRMValueHead,
    UniRoPE,
    VirtuAttention,
    VirtuDeepSeekMoELayer,
    VirtuOmni10B,
)


def _tiny_fullstack_config(**overrides) -> ModelConfig:
    """Build a compact deterministic full-stack config for fast CPU/GPU unit tests."""
    defaults = dict(
        num_layers=2,
        hidden_dim=64,
        intermediate_dim=128,
        num_attention_heads=4,
        num_kv_heads=2,
        head_dim=16,
        vocab_size=256,
        vision_codebook_size=64,
        image_resolution=28,
        patch_size=14,
        max_position_embeddings=128,
        max_loop_steps=1,
        use_moe=True,
        moe_layer_freq=2,
        num_routed_experts=4,
        moe_top_k=2,
        moe_intermediate_dim=48,
        moe_aux_loss_coef=0.01,
        use_loss_free_balancing=True,
        enable_geometry_modality=True,
        geometry_feature_dim=8,
        mtp_depth=2,
        mtp_loss_weight=0.3,
        enable_value_head=True,
        rope_scaling_factor=2.0,
        attn_logit_softcapping=30.0,
    )
    defaults.update(overrides)
    return ModelConfig(**defaults)


def test_config_validation_and_parameter_accounting():
    """Config validates new architecture fields and accounts for extra modules cleanly."""
    dense_cfg = _tiny_fullstack_config(
        use_moe=False,
        enable_geometry_modality=False,
        mtp_depth=0,
        enable_value_head=False,
        rope_scaling_factor=1.0,
        attn_logit_softcapping=0.0,
    )
    full_cfg = _tiny_fullstack_config()
    assert full_cfg.total_estimated_parameters > dense_cfg.total_estimated_parameters

    # Rule-4 negative probes: structurally invalid configs must fail fast with ModelError
    bad_kwargs = [
        {"moe_top_k": 5, "num_routed_experts": 4},
        {"moe_top_k": 0},
        {"moe_layer_freq": 0},
        {"rope_scaling_factor": 0.0},
        {"rope_scaling_factor": -2.0},
        {"attn_logit_softcapping": -0.5},
        {"mtp_depth": -1},
        {"geometry_feature_dim": 0},
    ]
    for kwargs in bad_kwargs:
        with pytest.raises(ModelError):
            _tiny_fullstack_config(**kwargs)


def test_unirope_3d_spatial_and_yarn_scaling():
    """3D RoPE differentiates XYZ coordinates while preserving norm; YaRN lowers 1D frequencies."""
    torch.manual_seed(42)
    rope_base = UniRoPE(dim=24, max_seq_len=128, scaling_factor=1.0)
    rope_yarn = UniRoPE(dim=24, max_seq_len=128, scaling_factor=4.0)

    assert rope_yarn.mscale > rope_base.mscale
    assert torch.all(rope_yarn.inv_freq_1d < rope_base.inv_freq_1d)

    q = torch.randn(2, 5, 4, 24)
    k = torch.randn(2, 5, 2, 24)
    coords_a = torch.tensor([
        [[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [0.0, 10.0, 0.0], [0.0, 0.0, 10.0], [5.0, 5.0, 5.0]],
        [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0], [10.0, 11.0, 12.0], [0.0, 0.0, 0.0]],
    ])
    coords_b = coords_a.clone()
    coords_b[:, 2, :] += torch.tensor([12.5, -7.5, 3.0])

    qa, ka = rope_base.apply_3d_rope(q, k, coords_a)
    qb, kb = rope_base.apply_3d_rope(q, k, coords_b)
    assert qa.shape == q.shape and ka.shape == k.shape
    # Origin coordinates (0, 0, 0) yield identity rotation on token 0 of batch 0
    assert torch.allclose(qa[0, 0], q[0, 0], atol=1e-6)
    # 3D norm conservation
    assert torch.allclose(qa.norm(dim=-1), q.norm(dim=-1), atol=1e-5)
    # Perturbing coords[2] must alter only token 2 rotation
    assert torch.allclose(qa[:, :2], qb[:, :2], atol=1e-6)
    assert not torch.allclose(qa[:, 2], qb[:, 2], atol=1e-4)

    # Rule-4 falsifiable probe: bad coords trailing dimension must fail
    with pytest.raises(ModelError):
        rope_base.apply_3d_rope(q, k, torch.zeros(2, 5, 2))


def test_attention_logit_softcapping():
    """Attention logit softcapping bounds extreme attention logits and alters outputs smoothly."""
    torch.manual_seed(7)
    cfg_uncapped = _tiny_fullstack_config(attn_logit_softcapping=0.0, use_qk_norm=False)
    cfg_capped = _tiny_fullstack_config(attn_logit_softcapping=2.0, use_qk_norm=False)

    attn_uncapped = VirtuAttention(cfg_uncapped)
    attn_capped = VirtuAttention(cfg_capped)
    attn_capped.load_state_dict(attn_uncapped.state_dict())

    rope = UniRoPE(dim=cfg_capped.head_dim, max_seq_len=64)
    x = torch.randn(2, 6, cfg_capped.hidden_dim) * 15.0

    out_uncapped = attn_uncapped(x, rope_engine=rope)
    out_capped = attn_capped(x, rope_engine=rope)
    assert torch.isfinite(out_capped).all()
    assert not torch.allclose(out_uncapped, out_capped, atol=1e-3)


def test_hybrid_moe_and_loss_free_dynamic_balancing():
    """Hybrid backbone mixes MoE & dense blocks, aggregates aux_loss, and updates expert_bias."""
    torch.manual_seed(11)
    assert VirtuDeepSeekMoELayer.falsifiable_moe_probe()

    cfg = _tiny_fullstack_config(
        num_layers=4,
        moe_layer_freq=2,
        enable_geometry_modality=False,
        mtp_depth=0,
        enable_value_head=False,
    )
    model = VirtuOmni10B(cfg)
    assert [layer.is_moe_layer for layer in model.layers] == [True, False, True, False]
    assert isinstance(model.layers[0].mlp, VirtuDeepSeekMoELayer)

    model.train()
    input_ids = torch.randint(0, cfg.vocab_size, (2, 10))
    labels = input_ids.clone()

    bias_before = model.layers[0].mlp.router.expert_bias.clone()
    out = model(input_ids=input_ids, labels=labels, loop_steps=2)
    bias_after = model.layers[0].mlp.router.expert_bias.clone()

    assert "moe_aux_loss" in out and out["moe_aux_loss"] >= 0.0
    assert "moe_metrics" in out and len(out["moe_metrics"]) == 2
    assert bias_before.abs().sum().item() == 0.0
    assert not torch.allclose(bias_before, bias_after)

    out["loss"].backward()
    assert model.layers[0].mlp.router.gate_proj.weight.grad is not None
    assert model.layers[0].mlp.shared_expert.w_gate.weight.grad is not None
    assert model.layers[1].mlp.gate_proj.weight.grad is not None


def test_trimodal_bhcm_causal_isolation_mtp_and_prm_value():
    """Verify Vision + 3D Geometry + Text forward/backward, MTP, PRM Value Head, and BHCM isolation."""
    torch.manual_seed(123)
    cfg = _tiny_fullstack_config()
    model = VirtuOmni10B(cfg)
    model.train()

    batch, n_geom, n_text = 2, 5, 8
    images = torch.randn(batch, 3, cfg.image_resolution, cfg.image_resolution)
    geom_features = torch.randn(batch, n_geom, cfg.geometry_feature_dim)
    geom_coords = torch.randn(batch, n_geom, 3) * 10.0
    input_ids = torch.randint(1, cfg.vocab_size, (batch, n_text))
    labels = input_ids.clone()
    prm_targets = torch.rand(batch, n_text)

    out = model(
        input_ids=input_ids,
        images=images,
        labels=labels,
        geom_features=geom_features,
        geom_coords=geom_coords,
        prm_targets=prm_targets,
    )

    num_vision = (cfg.image_resolution // cfg.patch_size) ** 2  # 4
    expected_total_seq = num_vision + n_geom + n_text
    assert out["hidden_states"].shape == (batch, expected_total_seq, cfg.hidden_dim)
    assert out["logits"].shape == (batch, n_text, cfg.vocab_size)
    assert len(out["mtp_logits"]) == cfg.mtp_depth
    assert out["mtp_logits"][0].shape == (batch, n_text - 1, cfg.vocab_size)
    assert out["mtp_logits"][1].shape == (batch, n_text - 2, cfg.vocab_size)
    assert out["prm_values"].shape == (batch, n_text)
    assert torch.all((out["prm_values"] >= 0.0) & (out["prm_values"] <= 1.0))

    for loss_key in ("loss_ce", "z_loss", "loss_mtp", "loss_value", "moe_aux_loss"):
        assert loss_key in out and torch.isfinite(torch.tensor(out[loss_key]))

    out["loss"].backward()
    for mod_name, param in [
        ("geometry_projector", model.geometry_projector.input_proj.weight),
        ("vision_projector", model.vision_projector.proj_in.weight),
        ("mtp_0", model.mtp_modules[0].proj.weight),
        ("value_head", model.value_head.fc2.weight),
        ("embed_tokens", model.embed_tokens.weight),
    ]:
        assert param.grad is not None, f"Missing gradient on {mod_name}"
        assert torch.isfinite(param.grad).all(), f"Non-finite gradient on {mod_name}"

    # Rule-4 Causality & 3D Coordinate Mutation Probes in eval mode
    model.eval()
    with torch.no_grad():
        ref_out = model(
            input_ids=input_ids,
            images=images,
            geom_features=geom_features,
            geom_coords=geom_coords,
        )
        # Mutate ONLY future tokens [:, 4:]
        mutated_ids = input_ids.clone()
        mutated_ids[:, 4:] = (mutated_ids[:, 4:] + 17) % cfg.vocab_size
        fut_out = model(
            input_ids=mutated_ids,
            images=images,
            geom_features=geom_features,
            geom_coords=geom_coords,
        )
        prefix_len = num_vision + n_geom
        # Prefix (Vision + Geometry) & early text tokens (0..3) MUST remain invariant
        assert torch.allclose(
            ref_out["hidden_states"][:, : prefix_len + 4, :],
            fut_out["hidden_states"][:, : prefix_len + 4, :],
            atol=1e-5,
        )
        assert torch.allclose(
            ref_out["logits"][:, :4, :], fut_out["logits"][:, :4, :], atol=1e-5
        )
        # Future positions MUST diverge
        assert not torch.allclose(
            ref_out["logits"][:, 4:, :], fut_out["logits"][:, 4:, :], atol=1e-4
        )

        # Mutate ONLY geom_coords -> output logits & geometry hidden states must reflect 3D shift
        moved_coords = geom_coords + 25.0
        moved_out = model(
            input_ids=input_ids,
            images=images,
            geom_features=geom_features,
            geom_coords=moved_coords,
        )
        assert not torch.allclose(ref_out["logits"], moved_out["logits"], atol=1e-4)


def test_trimodal_kv_cache_generation_equivalence():
    """Tri-modal KV-cached generate() and generate_stream() must match uncached greedy decoding."""
    torch.manual_seed(99)
    cfg = _tiny_fullstack_config(mtp_depth=0)
    model = VirtuOmni10B(cfg)
    model.eval()

    input_ids = torch.randint(3, cfg.vocab_size, (1, 5))
    images = torch.randn(1, 3, cfg.image_resolution, cfg.image_resolution)
    geom_features = torch.randn(1, 4, cfg.geometry_feature_dim)
    geom_coords = torch.randn(1, 4, 3)

    gen_cached = model.generate(
        input_ids=input_ids,
        images=images,
        geom_features=geom_features,
        geom_coords=geom_coords,
        max_new_tokens=5,
        temperature=0.0,
        repetition_penalty=1.0,
        eos_token_id=None,
        use_cache=True,
    )
    gen_uncached = model.generate(
        input_ids=input_ids,
        images=images,
        geom_features=geom_features,
        geom_coords=geom_coords,
        max_new_tokens=5,
        temperature=0.0,
        repetition_penalty=1.0,
        eos_token_id=None,
        use_cache=False,
    )
    assert torch.equal(gen_cached, gen_uncached)

    streamed = list(
        model.generate_stream(
            input_ids=input_ids,
            images=images,
            geom_features=geom_features,
            geom_coords=geom_coords,
            max_new_tokens=5,
            temperature=0.0,
            repetition_penalty=1.0,
            eos_token_id=None,
            use_cache=True,
        )
    )
    assert streamed == gen_cached[0, 5:].tolist()


def test_trimodal_boundary_error_probes():
    """Invalid tri-modal inputs raise explicit ModelError instead of silent failures."""
    cfg_no_geom = _tiny_fullstack_config(enable_geometry_modality=False)
    model_no_geom = VirtuOmni10B(cfg_no_geom)
    with pytest.raises(ModelError):
        model_no_geom(
            input_ids=torch.randint(0, 64, (1, 4)),
            geom_features=torch.randn(1, 3, 8),
        )

    cfg = _tiny_fullstack_config()
    model = VirtuOmni10B(cfg)
    assert isinstance(model.mtp_modules[0], MultiTokenPredictionModule)
    assert isinstance(model.value_head, PRMValueHead)

    with pytest.raises(ModelError):
        model(
            input_ids=torch.randint(0, 64, (1, 4)),
            geom_features=torch.randn(1, 3, 8),
            geom_coords=torch.randn(1, 3, 2),  # bad coord dim != 3
        )
    with pytest.raises(ModelError):
        model(
            input_ids=torch.randint(0, 64, (1, 4)),
            prm_targets=torch.rand(1, 5),  # bad target len != 4
        )
    with pytest.raises(ModelError):
        model.create_block_hybrid_mask(2, 4, torch.device("cpu"), num_geom=-1)
