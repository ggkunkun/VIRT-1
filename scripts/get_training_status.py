"""Query remote training status and loss log."""

import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("cn-north-b.ssh.damodel.com", port=40526, username="root", password="m2A5jbYmbP")

# Get last 20 lines of train.log
stdin, stdout, stderr = client.exec_command("tail -n 20 /root/cad_cam_finetune/train.log")
lines = stdout.read().decode().strip()
print("=== TAIL TRAIN.LOG ===")
print(lines)

# Check GPU status
stdin, stdout, stderr = client.exec_command("nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,power.draw --format=csv,noheader")
gpu_stat = stdout.read().decode().strip()
print(f"\n=== GPU STATS ===\n{gpu_stat}")

# Check checkpoint files
stdin, stdout, stderr = client.exec_command("ls -la /root/cad_cam_finetune/output_checkpoints")
ckpts = stdout.read().decode().strip()
print(f"\n=== CHECKPOINTS DIR ===\n{ckpts}")

client.close()
