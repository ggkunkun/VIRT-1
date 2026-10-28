"""Unit tests for Distributed 3D Trainer."""

import os
import tempfile
import torch
from virtu_omni.config import VirtuOmniConfig, ModelConfig, TrainingConfig
from virtu_omni.models.architecture import VirtuOmni10B
from virtu_omni.training.trainer import Distributed3DTrainer
from virtu_omni.training.monitor import TrainingHealthMonitor


def test_trainer_initialization():
    cfg = VirtuOmniConfig(
        model=ModelConfig(
            num_layers=1,
            hidden_dim=64,
            intermediate_dim=192,
            vocab_size=100,
            image_resolution=56,
            patch_size=14,
        ),
        training=TrainingConfig(learning_rate=1e-3, warmup_steps=10, max_steps=100),
    )
    trainer = Distributed3DTrainer(config=cfg)
    assert trainer.model is not None
    assert trainer.optimizer is not None
    assert trainer.global_step == 0

    # Test LR schedule
    lr_warmup = trainer.get_learning_rate(step=5)
    lr_decay = trainer.get_learning_rate(step=50)
    lr_min = trainer.get_learning_rate(step=120)
    assert lr_warmup > 0
    assert lr_decay > 0
    assert lr_min == cfg.training.min_learning_rate


def test_trainer_step_and_loop():
    cfg = VirtuOmniConfig(
        model=ModelConfig(
            num_layers=1,
            hidden_dim=64,
            intermediate_dim=192,
            vocab_size=100,
            image_resolution=56,
            patch_size=14,
        ),
        training=TrainingConfig(learning_rate=1e-3, warmup_steps=2, max_steps=50),
    )
    model = VirtuOmni10B(cfg.model)
    monitor = TrainingHealthMonitor(cfg.monitor)
    trainer = Distributed3DTrainer(config=cfg, model=model, monitor=monitor)

    # Mock single batch
    batch = {
        "input_ids": torch.randint(0, 100, (2, 8)),
        "labels": torch.randint(0, 100, (2, 8)),
        "images": torch.randn(2, 3, 56, 56),
    }

    # Test single train step
    metrics = trainer.train_step(batch)
    assert "loss" in metrics
    assert metrics["loss"] > 0

    # Test train loop with generator
    def mock_data_generator():
        for _ in range(5):
            yield batch

    loop_res = trainer.train_loop(mock_data_generator(), num_steps=2)
    assert loop_res["completed_steps"] >= 1
    assert loop_res["final_loss"] is not None


def test_trainer_checkpoint_resume():
    cfg = VirtuOmniConfig(
        model=ModelConfig(
            num_layers=1,
            hidden_dim=64,
            intermediate_dim=192,
            vocab_size=100,
            image_resolution=56,
            patch_size=14,
        )
    )
    with tempfile.TemporaryDirectory() as tmp_dir:
        ckpt_path = os.path.join(tmp_dir, "test_checkpoint.pt")
        trainer = Distributed3DTrainer(config=cfg)
        trainer.global_step = 42
        saved = trainer.save_checkpoint(ckpt_path)
        assert os.path.exists(saved)

        # Create new trainer and load
        new_trainer = Distributed3DTrainer(config=cfg)
        new_trainer.load_checkpoint(saved)
        assert new_trainer.global_step == 42
