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
    ("查看工作区目录与最新生成文件", "ls -lart /root/workspace/virtu/"),
    ("检查训练进程的实时日志或输出", "tail -n 35 /root/workspace/virtu/training.log 2>/dev/null || tail -n 35 /root/workspace/virtu/train.log 2>/dev/null || ps aux | grep train_virtu_toolcall"),
    ("检查虚拟显存与占用率", "nvidia-smi"),
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
