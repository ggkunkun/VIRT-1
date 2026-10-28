"""Loss functions for Knowledge Distillation with Temperature Scaling."""

from __future__ import annotations
from typing import Optional, Dict
import torch
import torch.nn as nn
import torch.nn.functional as F


class DistillationLoss(nn.Module):
    """Knowledge Distillation loss combining soft teacher probabilities and hard target labels.

    L_total = (1 - alpha) * L_CE(y_student, labels) + alpha * T^2 * KL(student_probs || teacher_probs)
    """

    def __init__(
        self,
        temperature: float = 2.0,
        alpha: float = 0.5,
        hidden_loss_weight: float = 0.0,
    ) -> None:
        super().__init__()
        self.temperature = temperature
        self.alpha = alpha
        self.hidden_loss_weight = hidden_loss_weight
        self.kl_div = nn.KLDivLoss(reduction="batchmean")

    def forward(
        self,
        student_logits: torch.Tensor,
        teacher_logits: torch.Tensor,
        labels: Optional[torch.Tensor] = None,
        student_hidden: Optional[torch.Tensor] = None,
        teacher_hidden: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """Compute combined knowledge distillation loss."""
        # 1. Hard Cross Entropy Loss (if labels provided)
        vocab_size = student_logits.shape[-1]
        ce_loss = torch.tensor(0.0, device=student_logits.device)
        if labels is not None:
            ce_loss = F.cross_entropy(
                student_logits.reshape(-1, vocab_size),
                labels.reshape(-1),
                ignore_index=-100,
            )

        # 2. Soft Distillation Loss (KL Divergence with Temperature)
        # Log-Softmax for student, Softmax for teacher
        student_log_probs = F.log_softmax(student_logits / self.temperature, dim=-1)
        teacher_probs = F.softmax(teacher_logits / self.temperature, dim=-1)

        kl_loss = self.kl_div(student_log_probs, teacher_probs) * (self.temperature ** 2)

        # 3. Optional Hidden State Alignment (MSE)
        hidden_loss = torch.tensor(0.0, device=student_logits.device)
        if self.hidden_loss_weight > 0.0 and student_hidden is not None and teacher_hidden is not None:
            if student_hidden.shape == teacher_hidden.shape:
                hidden_loss = F.mse_loss(student_hidden, teacher_hidden)

        # Total combined
        if labels is not None:
            total_loss = (1.0 - self.alpha) * ce_loss + self.alpha * kl_loss
        else:
            total_loss = kl_loss

        if self.hidden_loss_weight > 0.0:
            total_loss = total_loss + self.hidden_loss_weight * hidden_loss

        return {
            "loss": total_loss,
            "ce_loss": ce_loss.detach(),
            "kl_loss": kl_loss.detach(),
            "hidden_loss": hidden_loss.detach(),
        }
