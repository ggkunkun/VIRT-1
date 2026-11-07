#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GPU 实例远程通道（paramiko）。连接信息走环境变量，避免把口令写死进仓库。

    set DAMODEL_HOST=cn-north-b.ssh.damodel.com
    set DAMODEL_PORT=44228
    set DAMODEL_USER=root
    set DAMODEL_PASS=...

    python scripts/remote_gpu.py probe          # 体检：GPU/磁盘/torch/ollama
    python scripts/remote_gpu.py exec  "<cmd>"
    python scripts/remote_gpu.py push  <local> <remote>
"""
from __future__ import annotations

import os
import sys
import time

import paramiko

HOST = os.environ.get("DAMODEL_HOST", "cn-north-b.ssh.damodel.com")
PORT = int(os.environ.get("DAMODEL_PORT", "44228"))
USER = os.environ.get("DAMODEL_USER", "root")
PASS = os.environ.get("DAMODEL_PASS", "")

CONNECT_TIMEOUT = 30


def connect():
    if not PASS:
        sys.exit("[FATAL] 未设 DAMODEL_PASS 环境变量")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(hostname=HOST, port=PORT, username=USER, password=PASS,
              timeout=CONNECT_TIMEOUT, allow_agent=False, look_for_keys=False)
    return c


def exec_remote(cmd, timeout=600, stream=True):
    """执行远程命令。返回 (exit_status, stdout, stderr)。"""
    c = connect()
    try:
        stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout, get_pty=False)
        out_lines = []
        if stream:
            for line in iter(stdout.readline, ""):
                print(line, end="", flush=True)
                out_lines.append(line)
        out = "".join(out_lines)
        err = stderr.read().decode("utf-8", errors="replace")
        if not stream:
            out = stdout.read().decode("utf-8", errors="replace")
        rc = stdout.channel.recv_exit_status()
        return rc, out, err
    finally:
        c.close()


def upload(local_path, remote_path):
    c = connect()
    try:
        sftp = c.open_sftp()
        print(f"[SFTP] {local_path} -> {remote_path}", flush=True)
        sftp.put(local_path, remote_path)
        sftp.close()
        print("[SFTP] OK")
    finally:
        c.close()


PROBE_CMD = r"""
echo "### 主机名"; hostname
echo "### GPU"; nvidia-smi --query-gpu=index,name,memory.total,memory.used,driver_version --format=csv 2>&1 | head -10
echo "### CPU/内存"; nproc; free -g | head -2
echo "### 磁盘"; df -h / /root /tmp 2>&1 | head -8
echo "### Python"; python -V 2>&1; which python python3 pip 2>&1
echo "### 版本表"; python - <<'PY' 2>&1
import importlib
for m in ["torch","transformers","datasets","accelerate","peft","bitsandbytes","flash_attn","modelscope"]:
    try:
        mod=importlib.import_module(m)
        if m=="torch":
            print(f"  torch {mod.__version__} cuda={mod.version.cuda} avail={mod.cuda.is_available()}")
        else:
            print(f"  {m} {getattr(mod,'__version__','?')}")
    except Exception as e:
        print(f"  {m} MISSING")
PY
echo "### Ollama"; which ollama 2>&1; ollama --version 2>&1 | head -2
echo "### llama.cpp"; ls -d /root/llama.cpp 2>&1
echo "### 已有工作区"; ls -la /root/workspace 2>&1 | head -12
"""


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    action = sys.argv[1]
    t0 = time.time()
    if action == "probe":
        exec_remote(PROBE_CMD, timeout=300)
    elif action == "exec":
        exec_remote(sys.argv[2], timeout=int(os.environ.get("CMD_TIMEOUT", "1800")))
    elif action == "push":
        upload(sys.argv[2], sys.argv[3])
    else:
        print(__doc__)
        sys.exit(1)
    print(f"\n[remote_gpu] {action} 用时 {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
