import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('cpod-1xesnvd6jbqp.podtcp.compshare.cn', port=24334, username='root', password='0158TRUs7ihD9y23', timeout=15)
stdin, stdout, stderr = client.exec_command('/usr/local/miniconda3/envs/py312/bin/python -c "import inspect; from trl import SFTConfig; print([k for k in inspect.signature(SFTConfig.__init__).parameters.keys() if \'length\' in k or \'seq\' in k or \'dataset\' in k])"')
print(stdout.read().decode())
client.close()
