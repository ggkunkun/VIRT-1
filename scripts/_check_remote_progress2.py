#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Probe the RUNNING job's real trainer_state + recent log tail."""
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
import _ssh_damodel as S

remote = r'''
echo "=== RUNNING JOB trainer_state ==="
ts=/root/virtu_train/out/virtu_hardened_v1_lora/trainer_state.json
if [ -f "$ts" ]; then cat "$ts"; else echo "NO $ts"; fi
echo
echo "=== LOG TAIL (last 25 lines) ==="
tail -n 25 /root/virtu_train/logs/train.log 2>/dev/null || echo "NO train.log"
echo "=== LOG HEAD (first 20 lines) ==="
head -n 20 /root/virtu_train/logs/train.log 2>/dev/null
echo "=== ls output dir ==="
ls -la /root/virtu_train/out/virtu_hardened_v1_lora/ 2>/dev/null
'''
out, err, rc = S.run(remote, timeout=90)
print(out)
if err.strip():
    print("ERR:", err)
print("RC:", rc)
