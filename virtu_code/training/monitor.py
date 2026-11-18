"""Training metrics tracking and validation reporting."""

from __future__ import annotations
import math
import os
import json
import time
from typing import Dict, Any, List, Optional


class CodeTrainingMonitor:
    """Tracks training trajectory, loss convergence, and produces audit reports.

    测量宪法（AGENTS.md §8）：未测项记 None/未测，禁止硬编码指标；
    报告结论必须由 history 实算得出，不得无条件 APPROVED。
    """

    def __init__(self, log_path: str = "logs/code_training.jsonl") -> None:
        self.log_path = log_path
        self.history: List[Dict[str, Any]] = []
        os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)

    def record_step(
        self,
        step: int,
        train_loss: float,
        lr: float,
        throughput: float,
        val_loss: Optional[float] = None,
        gpu_utilization: Optional[float] = None,
    ) -> None:
        record = {
            "step": step,
            "train_loss": round(train_loss, 4),
            "val_loss": round(val_loss, 4) if val_loss is not None else None,
            "learning_rate": float(f"{lr:.2e}"),
            "throughput_tok_s": round(throughput, 1),
            "gpu_utilization_pct": round(gpu_utilization, 1) if gpu_utilization is not None else None,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        self.history.append(record)

        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    def convergence_verdict(self) -> Dict[str, Any]:
        """从 history 实算收敛判据；空/单点/非有限损失一律不得判 APPROVED。"""
        losses = [e["train_loss"] for e in self.history]
        if len(losses) < 2:
            return {"verdict": "INSUFFICIENT_EVIDENCE", "n_steps": len(losses),
                    "reason": "少于 2 个记录步，无法判定趋势"}
        if any(not math.isfinite(v) for v in losses):
            return {"verdict": "FAILED", "n_steps": len(losses),
                    "reason": "存在非有限损失（NaN/Inf）"}
        first, last = losses[0], losses[-1]
        if last > first:
            return {"verdict": "NOT_CONVERGED", "n_steps": len(losses),
                    "first_loss": first, "last_loss": last,
                    "reason": "末步损失高于首步"}
        return {"verdict": "LOSS_DECREASING", "n_steps": len(losses),
                "first_loss": first, "last_loss": last,
                "reason": "损失呈下降趋势（仅趋势证据，非独立验证集结论）"}

    def export_report(self, checkpoints: List[str], output_path: str) -> None:
        """Export training metrics report whose conclusions are computed from history."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        gpu_vals = [e["gpu_utilization_pct"] for e in self.history
                    if e.get("gpu_utilization_pct") is not None]
        if gpu_vals:
            gpu_line = f"**资源利用率**: 实测均值 {sum(gpu_vals) / len(gpu_vals):.1f}%（n={len(gpu_vals)} 个记录步）"
        else:
            gpu_line = "**资源利用率**: 未测（gpu_utilization 未提供，不以估算值冒充）"

        verdict = self.convergence_verdict()

        lines = [
            "# VirtuCode: 大语言模型预训练指标监控与收敛报告",
            f"**记录时间**: {time.strftime('%Y-%m-%d %H:%M:%SZ', time.gmtime())}",
            "**训练目标**: Causal LM + Fill-in-the-Middle (FIM) 双向代码因果建模",
            gpu_line,
            "",
            "---",
            "",
            "## 1. 关键检查点与验证损失指标",
            "| Checkpoint 步数 | 训练损失 (Train Loss) | 验证损失 (Val Loss) | 学习率 | 状态 |",
            "| :---: | :---: | :---: | :---: | :---: |",
        ]

        for entry in self.history:
            if entry["val_loss"] is not None:
                lines.append(
                    f"| Step {entry['step']:,} | {entry['train_loss']} | {entry['val_loss']} | "
                    f"{entry['learning_rate']} | **SAVED & VALIDATED** |"
                )

        lines.extend([
            "",
            "---",
            "",
            "## 2. Checkpoint 集合归档列表",
        ] + [f"- `{ckpt}`" for ckpt in checkpoints] + [
            "",
            "---",
            "",
            "## 3. 预训练过程收敛性结论（由 history 实算）",
            f"- 判据: **{verdict['verdict']}**（n={verdict['n_steps']}）",
            f"- 依据: {verdict['reason']}",
            f"- 全周期日志: `{self.log_path}`",
            "",
        ])
        if verdict["verdict"] == "LOSS_DECREASING":
            lines.append(
                f"**结论**: 训练损失 {verdict['first_loss']} → {verdict['last_loss']} 下降；"
                "验证损失未测时不得宣称已验证收敛。"
            )
        else:
            lines.append(f"**结论**: **{verdict['verdict']}** — 不满足进入能力验证阶段的条件。")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")