"""SSH and SFTP Runner for Damodel GPU Instance (2 x L40S)."""

import os
import sys
import time
import tarfile
import paramiko

HOST = "cn-north-b.ssh.damodel.com"
PORT = 42688
USER = "root"
PASS = os.environ.get("DAMODEL_PASS", "")


def get_ssh_client(timeout=30):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=HOST, port=PORT, username=USER, password=PASS, timeout=timeout)
    return client


def exec_remote(cmd, stream_output=False, timeout=None):
    client = get_ssh_client()
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    if stream_output:
        for line in stdout:
            print(line, end="", flush=True)
        out = ""
    else:
        out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    exit_status = stdout.channel.recv_exit_status()
    client.close()
    return exit_status, out, err


def sftp_upload(local_path, remote_path):
    client = get_ssh_client()
    sftp = client.open_sftp()
    print(f"[SFTP] Uploading {local_path} -> {remote_path} ...")
    sftp.put(local_path, remote_path)
    sftp.close()
    client.close()
    print(f"[SFTP] Upload complete.")


def sftp_download(remote_path, local_path):
    client = get_ssh_client()
    sftp = client.open_sftp()
    print(f"[SFTP] Downloading {remote_path} -> {local_path} ...")
    sftp.get(remote_path, local_path)
    sftp.close()
    client.close()
    print(f"[SFTP] Download complete.")


def exec_python_code(code_str, stream_output=False, timeout=None):
    client = get_ssh_client()
    stdin, stdout, stderr = client.exec_command("python3 -u -", timeout=timeout)
    stdin.write(code_str)
    stdin.channel.shutdown_write()
    if stream_output:
        for line in stdout:
            print(line, end="", flush=True)
        out = ""
    else:
        out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    exit_status = stdout.channel.recv_exit_status()
    client.close()
    return exit_status, out, err


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--py" and len(sys.argv) > 2:
            code = " ".join(sys.argv[2:])
            code, out, err = exec_python_code(code)
        elif sys.argv[1] == "--py-file" and len(sys.argv) > 2:
            with open(sys.argv[2], "r", encoding="utf-8") as f:
                code_str = f.read()
            code, out, err = exec_python_code(code_str, stream_output=True)
        else:
            cmd = " ".join(sys.argv[1:])
            code, out, err = exec_remote(cmd)
        if out:
            print(out)
        if err:
            print("[ERR]:", err, file=sys.stderr)
        sys.exit(code)
    else:
        print("Usage: python damodel_ssh_runner.py <remote_command>")
