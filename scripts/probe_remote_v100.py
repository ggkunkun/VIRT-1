import paramiko
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import damodel_env

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
host, port, user, password = damodel_env.load()
client.connect(host, port=port, username=user, password=password, timeout=60, banner_timeout=60)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    return stdout.read().decode('utf-8', errors='replace').strip()

print("=== Qwen models ===")
print(run("ls -la /root/public-storage/model/Qwen"))

print("=== CUDA / Driver ===")
print(run("nvidia-smi"))
print(run("nvcc --version 2>/dev/null || cat /usr/local/cuda/version.json 2>/dev/null"))

print("=== Check pre-cached packages ===")
print(run("ls -la /root/public-storage/package 2>/dev/null"))

client.close()
