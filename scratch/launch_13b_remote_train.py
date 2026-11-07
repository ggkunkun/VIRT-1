import paramiko
import sys
import time

HOST = "cpod-1xesnvd6jbqp.podtcp.compshare.cn"
PORT = 24334
USER = "root"
PASS = "0158TRUs7ihD9y23"

def launch_training(smoke: bool = False, stage: str = "all", base: str = "/model/ModelScope/Qwen/Qwen3-14B"):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=20)

    py_bin = "/usr/local/miniconda3/envs/py312/bin/python"
    remote_dir = "/root/cloud_train_pack"
    log_file = f"{remote_dir}/output_13b/train_live.log"

    # 确保目录存在
    client.exec_command("mkdir -p /root/cloud_train_pack/output_13b")

    smoke_flag = "--smoke" if smoke else ""
    cmd = (
        f"cd {remote_dir} && nohup {py_bin} -u train_cloud_virtu_13b.py "
        f"--base {base} --stage {stage} --epochs 1.5 --lr 1.2e-4 --dpo_lr 4e-6 {smoke_flag} "
        f"> {log_file} 2>&1 & echo $!"
    )
    print(f"Executing remote start: {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd)
    pid = stdout.read().decode().strip()
    print(f"[OK] Training process launched in background! PID = {pid}")
    
    time.sleep(3)
    stdin, stdout, stderr = client.exec_command(f"head -n 25 {log_file}")
    print(f"\n--- Initial Output from {log_file}: ---")
    print(stdout.read().decode().strip())
    
    client.close()
    return pid

if __name__ == "__main__":
    smoke_mode = "--smoke" in sys.argv
    launch_training(smoke=smoke_mode)
