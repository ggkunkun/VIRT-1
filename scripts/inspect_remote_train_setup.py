# -*- coding: utf-8 -*-
import sys
import paramiko
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import damodel_env

sys.stdout.reconfigure(encoding='utf-8')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
host, port, user, password = damodel_env.load()
client.connect(host, port=port, username=user, password=password, timeout=15)

cmds = [
    "cat /root/workspace/virtu/run_train.sh",
    "cat /root/workspace/virtu/handoff_manifest.json",
    "ls -la /root/workspace/virtu/scripts",
    "ls -la /root/workspace/virtu/virtu_toolcall_lora",
    "ls -la /root/workspace/virtu/data"
]

for cmd in cmds:
    print(f"=== {cmd} ===")
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='ignore').strip()
    if out:
        print(out)
    print()

client.close()
