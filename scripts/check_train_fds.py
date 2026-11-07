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
    ("查看训练进程输出文件描述符", "ls -l /proc/13671/fd/"),
    ("检查父进程 13236 文件描述符", "ls -l /proc/13236/fd/"),
    ("搜索正在增长的日志文件", "find /root -name '*.log' -mmin -10 2>/dev/null || true"),
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
