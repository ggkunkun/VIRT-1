import os
import sys
import time
import tarfile
import paramiko
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import damodel_env

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

host, port, user, password = damodel_env.load()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK_DIR = os.path.join(ROOT, "cloud_train_pack")
ARCHIVE = os.path.join(ROOT, "cloud_train_pack.tar.gz")
REMOTE_DIR = "/root/virtu_train"

# 1. 重新打包
print("[1/5] 重新打包 cloud_train_pack.tar.gz ...")
with tarfile.open(ARCHIVE, "w:gz") as tar:
    tar.add(os.path.join(PACK_DIR, "train_turnkey.py"), arcname="train_turnkey.py")
    tar.add(os.path.join(PACK_DIR, "run.sh"), arcname="run.sh")
    tar.add(os.path.join(PACK_DIR, "dataset"), arcname="dataset")
print(f"  -> 打包完成！大小: {os.path.getsize(ARCHIVE)/1024/1024:.2f} MB")

# 2. 连接并上传
print(f"[2/5] 连接云端实例: {user}@{host}:{port} ...")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(hostname=host, port=port, username=user, password=password, timeout=60, banner_timeout=60)
print("  -> SSH 连接成功！")

# 杀死旧的进程如果存在
client.exec_command("pkill -f train_turnkey.py 2>/dev/null; pkill -f run.sh 2>/dev/null")

sftp = client.open_sftp()
client.exec_command(f"mkdir -p {REMOTE_DIR}")
remote_tar = f"{REMOTE_DIR}/cloud_train_pack.tar.gz"
print(f"[3/5] 上传至云端 {remote_tar} ...")
sftp.put(ARCHIVE, remote_tar)
sftp.close()

# 3. 解压并赋予权限
print("[4/5] 远端解压并赋予权限 ...")
client.exec_command(f"cd {REMOTE_DIR} && tar -zxvf cloud_train_pack.tar.gz && chmod +x run.sh")
time.sleep(2)

# 4. 启动后台训练
print("[5/5] 启动后台训练任务 (nohup bash run.sh > train.log 2>&1 &) ...")
client.exec_command(f"cd {REMOTE_DIR} && nohup bash run.sh > train.log 2>&1 &")
time.sleep(4)

# 5. 持续流式打印日志
print("\n" + "="*70)
print("📜 实时训练监控 (前 60 秒状态跟踪) :")
print("="*70)

for _ in range(12):
    time.sleep(5)
    stdin, stdout, stderr = client.exec_command(f"tail -n 25 {REMOTE_DIR}/train.log")
    log_content = stdout.read().decode('utf-8', errors='replace').strip()
    print(f"--- [+{_+1}*5s] ---")
    print(log_content)
    if "开始极速模型训练" in log_content or "trainable params" in log_content.lower():
        print("\n🎉 成功进入正式模型训练循环！")
        break

client.close()
