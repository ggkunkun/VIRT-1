"""Check environment on remote DAMODEL L40S instance."""

import paramiko

HOST = "cn-north-b.ssh.damodel.com"
PORT = 40526
USER = "root"
PASS = "m2A5jbYmbP"

def check_env():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=HOST, port=PORT, username=USER, password=PASS)

    cmds = [
        "python3 -c \"import torch; print('PyTorch:', torch.__version__, 'CUDA:', torch.cuda.is_available(), 'GPU count:', torch.cuda.device_count())\"",
        "python3 -c \"import transformers; print('Transformers:', transformers.__version__)\"",
        "python3 -c \"import peft; print('PEFT:', peft.__version__)\"",
        "pip3 --version",
        "ls -la /root",
    ]

    for c in cmds:
        print(f"\n>>> Executing: {c}")
        stdin, stdout, stderr = client.exec_command(c)
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        if out:
            print(out)
        if err:
            print(f"[ERR]: {err}")

    client.close()

if __name__ == "__main__":
    check_env()
