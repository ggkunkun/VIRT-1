# -*- coding: utf-8 -*-
import os
import sys
import paramiko

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import damodel_env

HOST = "cn-north-b.ssh.damodel.com"
PORT = 34087
USER = "root"
PASS = damodel_env.password_for(HOST, PORT)

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(hostname=HOST, port=PORT, username=USER, password=PASS, timeout=30, banner_timeout=30)

cmds = [
    ("GPU 状态 (nvidia-smi)", "nvidia-smi"),
    ("训练进程详情", "ps aux | grep -E 'train_turnkey|run.sh' | grep -v grep"),
    ("实时训练日志 (最新 80 行)", "tail -n 80 /root/virtu_train/train.log 2>&1"),
    ("输出目录产物检查", "ls -la /root/virtu_train/ 2>&1; echo '--- output dir ---'; ls -la /root/virtu_train/output/ 2>/dev/null || echo 'output/ not created yet'"),
    ("磁盘空间检查", "df -h /root")
]

for title, cmd in cmds:
    print(f"\n{'='*25} {title} {'='*25}")
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    if out:
        print(out)
    if err:
        print(f"[STDERR]: {err}")

client.close()
