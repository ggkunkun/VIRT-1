"""Upload and unpack Virtu模型 into /root/workspace/Virtu on Damodel instance."""

import os
import sys
import time
import paramiko

HOST = "cn-north-b.ssh.damodel.com"
PORT = 40526
USER = "root"
PASS = "m2A5jbYmbP"

LOCAL_TAR = r"D:\Virtu模型\virtu_model_release.tar.gz"
REMOTE_WORKSPACE = "/root/workspace"
REMOTE_TAR = f"{REMOTE_WORKSPACE}/virtu_model_release.tar.gz"
REMOTE_PROJECT_DIR = f"{REMOTE_WORKSPACE}/Virtu"

def main():
    print(f"Connecting to {USER}@{HOST}:{PORT} ...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=HOST, port=PORT, username=USER, password=PASS, timeout=30)
    print("[SUCCESS] SSH Connected.")

    sftp = client.open_sftp()
    
    # 1. Upload the tarball
    size_mb = os.path.getsize(LOCAL_TAR) / (1024 * 1024)
    print(f"Uploading {LOCAL_TAR} ({size_mb:.2f} MB) -> {REMOTE_TAR} ...")
    start_t = time.time()
    
    def progress_callback(transferred, total):
        pct = (transferred / total) * 100
        print(f"\rUploading: {pct:.1f}% ({transferred / (1024*1024):.2f}/{total / (1024*1024):.2f} MB)", end="")
        sys.stdout.flush()

    sftp.put(LOCAL_TAR, REMOTE_TAR, callback=progress_callback)
    print(f"\n[SUCCESS] Upload completed in {time.time() - start_t:.2f} seconds!")
    sftp.close()

    # 2. Extract on remote
    print("Extracting archive on remote host...")
    cmd = f"cd {REMOTE_WORKSPACE} && tar -xzf virtu_model_release.tar.gz && rm -f virtu_model_release.tar.gz && ls -la {REMOTE_PROJECT_DIR}"
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    print("[EXTRACT OUTPUT]:\n" + out)
    if err:
        print("[EXTRACT STDERR]:\n" + err)

    client.close()
    print("[ALL DONE] Virtu model repository deployed to Damodel server!")

if __name__ == "__main__":
    main()
