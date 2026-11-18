"""Unit tests for Method 3: Model Merging (SLERP, TIES, DARE, Linear)."""

from __future__ import annotations
import os
import tempfile
import pytest
# torch 是可选训练依赖：无 torch 的推理主机上跳过本模块，而不是让收集阶段中断。
pytest.importorskip("torch")
import torch

from virtu_edge.merging.methods import slerp, ties_merge, dare_merge, linear_merge
from virtu_edge.merging.merger import ModelMerger


def test_slerp_interpolation() -> None:
    """Test spherical linear interpolation on known unit vectors."""
    v0 = torch.tensor([1.0, 0.0])
    v1 = torch.tensor([0.0, 1.0])

    # Midway at t=0.5 should be [1/sqrt(2), 1/sqrt(2)]
    mid = slerp(v0, v1, factor=0.5)
    expected = 1.0 / (2.0 ** 0.5)
    assert abs(mid[0].item() - expected) < 1e-4
    assert abs(mid[1].item() - expected) < 1e-4

    # Boundary conditions
    assert torch.allclose(slerp(v0, v1, factor=0.0), v0, atol=1e-5)
    assert torch.allclose(slerp(v0, v1, factor=1.0), v1, atol=1e-5)


def test_ties_merging() -> None:
    """Test TIES sign consensus and density trimming."""
    base = torch.zeros(4)
    # Task 1 adds large positive values
    task1 = torch.tensor([10.0, 10.0, 0.1, 0.0])
    # Task 2 adds positive value on first, negative on second
    task2 = torch.tensor([5.0, -10.0, 0.0, 0.1])

    merged = ties_merge(base, [task1, task2], weights=[0.5, 0.5], density=0.5)
    # First component has consensus positive
    assert merged[0].item() > 0.0
    # Small components (0.1) trimmed by density threshold
    assert merged[2].item() == 0.0 or merged[3].item() == 0.0


def test_dare_merging() -> None:
    """Test DARE drop-and-rescale property."""
    base = torch.zeros(100)
    task1 = torch.ones(100)
    merged = dare_merge(base, [task1], weights=[1.0], drop_rate=0.5)

    # Some elements should be 0.0 due to dropout
    zero_count = (merged == 0.0).sum().item()
    assert 20 < zero_count < 80

    # Non-zero elements should be rescaled by 1 / (1 - 0.5) = 2.0
    non_zero = merged[merged != 0.0]
    assert torch.allclose(non_zero, torch.full_like(non_zero, 2.0))


def test_model_merger_end_to_end() -> None:
    """Test ModelMerger merging entire state dicts and saving physical checkpoint."""
    base_state = {
        "layer.weight": torch.randn(16, 16),
        "layer.bias": torch.randn(16),
        "step_counter": torch.tensor(10, dtype=torch.long),
    }
    task1_state = {
        "layer.weight": base_state["layer.weight"] + torch.randn(16, 16) * 0.1,
        "layer.bias": base_state["layer.bias"] + 0.1,
        "step_counter": torch.tensor(20, dtype=torch.long),
    }

    merger = ModelMerger(method="slerp")
    merged_dict = merger.merge_state_dicts(base_state, [task1_state], slerp_factor=0.5)

    assert "layer.weight" in merged_dict
    assert "layer.bias" in merged_dict
    assert "step_counter" in merged_dict
    assert merged_dict["step_counter"].item() == 10  # Preserved non-float buffer

    with tempfile.TemporaryDirectory() as tmp_dir:
        out_ckpt = os.path.join(tmp_dir, "merged_model.pt")
        report = merger.merge_and_save(base_state, [task1_state], out_ckpt)

        assert os.path.exists(out_ckpt)
        assert os.path.exists(out_ckpt.replace(".pt", "_receipt.json"))
        assert report["method"] == "slerp"
        assert report["total_parameters"] > 0
