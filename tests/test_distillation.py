"""Unit tests for Method 2: Knowledge Distillation and CoT Synthesis."""

from __future__ import annotations
import os
import tempfile
import pytest
# torch 是可选训练依赖：无 torch 的推理主机上跳过本模块，而不是让收集阶段中断。
pytest.importorskip("torch")
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from virtu_edge.distillation.loss import DistillationLoss
from virtu_edge.distillation.cot_dataset import SyntheticCoTGenerator, SimpleCoTDataset
from virtu_edge.distillation.distiller import KnowledgeDistillationTrainer


def test_distillation_loss_calculation() -> None:
    """Verify CE + KL divergence loss with temperature scaling."""
    loss_fn = DistillationLoss(temperature=2.0, alpha=0.6)
    student_logits = torch.randn(2, 4, 50, requires_grad=True)
    teacher_logits = torch.randn(2, 4, 50)
    labels = torch.randint(0, 50, (2, 4))

    out = loss_fn(student_logits, teacher_logits, labels=labels)
    assert "loss" in out
    assert "ce_loss" in out
    assert "kl_loss" in out
    assert out["loss"].item() > 0.0

    out["loss"].backward()
    assert student_logits.grad is not None


def test_cot_dataset_generation_and_loading() -> None:
    """Test synthetic CoT sample generation and formatted text."""
    samples = SyntheticCoTGenerator.generate_corpus(repeat=2)
    assert len(samples) == 12  # 6 templates * 2

    first = samples[0]
    assert "<think>" in first["formatted_text"]
    assert "</think>" in first["formatted_text"]
    assert "<answer>" in first["formatted_text"]

    with tempfile.TemporaryDirectory() as tmp_dir:
        jsonl_path = os.path.join(tmp_dir, "cot_corpus.jsonl")
        SyntheticCoTGenerator.save_corpus(jsonl_path, repeat=1)
        assert os.path.exists(jsonl_path)
        assert os.path.getsize(jsonl_path) > 100

    dataset = SimpleCoTDataset(samples, vocab_size=500, max_seq_len=32)
    assert len(dataset) == 12
    item = dataset[0]
    assert item["input_ids"].shape == (32,)
    assert item["labels"].shape == (32,)


class MockLanguageModel(nn.Module):
    def __init__(self, vocab_size: int = 200, dim: int = 32) -> None:
        super().__init__()
        self.emb = nn.Embedding(vocab_size, dim)
        self.fc = nn.Linear(dim, vocab_size)

    def forward(self, input_ids: torch.Tensor, **kwargs) -> dict:
        h = self.emb(input_ids)
        logits = self.fc(h)
        return {"logits": logits}


def test_knowledge_distillation_trainer() -> None:
    """Verify teacher-student knowledge distillation training loop."""
    teacher = MockLanguageModel(vocab_size=100, dim=32)
    student = MockLanguageModel(vocab_size=100, dim=16)

    # Initial teacher weights
    teacher_w_before = teacher.fc.weight.clone()

    trainer = KnowledgeDistillationTrainer(
        teacher_model=teacher,
        student_model=student,
        temperature=2.0,
        alpha=0.5,
        lr=1e-3,
    )

    dummy_batch = {"input_ids": torch.randint(0, 100, (4, 16))}
    metrics = trainer.train_step(dummy_batch)
    assert metrics["loss"] > 0.0
    assert metrics["kl_loss"] > 0.0

    # Verify teacher was strictly frozen and untouched
    assert torch.equal(teacher.fc.weight.cpu(), teacher_w_before.cpu())

    # Epoch training
    dataloader = [dummy_batch, dummy_batch, dummy_batch]
    res = trainer.train(dataloader, num_epochs=1)
    assert res["total_steps"] == 3
    assert res["final_loss"] > 0.0
