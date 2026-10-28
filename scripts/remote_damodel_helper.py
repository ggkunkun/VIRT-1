"""Helper script to interact with Damodel instance via SSH/SFTP."""

import os
import sys
import time
import tarfile
import paramiko

HOST = "cn-north-b.ssh.damodel.com"
PORT = 40526
USER = "root"
PASS = "m2A5jbYmbP"

def get_ssh_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=HOST, port=PORT, username=USER, password=PASS, timeout=30)
    return client

def exec_remote(cmd, stream_output=False):
    client = get_ssh_client()
    print(f"[EXEC] {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd)
    if stream_output:
        for line in stdout:
            print(line, end="")
    out = stdout.read().decode()
    err = stderr.read().decode()
    client.close()
    return out, err

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = " ".join(sys.argv[1:])
        out, err = exec_remote(cmd)
        if out:
            print("[STDOUT]:\n" + out)
        if err:
            print("[STDERR]:\n" + err)
    else:
        print("Usage: python remote_damodel_helper.py <command>")
