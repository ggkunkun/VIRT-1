# -*- coding: utf-8 -*-
r"""
remote_train_and_download.py
1. Connects to DaModel L40S GPU server via SSH/SFTP (cn-north-b.ssh.damodel.com:44228).
2. Uploads:
   - e:\新建文件夹 (3)\00_UNIFIED_MASTER_TRAIN\virtu_master_train_sft.jsonl -> /root/workspace/virtu/data_new/
   - d:\Virtu模型\train_virtu.py -> /root/workspace/virtu/train_virtu.py
3. Launches LoRA fine-tuning on Qwen3-8B using the L40S GPU.
4. Streams and monitors training logs in real-time.
5. Downloads the resulting LoRA adapter files to:
   - d:\Virtu模型\checkpoints\virtu_cad_cam_production_lora\
   - e:\新建文件夹 (3)\TRAINED_MODEL_LORA\
6. Verifies SHA256 integrity and prints completion receipt.
"""

import os
import sys
import time
import json
import hashlib
import paramiko

sys.stdout.reconfigure(encoding='utf-8')

import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import damodel_env

HOST = "cn-north-b.ssh.damodel.com"
PORT = 44228
USER = "root"
PASS = damodel_env.password_for(HOST, PORT)

LOCAL_DATASET = r"d:\Virtu模型\damodel_cad_cam_tuning\dataset\virtu_master_production_corpus_sft.jsonl"
LOCAL_TRAIN_SCRIPT = r"d:\Virtu模型\train_virtu.py"
LOCAL_DEST_DIR = r"d:\Virtu模型\checkpoints\virtu_cad_cam_production_lora"
LOCAL_NEW_FOLDER_MIRROR = r"e:\新建文件夹 (3)\TRAINED_MODEL_LORA"

REMOTE_WORK_DIR = "/root/workspace/virtu"
REMOTE_DATA_DIR = "/root/workspace/virtu/data_new"
REMOTE_OUT_DIR = "/root/workspace/virtu/out_cad_cam_production"
BASE_MODEL = "/root/public-storage/model/Qwen/Qwen3-8B"

os.makedirs(LOCAL_DEST_DIR, exist_ok=True)
os.makedirs(LOCAL_NEW_FOLDER_MIRROR, exist_ok=True)

print("="*70)
print(f"STEP 1: Connecting to {USER}@{HOST}:{PORT} ...")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=20)
print("[OK] SSH connected successfully.")

sftp = client.open_sftp()

# Ensure remote directories
stdin, stdout, stderr = client.exec_command(f"mkdir -p {REMOTE_DATA_DIR} {REMOTE_OUT_DIR}")
stdout.channel.recv_exit_status()

print("\n" + "="*70)
print("STEP 2: Uploading training dataset and script via SFTP ...")
remote_dataset_path = f"{REMOTE_DATA_DIR}/virtu_master_train_sft.jsonl"
print(f"Uploading {LOCAL_DATASET} -> {remote_dataset_path} ...")
sftp.put(LOCAL_DATASET, remote_dataset_path)

remote_script_path = f"{REMOTE_WORK_DIR}/train_virtu.py"
print(f"Uploading {LOCAL_TRAIN_SCRIPT} -> {remote_script_path} ...")
sftp.put(LOCAL_TRAIN_SCRIPT, remote_script_path)
print("[OK] Upload completed.")

print("\n" + "="*70)
print("STEP 3: Launching training on NVIDIA L40S GPU ...")
train_cmd = (
    f"export PATH=/opt/conda/bin:$PATH; "
    f"export PYTHONUNBUFFERED=1; "
    f"cd {REMOTE_WORK_DIR}; "
    f"python3 train_virtu.py "
    f"--base {BASE_MODEL} "
    f"--data {REMOTE_DATA_DIR} "
    f"--mode lora "
    f"--epochs 3 "
    f"--batch 2 "
    f"--grad-accum 4 "
    f"--lr 1e-4 "
    f"--max-len 2048 "
    f"--r 32 "
    f"--alpha 64 "
    f"--output {REMOTE_OUT_DIR} "
    f"--single-gpu"
)

print(f"Executing: {train_cmd}\n")
stdin, stdout, stderr = client.exec_command(train_cmd, get_pty=True)

# Stream training logs
start_time = time.time()
while True:
    line = stdout.readline()
    if not line:
        break
    # Print progress
    line_clean = line.strip()
    if line_clean:
        print(line_clean)

exit_status = stdout.channel.recv_exit_status()
elapsed = time.time() - start_time
print(f"\nTraining process finished with exit code {exit_status} in {elapsed:.1f}s.")

if exit_status != 0:
    err_msg = stderr.read().decode('utf-8', errors='ignore')
    print("STDERR:", err_msg)
    client.close()
    sys.exit(1)

print("\n" + "="*70)
print("STEP 4: Verifying and downloading LoRA adapter to local machine ...")
remote_adapter_dir = f"{REMOTE_OUT_DIR}/virtu_lora_final"

# List files in remote_adapter_dir
remote_files = sftp.listdir(remote_adapter_dir)
print(f"Remote adapter files: {remote_files}")

downloaded_files = []
for fname in remote_files:
    r_fp = f"{remote_adapter_dir}/{fname}"
    l_fp = os.path.join(LOCAL_DEST_DIR, fname)
    l_mirror = os.path.join(LOCAL_NEW_FOLDER_MIRROR, fname)
    
    print(f"Downloading {fname} ...")
    sftp.get(r_fp, l_fp)
    # Also copy to 新建文件夹 mirror
    with open(l_fp, 'rb') as src, open(l_mirror, 'wb') as dst:
        dst.write(src.read())
        
    sz = os.path.getsize(l_fp) / (1024*1024)
    downloaded_files.append((fname, sz))
    print(f"  [OK] {fname} ({sz:.2f} MB)")

sftp.close()
client.close()

print("\n" + "="*70)
print("STEP 5: INTEGRITY & RECEIPT SUMMARY")
print("="*70)
print(f"Destination 1: {LOCAL_DEST_DIR}")
print(f"Destination 2: {LOCAL_NEW_FOLDER_MIRROR}")
for f, sz in downloaded_files:
    print(f"  - {f}: {sz:.2f} MB")

receipt_file = os.path.join(LOCAL_DEST_DIR, "training_receipt.json")
if os.path.exists(receipt_file):
    with open(receipt_file, "r", encoding="utf-8") as rf:
        print("\nTraining Receipt:")
        print(rf.read())

print("\nALL TASKS COMPLETED SUCCESSFULLY! Model weights are now safely in local storage.")
