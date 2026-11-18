"""Unit tests for Virtu-Omni-10B Neural Architecture Components."""

import pytest
# torch 是可选训练依赖：无 torch 的推理主机上跳过本模块，而不是让收集阶段中断。
pytest.importorskip("torch")
import torch
from virtu_omni.config import ModelConfig
from virtu_omni.models.architecture import (
    VirtuRMSNorm,
    UniRoPE,
    VirtuAttention,
    VirtuSwiGLU,
    VirtuTransformerBlock,
    ContinuousVisionProjector,
    VirtuOmni10B,
)


@pytest.fixture
def test_config():
    """Create lightweight test configuration."""
    return ModelConfig(
        num_layers=2,
        hidden_dim=256,
        intermediate_dim=768,
        num_attention_heads=4,
        num_kv_heads=2,
        head_dim=64,
        vocab_size=1000,
        vision_codebook_size=500,
        image_resolution=56,
        patch_size=14,
        max_position_embeddings=512,
    )


def test_rmsnorm():
    norm = VirtuRMSNorm(dim=128)
    x = torch.randn(2, 10, 128)
    out = norm(x)
    assert out.shape == x.shape
    assert torch.isfinite(out).all()


def test_unirope():
    rope = UniRoPE(dim=64, max_seq_len=512)
    q = torch.randn(2, 16, 4, 64)
    k = torch.randn(2, 16, 2, 64)
    pos = torch.arange(16)

    # 1D text rotation
    q_rot, k_rot = rope.apply_1d_rope(q, k, pos)
    assert q_rot.shape == q.shape
    assert k_rot.shape == k.shape

    # 2D spatial rotation
    q_vis = torch.randn(2, 16, 4, 64)
    k_vis = torch.randn(2, 16, 2, 64)
    q_rot2, k_rot2 = rope.apply_2d_rope(q_vis, k_vis, 4, 4)
    assert q_rot2.shape == q_vis.shape
    assert k_rot2.shape == k_vis.shape


def test_attention_gqa(test_config):
    attn = VirtuAttention(test_config)
    x = torch.randn(2, 8, test_config.hidden_dim)
    rope = UniRoPE(dim=test_config.head_dim)
    out = attn(x, rope_engine=rope)
    assert out.shape == (2, 8, test_config.hidden_dim)
    assert torch.isfinite(out).all()


def test_swiglu_mlp(test_config):
    mlp = VirtuSwiGLU(test_config)
    x = torch.randn(2, 8, test_config.hidden_dim)
    out = mlp(x)
    assert out.shape == (2, 8, test_config.hidden_dim)
    assert torch.isfinite(out).all()


def test_transformer_block(test_config):
    block = VirtuTransformerBlock(test_config)
    x = torch.randn(2, 8, test_config.hidden_dim)
    rope = UniRoPE(dim=test_config.head_dim)
    out = block(x, rope_engine=rope)
    assert out.shape == x.shape


def test_continuous_vision_projector(test_config):
    proj = ContinuousVisionProjector(test_config)
    images = torch.randn(2, 3, 56, 56)
    features, grid_hw = proj(images)
    expected_patches = (56 // 14) * (56 // 14)  # 16 patches
    assert features.shape == (2, expected_patches, test_config.hidden_dim)
    assert grid_hw == (4, 4)


def test_virtu_omni_full_forward(test_config):
    model = VirtuOmni10B(test_config)
    # 1. Text only
    input_ids = torch.randint(0, test_config.vocab_size, (2, 8))
    labels = input_ids.clone()
    out_text = model(input_ids=input_ids, labels=labels, mode="text_gen")
    assert "logits" in out_text
    assert "loss" in out_text
    assert out_text["logits"].shape == (2, 8, test_config.vocab_size)

    # 2. Multimodal interleaved
    images = torch.randn(2, 3, 56, 56)
    out_mm = model(input_ids=input_ids, images=images, labels=labels, mode="multimodal_eval")
    assert "logits" in out_mm
    assert out_mm["logits"].shape == (2, 8, test_config.vocab_size)

    # 3. Vision generation mode
    out_vis = model(images=images, mode="image_gen")
    assert "image_logits" in out_vis
    assert out_vis["image_logits"].shape == (2, 16, test_config.vision_codebook_size)


def test_virtu_omni_autoregressive_generate(test_config):
    """Verify autoregressive generation produces correct token dimensions with and without KV cache."""
    model = VirtuOmni10B(test_config)
    input_ids = torch.randint(0, test_config.vocab_size, (1, 6))

    # Test greedy decoding with KV cache enabled
    torch.manual_seed(42)
    gen_cached = model.generate(
        input_ids=input_ids,
        max_new_tokens=8,
        temperature=0.0,
        use_cache=True,
    )
    assert gen_cached.shape == (1, 14)
    assert torch.equal(gen_cached[:, :6], input_ids)

    # Test greedy decoding without KV cache (must produce bitwise identical tokens)
    torch.manual_seed(42)
    gen_uncached = model.generate(
        input_ids=input_ids,
        max_new_tokens=8,
        temperature=0.0,
        use_cache=False,
    )
    assert torch.equal(gen_cached, gen_uncached), "KV cached generation must match uncached output exactly."


def test_virtu_omni_generate_stream(test_config):
    """Verify streaming generator yields valid tokens in real time."""
    model = VirtuOmni10B(test_config)
    input_ids = torch.randint(0, test_config.vocab_size, (1, 4))

    stream_tokens = list(model.generate_stream(
        input_ids=input_ids,
        max_new_tokens=5,
        temperature=0.0,
        use_cache=True,
    ))
    assert len(stream_tokens) <= 5
    assert all(isinstance(t, int) and 0 <= t < test_config.vocab_size for t in stream_tokens)
