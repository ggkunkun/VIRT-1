import paramiko

HOST = "cpod-1xesnvd6jbqp.podtcp.compshare.cn"
PORT = 24334
USER = "root"
PASS = "0158TRUs7ihD9y23"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)

stdin, stdout, stderr = client.exec_command('grep -n "warmup_steps" /root/cloud_train_pack/train_cloud_virtu_13b.py')
print("warmup_steps:")
print(stdout.read().decode())

stdin, stdout, stderr = client.exec_command('grep -n "processing_class" /root/cloud_train_pack/train_cloud_virtu_13b.py')
print("processing_class:")
print(stdout.read().decode())

client.close()
