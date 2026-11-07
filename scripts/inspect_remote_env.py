# -*- coding: utf-8 -*-
import sys
import paramiko
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import damodel_env

sys.stdout.reconfigure(encoding='utf-8')

host, port, user, password = damodel_env.load()
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, port=port, username=user, password=password, timeout=15)

commands = [
    ("Check Conda / Pythons", "which conda; conda info --envs 2>/dev/null; which python; which python3; find / -name python 2>/dev/null | grep -E 'conda|venv|bin/python' | head -n 20"),
    ("Check /root/workspace", "ls -la /root/workspace"),
    ("Check Qwen models in /root/public-storage/model", "ls -la /root/public-storage/model | grep -i qwen")
]

for title, cmd in commands:
    print(f"=== {title} ===")
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='ignore')
    if out:
        print(out.strip())
    print()

client.close()
