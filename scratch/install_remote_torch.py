import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('cpod-1xesnvd6jbqp.podtcp.compshare.cn', port=24334, username='root', password='0158TRUs7ihD9y23', timeout=15)

py_bin = "/usr/local/miniconda3/envs/py312/bin/python"
pip_bin = "/usr/local/miniconda3/envs/py312/bin/pip"

# Let's test pip install torch
cmd = f"{pip_bin} install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cu124"
print(f"Starting command: {cmd}")
stdin, stdout, stderr = client.exec_command(cmd)

# stream output
for line in iter(stdout.readline, ""):
    print(line.strip())
err = stderr.read().decode('utf-8', errors='replace').strip()
if err:
    print("[STDERR]", err)

client.close()
