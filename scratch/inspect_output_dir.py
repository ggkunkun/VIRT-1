# --- 凭据外置：口令不得写入源码（机制见 scripts/damodel_env.py / tests/test_no_hardcoded_credentials.py）
import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'scripts'))
from damodel_env import password_for as _pw
# ---
import paramiko
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('cpod-1xesnvd6jbqp.podtcp.compshare.cn', port=24334, username='root', password=_pw('cpod-1xesnvd6jbqp.podtcp.compshare.cn', 24334), timeout=10)
stdin, stdout, stderr = client.exec_command("ls -la /root/cloud_train_pack/output_13b/")
print('Output dir contents:\n', stdout.read().decode().strip())
client.close()
