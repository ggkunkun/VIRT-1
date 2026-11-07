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
    "ls -la /root/workspace/virtu",
    "/opt/conda/bin/python -c 'import torch, transformers, peft, datasets; print(\"Torch:\", torch.__version__, \"CUDA:\", torch.cuda.is_available(), \"Device:\", torch.cuda.get_device_name(0)); print(\"Transformers:\", transformers.__version__, \"PEFT:\", peft.__version__)'",
    "cat /root/workspace/virtu/README.md 2>/dev/null || ls -la /root/workspace/virtu"
]

for cmd in cmds:
    print(f"=== {cmd} ===")
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='ignore').strip()
    err = stderr.read().decode('utf-8', errors='ignore').strip()
    if out:
        print(out)
    if err:
        print("STDERR:", err)
    print()

client.close()
