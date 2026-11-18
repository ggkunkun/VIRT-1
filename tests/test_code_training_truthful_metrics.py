#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""反证测试：virtu_code 训练链假测量修复（2026-11-16，AGENTS.md §8 测量宪法）。

修复前的三处假测量（均可植入坏样本复现）：
  T1  trainer.train_steps 用 `val_loss = loss_val * 0.98` 冒充验证损失；
  T2  吞吐 `numel()/0.05` 硬编码步时、GPU 利用率硬编码 88.5%；
  T3  monitor.export_report 硬编码「88.5% 满足工业标准」「损失平稳下降」
      「多卡通信重叠」并无条件 **APPROVED** —— 空历史/上升损失/NaN 也照样批准。

本文件保证：未测项记 None/未测；报告结论由 history 实算；坏轨迹必须不得批准。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

import pytest
# torch 是可选训练依赖：无 torch 的推理主机上跳过本模块，而不是让收集阶段中断。
pytest.importorskip("torch")
import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from virtu_code.config import CodeTrainingConfig  # noqa: E402
from virtu_code.training.model import CodeTransformerLM  # noqa: E402
from virtu_code.training.trainer import DistributedCodeTrainer  # noqa: E402
from virtu_code.training.monitor import CodeTrainingMonitor  # noqa: E402


def _tiny_trainer(tmp_dir: str) -> DistributedCodeTrainer:
    cfg = CodeTrainingConfig(
        hidden_dim=64, intermediate_dim=128, num_layers=1,
        num_attention_heads=2, num_kv_heads=1,
        checkpoint_dir=os.path.join(tmp_dir, "ckpts"),
        training_log_path=os.path.join(tmp_dir, "train_log.jsonl"),
    )
    model = CodeTransformerLM(cfg, vocab_size=500)
    return DistributedCodeTrainer(config=cfg, model=model)


def _batch_iter():
    while True:
        ids = torch.randint(0, 500, (2, 16))
        yield {"input_ids": ids, "labels": ids.clone()}


# ---------------------------------------------------------------------------
# T1/T2 trainer：val_loss 未测就是 None；吞吐实测；GPU 利用率不编造
# ---------------------------------------------------------------------------
def test_trainer_never_fabricates_val_loss():
    with tempfile.TemporaryDirectory() as tmp:
        trainer = _tiny_trainer(tmp)
        trainer.train_steps(_batch_iter(), total_steps=2, checkpoint_interval=1)
        assert trainer.monitor.history, "no steps recorded"
        for rec in trainer.monitor.history:
            assert rec["val_loss"] is None, rec
            assert rec["gpu_utilization_pct"] is None, rec
            assert rec["throughput_tok_s"] > 0
        for ckpt in trainer.saved_checkpoints:
            payload = torch.load(ckpt, weights_only=False)
            assert payload["val_loss"] is None, payload["val_loss"]


def test_trainer_throughput_is_measured_not_hardcoded():
    """旧假值 = numel/0.05 = 640.0 tok/s 恒定；实测值必须随步时变化且量级合理。"""
    with tempfile.TemporaryDirectory() as tmp:
        trainer = _tiny_trainer(tmp)
        trainer.train_steps(_batch_iter(), total_steps=3, checkpoint_interval=3)
        tputs = [r["throughput_tok_s"] for r in trainer.monitor.history]
        assert len(tputs) == 3
        assert all(t > 0 for t in tputs)
        # 微型 CPU/CUDA 模型单步不可能恒等于假公式的 640.0
        assert not all(abs(t - 640.0) < 1e-6 for t in tputs), tputs


# ---------------------------------------------------------------------------
# T3 monitor：结论由数据驱动，坏轨迹不得批准
# ---------------------------------------------------------------------------
def _monitor_with(tmp: str, losses) -> CodeTrainingMonitor:
    m = CodeTrainingMonitor(log_path=os.path.join(tmp, "log.jsonl"))
    for i, lv in enumerate(losses):
        m.record_step(step=i + 1, train_loss=lv, lr=1e-4, throughput=100.0)
    return m


def test_empty_history_is_not_approved():
    with tempfile.TemporaryDirectory() as tmp:
        m = CodeTrainingMonitor(log_path=os.path.join(tmp, "log.jsonl"))
        v = m.convergence_verdict()
        assert v["verdict"] == "INSUFFICIENT_EVIDENCE", v
        out = os.path.join(tmp, "report.md")
        m.export_report([], out)
        content = open(out, encoding="utf-8").read()
        assert "APPROVED" not in content
        assert "88.5" not in content
        assert "未测" in content


def test_single_step_is_insufficient_evidence():
    with tempfile.TemporaryDirectory() as tmp:
        m = _monitor_with(tmp, [2.0])
        assert m.convergence_verdict()["verdict"] == "INSUFFICIENT_EVIDENCE"


def test_rising_loss_is_not_converged():
    with tempfile.TemporaryDirectory() as tmp:
        m = _monitor_with(tmp, [1.0, 1.5, 2.5])
        v = m.convergence_verdict()
        assert v["verdict"] == "NOT_CONVERGED", v
        out = os.path.join(tmp, "report.md")
        m.export_report([], out)
        content = open(out, encoding="utf-8").read()
        assert "APPROVED" not in content
        assert "NOT_CONVERGED" in content


def test_nan_loss_fails():
    with tempfile.TemporaryDirectory() as tmp:
        m = _monitor_with(tmp, [2.0, float("nan"), 1.0])
        assert m.convergence_verdict()["verdict"] == "FAILED"


def test_decreasing_loss_reports_trend_not_blanket_approval():
    with tempfile.TemporaryDirectory() as tmp:
        m = _monitor_with(tmp, [3.0, 2.0, 1.0])
        v = m.convergence_verdict()
        assert v["verdict"] == "LOSS_DECREASING", v
        out = os.path.join(tmp, "report.md")
        m.export_report(["ckpt_1.pt"], out)
        content = open(out, encoding="utf-8").read()
        assert "LOSS_DECREASING" in content
        assert "88.5" not in content
        assert "多卡通信重叠" not in content


def test_measured_gpu_utilization_is_reported_as_measured():
    with tempfile.TemporaryDirectory() as tmp:
        m = CodeTrainingMonitor(log_path=os.path.join(tmp, "log.jsonl"))
        m.record_step(step=1, train_loss=2.0, lr=1e-4, throughput=100.0, gpu_utilization=72.0)
        m.record_step(step=2, train_loss=1.5, lr=1e-4, throughput=100.0, gpu_utilization=76.0)
        out = os.path.join(tmp, "report.md")
        m.export_report([], out)
        content = open(out, encoding="utf-8").read()
        assert "74.0%" in content, content
        assert "n=2" in content


def test_unmeasured_gpu_never_written_as_number():
    with tempfile.TemporaryDirectory() as tmp:
        m = _monitor_with(tmp, [2.0, 1.0])
        for rec in m.history:
            assert rec["gpu_utilization_pct"] is None
        lines = open(m.log_path, encoding="utf-8").read().splitlines()
        for ln in lines:
            assert json.loads(ln)["gpu_utilization_pct"] is None