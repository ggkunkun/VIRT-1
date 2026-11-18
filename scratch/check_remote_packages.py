# --- 凭据外置：口令不得写入源码（机制见 scripts/damodel_env.py / tests/test_no_hardcoded_credentials.py）
import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'scripts'))
from damodel_env import password_for as _pw
# ---
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('cpod-1xesnvd6jbqp.podtcp.compshare.cn', port=24334, username='root', password=_pw('cpod-1xesnvd6jbqp.podtcp.compshare.cn', 24334), timeout=15)

py_bin = "/usr/local/miniconda3/envs/py312/bin/python"
pip_bin = "/usr/local/miniconda3/envs/py312/bin/pip"

cmds = [
    f"{py_bin} -V",
    f"{py_bin} -c \"import torch; print('Torch:', torch.__version__, 'CUDA:', torch.cuda.is_available(), 'Device:', torch.cuda.get_device_name(0))\"",
    f"{pip_bin} list | grep -E 'transformers|peft|trl|bitsandbytes|accelerate|modelscope|torch|vllm|deepspeed'",
]

for cmd in cmds:
    print(f">>> {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if out:
        print(out)
    if err:
        print(f"[ERR] {err}")
    print()

client.close()
