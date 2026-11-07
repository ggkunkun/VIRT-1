"""Query remote training status and loss log."""

import os
import paramiko
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import damodel_env

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
DAMODEL_PASS = os.environ.get("DAMODEL_PASS", "")
if not DAMODEL_PASS:
    raise SystemExit(
        "[FATAL] 未设置 DAMODEL_PASS 环境变量；该实例口令已泄漏于 git 历史，"
        "必须先轮换密码，再通过环境变量注入，不要写回源码。"
    )

host, port, user, password = damodel_env.load()
client.connect(host, port=port, username=user, password=DAMODEL_PASS)

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
