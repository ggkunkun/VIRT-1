"""Deploy and Launch UG 888 Teacher-Guided Agent Training on Damodel GPU 1."""

import os
import sys
import time
import paramiko

sys.stdout.reconfigure(encoding="utf-8")

HOST = "cn-north-b.ssh.damodel.com"
PORT = 42688
USER = "root"
PASS = os.environ.get("DAMODEL_PASS", "")

WORKSPACE_DIR = r"D:\Virtu模型"
REMOTE_DIR = "/root/workspace/Virtu"


def get_ssh_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=HOST, port=PORT, username=USER, password=PASS, timeout=30)
    return client


def main():
    print(f"Connecting to Damodel SSH {USER}@{HOST}:{PORT} ...")
    client = get_ssh_client()
    print("[SUCCESS] SSH Connected.")

    # 1. Ensure remote directories exist
    dirs = [
        f"{REMOTE_DIR}/damodel_cad_cam_tuning/dataset",
        f"{REMOTE_DIR}/checkpoints/ug_teacher_guided_agent_lora",
        f"{REMOTE_DIR}/scripts",
    ]
    client.exec_command(f"mkdir -p {' '.join(dirs)}")
    time.sleep(1)

    # 2. Release GPU 1 if any stale training process remains
    print("Checking and releasing GPU 1...")
    client.exec_command("pkill -9 -f train_omni_autonomous_agent.py; pkill -9 -f train_ug_teacher_guided_agent.py")
    time.sleep(2)

    sftp = client.open_sftp()

    # 3. Upload blended dataset
    local_data = os.path.join(WORKSPACE_DIR, "damodel_cad_cam_tuning", "dataset", "ug_teacher_student_omni_train.jsonl")
    remote_data = f"{REMOTE_DIR}/damodel_cad_cam_tuning/dataset/ug_teacher_student_omni_train.jsonl"
    print(f"[Upload] Teacher-Student Dataset: {local_data} ({os.path.getsize(local_data):,} bytes) -> {remote_data}")
    sftp.put(local_data, remote_data)

    # 4. Upload training script
    local_train_py = os.path.join(WORKSPACE_DIR, "scripts", "train_ug_teacher_guided_agent.py")
    remote_train_py = f"{REMOTE_DIR}/scripts/train_ug_teacher_guided_agent.py"
    print(f"[Upload] Train Script -> {remote_train_py}")
    sftp.put(local_train_py, remote_train_py)

    sftp.close()
    print("[SUCCESS] Dataset and training scripts deployed to cloud.")

    # 5. Launch training on GPU 1
    log_path = f"{REMOTE_DIR}/train_ug_teacher.log"
    client.exec_command(f"rm -f {log_path}")
    launch_cmd = f"cd {REMOTE_DIR} && CUDA_VISIBLE_DEVICES=1 nohup python3 -u {remote_train_py} > {log_path} 2>&1 & echo $!"
    print(f"[LAUNCH] Executing on GPU 1: {launch_cmd}")
    stdin, stdout, stderr = client.exec_command(launch_cmd)
    pid = stdout.read().decode().strip()
    print(f"[STARTED] Background UG Teacher-Guided Agent training PID: {pid}")

    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
