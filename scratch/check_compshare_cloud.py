# --- 凭据外置：口令不得写入源码（机制见 scripts/damodel_env.py / tests/test_no_hardcoded_credentials.py）
import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'scripts'))
from damodel_env import password_for as _pw
# ---
import os
import sys
import paramiko

HOST = "cpod-1xesnvd6jbqp.podtcp.compshare.cn"
PORT = 24334
USER = "root"
PASS = _os.environ.get("CLOUD_SSH_PASS") or _pw(HOST, PORT)

def main():
    print(f"Connecting to {USER}@{HOST}:{PORT}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(hostname=HOST, port=PORT, username=USER, password=PASS, timeout=20)
        print("[SUCCESS] SSH Connection established successfully!\n")
        
        cmds = [
            ("GPU Details", "nvidia-smi --query-gpu=name,memory.total,memory.free,driver_version --format=csv"),
            ("CUDA & Torch Environment", "python3 -c \"import torch; print(f'PyTorch {torch.__version__} | CUDA Available: {torch.cuda.is_available()} | Device Count: {torch.cuda.device_count()} | Device Name: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}')\""),
            ("Transformers & Packages", "python3 -c \"for pkg in ['transformers', 'peft', 'trl', 'bitsandbytes', 'accelerate', 'modelscope']: import importlib; print(f'{pkg}: {importlib.import_module(pkg).__version__}' if importlib.util.find_spec(pkg) else f'{pkg}: Not Installed')\""),
            ("CPU & Memory", "lscpu | grep 'Model name\\|CPU(s):' | head -n 3; free -h"),
            ("Disk Storage", "df -h /root /"),
            ("Existing Files in /root", "ls -la /root"),
        ]
        
        for label, cmd in cmds:
            print(f"=== {label} (`{cmd}`) ===")
            stdin, stdout, stderr = client.exec_command(cmd)
            out = stdout.read().decode("utf-8", errors="replace").strip()
            err = stderr.read().decode("utf-8", errors="replace").strip()
            if out:
                print(out)
            if err:
                print(f"[STDERR]: {err}")
            print()
            
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    main()
