# -*- coding: utf-8 -*-
import paramiko

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import damodel_env

HOST = "cn-north-b.ssh.damodel.com"
PORT = 44228
USER = "root"
PASS = damodel_env.password_for(HOST, PORT)

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(hostname=HOST, port=PORT, username=USER, password=PASS, timeout=20)

cmds = [
    ("排查占用 28G 显存的进程", "ps -ef | grep -E 'python|ollama|vllm'"),
    ("检查 /opt/conda 默认环境", "/opt/conda/bin/python -c 'import torch; print(\"Torch:\", torch.__version__, \"CUDA:\", torch.cuda.is_available())'"),
    ("检查 Conda 虚拟环境列表", "/opt/conda/bin/conda info --envs"),
    ("检查当前 PATH 与 python 路径", "echo $PATH; which python; which conda"),
    ("检查 transformers, peft, accelerate", "/opt/conda/bin/python -c 'import transformers, peft, accelerate; print(\"transformers:\", transformers.__version__, \"peft:\", peft.__version__)'"),
]

for title, cmd in cmds:
    print(f"\n>>> {title} <<<")
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode("utf-8", errors="ignore").strip()
    err = stderr.read().decode("utf-8", errors="ignore").strip()
    if out:
        print(out)
    if err:
        print(f"[ERR]: {err}")

client.close()
