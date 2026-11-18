# --- 凭据外置：口令不得写入源码（机制见 scripts/damodel_env.py / tests/test_no_hardcoded_credentials.py）
import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'scripts'))
from damodel_env import password_for as _pw
# ---
import paramiko
from pathlib import Path

HOST = "cpod-1xesnvd6jbqp.podtcp.compshare.cn"
PORT = 24334
USER = "root"
PASS = _pw(HOST, PORT)

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)

sftp = client.open_sftp()
local_script = Path(r"D:\Virtu模型\cloud_train_pack\train_cloud_virtu_13b.py")
remote_script = "/root/cloud_train_pack/train_cloud_virtu_13b.py"
print(f"Syncing {local_script} -> {remote_script}")
sftp.put(str(local_script), remote_script)

local_calib = Path(r"D:\Virtu模型\scripts\calibrate_moe_layer_centroids.py")
remote_calib = "/root/scripts/calibrate_moe_layer_centroids.py"
sftp.put(str(local_calib), remote_calib)

sftp.close()
client.close()
print("Synced successfully!")
