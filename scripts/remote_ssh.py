import paramiko
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import damodel_env

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

cmd = sys.argv[1] if len(sys.argv) > 1 else 'echo ok'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
host, port, user, password = damodel_env.load()
ssh.connect(host, port=port, username=user, password=password, timeout=20, banner_timeout=45)
stdin, stdout, stderr = ssh.exec_command(cmd)
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
if out:
    print(out)
if err:
    print("STDERR:\n" + err)
ssh.close()
