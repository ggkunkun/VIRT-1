"""Launch comprehensive CAD/CAM/CAE training on DAMODEL L40S."""

import os
import time
import sys
import paramiko

sys.stdout.reconfigure(encoding="utf-8")

HOST = os.environ.get("DAMODEL_HOST", "cn-north-b.ssh.damodel.com")
PORT = int(os.environ.get("DAMODEL_PORT", "40526"))
USER = os.environ.get("DAMODEL_USER", "root")
PASS = os.environ.get("DAMODEL_PASS", "")
if not PASS:
    raise SystemExit(
        "[FATAL] 未设置 DAMODEL_PASS 环境变量。\n"
        "该实例的明文口令曾硬编码在源码并进入 git 历史，必须先轮换密码，\n"
        "再通过 $env:DAMODEL_PASS = '<新密码>' 注入，不要再写回源码。"
    )

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=20)
print("[1] SSH Connected.")

cmd = "cd /root/cad_cam_finetune && rm -f train.log && nohup python3 -u train_cad_cam_l40s.py > train.log 2>&1 & echo $!"
stdin, stdout, stderr = client.exec_command(cmd)
pid = stdout.read().decode().strip()
print(f"[2] Background training started, PID: {pid}")

time.sleep(12)

stdin, stdout, stderr = client.exec_command("ps aux | grep train_cad_cam")
ps_out = stdout.read().decode().strip()
print(f"[3] Process status:\n{ps_out}")

stdin, stdout, stderr = client.exec_command("tail -n 20 /root/cad_cam_finetune/train.log")
log_out = stdout.read().decode().strip()
print(f"[4] Initial train.log:\n{log_out}")

stdin, stdout, stderr = client.exec_command("nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,power.draw --format=csv,noheader")
gpu_out = stdout.read().decode().strip()
print(f"[5] GPU Status:\n{gpu_out}")

client.close()
