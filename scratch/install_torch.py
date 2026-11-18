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
/usr/local/miniconda3/envs/py312/bin/pip install torch -q
/usr/local/miniconda3/envs/py312/bin/python -c "import torch; print('PyTorch version:', torch.__version__, 'CUDA available:', torch.cuda.is_available(), 'GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None')"
"""

_, stdout, stderr = client.exec_command(cmd)
print(stdout.read().decode('utf-8', errors='replace'))
print("ERRORS:", stderr.read().decode('utf-8', errors='replace'))
client.close()
