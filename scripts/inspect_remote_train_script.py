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

stdin, stdout, stderr = client.exec_command("head -n 50 /root/workspace/virtu/scripts/train_virtu_toolcall.py")
print(stdout.read().decode('utf-8', errors='ignore'))

client.close()
