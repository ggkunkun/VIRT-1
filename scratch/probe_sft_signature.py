import paramiko

HOST = "cpod-1xesnvd6jbqp.podtcp.compshare.cn"
PORT = 24334
USER = "root"
PASS = "0158TRUs7ihD9y23"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)

py_bin = "/usr/local/miniconda3/envs/py312/bin/python"

probe_code = """
import inspect
from trl import SFTTrainer, SFTConfig
sig = inspect.signature(SFTTrainer.__init__)
print('SFTTrainer params:', list(sig.parameters.keys())[:15])
"""

cmd = f"{py_bin} -c \"{probe_code}\""
stdin, stdout, stderr = client.exec_command(cmd)
print("STDOUT:\n", stdout.read().decode().strip())
print("STDERR:\n", stderr.read().decode().strip())

client.close()
