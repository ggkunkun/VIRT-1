# -*- coding: utf-8 -*-
"""
remote_damodel_mgr.py — 管理 Damodel 远程 GPU 机器探测、部署、训练与产物回传
"""

import os
import sys
import time
import paramiko

import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import damodel_env

HOST = "cn-north-b.ssh.damodel.com"
PORT = 44228
USER = "root"
PASS = damodel_env.password_for(HOST, PORT)


def get_ssh_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=HOST, port=PORT, username=USER, password=PASS, timeout=20)
    return client


def probe():
    client = get_ssh_client()
    print("[SUCCESS] Connected to Damodel GPU instance!")
    
    cmds = [
        ("NVIDIA-SMI 显卡配置", "nvidia-smi"),
        ("磁盘空间", "df -h"),
        ("Python 与 PyTorch 环境", "python3 -c \"import torch; print('PyTorch:', torch.__version__, '| CUDA available:', torch.cuda.is_available(), '| Device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None', '| VRAM (GB):', round(torch.cuda.get_device_properties(0).total_memory/1e9, 2) if torch.cuda.is_available() else 0)\""),
        ("关键依赖检查", "python3 -c \"for m in ['transformers', 'peft', 'datasets', 'accelerate', 'bitsandbytes', 'modelscope']: try: mod = __import__(m); print(f'  {m}: {getattr(mod, \\\"__version__\\\", \\\"ok\\\")}')\n except Exception as e: print(f'  {m}: NOT INSTALLED ({e})')\""),
        ("预置公共模型目录", "ls -ld /root/public-storage/model/* 2>/dev/null || true"),
        ("Qwen 预置模型", "ls -ld /root/public-storage/model/Qwen/* 2>/dev/null || true"),
        ("本地模型存储", "ls -ld /root/models/* 2>/dev/null || true"),
    ]
    
    for title, cmd in cmds:
        print(f"\n>>> {title} <<<")
        stdin, stdout, stderr = client.exec_command(cmd)
        out = stdout.read().decode("utf-8", errors="ignore").strip()
        err = stderr.read().decode("utf-8", errors="ignore").strip()
        if out:
            print(out)
        if err:
            print(f"[STDERR]: {err}")
            
    client.close()


if __name__ == "__main__":
    probe()
