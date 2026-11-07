import paramiko
from pathlib import Path

HOST = "cpod-1xesnvd6jbqp.podtcp.compshare.cn"
PORT = 24334
USER = "root"
PASS = "0158TRUs7ihD9y23"

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
