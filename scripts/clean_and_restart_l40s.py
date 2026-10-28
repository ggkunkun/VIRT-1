"""Clean all stale processes on remote GPU and restart training cleanly."""

import time
import paramiko

HOST = "cn-north-b.ssh.damodel.com"
PORT = 40526
USER = "root"
PASS = "m2A5jbYmbP"
REMOTE_DIR = "/root/cad_cam_finetune"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(hostname=HOST, port=PORT, username=USER, password=PASS, timeout=20)
print("[1] Connected.")

# 1. Kill any existing python processes holding GPU memory
stdin, stdout, stderr = client.exec_command("killall -9 python python3 ; pkill -9 -f python ; sleep 2")
stdout.read()
print("[2] Killed existing python processes.")

# 2. Check GPU free memory
stdin, stdout, stderr = client.exec_command("nvidia-smi --query-gpu=memory.used,memory.free,memory.total --format=csv,noheader")
print("[3] GPU Memory after cleanup:", stdout.read().decode().strip())

# 3. Clean train.log and launch fresh training
stdin, stdout, stderr = client.exec_command(f"cd {REMOTE_DIR} && rm -f train.log && nohup python3 -u train_cad_cam_l40s.py > train.log 2>&1 & echo $!")
pid = stdout.read().decode().strip()
print(f"[4] Launched training job with PID: {pid}")

# 4. Wait 15 seconds and check log
time.sleep(15)
stdin, stdout, stderr = client.exec_command(f"tail -n 25 {REMOTE_DIR}/train.log")
print("[5] Initial log output:\n", stdout.read().decode())

# 5. Check GPU memory
stdin, stdout, stderr = client.exec_command("nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,power.draw --format=csv,noheader")
print("[6] GPU status:\n", stdout.read().decode())

client.close()
