"""Deploy 1200-sample comprehensive Wish-Style dataset and launch training on DAMODEL L40S."""

import os
import sys
import time
import paramiko

sys.stdout.reconfigure(encoding="utf-8")

HOST = "cn-north-b.ssh.damodel.com"
PORT = 40526
USER = "root"
PASS = "m2A5jbYmbP"

LOCAL_DIR = r"D:\Virtu模型\damodel_cad_cam_tuning"
REMOTE_DIR = "/root/cad_cam_finetune"


def deploy_and_launch():
    print(f"Connecting to {USER}@{HOST}:{PORT} ...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=HOST, port=PORT, username=USER, password=PASS, timeout=30)
    print("[SUCCESS] SSH Connected.")

    sftp = client.open_sftp()

    # 1. Upload the 1200-sample comprehensive dataset
    local_sft = os.path.join(LOCAL_DIR, "dataset", "comprehensive_wish_cad_cam_sft_1200.jsonl")
    remote_sft = f"{REMOTE_DIR}/comprehensive_wish_cad_cam_sft_1200.jsonl"
    print(f"Uploading comprehensive dataset: {local_sft} ({os.path.getsize(local_sft):,} bytes) -> {remote_sft}")
    sftp.put(local_sft, remote_sft)
    print("[OK] Dataset uploaded.")

    # 2. Upload training script
    local_py = os.path.join(LOCAL_DIR, "train_cad_cam_l40s.py")
    remote_py = f"{REMOTE_DIR}/train_cad_cam_l40s.py"
    print(f"Uploading training script: {local_py} -> {remote_py}")
    sftp.put(local_py, remote_py)
    print("[OK] Training script uploaded.")

    sftp.close()

    # 3. Kill any lingering python train processes on remote
    print("Stopping any previous training processes...")
    client.exec_command("pkill -9 -f train_cad_cam_l40s.py")
    time.sleep(2)

    # 4. Clean previous log and launch training
    print("Launching comprehensive fine-tuning on NVIDIA L40S...")
    run_cmd = f"cd {REMOTE_DIR} && rm -f train.log && nohup python3 -u train_cad_cam_l40s.py > train.log 2>&1 & echo $!"
    stdin, stdout, stderr = client.exec_command(run_cmd)
    pid = stdout.read().decode().strip()
    print(f"[JOB LAUNCHED] Remote PID: {pid}")

    # 5. Monitor startup for 20 seconds
    print("\nStreaming startup logs...")
    for _ in range(8):
        time.sleep(3)
        stdin, stdout, stderr = client.exec_command(f"tail -n 20 {REMOTE_DIR}/train.log")
        log_out = stdout.read().decode().strip()
        print("-" * 50)
        print(log_out)
        if "STARTING COMPREHENSIVE TRAINING" in log_out or "it/s" in log_out:
            break

    # 6. Check GPU stats
    stdin, stdout, stderr = client.exec_command("nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,power.draw --format=csv,noheader")
    gpu_stats = stdout.read().decode().strip()
    print(f"\n[GPU STATUS] {gpu_stats}")

    client.close()
    print("\n[SUCCESS] Comprehensive Wish-Style training is actively running on DAMODEL L40S!")


if __name__ == "__main__":
    deploy_and_launch()
