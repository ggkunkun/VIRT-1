"""Monitor UG 888 Teacher-Guided Agent Training and Fetch Final Weights."""

import os
import sys
import time
import stat
import json
from damodel_ssh_runner import get_ssh_client, exec_remote

REMOTE_CHECKPOINT_DIR = "/root/workspace/Virtu/checkpoints/ug_teacher_guided_agent_lora"
LOCAL_CHECKPOINT_DIR = r"D:\Virtu模型\checkpoints\ug_teacher_guided_agent_lora"
REMOTE_LOG = "/root/workspace/Virtu/train_ug_teacher.log"


def get_latest_log():
    code, out, err = exec_remote(f"tail -n 8 {REMOTE_LOG}")
    return out.strip()


def check_is_finished():
    code, out, err = exec_remote(f"test -f {REMOTE_CHECKPOINT_DIR}/training_receipt.json && echo YES || echo NO")
    return out.strip() == "YES"


def download_weights():
    os.makedirs(LOCAL_CHECKPOINT_DIR, exist_ok=True)
    print(f"\n[DOWNLOAD] Connecting to download model weights from {REMOTE_CHECKPOINT_DIR} ...")
    client = get_ssh_client()
    sftp = client.open_sftp()

    try:
        remote_files = sftp.listdir(REMOTE_CHECKPOINT_DIR)
        print(f"[DOWNLOAD] Found {len(remote_files)} items in {REMOTE_CHECKPOINT_DIR}: {remote_files}")

        for fname in remote_files:
            r_path = f"{REMOTE_CHECKPOINT_DIR}/{fname}"
            # Check if directory
            st = sftp.stat(r_path)
            if stat.S_ISDIR(st.st_mode):
                print(f"[SKIP] Directory {fname}")
                continue

            l_path = os.path.join(LOCAL_CHECKPOINT_DIR, fname)
            fsize_mb = st.st_size / (1024 * 1024)
            print(f"[FETCH] Downloading {fname} ({fsize_mb:.2f} MB) -> {l_path} ...")

            def progress_callback(transferred, total, name=fname):
                pct = (transferred / total) * 100
                mb_tr = transferred / (1024 * 1024)
                mb_tot = total / (1024 * 1024)
                print(f"\r  [{name}] {pct:5.1f}% ({mb_tr:6.1f} / {mb_tot:6.1f} MB)", end="", flush=True)

            sftp.get(r_path, l_path, callback=progress_callback)
            print(f"\n[SUCCESS] Downloaded {fname}")

    finally:
        sftp.close()
        client.close()

    print(f"\n[COMPLETE] All fine-tuned weights synced to {LOCAL_CHECKPOINT_DIR}!")


def main():
    print("==================================================================")
    print("  Virtu: Supervise UG 888 Teacher-Student Training & Sync")
    print("==================================================================")

    if check_is_finished():
        print("\n[SUCCESS] Training is ALREADY COMPLETED on Damodel GPU 1!")
        download_weights()
        return 0

    step = 0
    while True:
        step += 1
        log_snippet = get_latest_log()
        lines = [l for l in log_snippet.split("\n") if l.strip()]
        last_line = lines[-1] if lines else "Waiting for log..."

        print(f"[{time.strftime('%H:%M:%S')}] Poll #{step}: {last_line}")

        if check_is_finished():
            print("\n[SUCCESS] Training is COMPLETED on Damodel GPU 1!")
            break

        # Check if process died
        code, out, err = exec_remote("ps aux | grep train_ug_teacher_guided_agent.py | grep -v grep")
        if not out.strip() and not check_is_finished():
            print("\n[ERROR] Training process exited unexpectedly!")
            print("Full tail log:")
            print(get_latest_log())
            return 1

        time.sleep(15)

    download_weights()
    return 0


if __name__ == "__main__":
    sys.exit(main())
