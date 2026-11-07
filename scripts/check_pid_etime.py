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
    ("进程运行时间与状态", "ps -p 13671 -o pid,stat,etime,time,%cpu,%mem,cmd"),
    ("检查 virtu_toolcall_lora 目录中的最新变动", "ls -lart /root/workspace/virtu/virtu_toolcall_lora"),
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
