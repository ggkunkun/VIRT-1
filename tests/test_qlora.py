"""Unit tests for Method 1: QLoRA 4-bit quantization and adapter training."""

from __future__ import annotations
import os
import tempfile
import pytest
# torch 是可选训练依赖：无 torch 的推理主机上跳过本模块，而不是让收集阶段中断。
pytest.importorskip("torch")
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from virtu_edge.qlora.linear_4bit import (
    quantize_to_int4_blockwise,
    dequantize_int4_blockwise,
    Linear4bitLoRA,
)
from virtu_edge.qlora.model import LoRAConfig, LoRAModel
from virtu_edge.qlora.trainer import QLoRATrainer


def test_4bit_quantize_dequantize_error() -> None:
    """Test 4-bit block-wise quantization round-trip precision."""
    torch.manual_seed(42)
    weight = torch.randn(128, 128) * 0.05
    packed, scales, zeros = quantize_to_int4_blockwise(weight, block_size=32)

    dequant = dequantize_int4_blockwise(packed, scales, zeros, weight.shape, block_size=32)
    # 4-bit quantization has finite resolution, max absolute error should be small (< 0.02)
    max_err = torch.max(torch.abs(weight - dequant)).item()
    assert max_err < 0.02


def test_linear_4bit_lora_forward_and_merge() -> None:
    """Test Linear4bitLoRA forward pass and weight merging."""
    orig_linear = nn.Linear(64, 32, bias=True)
    lora_layer = Linear4bitLoRA.from_linear(orig_linear, r=4, lora_alpha=8.0)

    x = torch.randn(2, 64)
    y_before = lora_layer(x)
    assert y_before.shape == (2, 32)

    # Gradient flows into lora_A and lora_B, not packed base weight
    loss = y_before.sum()
    loss.backward()

    assert lora_layer.lora_A.grad is not None
    assert lora_layer.lora_B.grad is not None
    assert not hasattr(lora_layer.packed_weight, "grad") or lora_layer.packed_weight.grad is None

    # Merge weights
    lora_layer.merge_weights()
    assert lora_layer._merged is True
    y_after = lora_layer(x)
    assert y_after.shape == (2, 32)


class SimpleToyModel(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.q_proj = nn.Linear(32, 32)
        self.v_proj = nn.Linear(32, 32)
        self.out_proj = nn.Linear(32, 32)
        self.head = nn.Linear(32, 10)

    def forward(self, x: torch.Tensor, labels: torch.Tensor = None) -> dict:
        h = torch.relu(self.q_proj(x) + self.v_proj(x))
        h = self.out_proj(h)
        logits = self.head(h)
        loss = None
        if labels is not None:
            loss = nn.functional.cross_entropy(logits.view(-1, 10), labels.view(-1))
        return {"logits": logits, "loss": loss}


def test_lora_model_wrapper_and_persistence() -> None:
    """Test LoRAModel parameter reduction and checkpoint saving/loading."""
    toy = SimpleToyModel()
    cfg = LoRAConfig(r=4, lora_alpha=8.0, target_modules=["q_proj", "v_proj"])
    lora_model = LoRAModel(toy, cfg)

    param_stats = lora_model.get_trainable_parameters()
    # Trainable parameters should be a small fraction of total
    assert param_stats["trainable_percent"] < 35.0
    assert param_stats["injected_layers"] == 2

    # Forward
    x = torch.randn(4, 32)
    labels = torch.randint(0, 10, (4,))
    out = lora_model(x, labels=labels)
    assert out["loss"] is not None

    with tempfile.TemporaryDirectory() as tmp_dir:
        save_path = os.path.join(tmp_dir, "adapter")
        lora_model.save_pretrained(save_path)
        assert os.path.exists(os.path.join(save_path, "adapter_model.pt"))
        assert os.path.exists(os.path.join(save_path, "adapter_config.json"))

        # Reload adapter
        new_toy = SimpleToyModel()
        new_lora = LoRAModel(new_toy, cfg)
        new_lora.load_adapter(save_path)

        # Merge and unload
        standalone = new_lora.merge_and_unload()
        out_merged = standalone(x)
        assert out_merged["logits"].shape == (4, 10)


def test_qlora_trainer_step_and_epochs() -> None:
    """Test QLoRATrainer running actual optimization on adapter parameters."""
    toy = SimpleToyModel()
    cfg = LoRAConfig(r=4, lora_alpha=8.0, target_modules=["q_proj", "v_proj"])
    lora_model = LoRAModel(toy, cfg)

    trainer = QLoRATrainer(lora_model, lr=1e-3)
    x = torch.randn(16, 32)
    y = torch.randint(0, 10, (16,))
    dataset = TensorDataset(x, y)
    loader = DataLoader(dataset, batch_size=4)

    # Adapt dataset batch format for trainer
    class FormattedLoader:
        def __init__(self, dl: DataLoader) -> None:
            self.dl = dl

        def __iter__(self):
            for batch_x, batch_y in self.dl:
                yield {"input_ids": batch_x, "labels": batch_y}

    res = trainer.train(FormattedLoader(loader), num_epochs=2, log_interval=2)
    assert res["total_steps"] == 8
    assert res["final_loss"] > 0.0
    assert len(res["history"]) > 0
