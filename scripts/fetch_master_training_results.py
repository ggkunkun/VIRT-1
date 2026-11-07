"""Fetch trained Master LoRA weights and evaluation report from Damodel (2xL40S)."""

import os
import sys
import time
import json
import paramiko

sys.stdout.reconfigure(encoding="utf-8")

HOST = "cn-north-b.ssh.damodel.com"
PORT = 42688
USER = "root"
PASS = os.environ.get("DAMODEL_PASS", "")

REMOTE_ADAPTER_DIR = "/root/workspace/Virtu/checkpoints/cad_cam_six_software_lora"
REMOTE_BENCHMARKS_DIR = "/root/workspace/Virtu/benchmarks"

LOCAL_TARGETS = [
    r"D:\Virtu模型\checkpoints\cad_cam_six_software_lora",
    r"D:\Virtu模型\checkpoints\damodel_l40s_cad_cam_lora",
]
LOCAL_BENCHMARKS = r"D:\Virtu模型\benchmarks"


def get_ssh_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=HOST, port=PORT, username=USER, password=PASS, timeout=30)
    return client


def fetch_all():
    print(f"Connecting to {USER}@{HOST}:{PORT} ...")
    client = get_ssh_client()
    sftp = client.open_sftp()

    # 1. Check if adapter files exist
    try:
        remote_files = sftp.listdir(REMOTE_ADAPTER_DIR)
        print(f"Found {len(remote_files)} files in {REMOTE_ADAPTER_DIR}: {remote_files}")
    except Exception as e:
        print(f"[WAIT] Remote adapter dir not ready yet: {e}")
        sftp.close()
        client.close()
        return False

    if "adapter_model.safetensors" not in remote_files:
        print("[WAIT] adapter_model.safetensors has not been saved yet.")
        sftp.close()
        client.close()
        return False

    # Download to first local target
    primary_local = LOCAL_TARGETS[0]
    os.makedirs(primary_local, exist_ok=True)

    for fname in remote_files:
        r_path = f"{REMOTE_ADAPTER_DIR}/{fname}"
        l_path = os.path.join(primary_local, fname)
        print(f"Downloading {fname} -> {l_path} ...")
        sftp.get(r_path, l_path)

    # Replicate to secondary local target
    secondary_local = LOCAL_TARGETS[1]
    os.makedirs(secondary_local, exist_ok=True)
    import shutil
    for fname in remote_files:
        src = os.path.join(primary_local, fname)
        dst = os.path.join(secondary_local, fname)
        shutil.copy2(src, dst)
    print(f"[COPIED] Replicated weights to {secondary_local}")

    # Fetch benchmark report if available
    try:
        bench_files = sftp.listdir(REMOTE_BENCHMARKS_DIR)
        os.makedirs(LOCAL_BENCHMARKS, exist_ok=True)
        for bf in bench_files:
            r_bf = f"{REMOTE_BENCHMARKS_DIR}/{bf}"
            l_bf = os.path.join(LOCAL_BENCHMARKS, bf)
            print(f"Downloading benchmark artifact {bf} -> {l_bf} ...")
            sftp.get(r_bf, l_bf)
    except Exception as e:
        print(f"[INFO] Benchmarks not ready yet: {e}")

    sftp.close()
    client.close()
    print("[SUCCESS] All artifacts fetched and synchronized successfully.")
    return True


if __name__ == "__main__":
    fetch_all()
