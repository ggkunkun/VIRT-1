"""Unit tests for Parameter Expander Engine."""

import os
import tempfile
import torch
from virtu_omni.config import ModelConfig
from virtu_omni.models.expander import BaseParameterExpander


def test_orthogonal_basis_generation():
    expander = BaseParameterExpander()
    q = expander._generate_orthogonal_basis(target_dim=128, source_dim=32)
    assert q.shape == (128, 32)
    # Check Q^T Q == I
    identity_approx = torch.matmul(q.t(), q)
    eye = torch.eye(32)
    assert torch.allclose(identity_approx, eye, atol=1e-5)


def test_expand_matrix_width():
    expander = BaseParameterExpander()
    src_weight = torch.randn(64, 32)
    expanded = expander.expand_matrix_width(src_weight, target_out_dim=256, target_in_dim=128)
    assert expanded.shape == (256, 128)
    assert torch.isfinite(expanded).all()


def test_build_expanded_state_dict():
    # Lightweight model configuration for fast test
    config = ModelConfig(num_layers=2, hidden_dim=64, intermediate_dim=192, vocab_size=200)
    expander = BaseParameterExpander(config=config)
    state_dict = expander.build_expanded_10b_state_dict()

    assert len(state_dict) > 0
    assert "layers.0.self_attn.q_proj.weight" in state_dict
    assert state_dict["layers.0.self_attn.q_proj.weight"].shape == (64, 64)

    # Test saving checkpoint
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_file = os.path.join(tmp_dir, "test_expanded.pt")
        saved_path = expander.save_checkpoint(out_file)
        assert saved_path == out_file
        ckpt = torch.load(saved_path, weights_only=False)
        assert "model_state_dict" in ckpt
