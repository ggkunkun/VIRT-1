"""Upload and extract UG 888 exercise drawings to cloud server."""

import os
import sys
import time
import stat
from damodel_ssh_runner import get_ssh_client, exec_remote

LOCAL_ZIP = r"D:\Virtu模型\ug_888_drawings.zip"
REMOTE_ZIP = "/root/workspace/Virtu/ug_drawings.zip"
REMOTE_DIR = "/root/workspace/Virtu/ug_drawings"

def progress_callback(transferred, total):
    pct = (transferred / total) * 100
    mb_trans = transferred / (1024 * 1024)
    mb_tot = total / (1024 * 1024)
    print(f"\r[SFTP Upload] {pct:5.1f}% ({mb_trans:6.1f} / {mb_tot:6.1f} MB)", end="", flush=True)

def main():
    if not os.path.exists(LOCAL_ZIP):
        print(f"[ERROR] Local zip not found: {LOCAL_ZIP}")
        return 1

    file_size_mb = os.path.getsize(LOCAL_ZIP) / (1024 * 1024)
    print(f"[INFO] Uploading {LOCAL_ZIP} ({file_size_mb:.2f} MB) to {REMOTE_ZIP} ...")

    client = get_ssh_client()
    sftp = client.open_sftp()
    t0 = time.time()
    try:
        sftp.put(LOCAL_ZIP, REMOTE_ZIP, callback=progress_callback)
        print()
    finally:
        sftp.close()
        client.close()

    t1 = time.time()
    speed_mb_s = file_size_mb / max(t1 - t0, 0.1)
    print(f"[SUCCESS] Upload finished in {t1 - t0:.1f}s ({speed_mb_s:.2f} MB/s)")

    print(f"[INFO] Extracting {REMOTE_ZIP} to {REMOTE_DIR} on cloud...")
    cmd = f"mkdir -p {REMOTE_DIR} && unzip -q -o {REMOTE_ZIP} -d {REMOTE_DIR}/ && rm -f {REMOTE_ZIP} && find {REMOTE_DIR} -type f | wc -l"
    code, out, err = exec_remote(cmd)
    if code == 0:
        file_count = out.strip()
        print(f"[SUCCESS] Extraction complete! Total drawings in remote {REMOTE_DIR}: {file_count} files.")
    else:
        print(f"[ERROR] Unzip failed (code {code}): {err}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
