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

cmds = [
    "bash -l -c 'python -c \"import torch; print(f\\\"PyTorch: {torch.__version__} | CUDA: {torch.cuda.is_available()} | Device: {torch.cuda.get_device_name(0)}\\\")\"'",
    "bash -l -c 'python -c \"import transformers, peft, bitsandbytes; print(f\\\"Transformers: {transformers.__version__} | PEFT: {peft.__version__} | BNB: {bitsandbytes.__version__}\\\")\"'",
    "bash -l -c 'which python; conda info --envs'",
    "ls -la /root"
]

for cmd in cmds:
    print(f"=== {cmd} ===")
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if out:
        print(out)
    if err:
        print(f"[ERR] {err}")
    print()

client.close()
