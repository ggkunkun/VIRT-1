import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('cpod-1xesnvd6jbqp.podtcp.compshare.cn', port=24334, username='root', password='0158TRUs7ihD9y23', timeout=15)

cmds = [
    "bash -l -c 'python -c \"import torch; print(f\\\"PyTorch: {torch.__version__} | CUDA: {torch.cuda.is_available()} | Device: {torch.cuda.get_device_name(0)}\\\")\"'",
    "bash -l -c 'python -c \"import transformers, peft, bitsandbytes; print(f\\\"Transformers: {transformers.__version__} | PEFT: {peft.__version__} | BNB: {bitsandbytes.__version__}\\\")\"'",
    "bash -l -c 'which python; conda info --envs'",
    "ls -la /root"
]

for cmd in cmds:
    print(f"=== {cmd} ===")
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if out:
        print(out)
    if err:
        print(f"[ERR] {err}")
    print()

client.close()
