#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
只读云端环境核查（新实例 39473）。
SSH 密码只从 DAMODEL_PW 环境变量读取，不打印、不落盘到别处。
用法（项目根目录 D:/Virtu模型）：
  "D:/Virtu模型/.venv/Scripts/python.exe" scripts/_probe_cloud.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# 必须在 import _ssh_damodel 之前设置好连接参数（该模块在 import 时读取）
os.environ["DAMODEL_HOST"] = os.environ.get("DAMODEL_HOST", "cn-north-b.ssh.damodel.com")
os.environ["DAMODEL_PORT"] = os.environ.get("DAMODEL_PORT", "41858")
os.environ["DAMODEL_USER"] = os.environ.get("DAMODEL_USER", "root")
sys.path.insert(0, HERE)
import _ssh_damodel as S

CMDS = [
    'echo "== whoami/host =="; whoami; hostname; uname -a',
    'echo "== gpu =="; nvidia-smi --query-gpu=name,memory.total,memory.used,utilization.gpu --format=csv 2>&1 | head -6',
    'echo "== disk =="; df -h / 2>/dev/null | tail -2',
    'echo "== virtu_train tree =="; ls -la /root/virtu_train 2>/dev/null; echo "--- out ---"; ls -la /root/virtu_train/out 2>/dev/null',
    'echo "== train scripts =="; ls -la /root/virtu_train/scripts/*.py 2>/dev/null',
    'echo "== py/torch =="; which python3; python3 -c "import torch,transformers; print(\\"torch\\",torch.__version__,\\"cuda\\",torch.cuda.is_available())" 2>&1 | head -3',
    'echo "== base model? =="; ls -d /root/virtu_train/models/*qwen* 2>/dev/null; find /root -maxdepth 4 -iname "*qwen3*" -type d 2>/dev/null | head',
    'echo "== running procs =="; ps aux | grep -E "cloud_launch|train_qwen|python" | grep -v grep | head',
]

try:
    for c in CMDS:
        out, err, rc = S.run(c, timeout=120)
        sys.stdout.write(out)
        if err.strip():
            sys.stderr.write("[ERR] " + err.strip()[:500] + "\n")
    print("\nPROBE_OK")
except Exception as e:
    sys.stderr.write(f"PROBE_FAIL: {e!r}\n")
    sys.exit(1)
