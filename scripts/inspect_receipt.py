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

stdin, stdout, stderr = client.exec_command("cat /root/workspace/virtu/virtu_toolcall_lora/training_receipt.json")
print(stdout.read().decode('utf-8', errors='ignore'))

stdin, stdout, stderr = client.exec_command("tail -n 25 /root/workspace/virtu/logs/train.log 2>/dev/null || ls -la /root/workspace/virtu/logs")
print(stdout.read().decode('utf-8', errors='ignore'))

client.close()
