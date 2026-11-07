import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('cpod-1xesnvd6jbqp.podtcp.compshare.cn', port=24334, username='root', password='0158TRUs7ihD9y23', timeout=15)

cmds = [
    "find / -name '*Qwen*' -maxdepth 4 2>/dev/null",
    "ls -la /mnt /data /home 2>/dev/null",
    "nvidia-smi"
]

for cmd in cmds:
    print(f">>> {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    if out:
        print(out)
    print()

client.close()
