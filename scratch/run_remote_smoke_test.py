# --- 凭据外置：口令不得写入源码（机制见 scripts/damodel_env.py / tests/test_no_hardcoded_credentials.py）
import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'scripts'))
from damodel_env import password_for as _pw
# ---
import paramiko
import sys
import time

HOST = "cpod-1xesnvd6jbqp.podtcp.compshare.cn"
PORT = 24334
USER = "root"
PASS = _pw(HOST, PORT)

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)

py_bin = "/usr/local/miniconda3/envs/py312/bin/python"
base_model = "/model/ModelScope/Qwen/Qwen3-14B"

cmd = f"cd /root/cloud_train_pack && {py_bin} -u train_cloud_virtu_13b.py --base {base_model} --stage all --smoke"
print("=" * 70)
print(f"Executing Cloud Smoke Test: {cmd}")
print("=" * 70, flush=True)

stdin, stdout, stderr = client.exec_command(cmd, get_pty=True)

for line in iter(stdout.readline, ""):
    sys.stdout.write(line)
    sys.stdout.flush()

exit_code = stdout.channel.recv_exit_status()
print(f"\n[Smoke Test Finished] Exit Code: {exit_code}")

client.close()
sys.exit(exit_code)
