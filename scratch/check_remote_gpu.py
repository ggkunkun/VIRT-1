import paramiko

HOST = "cpod-1xesnvd6jbqp.podtcp.compshare.cn"
PORT = 24334
USER = "root"
PASS = "0158TRUs7ihD9y23"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=10)

stdin, stdout, stderr = client.exec_command("nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw --format=csv,noheader")
print("GPU Status (util, mem_used, mem_total, temp, power):", stdout.read().decode().strip())

stdin, stdout, stderr = client.exec_command("ps -ef | grep python | grep -v grep")
print("Running Python Processes:\n", stdout.read().decode().strip())
client.close()
