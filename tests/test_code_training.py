"""Unit tests for Code LLM pretraining components."""

import os
import tempfile
import pytest
# torch 是可选训练依赖：无 torch 的推理主机上跳过本模块，而不是让收集阶段中断。
pytest.importorskip("torch")
import torch
from virtu_code.config import CodeTrainingConfig
from virtu_code.training.model import CodeTransformerLM
from virtu_code.training.trainer import DistributedCodeTrainer
from virtu_code.training.monitor import CodeTrainingMonitor


def test_code_transformer_lm_forward() -> None:
    cfg = CodeTrainingConfig(
        hidden_dim=128,
        intermediate_dim=256,
        num_layers=2,
        num_attention_heads=4,
        num_kv_heads=2,
    )
    model = CodeTransformerLM(cfg, vocab_size=500)
    input_ids = torch.randint(0, 500, (2, 16))
    labels = torch.randint(0, 500, (2, 16))

    out = model(input_ids, labels=labels)
    assert "logits" in out
    assert out["logits"].shape == (2, 16, 500)
    assert "loss" in out
    assert out["loss"].item() > 0.0


def test_cosine_learning_rate_scheduler() -> None:
    # 调度器是纯数学单测：不得构造默认 24 层/2048 维/64000 词表的生产规模模型。
    # 2026-11-16 实测：内存吃紧时默认规模分配直接 access violation，杀死整个 pytest 会话。
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg = CodeTrainingConfig(
            learning_rate=1e-3, min_learning_rate=1e-5, warmup_steps=100, max_steps=1000,
            hidden_dim=64, intermediate_dim=128, num_layers=1,
            num_attention_heads=2, num_kv_heads=1,
            checkpoint_dir=os.path.join(tmp_dir, "ckpts"),
            training_log_path=os.path.join(tmp_dir, "train_log.jsonl"),
        )
        model = CodeTransformerLM(cfg, vocab_size=500)
        trainer = DistributedCodeTrainer(config=cfg, model=model)

        # During warmup
        lr_0 = trainer.get_learning_rate(0)
        lr_50 = trainer.get_learning_rate(50)
        assert lr_0 < lr_50 <= 1e-3

        # End of warmup
        lr_100 = trainer.get_learning_rate(100)
        assert abs(lr_100 - 1e-3) < 1e-5

        # During decay
        lr_500 = trainer.get_learning_rate(500)
        assert lr_100 > lr_500 > 1e-5

        # At max steps
        lr_1000 = trainer.get_learning_rate(1000)
        assert abs(lr_1000 - 1e-5) < 1e-6


def test_checkpoint_saving_and_loading() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        ckpt_dir = os.path.join(tmp_dir, "ckpts")
        cfg = CodeTrainingConfig(
            hidden_dim=64,
            intermediate_dim=128,
            num_layers=1,
            num_attention_heads=2,
            num_kv_heads=1,
            checkpoint_dir=ckpt_dir,
            training_log_path=os.path.join(tmp_dir, "train_log.jsonl"),
        )
        model = CodeTransformerLM(cfg, vocab_size=500)
        trainer = DistributedCodeTrainer(config=cfg, model=model)
        path = trainer.save_checkpoint(step=1000, val_loss=1.85, train_loss=1.90)

        assert os.path.exists(path)
        loaded = torch.load(path, weights_only=False)
        assert loaded["step"] == 1000
        assert loaded["val_loss"] == 1.85
        assert "model_state_dict" in loaded
        assert "optimizer_state_dict" in loaded


def test_training_monitor_report() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        log_path = os.path.join(tmp_dir, "train_log.jsonl")
        monitor = CodeTrainingMonitor(log_path=log_path)

        monitor.record_step(step=10, train_loss=2.5, lr=1e-4, throughput=5000.0, val_loss=2.4)
        monitor.record_step(step=20, train_loss=2.0, lr=2e-4, throughput=5200.0, val_loss=1.9)

        rep_path = os.path.join(tmp_dir, "report.md")
        monitor.export_report(["ckpt_10.pt", "ckpt_20.pt"], rep_path)

        assert os.path.exists(rep_path)
        with open(rep_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "Step 10" in content
        assert "Step 20" in content
        assert "ckpt_10.pt" in content
