import paramiko

HOST = "cpod-1xesnvd6jbqp.podtcp.compshare.cn"
PORT = 24334
USER = "root"
PASS = "0158TRUs7ihD9y23"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)

py_bin = "/usr/local/miniconda3/envs/py312/bin/python"

cmds = [
    # Verify torch & GPU
    f"{py_bin} -c \"import torch; print('CUDA available:', torch.cuda.is_available(), '| Device count:', torch.cuda.device_count(), '| Device name:', torch.cuda.get_device_name(0), '| VRAM:', round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 1), 'GB')\"",
    # Verify transformers & peft & trl
    f"{py_bin} -c \"import transformers, peft, trl, bitsandbytes; print('Transformers:', transformers.__version__, '| PEFT:', peft.__version__, '| TRL:', trl.__version__, '| BNB:', bitsandbytes.__version__)\"",
    # Test Stage 0 calibrate
    f"cd /root && {py_bin} cloud_train_pack/train_cloud_virtu_13b.py --stage calibrate"
]

for cmd in cmds:
    print(f">>> {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        print(out)
    if err:
        print(f"[ERR] {err}")
    print()

client.close()
