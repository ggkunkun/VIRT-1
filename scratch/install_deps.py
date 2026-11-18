# --- 凭据外置：口令不得写入源码（机制见 scripts/damodel_env.py / tests/test_no_hardcoded_credentials.py）
import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'scripts'))
from damodel_env import password_for as _pw
# ---
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('cpod-1xc9awyq3yn1.podtcp.compshare.cn', port=29306, username='root', password=_pw('cpod-1xc9awyq3yn1.podtcp.compshare.cn', 29306), timeout=30)

cmd = """
/usr/local/miniconda3/envs/py312/bin/pip install "transformers>=4.45.0" "peft>=0.10.0" "bitsandbytes>=0.43.0" "trl>=0.12.0" "accelerate" "datasets" "modelscope" "numpy" -i https://pypi.tuna.tsinghua.edu.cn/simple -q
/usr/local/miniconda3/envs/py312/bin/python -c "import torch, transformers, peft, trl, bitsandbytes, datasets, modelscope; print('ALL LIBRARIES OK!')"
"""
stdin, stdout, stderr = client.exec_command(cmd, get_pty=True)
for line in stdout:
    print(line, end="")
client.close()
