import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('cpod-1xc9awyq3yn1.podtcp.compshare.cn', port=29306, username='root', password='3NP6G214m098WXoQ', timeout=30)

cmd = """
/usr/local/miniconda3/envs/py312/bin/pip install "transformers>=4.45.0" "peft>=0.10.0" "bitsandbytes>=0.43.0" "trl>=0.12.0" "accelerate" "datasets" "modelscope" "numpy" -i https://pypi.tuna.tsinghua.edu.cn/simple -q
/usr/local/miniconda3/envs/py312/bin/python -c "import torch, transformers, peft, trl, bitsandbytes, datasets, modelscope; print('ALL LIBRARIES OK!')"
"""
stdin, stdout, stderr = client.exec_command(cmd, get_pty=True)
for line in stdout:
    print(line, end="")
client.close()
