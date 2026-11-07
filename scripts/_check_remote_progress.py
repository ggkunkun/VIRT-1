#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-shot remote training progress probe (non-destructive)."""
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
import _ssh_damodel as S

remote = r'''
echo "=== PROC ==="
ps -eo pid,etime,cmd 2>/dev/null | grep -E "train_.*\.py" | grep -v grep || echo NO_TRAIN_PROC
echo "=== GPU ==="
nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader 2>/dev/null || echo NO_NVIDIA
echo "=== STATUS FILES ==="
for f in /root/virtu_train/TRAIN_STATUS.json /data/virtu_train/TRAIN_STATUS.json /root/autodl-tmp/virtu_train/TRAIN_STATUS.json /workspace/virtu_train/TRAIN_STATUS.json; do [ -f "$f" ] && { echo "-- $f --"; cat "$f"; }; done
echo "=== TRAINER_STATE (first match) ==="
ts=$(find /root /data -maxdepth 7 -name trainer_state.json 2>/dev/null | head -1)
if [ -n "$ts" ]; then echo "-- $ts --"; cat "$ts"; else echo "NO trainer_state.json found"; fi
echo "=== RECEIPTS ==="
for r in /root/virtu_train/checkpoints/cad_cam_boundary_lora/training_receipt.json /root/virtu_train/out/virtu_hardened_v1_lora/training_receipt.json; do [ -f "$r" ] && { echo "-- $r --"; cat "$r"; } || echo "MISSING $r"; done
echo "=== DONE FLAG ==="
ls -la /root/virtu_train/DONE.flag /data/virtu_train/DONE.flag 2>/dev/null || echo "NO DONE.flag"
'''
out, err, rc = S.run(remote, timeout=90)
print(out)
if err.strip():
    print("ERR:", err)
print("RC:", rc)
