"""Knowledge Distillation Engine for Teacher-Student Knowledge Transfer."""

from __future__ import annotations
import time
from typing import Dict, Any, List, Optional
import torch
import torch.nn as nn
from torch.optim import AdamW

from virtu_edge.distillation.loss import DistillationLoss


class KnowledgeDistillationTrainer:
    """Trains a compact student model using teacher output distribution and CoT data."""

    def __init__(
        self,
        teacher_model: nn.Module,
        student_model: nn.Module,
        temperature: float = 2.0,
        alpha: float = 0.5,
        lr: float = 3e-4,
        device: Optional[torch.device] = None,
    ) -> None:
        self.device = device or (torch.device("cuda" if torch.cuda.is_available() else "cpu"))
        self.teacher = teacher_model.to(self.device)
        self.student = student_model.to(self.device)

        # Teacher is strictly frozen (evaluation mode)
        self.teacher.eval()
        for p in self.teacher.parameters():
            p.requires_grad = False

        self.student.train()
        self.loss_fn = DistillationLoss(temperature=temperature, alpha=alpha)
        self.optimizer = AdamW(self.student.parameters(), lr=lr, weight_decay=0.01)
        self.history: List[Dict[str, Any]] = []

    def train_step(self, batch: Dict[str, torch.Tensor]) -> Dict[str, float]:
        """Single distillation step."""
        self.student.train()
        input_ids = batch["input_ids"].to(self.device)
        labels = batch.get("labels", input_ids).to(self.device)

        # 1. Forward teacher without gradients
        with torch.no_grad():
            teacher_out = self.teacher(input_ids)
            teacher_logits = teacher_out["logits"] if isinstance(teacher_out, dict) else teacher_out

        # 2. Forward student
        student_out = self.student(input_ids)
        student_logits = student_out["logits"] if isinstance(student_out, dict) else student_out

        # 3. Compute distillation loss
        loss_dict = self.loss_fn(
            student_logits=student_logits,
            teacher_logits=teacher_logits,
            labels=labels,
        )

        total_loss = loss_dict["loss"]
        self.optimizer.zero_grad()
        total_loss.backward()
        self.optimizer.step()

        return {
            "loss": float(total_loss.item()),
            "ce_loss": float(loss_dict["ce_loss"].item()),
            "kl_loss": float(loss_dict["kl_loss"].item()),
        }

    def train(
        self,
        dataloader: Any,
        num_epochs: int = 1,
        max_steps: Optional[int] = None,
        log_interval: int = 5,
    ) -> Dict[str, Any]:
        """Run distillation epoch loop."""
        step = 0
        start_time = time.time()
        total_loss = 0.0

        for epoch in range(num_epochs):
            for batch in dataloader:
                metrics = self.train_step(batch)
                total_loss += metrics["loss"]

                if step % log_interval == 0:
                    self.history.append({
                        "step": step,
                        "epoch": epoch,
                        "loss": round(metrics["loss"], 4),
                        "kl_loss": round(metrics["kl_loss"], 4),
                    })

                step += 1
                if max_steps and step >= max_steps:
                    break
            if max_steps and step >= max_steps:
                break

        duration = time.time() - start_time
        return {
            "total_steps": step,
            "final_loss": round(total_loss / max(1, step), 4),
            "duration_sec": round(duration, 2),
            "history": self.history,
        }
