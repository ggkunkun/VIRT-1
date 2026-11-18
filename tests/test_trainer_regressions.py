import unittest
from unittest.mock import Mock

import pytest
# torch 是可选训练依赖：无 torch 的推理主机上跳过本模块，而不是让收集阶段中断。
pytest.importorskip("torch")
import torch

from virtu_omni.config import VirtuOmniConfig, ParallelismConfig, TrainingConfig
from virtu_omni.training.trainer import Distributed3DTrainer


class _Linear(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.weight = torch.nn.Parameter(torch.tensor(0.0))

    def forward(self, input_ids=None, images=None, labels=None, mode=None):
        loss = (self.weight - input_ids.float().mean()).square()
        return {"loss": loss, "loss_ce": loss.detach(), "z_loss": 0.0}


class _Monitor:
    def inspect_and_handle(self, **kwargs):
        return False


class TrainerRegressionTests(unittest.TestCase):
    def make_trainer(self, accum_steps):
        cfg = VirtuOmniConfig(
            parallelism=ParallelismConfig(
                tensor_parallel_size=1,
                pipeline_parallel_size=1,
                data_parallel_size=1,
                gradient_accumulation_steps=accum_steps,
                mixed_precision="bf16",
                micro_batch_size=1,
            ),
            training=TrainingConfig(
                learning_rate=0.1,
                warmup_steps=0,
                max_steps=20,
                min_learning_rate=0.1,
                weight_decay=0.0,
                clip_grad_norm=100.0,
                save_interval_steps=1000,
            ),
        )
        trainer = Distributed3DTrainer(cfg, model=_Linear(), monitor=_Monitor())
        original_step = trainer.optimizer.step
        trainer.gradients_at_step = []

        def capture_gradient(*args, **kwargs):
            trainer.gradients_at_step.append(trainer.model.weight.grad.item())
            return original_step(*args, **kwargs)

        trainer.optimizer.step = Mock(side_effect=capture_gradient)
        return trainer

    @staticmethod
    def batch(target):
        return {"input_ids": torch.tensor([[target]], dtype=torch.float32), "labels": None}

    def test_full_accumulation_averages_gradients(self):
        trainer = self.make_trainer(2)
        result = trainer.train_loop(iter([self.batch(1.0), self.batch(3.0)]), num_steps=1)
        # At w=0, gradients are -2 and -6; their mean is -4, not their sum.
        self.assertEqual(len(trainer.gradients_at_step), 1)
        self.assertAlmostEqual(trainer.gradients_at_step[0], -4.0, places=5)
        self.assertEqual(result["completed_steps"], 1)
        trainer.optimizer.step.assert_called_once()

    def test_short_final_window_uses_actual_microstep_count(self):
        trainer = self.make_trainer(4)
        trainer.train_loop(iter([self.batch(2.0)]), num_steps=3)
        # One available sample gives gradient -4; it must not be divided by configured 4.
        self.assertEqual(len(trainer.gradients_at_step), 1)
        self.assertAlmostEqual(trainer.gradients_at_step[0], -4.0, places=5)
        # Next fetch finds no data: no empty optimizer update or extra step.
        self.assertEqual(trainer.optimizer.step.call_count, 1)
        self.assertEqual(trainer.global_step, 1)
        self.assertIsNone(trainer.model.weight.grad)

    def test_empty_iterator_does_not_step_optimizer(self):
        trainer = self.make_trainer(2)
        result = trainer.train_loop(iter([]), num_steps=2)
        self.assertEqual(result["completed_steps"], 0)
        trainer.optimizer.step.assert_not_called()
        self.assertIsNone(trainer.model.weight.grad)

    def test_nonpositive_accumulation_is_rejected(self):
        trainer = self.make_trainer(0)
        with self.assertRaisesRegex(ValueError, "positive integer"):
            trainer.train_loop(iter([]), num_steps=1)


if __name__ == "__main__":
    unittest.main()
