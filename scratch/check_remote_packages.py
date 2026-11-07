import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('cpod-1xesnvd6jbqp.podtcp.compshare.cn', port=24334, username='root', password='0158TRUs7ihD9y23', timeout=15)

py_bin = "/usr/local/miniconda3/envs/py312/bin/python"
pip_bin = "/usr/local/miniconda3/envs/py312/bin/pip"

cmds = [
    f"{py_bin} -V",
    f"{py_bin} -c \"import torch; print('Torch:', torch.__version__, 'CUDA:', torch.cuda.is_available(), 'Device:', torch.cuda.get_device_name(0))\"",
    f"{pip_bin} list | grep -E 'transformers|peft|trl|bitsandbytes|accelerate|modelscope|torch|vllm|deepspeed'",
]

for cmd in cmds:
    print(f">>> {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if out:
        print(out)
    if err:
        print(f"[ERR] {err}")
    print()

client.close()
