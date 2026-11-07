# -*- coding: utf-8 -*-
import paramiko

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import damodel_env

HOST = "cn-north-b.ssh.damodel.com"
PORT = 44228
USER = "root"
PASS = damodel_env.password_for(HOST, PORT)

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(hostname=HOST, port=PORT, username=USER, password=PASS, timeout=20)

cmds = [
    ("实时训练进度与 Loss 曲线", "tail -n 40 /root/workspace/virtu/logs/train.log"),
    ("训练产物目录", "ls -la /root/workspace/virtu/virtu_toolcall_lora/"),
    ("显卡最新状态", "nvidia-smi --query-gpu=utilization.gpu,utilization.memory,memory.used,memory.total,power.draw,temperature.gpu --format=csv"),
]

for title, cmd in cmds:
    print(f"\n>>> {title} <<<")
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode("utf-8", errors="ignore").strip()
    err = stderr.read().decode("utf-8", errors="ignore").strip()
    if out:
        print(out)
    if err:
        print(f"[ERR]: {err}")

client.close()
