"""Unit tests for Training Health Monitor and Alert System."""

import os
import glob
import tempfile
import pytest
# torch 是可选训练依赖：无 torch 的推理主机上跳过本模块，而不是让收集阶段中断。
pytest.importorskip("torch")
import torch
from virtu_omni.config import MonitorConfig
from virtu_omni.training.monitor import TrainingHealthMonitor


def test_monitor_nominal_stats():
    monitor = TrainingHealthMonitor()
    for val_l in [4.5, 4.4, 4.35, 4.3, 4.28]:
        is_spike, msg = monitor.update_loss_stats(val_l)
        assert not is_spike


def test_monitor_loss_spike_detection():
    monitor = TrainingHealthMonitor(MonitorConfig(loss_spike_sigma_threshold=2.0))
    # Warmup with small variance
    for _ in range(15):
        monitor.update_loss_stats(4.0)
    # Inject large loss spike
    is_spike, msg = monitor.update_loss_stats(15.0)
    assert is_spike
    assert "Loss Spike Detected" in msg


def test_monitor_nan_loss():
    monitor = TrainingHealthMonitor()
    is_nan, msg = monitor.update_loss_stats(float("nan"))
    assert is_nan
    assert "Numerical Instability" in msg


def test_monitor_emergency_checkpoint():
    with tempfile.TemporaryDirectory() as tmp_dir:
        emergency_dir = os.path.join(tmp_dir, "emergency")
        cfg = MonitorConfig(emergency_checkpoint_dir=emergency_dir)
        monitor = TrainingHealthMonitor(cfg)
        model = torch.nn.Linear(10, 2)
        # Trigger emergency pause
        monitor._trigger_emergency_pause(step=42, model=model, optimizer=None, reason="Unit test trigger")
        assert monitor.is_paused
        files = glob.glob(os.path.join(emergency_dir, "*.pt"))
        assert len(files) == 1
        assert "step_42" in files[0]
