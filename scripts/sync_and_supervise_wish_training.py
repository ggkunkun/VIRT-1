"""Orchestration script to upload datasets, supervise training on L40S, run blind-test, and download model back."""

import json
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


LOCAL_ROOT = r"D:\Virtu模型"
REMOTE_ROOT = "/root/workspace/Virtu"

FILES_TO_UPLOAD = [
    (
        os.path.join(LOCAL_ROOT, "damodel_cad_cam_tuning", "dataset", "wish_parametric_train.jsonl"),
        f"{REMOTE_ROOT}/damodel_cad_cam_tuning/dataset/wish_parametric_train.jsonl"
    ),
    (
        os.path.join(LOCAL_ROOT, "damodel_cad_cam_tuning", "dataset", "wish_parametric_blind_test.jsonl"),
        f"{REMOTE_ROOT}/damodel_cad_cam_tuning/dataset/wish_parametric_blind_test.jsonl"
    ),
    (
        os.path.join(LOCAL_ROOT, "scripts", "train_wish_parametric_model.py"),
        f"{REMOTE_ROOT}/scripts/train_wish_parametric_model.py"
    ),
    (
        os.path.join(LOCAL_ROOT, "scripts", "run_blind_test_evaluator.py"),
        f"{REMOTE_ROOT}/scripts/run_blind_test_evaluator.py"
    ),
]


def get_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=HOST, port=PORT, username=USER, password=PASS, timeout=30)
    return client


def upload_assets():
    print(f"Connecting to {USER}@{HOST}:{PORT} ...")
    client = get_client()
    sftp = client.open_sftp()

    # Ensure remote dirs exist
    client.exec_command(f"mkdir -p {REMOTE_ROOT}/damodel_cad_cam_tuning/dataset {REMOTE_ROOT}/scripts {REMOTE_ROOT}/benchmarks {REMOTE_ROOT}/checkpoints")
    time.sleep(1)

    for local_path, remote_path in FILES_TO_UPLOAD:
        sz_kb = os.path.getsize(local_path) / 1024
        print(f"Uploading: {os.path.basename(local_path)} ({sz_kb:.1f} KB) -> {remote_path}")
        sftp.put(local_path, remote_path)

    sftp.close()
    client.close()
    print("[SUCCESS] All training assets and scripts synced to Damodel server.")


def launch_training():
    client = get_client()
    # Check if any old training is running and kill it
    client.exec_command("pkill -9 -f train_wish_parametric_model; pkill -9 -f train_cad_cam")
    time.sleep(2)

    # Launch new training with nohup
    launch_cmd = f"cd {REMOTE_ROOT} && nohup python3 scripts/train_wish_parametric_model.py > train_wish.log 2>&1 & echo $!"
    print(f"Launching intensive training job: {launch_cmd}")
    stdin, stdout, stderr = client.exec_command(launch_cmd)
    pid = stdout.read().decode().strip()
    client.close()
    print(f"[SUCCESS] Training process launched on L40S GPU! Remote PID: {pid}")
    return pid


def download_model_back():
    print("\n" + "=" * 60)
    print("  Copying Trained Model and Reports Back to Original Local Folder")
    print("=" * 60)
    
    local_target = os.path.join(LOCAL_ROOT, "checkpoints", "cad_cam_six_software_lora")
    os.makedirs(local_target, exist_ok=True)
    remote_adapter_dir = f"{REMOTE_ROOT}/checkpoints/cad_cam_six_software_lora"

    client = get_client()
    sftp = client.open_sftp()

    # List files in remote adapter dir
    files = sftp.listdir(remote_adapter_dir)
    print(f"Found {len(files)} model artifacts in remote adapter directory: {files}")

    for f in files:
        rem_f = f"{remote_adapter_dir}/{f}"
        loc_f = os.path.join(local_target, f)
        
        # Check size
        attr = sftp.stat(rem_f)
        size_mb = attr.st_size / (1024 * 1024)
        print(f"Downloading {f} ({size_mb:.2f} MB) -> {loc_f} ...")
        t0 = time.time()
        sftp.get(rem_f, loc_f)
        print(f"  -> Done in {time.time() - t0:.2f}s")

    # Also download blind-test report
    rem_report = f"{REMOTE_ROOT}/benchmarks/cad_cam_blind_test_report.md"
    loc_report = os.path.join(LOCAL_ROOT, "benchmarks", "cad_cam_blind_test_report.md")
    try:
        sftp.get(rem_report, loc_report)
        print(f"[SUCCESS] Downloaded Blind-Test report to: {loc_report}")
    except Exception as e:
        print(f"[Warning] Could not download report: {e}")

    sftp.close()
    client.close()
    print("\n[ALL COMPLETE] Model has been copied back to local directory successfully!")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--download":
        download_model_back()
    elif len(sys.argv) > 1 and sys.argv[1] == "--upload-and-launch":
        upload_assets()
        pid = launch_training()
    else:
        print("Usage: python sync_and_supervise_wish_training.py [--upload-and-launch | --download]")
