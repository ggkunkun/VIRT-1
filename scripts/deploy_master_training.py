"""Deploy Master Training Dataset and Code to Damodel (2xL40S) and Launch Fine-Tuning."""

import os
import sys
import time
import tarfile
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


def make_tarfile(output_filename, source_dir):
    with tarfile.open(output_filename, "w:gz") as tar:
        tar.add(source_dir, arcname=os.path.basename(source_dir))


def main():
    print(f"Connecting to Damodel SSH {USER}@{HOST}:{PORT} ...")
    client = get_ssh_client()
    print("[SUCCESS] SSH Connected.")

    # 1. Create remote directory tree
    dirs = [
        f"{REMOTE_DIR}",
        f"{REMOTE_DIR}/damodel_cad_cam_tuning/dataset",
        f"{REMOTE_DIR}/checkpoints",
        f"{REMOTE_DIR}/checkpoints/cad_cam_six_software_lora",
        f"{REMOTE_DIR}/scripts",
        f"{REMOTE_DIR}/benchmarks",
    ]
    client.exec_command(f"mkdir -p {' '.join(dirs)}")
    time.sleep(1)

    sftp = client.open_sftp()

    # 2. Upload master training dataset
    local_data = os.path.join(WORKSPACE_DIR, "damodel_cad_cam_tuning", "dataset", "master_cad_cam_six_software_train.jsonl")
    remote_data = f"{REMOTE_DIR}/damodel_cad_cam_tuning/dataset/master_cad_cam_six_software_train.jsonl"
    print(f"[Upload] Master Dataset: {local_data} ({os.path.getsize(local_data):,} bytes) -> {remote_data}")
    sftp.put(local_data, remote_data)

    # 3. Upload blind test dataset
    local_blind = os.path.join(WORKSPACE_DIR, "damodel_cad_cam_tuning", "dataset", "wish_parametric_blind_test.jsonl")
    remote_blind = f"{REMOTE_DIR}/damodel_cad_cam_tuning/dataset/wish_parametric_blind_test.jsonl"
    print(f"[Upload] Blind Test: {local_blind} -> {remote_blind}")
    sftp.put(local_blind, remote_blind)

    # 4. Upload training script
    local_train_py = os.path.join(WORKSPACE_DIR, "scripts", "train_master_cad_cam_2xl40s.py")
    remote_train_py = f"{REMOTE_DIR}/scripts/train_master_cad_cam_2xl40s.py"
    print(f"[Upload] Train Script: {local_train_py} -> {remote_train_py}")
    sftp.put(local_train_py, remote_train_py)

    # 5. Upload blind test evaluator
    local_eval_py = os.path.join(WORKSPACE_DIR, "scripts", "run_blind_test_evaluator.py")
    remote_eval_py = f"{REMOTE_DIR}/scripts/run_blind_test_evaluator.py"
    print(f"[Upload] Evaluator: {local_eval_py} -> {remote_eval_py}")
    sftp.put(local_eval_py, remote_eval_py)

    # 6. Package and upload virtu_omni
    tar_path = os.path.join(WORKSPACE_DIR, "virtu_omni.tar.gz")
    print(f"[Packaging] Compressing virtu_omni -> {tar_path} ...")
    make_tarfile(tar_path, os.path.join(WORKSPACE_DIR, "virtu_omni"))
    sftp.put(tar_path, f"{REMOTE_DIR}/virtu_omni.tar.gz")
    if os.path.exists(tar_path):
        os.remove(tar_path)
    sftp.close()

    # Extract virtu_omni on remote
    client.exec_command(f"cd {REMOTE_DIR} && tar -xzf virtu_omni.tar.gz && rm -f virtu_omni.tar.gz")
    print("[SUCCESS] All files and packages deployed to remote.")

    # 7. Terminate any previous training process
    print("Terminating any prior training processes...")
    client.exec_command("pkill -9 -f train_master_cad_cam_2xl40s.py")
    time.sleep(2)

    # 8. Launch training in background with unbuffered logging
    log_path = f"{REMOTE_DIR}/train_2xl40s.log"
    client.exec_command(f"rm -f {log_path}")
    launch_cmd = f"cd {REMOTE_DIR} && nohup python3 -u {remote_train_py} > {log_path} 2>&1 & echo $!"
    print(f"[LAUNCH] Executing: {launch_cmd}")
    stdin, stdout, stderr = client.exec_command(launch_cmd)
    pid = stdout.read().decode().strip()
    print(f"[STARTED] Background training PID: {pid}")

    client.close()


if __name__ == "__main__":
    main()
