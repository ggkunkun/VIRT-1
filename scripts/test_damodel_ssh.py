"""Test SSH connection to DAMODEL instance dbh0lss7v38s73anbheg."""

import paramiko
import sys

HOST = "cn-north-b.ssh.damodel.com"
PORT = 40526
USER = "root"
PASS = "m2A5jbYmbP"

def test_connection():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {USER}@{HOST}:{PORT} ...")
    try:
        client.connect(hostname=HOST, port=PORT, username=USER, password=PASS, timeout=15)
        print("[SUCCESS] Connected to DAMODEL L40S instance!")
        
        # Run nvidia-smi and lscpu
        commands = [
            "nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader",
            "uname -a",
            "python3 --version",
            "df -h /root",
        ]
        
        for cmd in commands:
            stdin, stdout, stderr = client.exec_command(cmd)
            out = stdout.read().decode().strip()
            err = stderr.read().decode().strip()
            print(f"\n--- Output of '{cmd}': ---")
            if out:
                print(out)
            if err:
                print(f"[STDERR]: {err}")
                
        client.close()
        return True
    except Exception as e:
        print(f"[ERROR] Failed to connect: {e}")
        return False

if __name__ == "__main__":
    test_connection()
