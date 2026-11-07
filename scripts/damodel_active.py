# -*- coding: utf-8 -*-
"""Damodel active connection and deployment helper."""
import os
import sys
import time
import tarfile
import paramiko

sys.stdout.reconfigure(encoding="utf-8")

# Credentials come from the environment or the gitignored passfile, never from this file.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import damodel_env  # noqa: E402


def get_client(timeout: int = 20) -> paramiko.SSHClient:
    host, port, user, password = damodel_env.load()
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(hostname=host, port=port, username=user, password=password, timeout=timeout)
    return c


def run_cmd(cmd: str, stream: bool = True) -> int:
    client = get_client()
    print(f"\n[SSH RUN] {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd)
    for line in stdout:
        if stream:
            print(line, end="")
    err = stderr.read().decode("utf-8", errors="replace")
    if err and err.strip():
        print(f"[STDERR]\n{err}")
    code = stdout.channel.recv_exit_status()
    client.close()
    return code


def upload_bundle(local_path: str, remote_path: str = "/root/virtu_train_bundle.tar.gz") -> None:
    client = get_client()
    sftp = client.open_sftp()
    size_mb = os.path.getsize(local_path) / (1024 * 1024)
    print(f"[SFTP] Uploading {local_path} ({size_mb:.2f} MB) -> {remote_path} ...")
    t0 = time.time()

    def cb(transferred, total):
        pct = (transferred / total) * 100
        speed = (transferred / (1024 * 1024)) / max(0.1, (time.time() - t0))
        print(f"\r[SFTP] {pct:5.1f}% ({transferred/1024/1024:.2f} / {total/1024/1024:.2f} MB) | {speed:.2f} MB/s", end="", flush=True)

    sftp.put(local_path, remote_path, callback=cb)
    print(f"\n[SFTP] Upload completed in {time.time()-t0:.1f}s")
    sftp.close()
    client.close()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "inspect":
        run_cmd("nvidia-smi")
        run_cmd("df -h")
        run_cmd("ls -la /root")
        run_cmd("python3 --version || which python3")
    elif len(sys.argv) > 1 and sys.argv[1] == "upload":
        bundle_path = r"c:\Users\Administrator\Desktop\virtu_train_bundle.tar.gz"
        upload_bundle(bundle_path)
    elif len(sys.argv) > 1:
        run_cmd(" ".join(sys.argv[1:]))
    else:
        run_cmd("nvidia-smi")
