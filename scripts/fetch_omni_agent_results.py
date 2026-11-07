"""Fetch trained Omni Autonomous Industrial Agent weights from Damodel (L40S)."""

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

REMOTE_ADAPTER_DIR = "/root/workspace/Virtu/checkpoints/omni_autonomous_agent_lora"
LOCAL_TARGET = r"D:\Virtu模型\checkpoints\omni_autonomous_agent_lora"


def get_ssh_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=HOST, port=PORT, username=USER, password=PASS, timeout=30)
    return client


def fetch_all():
    print(f"Connecting to {USER}@{HOST}:{PORT} ...")
    client = get_ssh_client()
    sftp = client.open_sftp()

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

    os.makedirs(LOCAL_TARGET, exist_ok=True)

    import stat
    for fname in remote_files:
        r_path = f"{REMOTE_ADAPTER_DIR}/{fname}"
        try:
            r_stat = sftp.stat(r_path)
            if stat.S_ISDIR(r_stat.st_mode):
                print(f"[SKIP DIR] {fname}")
                continue
        except Exception:
            pass
        l_path = os.path.join(LOCAL_TARGET, fname)
        print(f"Downloading {fname} -> {l_path} ...")
        sftp.get(r_path, l_path)

    sftp.close()
    client.close()
    print(f"[SUCCESS] All Omni Agent artifacts synchronized to: {LOCAL_TARGET}")
    return True


if __name__ == "__main__":
    fetch_all()
