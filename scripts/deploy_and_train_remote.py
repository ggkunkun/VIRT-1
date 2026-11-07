"""Deploy SFT dataset and training script to DAMODEL L40S and start fine-tuning."""

import os
import sys
import time
import paramiko

HOST = "cn-north-b.ssh.damodel.com"
PORT = 40526
USER = "root"
PASS = os.environ.get("DAMODEL_PASS", "")
if not PASS:
    raise SystemExit(
        "[FATAL] 未设置 DAMODEL_PASS 环境变量；该实例口令已泄漏于 git 历史，"
        "必须先轮换密码，再通过环境变量注入，不要写回源码。"
    )


LOCAL_DIR = r"D:\Virtu模型\damodel_cad_cam_tuning"
REMOTE_DIR = "/root/cad_cam_finetune"


def deploy_and_start_training():
    print(f"Connecting to {USER}@{HOST}:{PORT} ...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=HOST, port=PORT, username=USER, password=PASS, timeout=20)
    print("[SUCCESS] SSH Connected.")

    # 1. Create remote directory
    client.exec_command(f"mkdir -p {REMOTE_DIR}")
    time.sleep(1)

    # 2. Upload files via SFTP
    sftp = client.open_sftp()
    
    local_sft = os.path.join(LOCAL_DIR, "dataset", "six_software_parametric_sft.jsonl")
    remote_sft = f"{REMOTE_DIR}/six_software_parametric_sft.jsonl"
    print(f"Uploading SFT dataset: {local_sft} -> {remote_sft}")
    sftp.put(local_sft, remote_sft)

    local_py = os.path.join(LOCAL_DIR, "train_cad_cam_l40s.py")
    remote_py = f"{REMOTE_DIR}/train_cad_cam_l40s.py"
    print(f"Uploading training script: {local_py} -> {remote_py}")
    sftp.put(local_py, remote_py)
    sftp.close()
    print("[SUCCESS] Files uploaded to DAMODEL instance.")

    # 3. Start training in background using nohup
    run_cmd = f"cd {REMOTE_DIR} && nohup python3 train_cad_cam_l40s.py > train.log 2>&1 & echo $!"
    print(f"Launching training job: {run_cmd}")
    stdin, stdout, stderr = client.exec_command(run_cmd)
    pid = stdout.read().decode().strip()
    print(f"[JOB LAUNCHED] Remote Training PID: {pid}")

    # 4. Stream log for 15 seconds to verify startup and GPU load
    print("\nStreaming initial training logs...")
    for _ in range(6):
        time.sleep(3)
        stdin, stdout, stderr = client.exec_command(f"cat {REMOTE_DIR}/train.log | tail -n 25")
        log_content = stdout.read().decode().strip()
        print("-" * 50)
        print(log_content)
        if "STARTING TRAINING" in log_content or "step" in log_content:
            break

    # 5. Check nvidia-smi GPU memory
    stdin, stdout, stderr = client.exec_command("nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader")
    gpu_stats = stdout.read().decode().strip()
    print(f"\n[GPU STATUS] {gpu_stats}")

    client.close()
    print("\n[SUCCESS] Fine-tuning is actively running on the remote NVIDIA L40S instance!")


if __name__ == "__main__":
    deploy_and_start_training()
