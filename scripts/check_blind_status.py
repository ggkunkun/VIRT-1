import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("cn-north-b.ssh.damodel.com", port=40526, username="root", password="m2A5jbYmbP", timeout=15)

stdin, stdout, stderr = client.exec_command("ls -lt /root/cad_cam_finetune/*.json /root/*.json 2>/dev/null")
print("=== JSON FILES ===")
print(stdout.read().decode())

stdin, stdout, stderr = client.exec_command("ls -lh /root/cad_cam_finetune/output_checkpoints/cad_cam_six_software_lora_final")
print("=== FINAL ADAPTER FILES ===")
print(stdout.read().decode())

client.close()
