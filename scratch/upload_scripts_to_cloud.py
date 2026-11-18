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

try:
    sftp.mkdir("/root/scripts")
except Exception:
    pass

local_file = Path(r"D:\Virtu模型\scripts\hf_to_gguf_numpy.py")
remote_file = "/root/scripts/hf_to_gguf_numpy.py"

print(f"Uploading {local_file} -> {remote_file}...")
sftp.put(str(local_file), remote_file)
print("Upload successful!")

# Also upload convert_lora_to_gguf.py if exists
local_lora = Path(r"D:\Virtu模型\scripts\convert_lora_to_gguf.py")
if local_lora.exists():
    sftp.put(str(local_lora), "/root/scripts/convert_lora_to_gguf.py")
    print("Uploaded convert_lora_to_gguf.py")

sftp.close()
client.close()
