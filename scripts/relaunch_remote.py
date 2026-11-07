import os
import sys
import time
import paramiko

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import damodel_env

HOST = "cn-north-b.ssh.damodel.com"
PORT = 34087
USER = "root"
PASS = damodel_env.password_for(HOST, PORT)
REMOTE_DIR = "/root/virtu_train"

print("="*60)
print("🚀 上传调优后的训练脚本与参数到云端算力实例 ...")
print("="*60)

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(hostname=HOST, port=PORT, username=USER, password=PASS, timeout=30, banner_timeout=45)

# 1. 确保之前遗留的可能死锁或孤儿进程被清理
client.exec_command("pkill -9 -f train_turnkey.py")
time.sleep(1)

# 2. 上传更新的 train_turnkey.py 和 run.sh
sftp = client.open_sftp()
sftp.put("cloud_train_pack/train_turnkey.py", f"{REMOTE_DIR}/train_turnkey.py")
sftp.put("cloud_train_pack/run.sh", f"{REMOTE_DIR}/run.sh")
sftp.close()
print("✅ 文件同步完成: train_turnkey.py, run.sh")

# 3. 授予执行权限并清空旧的 train.log
client.exec_command(f"chmod +x {REMOTE_DIR}/run.sh && rm -f {REMOTE_DIR}/train.log")
time.sleep(1)

# 4. 启动训练任务
print("🚀 启动远程训练守护进程: nohup bash run.sh > train.log 2>&1 &")
cmd = f"cd {REMOTE_DIR} && nohup bash run.sh > train.log 2>&1 &"
client.exec_command(cmd)
time.sleep(3)

# 5. 检查是否成功启动
stdin, stdout, stderr = client.exec_command("pgrep -f run.sh || pgrep -f train_turnkey.py")
pids = stdout.read().decode('utf-8').strip()
print(f"✅ 任务启动状态: 运行中 (PID: {pids})")

client.close()
print("="*60)
