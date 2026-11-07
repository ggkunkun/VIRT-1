# -*- coding: utf-8 -*-
import sys
import paramiko
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import damodel_env

sys.stdout.reconfigure(encoding='utf-8')

host, port, user, password = damodel_env.load()
print(f"Connecting to {user}@{host}:{port} ...")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect(host, port=port, username=user, password=password, timeout=15)
    print("SSH connection successful!\n")
    
    commands = [
        ("GPU Information", "nvidia-smi"),
        ("Disk Space", "df -h"),
        ("Python & Torch", "python3 -c 'import torch; print(\"Torch:\", torch.__version__, \"CUDA available:\", torch.cuda.is_available(), \"Device:\", torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"None\")'"),
        ("Home Directory", "ls -la /root"),
        ("Check Public Storage / Models", "ls -la /root/public-storage 2>/dev/null || ls -la /root/models 2>/dev/null || echo 'No public-storage/models'")
    ]
    
    for title, cmd in commands:
        print(f"=== {title} ({cmd}) ===")
        stdin, stdout, stderr = client.exec_command(cmd)
        out = stdout.read().decode('utf-8', errors='ignore')
        err = stderr.read().decode('utf-8', errors='ignore')
        if out:
            print(out.strip())
        if err:
            print("STDERR:", err.strip())
        print()

finally:
    client.close()
