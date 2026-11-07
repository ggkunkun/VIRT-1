import os
import paramiko
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import damodel_env

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
DAMODEL_PASS = os.environ.get("DAMODEL_PASS", "")
if not DAMODEL_PASS:
    raise SystemExit(
        "[FATAL] 未设置 DAMODEL_PASS 环境变量；该实例口令已泄漏于 git 历史，"
        "必须先轮换密码，再通过环境变量注入，不要写回源码。"
    )

host, port, user, password = damodel_env.load()
client.connect(host, port=port, username=user, password=DAMODEL_PASS, timeout=15)

stdin, stdout, stderr = client.exec_command("tail -n 10 /root/cad_cam_finetune/train.log")
print("=== TAIL TRAIN.LOG ===")
print(stdout.read().decode())

stdin, stdout, stderr = client.exec_command("grep -E 'TRAINING COMPLETE|Step' /root/cad_cam_finetune/train.log | tail -n 5")
print("=== GREP LOG ===")
print(stdout.read().decode())

stdin, stdout, stderr = client.exec_command("ls -lh /root/cad_cam_finetune/output_checkpoints/cad_cam_six_software_lora_final 2>/dev/null")
print("=== SAVED CHECKPOINT ===")
print(stdout.read().decode())

stdin, stdout, stderr = client.exec_command("nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader")
print("=== NVIDIA APPS ===")
print(stdout.read().decode())

client.close()
