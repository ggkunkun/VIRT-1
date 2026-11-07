import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('cpod-1xc9awyq3yn1.podtcp.compshare.cn', port=29306, username='root', password='3NP6G214m098WXoQ', timeout=30)

cmd = """
/usr/local/miniconda3/envs/py312/bin/pip install torch --index-url https://download.pytorch.org/whl/cu124 --dry-run
"""

_, stdout, stderr = client.exec_command(cmd)
print(stdout.read().decode('utf-8', errors='replace'))
print("ERRORS:", stderr.read().decode('utf-8', errors='replace'))
client.close()
