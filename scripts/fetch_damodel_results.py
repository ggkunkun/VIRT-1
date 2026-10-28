"""Fetch evaluation results, train log, and trained LoRA adapter from DAMODEL L40S."""

import os
import sys
import json
import paramiko

sys.stdout.reconfigure(encoding="utf-8")

HOST = "cn-north-b.ssh.damodel.com"
PORT = 40526
USER = "root"
PASS = "m2A5jbYmbP"

LOCAL_DIR = r"D:\Virtu模型\damodel_cad_cam_tuning"
LOCAL_CKPT_DIR = r"D:\Virtu模型\checkpoints\damodel_l40s_cad_cam_lora"
REMOTE_DIR = "/root/cad_cam_finetune"
REMOTE_FINAL_ADAPTER = f"{REMOTE_DIR}/output_checkpoints/cad_cam_six_software_lora_final"

os.makedirs(LOCAL_CKPT_DIR, exist_ok=True)
os.makedirs(LOCAL_DIR, exist_ok=True)

print(f"Connecting to {USER}@{HOST}:{PORT} ...")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(hostname=HOST, port=PORT, username=USER, password=PASS, timeout=30)
print("[SUCCESS] SSH Connected.")

sftp = client.open_sftp()

# 1. Download eval_results.json
remote_eval = f"{REMOTE_DIR}/eval_results.json"
local_eval = os.path.join(LOCAL_DIR, "eval_results.json")
print(f"Downloading {remote_eval} -> {local_eval}")
sftp.get(remote_eval, local_eval)
print(f"[OK] Downloaded eval_results.json ({os.path.getsize(local_eval):,} bytes)")

# 2. Download train.log
remote_log = f"{REMOTE_DIR}/train.log"
local_log = os.path.join(LOCAL_DIR, "train_damodel_l40s.log")
print(f"Downloading {remote_log} -> {local_log}")
sftp.get(remote_log, local_log)
print(f"[OK] Downloaded train_damodel_l40s.log ({os.path.getsize(local_log):,} bytes)")

# 3. Download final adapter weights and configs
print(f"\nListing adapter directory: {REMOTE_FINAL_ADAPTER}")
stdin, stdout, stderr = client.exec_command(f"ls -1 {REMOTE_FINAL_ADAPTER}")
file_list = stdout.read().decode().strip().splitlines()

for fname in file_list:
    fname = fname.strip()
    if not fname:
        continue
    r_file = f"{REMOTE_FINAL_ADAPTER}/{fname}"
    l_file = os.path.join(LOCAL_CKPT_DIR, fname)
    print(f"  Fetching: {fname} -> {l_file} ...")
    sftp.get(r_file, l_file)
    print(f"    [SAVED] {fname} ({os.path.getsize(l_file):,} bytes)")

sftp.close()
client.close()
print("\n[SUCCESS] All artifacts fetched successfully!")
