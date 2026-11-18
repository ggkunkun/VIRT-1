# --- 凭据外置：口令不得写入源码（机制见 scripts/damodel_env.py / tests/test_no_hardcoded_credentials.py）
import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'scripts'))
from damodel_env import password_for as _pw
# ---
import os
import paramiko
from pathlib import Path

HOST = "cpod-1xesnvd6jbqp.podtcp.compshare.cn"
PORT = 24334
USER = "root"
PASS = _pw(HOST, PORT)

LOCAL_DIR = Path(r"D:\Virtu模型\models\virtu-13b")
LOCAL_DIR.mkdir(parents=True, exist_ok=True)

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)

sftp = client.open_sftp()
remote_dir = "/root/cloud_train_pack/output_13b"

files_to_download = [
    "COMPREHENSIVE_EVAL_REPORT.json",
    "COMPREHENSIVE_EVAL_REPORT.md",
    "Modelfile_virtu_13b",
    "raw.jsonl",
    "virtu_13b_deliverable_20261107_062008.tar.gz",
    "virtu_13b_deliverable_20261107_062008.tar.gz.sha256"
]

for f in files_to_download:
    remote_path = f"{remote_dir}/{f}"
    local_path = LOCAL_DIR / f
    print(f"Downloading {remote_path} -> {local_path} ...", flush=True)
    sftp.get(remote_path, str(local_path))
    size_mb = local_path.stat().st_size / (1024 * 1024)
    print(f"Downloaded {f}: {size_mb:.2f} MB")

sftp.close()
client.close()
print("All artifacts successfully transferred to local!")
