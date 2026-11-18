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

pip_bin = "/usr/local/miniconda3/envs/py312/bin/pip"
py_bin = "/usr/local/miniconda3/envs/py312/bin/python"

# Step 1: Install PyTorch with CUDA 12.4
print("=== Installing PyTorch on RTX 4090 Cloud Instance ===")
cmd = f"{pip_bin} install torch torchvision --index-url https://download.pytorch.org/whl/cu124"
print(f"Executing: {cmd}")
stdin, stdout, stderr = client.exec_command(cmd)

for line in iter(stdout.readline, ""):
    print(line.strip())
err = stderr.read().decode().strip()
if err:
    print("[STDERR]", err)

# Step 2: Verify PyTorch and CUDA
stdin, stdout, stderr = client.exec_command(f"{py_bin} -c \"import torch; print('PyTorch Version:', torch.__version__, '| CUDA OK:', torch.cuda.is_available(), '| GPU:', torch.cuda.get_device_name(0))\"")
print("\n=== Verification ===")
print(stdout.read().decode().strip())
print(stderr.read().decode().strip())

client.close()
