import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("cn-north-b.ssh.damodel.com", port=40526, username="root", password="m2A5jbYmbP", timeout=15)

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
