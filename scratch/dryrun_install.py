import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('cpod-1xesnvd6jbqp.podtcp.compshare.cn', port=24334, username='root', password='0158TRUs7ihD9y23', timeout=15)

py_bin = "/usr/local/miniconda3/envs/py312/bin/python"
pip_bin = "/usr/local/miniconda3/envs/py312/bin/pip"

cmd = f"{pip_bin} install --dry-run torch transformers peft trl bitsandbytes accelerate datasets"
stdin, stdout, stderr = client.exec_command(cmd)
print("OUT:\n", stdout.read().decode())
print("ERR:\n", stderr.read().decode())

client.close()
