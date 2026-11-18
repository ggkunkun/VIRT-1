"""Distributed training pipeline for Code LLM pretraining."""

from __future__ import annotations
import math
import os
import time
from typing import Dict, Any, List, Optional, Iterator
import torch
from torch.optim import AdamW

from virtu_code.config import CodeTrainingConfig
from virtu_code.training.model import CodeTransformerLM
from virtu_code.training.monitor import CodeTrainingMonitor


class DistributedCodeTrainer:
    """Pretraining engine with cosine learning rate scheduling and step-based checkpointing."""

    def __init__(
        self,
        config: Optional[CodeTrainingConfig] = None,
        model: Optional[CodeTransformerLM] = None,
        monitor: Optional[CodeTrainingMonitor] = None,
    ) -> None:
        self.config = config or CodeTrainingConfig()
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = model or CodeTransformerLM(self.config)
        self.model.to(self.device)

        self.monitor = monitor or CodeTrainingMonitor(self.config.training_log_path)
        self.optimizer = AdamW(
            self.model.parameters(),
            lr=self.config.learning_rate,
            weight_decay=0.1,
            betas=(0.9, 0.95),
            eps=1e-8,
        )

        self.global_step = 0
        self.saved_checkpoints: List[str] = []
        os.makedirs(self.config.checkpoint_dir, exist_ok=True)

    def get_learning_rate(self, step: int) -> float:
        """Compute cosine annealing learning rate with linear warmup."""
        if step < self.config.warmup_steps:
            return self.config.learning_rate * (step + 1) / max(1, self.config.warmup_steps)

        total_decay_steps = max(1, (self.config.max_steps - self.config.warmup_steps))
        progress = (step - self.config.warmup_steps) / total_decay_steps
        cosine_decay = 0.5 * (1.0 + math.cos(math.pi * min(1.0, progress)))
        lr_range = self.config.learning_rate - self.config.min_learning_rate
        return self.config.min_learning_rate + lr_range * cosine_decay

    def set_learning_rate(self, lr: float) -> None:
        for param_group in self.optimizer.param_groups:
            param_group["lr"] = lr

    def save_checkpoint(self, step: int, val_loss: float, train_loss: float) -> str:
        """Persist intermediate model checkpoint with optimizer state and loss metrics."""
        ckpt_name = f"checkpoint_step_{step}.pt"
        ckpt_path = os.path.join(self.config.checkpoint_dir, ckpt_name)

        torch.save(
            {
                "step": step,
                "model_state_dict": self.model.state_dict(),
                "optimizer_state_dict": self.optimizer.state_dict(),
                "val_loss": val_loss,
                "train_loss": train_loss,
                "config": self.config,
            },
            ckpt_path,
        )
        self.saved_checkpoints.append(ckpt_path)
        val_repr = f"{val_loss:.4f}" if val_loss is not None else "unmeasured"
        print(f"[Trainer] Checkpoint successfully saved to: {ckpt_path} (Val Loss: {val_repr})")
        return ckpt_path

    def train_steps(
        self,
        batch_iterator: Iterator[Dict[str, torch.Tensor]],
        total_steps: int = 20,
        checkpoint_interval: int = 10,
    ) -> Dict[str, Any]:
        """Execute pretraining loop across given steps with validation and checkpointing."""
        self.model.train()
        accumulated_loss = 0.0

        for step in range(1, total_steps + 1):
            self.global_step += 1
            batch = next(batch_iterator)

            input_ids = batch["input_ids"].to(self.device)
            labels = batch["labels"].to(self.device)

            lr = self.get_learning_rate(self.global_step)
            self.set_learning_rate(lr)

            t0 = time.perf_counter()
            self.optimizer.zero_grad()
            outputs = self.model(input_ids=input_ids, labels=labels)
            loss = outputs["loss"]
            loss.backward()

            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            self.optimizer.step()
            step_elapsed = time.perf_counter() - t0

            loss_val = loss.item()
            accumulated_loss += loss_val

            # 无独立验证集 ⇒ val_loss 未测。禁止用 train_loss*0.98 冒充验证损失（§8 测量宪法）。
            val_loss = None
            if step % checkpoint_interval == 0 or step == total_steps:
                self.save_checkpoint(self.global_step, val_loss=val_loss, train_loss=loss_val)

            tokens_per_sec = input_ids.numel() / max(step_elapsed, 1e-9)
            self.monitor.record_step(
                step=self.global_step,
                train_loss=loss_val,
                lr=lr,
                throughput=tokens_per_sec,
                val_loss=val_loss,
            )

        return {
            "completed_steps": total_steps,
            "final_loss": round(accumulated_loss / total_steps, 4),
            "checkpoints": self.saved_checkpoints,
        }
