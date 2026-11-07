import paramiko
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('cpod-1xesnvd6jbqp.podtcp.compshare.cn', port=24334, username='root', password='0158TRUs7ihD9y23', timeout=10)
stdin, stdout, stderr = client.exec_command("/usr/local/miniconda3/envs/py312/bin/python -c 'import sys; sys.path.insert(0, \"/root\"); from virtu_eval.runner import load_cases; print(len(load_cases(\"/root/data/benchmark/virtu_eval_phys_v1\", dims=[\"physics\"])))'")
print('Physics cases on remote:', stdout.read().decode().strip())
client.close()
