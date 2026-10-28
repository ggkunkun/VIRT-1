"""QLoRA Single-GPU / Edge Training Engine."""

from __future__ import annotations
import os
import time
from typing import Dict, Any, List, Optional
import torch
import torch.nn as nn
from torch.optim import AdamW

from virtu_edge.qlora.model import LoRAModel


class QLoRATrainer:
    """Trainer optimized for single-GPU 4-bit LoRA fine-tuning."""

    def __init__(
        self,
        model: LoRAModel,
        lr: float = 2e-4,
        weight_decay: float = 0.01,
        gradient_accumulation_steps: int = 1,
        max_grad_norm: float = 1.0,
        device: Optional[torch.device] = None,
    ) -> None:
        self.model = model
        self.device = device or (torch.device("cuda" if torch.cuda.is_available() else "cpu"))
        self.model.to(self.device)

        # Train ONLY parameters that require grad (LoRA adapters)
        trainable_params = [p for p in self.model.parameters() if p.requires_grad]
        self.optimizer = AdamW(trainable_params, lr=lr, weight_decay=weight_decay)
        self.gradient_accumulation_steps = gradient_accumulation_steps
        self.max_grad_norm = max_grad_norm
        self.history: List[Dict[str, Any]] = []

    def train_step(self, batch: Dict[str, torch.Tensor], step: int) -> float:
        """Execute a single forward-backward optimization step."""
        self.model.train()
        input_ids = batch["input_ids"].to(self.device)
        labels = batch.get("labels", input_ids).to(self.device)

        out = self.model(input_ids, labels=labels)
        loss = out["loss"] if isinstance(out, dict) and "loss" in out else out

        loss = loss / self.gradient_accumulation_steps
        loss.backward()

        if (step + 1) % self.gradient_accumulation_steps == 0:
            torch.nn.utils.clip_grad_norm_(
                [p for p in self.model.parameters() if p.requires_grad],
                self.max_grad_norm,
            )
            self.optimizer.step()
            self.optimizer.zero_grad()

        return float(loss.item() * self.gradient_accumulation_steps)

    def train(
        self,
        train_dataloader: Any,
        num_epochs: int = 1,
        max_steps: Optional[int] = None,
        log_interval: int = 5,
    ) -> Dict[str, Any]:
        """Run complete QLoRA training epoch loop."""
        step = 0
        start_time = time.time()
        self.model.train()

        total_loss = 0.0
        vram_peak_mb = 0.0

        for epoch in range(num_epochs):
            for batch in train_dataloader:
                loss_val = self.train_step(batch, step)
                total_loss += loss_val

                if torch.cuda.is_available():
                    vram_mb = torch.cuda.max_memory_allocated(self.device) / (1024 * 1024)
                    if vram_mb > vram_peak_mb:
                        vram_peak_mb = vram_mb

                if step % log_interval == 0:
                    avg_loss = total_loss / (step + 1)
                    self.history.append({
                        "step": step,
                        "epoch": epoch,
                        "loss": round(loss_val, 4),
                        "avg_loss": round(avg_loss, 4),
                        "vram_peak_mb": round(vram_peak_mb, 2),
                    })

                step += 1
                if max_steps and step >= max_steps:
                    break
            if max_steps and step >= max_steps:
                break

        duration = time.time() - start_time
        final_loss = total_loss / max(1, step)

        return {
            "total_steps": step,
            "final_loss": round(final_loss, 4),
            "duration_sec": round(duration, 2),
            "vram_peak_mb": round(vram_peak_mb, 2),
            "history": self.history,
        }
