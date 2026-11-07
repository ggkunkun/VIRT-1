import paramiko
import re
import json

HOST = "cpod-1xesnvd6jbqp.podtcp.compshare.cn"
PORT = 24334
USER = "root"
PASS = "0158TRUs7ihD9y23"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)

# 1. GPU 状态
stdin, stdout, stderr = client.exec_command(
    "nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw --format=csv,noheader,nounits"
)
gpu_raw = stdout.read().decode().strip().split(",")
gpu_info = {
    "utilization": f"{gpu_raw[0].strip()}%",
    "mem_used": f"{gpu_raw[1].strip()} MB",
    "mem_total": f"{gpu_raw[2].strip()} MB",
    "temp": f"{gpu_raw[3].strip()} °C",
    "power": f"{gpu_raw[4].strip()} W"
}

# 2. 读取 log 中所有的 loss 记录
stdin, stdout, stderr = client.exec_command("cat /root/cloud_train_pack/output_13b/train_live.log")
full_log = stdout.read().decode("utf-8", errors="replace")

clean_lines = [l.strip() for l in full_log.split("\r") if l.strip()]
non_bar = [l for l in clean_lines if "%|" not in l and "it/s" not in l and "s/it" not in l]

print("Non bar lines sample (last 20):")
for l in non_bar[-20:]:
    print(l)

# 提取最新的 tqdm 进度条行
tqdm_lines = [l for l in clean_lines if "it/s" in l or "s/it" in l]
latest_tqdm = tqdm_lines[-1] if tqdm_lines else "N/A"

res = {
    "gpu": gpu_info,
    "latest_tqdm": latest_tqdm
}

print(json.dumps(res, indent=2, ensure_ascii=False))
client.close()
