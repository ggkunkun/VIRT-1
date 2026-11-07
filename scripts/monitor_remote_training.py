"""Monitor Damodel Remote 2xL40S Training Progress and GPU Stats."""

import os
import sys
import time
import paramiko

sys.stdout.reconfigure(encoding="utf-8")

HOST = "cn-north-b.ssh.damodel.com"
PORT = 42688
USER = "root"
PASS = os.environ.get("DAMODEL_PASS", "")
LOG_PATH = "/root/workspace/Virtu/train_2xl40s.log"


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=HOST, port=PORT, username=USER, password=PASS, timeout=30)

    # 1. Check if process is running
    stdin, stdout, stderr = client.exec_command("ps aux | grep -v grep | grep train_master_cad_cam_2xl40s.py")
    proc_info = stdout.read().decode().strip()
    if proc_info:
        print("[PROCESS ACTIVE]\n" + proc_info)
    else:
        print("[INFO] No active train_master_cad_cam_2xl40s.py process found.")

    # 2. Check GPU status
    stdin, stdout, stderr = client.exec_command("nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total,power.draw --format=csv,noheader")
    gpu_info = stdout.read().decode().strip()
    print("\n[GPU STATUS]\n" + gpu_info)

    # 3. Read latest log
    stdin, stdout, stderr = client.exec_command(f"tail -n 45 {LOG_PATH}")
    log_text = stdout.read().decode().strip()
    print(f"\n[LATEST LOG ({LOG_PATH})]\n" + ("-" * 60))
    print(log_text if log_text else "(Log is currently empty)")
    print("-" * 60)

    client.close()


if __name__ == "__main__":
    main()
