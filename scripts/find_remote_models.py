"""Find Coder models in DAMODEL storage."""

import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("cn-north-b.ssh.damodel.com", port=40526, username="root", password="m2A5jbYmbP")

stdin, stdout, stderr = client.exec_command("find /root/public-storage/model -maxdepth 3 -iname '*coder*' -o -iname '*qwen*'")
print(stdout.read().decode())
client.close()
