import paramiko
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('cpod-1xesnvd6jbqp.podtcp.compshare.cn', port=24334, username='root', password='0158TRUs7ihD9y23', timeout=10)

stdin, stdout, stderr = client.exec_command("ps -To pid,tid,time,comm -p 9621 | sort -k3 -r | head -n 10")
print("Top threads by CPU time:\n", stdout.read().decode().strip())

client.close()
