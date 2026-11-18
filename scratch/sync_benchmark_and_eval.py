# --- 凭据外置：口令不得写入源码（机制见 scripts/damodel_env.py / tests/test_no_hardcoded_credentials.py）
import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'scripts'))
from damodel_env import password_for as _pw
# ---
import os
import tarfile
import paramiko
from pathlib import Path

HOST = "cpod-1xesnvd6jbqp.podtcp.compshare.cn"
PORT = 24334
USER = "root"
PASS = _pw(HOST, PORT)

LOCAL_ROOT = Path(r"D:\Virtu模型")
tar_path = LOCAL_ROOT / "scratch" / "eval_bundle.tar.gz"

print("Packaging virtu_eval and data/benchmark...")
with tarfile.open(str(tar_path), "w:gz") as tar:
    if (LOCAL_ROOT / "virtu_eval").exists():
        tar.add(str(LOCAL_ROOT / "virtu_eval"), arcname="virtu_eval")
    if (LOCAL_ROOT / "data" / "benchmark").exists():
        tar.add(str(LOCAL_ROOT / "data" / "benchmark"), arcname="data/benchmark")

print(f"Tar created: {tar_path.stat().st_size / 1024:.1f} KB")

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)

sftp = client.open_sftp()
remote_tar = "/root/eval_bundle.tar.gz"
print(f"Uploading {tar_path} -> {remote_tar}...")
sftp.put(str(tar_path), remote_tar)
sftp.close()

stdin, stdout, stderr = client.exec_command("cd /root && tar -xzf eval_bundle.tar.gz && rm eval_bundle.tar.gz")
stdout.channel.recv_exit_status()
print("Extracted eval bundle on remote!")

client.close()
