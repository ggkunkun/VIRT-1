#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Targeted probe of the REAL training job (virtu_hardened_v1_lora)."""
import os, glob, json

ROOT = os.path.dirname(os.path.abspath(__file__))
import _ssh_damodel as S

remote = r'''
echo "=== REAL PROC (with full etime) ==="
ps -eo pid,lstart,etime,cmd 2>/dev/null | grep -E "train_virtu_v100.py" | grep -v grep || echo NO_TRAIN_PROC
echo "=== REAL trainer_state (virtu_hardened_v1_lora) ==="
ts=$(ls -t /root/virtu_train/out/virtu_hardened_v1_lora/checkpoint-*/trainer_state.json 2>/dev/null | head -1)
if [ -n "$ts" ]; then echo "-- $ts --"; python3 -c "import json,sys;d=json.load(open('$ts'));print('global_step=',d.get('global_step'),'max_steps=',d.get('max_steps'),'epoch=',d.get('epoch'),'loss_last=',(d.get('log_history') or [{}])[-1].get('loss'))"; else echo "NO real trainer_state.json"; fi
echo "=== REAL RECEIPT ==="
[ -f /root/virtu_train/out/virtu_hardened_v1_lora/training_receipt.json ] && cat /root/virtu_train/out/virtu_hardened_v1_lora/training_receipt.json || echo "MISSING real receipt"
echo "=== LOG TAIL (real job) ==="
L=/root/virtu_train/logs/train.log
[ -f "$L" ] && tail -n 5 "$L" || echo "NO LOG"
echo "=== DIR LIST out/virtu_hardened_v1_lora ==="
ls -la /root/virtu_train/out/virtu_hardened_v1_lora/ 2>/dev/null | head -30 || echo "NO DIR"
'''
out, err, rc = S.run(remote, timeout=90)
print(out)
if err.strip():
    print("ERR:", err)
print("RC:", rc)
