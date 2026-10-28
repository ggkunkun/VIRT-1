import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("cn-north-b.ssh.damodel.com", port=40526, username="root", password="m2A5jbYmbP", timeout=15)

stdin, stdout, stderr = client.exec_command("ps -fp 43354,43279")
print(stdout.read().decode())

stdin, stdout, stderr = client.exec_command("nvidia-smi")
print(stdout.read().decode())

client.close()
