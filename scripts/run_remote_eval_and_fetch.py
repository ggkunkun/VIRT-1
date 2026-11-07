"""Wait for training to finish on DAMODEL L40S, run evaluation across 6 software packages,
and download adapter weights and evaluation results to local workspace.
"""

import os
import sys
import time
import json
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
LOCAL_CKPT_DIR = r"D:\Virtu模型\checkpoints\damodel_l40s_cad_cam_lora"
REMOTE_DIR = "/root/cad_cam_finetune"
REMOTE_FINAL_ADAPTER = f"{REMOTE_DIR}/output_checkpoints/cad_cam_six_software_lora_final"


def main():
    os.makedirs(LOCAL_CKPT_DIR, exist_ok=True)
    os.makedirs(LOCAL_DIR, exist_ok=True)

    print(f"Connecting to {USER}@{HOST}:{PORT} ...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=HOST, port=PORT, username=USER, password=PASS, timeout=30)
    print("[SUCCESS] SSH Connected.")

    sftp = client.open_sftp()

    # Step 1: Wait for training completion
    print("Waiting for training completion...")
    max_wait = 180  # 3 minutes max
    waited = 0
    completed = False

    while waited < max_wait:
        stdin, stdout, stderr = client.exec_command(f"ls -la {REMOTE_FINAL_ADAPTER}")
        ls_out = stdout.read().decode().strip()
        if "adapter_model.safetensors" in ls_out or "adapter_config.json" in ls_out:
            print("\n[SUCCESS] Final LoRA Adapter detected!")
            completed = True
            break
        
        # Check train.log
        stdin, stdout, stderr = client.exec_command(f"tail -n 3 {REMOTE_DIR}/train.log")
        tail = stdout.read().decode().strip().replace('\r', ' ')
        print(f"  [Waiting {waited}s] {tail[-120:]}")
        time.sleep(10)
        waited += 10

    if not completed:
        print("[WARNING] Wait timeout, checking train.log for details...")
        stdin, stdout, stderr = client.exec_command(f"tail -n 30 {REMOTE_DIR}/train.log")
        print(stdout.read().decode())

    # Step 2: Upload evaluation script
    local_eval_py = os.path.join(LOCAL_DIR, "eval_six_software_remote.py")
    remote_eval_py = f"{REMOTE_DIR}/eval_six_software.py"
    print(f"\nUploading evaluation script: {local_eval_py} -> {remote_eval_py}")
    sftp.put(local_eval_py, remote_eval_py)

    # Step 3: Run evaluation script on remote L40S
    print("\nExecuting model evaluation on remote NVIDIA L40S across 6 software packages...")
    stdin, stdout, stderr = client.exec_command(f"python3 {remote_eval_py}", get_pty=True)
    for line in iter(stdout.readline, ""):
        print("  [REMOTE-EVAL]", line.strip())
    
    # Step 4: Download evaluation results
    remote_eval_res = f"{REMOTE_DIR}/eval_results.json"
    local_eval_res = os.path.join(LOCAL_DIR, "eval_results.json")
    print(f"\nDownloading evaluation results: {remote_eval_res} -> {local_eval_res}")
    sftp.get(remote_eval_res, local_eval_res)

    # Step 5: Download adapter files
    print(f"\nListing files in {REMOTE_FINAL_ADAPTER} ...")
    stdin, stdout, stderr = client.exec_command(f"ls -1 {REMOTE_FINAL_ADAPTER}")
    files = stdout.read().decode().strip().splitlines()
    print(f"Files to download: {files}")

    for fname in files:
        fname = fname.strip()
        if not fname:
            continue
        rpath = f"{REMOTE_FINAL_ADAPTER}/{fname}"
        lpath = os.path.join(LOCAL_CKPT_DIR, fname)
        print(f"  Downloading {fname} -> {lpath} ...")
        sftp.get(rpath, lpath)
        size = os.path.getsize(lpath)
        print(f"    [OK] Size: {size:,} bytes")

    # Download train.log as well
    sftp.get(f"{REMOTE_DIR}/train.log", os.path.join(LOCAL_DIR, "train_damodel_l40s.log"))

    sftp.close()
    client.close()
    print("\n[ALL FINISHED] DAMODEL L40S fine-tuning and evaluation complete!")


if __name__ == "__main__":
    main()
