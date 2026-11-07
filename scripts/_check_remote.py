#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _ssh_damodel as S

cmd = (
    "echo '=== uptime ==='; uptime; "
    "echo '=== disk /root ==='; df -h /root | tail -1; "
    "echo '=== virtu_train ==='; ls -la /root/virtu_train 2>/dev/null; "
    "echo '=== checkpoints ==='; ls -la /root/virtu_train/checkpoints 2>/dev/null; "
    "echo '=== model cache ==='; du -sh /root/.cache/modelscope 2>/dev/null; ls /root/.cache/modelscope 2>/dev/null | head; "
    "echo '=== running procs ==='; ps aux | grep -E 'train_qwen|cloud_launch|python3' | grep -v grep | head -20; "
    "echo '=== launch.log tail ==='; tail -n 50 /root/virtu_train/launch.log 2>/dev/null; "
    "echo '=== train.log tail ==='; tail -n 30 /root/virtu_train/train.log 2>/dev/null"
)
out, err, rc = S.run(cmd, timeout=60)
print(out)
if err.strip():
    print("STDERR:", err)
print("RC:", rc)
