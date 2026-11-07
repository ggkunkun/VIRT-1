import paramiko
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('cpod-1xesnvd6jbqp.podtcp.compshare.cn', port=24334, username='root', password='0158TRUs7ihD9y23', timeout=10)
stdin, stdout, stderr = client.exec_command("cat /proc/9621/stack")
print('Kernel stack:\n', stdout.read().decode().strip())
stdin, stdout, stderr = client.exec_command("cat /proc/9621/wchan")
print('Wchan:\n', stdout.read().decode().strip())
client.close()
