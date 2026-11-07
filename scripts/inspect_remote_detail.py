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
    "ls -d /root/*conda* /opt/*conda* /usr/local/*conda* 2>/dev/null",
    "cat /root/.bashrc | grep -E 'conda|PATH|export'",
    "ls -la /root/public-storage/model/Qwen 2>/dev/null || ls -la /root/public-storage/model | head -n 20",
    "ls -la /root/cad_cam_finetune 2>/dev/null || echo 'No cad_cam_finetune folder'",
    "ls -la /root/workspace"
]

for cmd in cmds:
    print(f"=== {cmd} ===")
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='ignore').strip()
    if out:
        print(out)
    print()

client.close()
