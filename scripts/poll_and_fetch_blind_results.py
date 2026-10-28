"""Poll training completion on DAMODEL L40S, execute 3 blind tests, and fetch all results."""

import os
import sys
import time
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


def main():
    print(f"Connecting to {USER}@{HOST}:{PORT} ...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=HOST, port=PORT, username=USER, password=PASS, timeout=30)
    print("[SUCCESS] Connected to DAMODEL instance.")

    # 1. Wait until training is complete
    print("\nMonitoring training progress...")
    while True:
        stdin, stdout, stderr = client.exec_command(f"tail -n 3 {REMOTE_DIR}/train.log")
        tail_out = stdout.read().decode().strip().replace('\r', ' ')
        
        # Check if finished
        stdin, stdout, stderr = client.exec_command(f"grep 'TRAINING COMPLETE' {REMOTE_DIR}/train.log")
        if "TRAINING COMPLETE" in stdout.read().decode():
            print("\n[SUCCESS] Training completed on remote L40S!")
            break
            
        print(f"  [TRAINING] {tail_out[-120:]}")
        time.sleep(20)

    # 2. Upload blind test script
    sftp = client.open_sftp()
    local_script = os.path.join(LOCAL_DIR, "run_blind_tests_remote.py")
    remote_script = f"{REMOTE_DIR}/run_blind_tests_remote.py"
    print(f"\nUploading blind test script: {local_script} -> {remote_script}")
    sftp.put(local_script, remote_script)

    # 3. Execute blind tests on L40S
    print("\nRunning 3 industrial blind tests on remote NVIDIA L40S...")
    stdin, stdout, stderr = client.exec_command(f"python3 -u {remote_script}")
    for line in iter(stdout.readline, ""):
        print("  [BLIND-TEST]", line.strip())

    # 4. Download blind test results
    remote_res = f"{REMOTE_DIR}/blind_test_results.json"
    local_res = os.path.join(LOCAL_DIR, "blind_test_results.json")
    print(f"\nDownloading blind test results: {remote_res} -> {local_res}")
    sftp.get(remote_res, local_res)

    # 5. Download updated LoRA adapter
    print(f"\nDownloading reinforced LoRA adapter files from {REMOTE_FINAL_ADAPTER} ...")
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

    # Download training log
    sftp.get(f"{REMOTE_DIR}/train.log", os.path.join(LOCAL_DIR, "train_damodel_l40s_comprehensive.log"))

    sftp.close()
    client.close()
    print("\n[ALL COMPLETE] Comprehensive training, blind tests, and artifact synchronization finished!")


if __name__ == "__main__":
    main()
