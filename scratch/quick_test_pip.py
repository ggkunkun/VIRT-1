import paramiko

HOST = "cpod-1xesnvd6jbqp.podtcp.compshare.cn"
PORT = 24334
USER = "root"
PASS = "0158TRUs7ihD9y23"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)

pip_bin = "/usr/local/miniconda3/envs/py312/bin/pip"
cmd = f"{pip_bin} install torch --index-url https://mirrors.aliyun.com/pypi/simple/"
print("Testing Aliyun/Tsinghua pip install torch...")
stdin, stdout, stderr = client.exec_command(f"{pip_bin} install torch")
for i in range(15):
    line = stdout.readline()
    if not line:
        break
    print(line.strip())

client.close()
