import paramiko

HOST = "cpod-1xesnvd6jbqp.podtcp.compshare.cn"
PORT = 24334
USER = "root"
PASS = "0158TRUs7ihD9y23"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)

cmds = [
    ("Running Python/Pip Processes", "ps -ef | grep -E 'python|pip' | grep -v grep"),
    ("Cloud Train Pack Directory Status", "ls -lh /root/cloud_train_pack | head -n 15"),
    ("Output Directory", "ls -lh /root/cloud_train_pack/output_13b 2>/dev/null"),
    ("GPU Utilization", "nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv")
]

for label, cmd in cmds:
    print(f"=== {label} ===")
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    if out:
        print(out)
    else:
        print("(None)")
    print()

client.close()
