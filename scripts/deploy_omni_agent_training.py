"""Deploy and Launch Omni Autonomous Industrial Agent Training on Damodel GPU."""

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
        f"{REMOTE_DIR}/checkpoints/omni_autonomous_agent_lora",
        f"{REMOTE_DIR}/data/tools",
        f"{REMOTE_DIR}/scripts",
    ]
    client.exec_command(f"mkdir -p {' '.join(dirs)}")
    time.sleep(1)

    # 2. Terminate previous completed evaluation on GPU 1 to release VRAM
    print("Releasing GPU 1 resources...")
    client.exec_command("pkill -9 -f run_blind_test_evaluator.py; pkill -9 -f train_master_cad_cam_2xl40s.py")
    time.sleep(2)

    sftp = client.open_sftp()

    # 3. Upload dataset
    local_data = os.path.join(WORKSPACE_DIR, "damodel_cad_cam_tuning", "dataset", "omni_autonomous_industrial_agent_train.jsonl")
    remote_data = f"{REMOTE_DIR}/damodel_cad_cam_tuning/dataset/omni_autonomous_industrial_agent_train.jsonl"
    print(f"[Upload] Master Dataset: {local_data} ({os.path.getsize(local_data):,} bytes) -> {remote_data}")
    sftp.put(local_data, remote_data)

    # 4. Upload tools schema
    local_tools = os.path.join(WORKSPACE_DIR, "data", "tools", "omni_autonomous_agent_tools.json")
    remote_tools = f"{REMOTE_DIR}/data/tools/omni_autonomous_agent_tools.json"
    print(f"[Upload] Tools Schema -> {remote_tools}")
    sftp.put(local_tools, remote_tools)

    # 5. Upload training script
    local_train_py = os.path.join(WORKSPACE_DIR, "scripts", "train_omni_autonomous_agent.py")
    remote_train_py = f"{REMOTE_DIR}/scripts/train_omni_autonomous_agent.py"
    print(f"[Upload] Train Script -> {remote_train_py}")
    sftp.put(local_train_py, remote_train_py)

    # 6. Package and upload updated virtu_omni
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

    # 7. Launch training on GPU 1
    log_path = f"{REMOTE_DIR}/train_omni_agent.log"
    client.exec_command(f"rm -f {log_path}")
    launch_cmd = f"cd {REMOTE_DIR} && CUDA_VISIBLE_DEVICES=1 nohup python3 -u {remote_train_py} > {log_path} 2>&1 & echo $!"
    print(f"[LAUNCH] Executing: {launch_cmd}")
    stdin, stdout, stderr = client.exec_command(launch_cmd)
    pid = stdout.read().decode().strip()
    print(f"[STARTED] Background Omni Agent training PID: {pid}")

    client.close()


if __name__ == "__main__":
    main()
