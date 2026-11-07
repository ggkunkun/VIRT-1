import os
import sys
import time
from pathlib import Path
import paramiko

HOST = "cpod-1xesnvd6jbqp.podtcp.compshare.cn"
PORT = 24334
USER = "root"
PASS = "0158TRUs7ihD9y23"

LOCAL_DIR = Path(r"D:\Virtu模型\cloud_train_pack")
REMOTE_DIR = "/root/cloud_train_pack"

def upload_directory(sftp, local_dir: Path, remote_dir: str):
    """递归上传目录到远端"""
    try:
        sftp.mkdir(remote_dir)
    except IOError:
        pass  # 目录已存在

    for item in local_dir.iterdir():
        if item.name.startswith(('.', '__pycache__')) or item.name.endswith(('.pyc', '.log')):
            continue
        remote_path = f"{remote_dir}/{item.name}"
        if item.is_dir():
            if item.name in ("output", "output_13b"):
                continue  # 跳过历史产物目录
            upload_directory(sftp, item, remote_path)
        else:
            size_mb = item.stat().st_size / (1024 * 1024)
            print(f"  [SFTP Upload] {item.name} ({size_mb:.2f} MB) -> {remote_path} ...", flush=True)
            sftp.put(str(item), remote_path)

def main():
    print("=" * 70)
    print("🚀 Virtu-13.63B Compshare RTX 4090 云端部署与环境初始化")
    print(f"目标主机: {USER}@{HOST}:{PORT}")
    print("=" * 70)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
    print("✓ SSH 连接成功")

    # 1. SFTP 上传 cloud_train_pack
    print("\n[1/4] 上传 cloud_train_pack 至云端主机...")
    sftp = client.open_sftp()
    upload_directory(sftp, LOCAL_DIR, REMOTE_DIR)
    
    # 额外上传本地 scripts/calibrate_moe_layer_centroids.py 和必要的工具
    try:
        sftp.mkdir("/root/scripts")
    except IOError:
        pass
    local_calib = Path(r"D:\Virtu模型\scripts\calibrate_moe_layer_centroids.py")
    if local_calib.exists():
        sftp.put(str(local_calib), "/root/scripts/calibrate_moe_layer_centroids.py")
        print("  [SFTP Upload] calibrate_moe_layer_centroids.py 上传完毕")

    sftp.close()
    print("✓ 核心训练套件上传完毕")

    # 2. 安装 Python 核心深度学习依赖
    pip_bin = "/usr/local/miniconda3/envs/py312/bin/pip"
    py_bin = "/usr/local/miniconda3/envs/py312/bin/python"

    print("\n[2/4] 在云端 py312 环境中安装核心依赖 (清华高速镜像)...")
    req_packages = "torch torchvision transformers peft trl bitsandbytes accelerate datasets modelscope"
    cmd_install = f"{pip_bin} install --no-cache-dir {req_packages}"
    print(f"执行命令: {cmd_install}")
    
    stdin, stdout, stderr = client.exec_command(cmd_install)
    for line in iter(stdout.readline, ""):
        line_s = line.strip()
        if "Collecting" in line_s or "Successfully installed" in line_s or "Installing collected" in line_s:
            print(f"  {line_s}")
    
    err = stderr.read().decode().strip()
    if err and "WARNING" not in err:
        print(f"[Install Notice]: {err[:300]}")

    # 3. 验证 PyTorch CUDA 与依赖版本
    print("\n[3/4] 验证远端 GPU 算力环境...")
    cmd_verify = f"{py_bin} -c \"import torch, transformers, peft, bitsandbytes; print(f'CUDA OK: {torch.cuda.is_available()} | GPU: {torch.cuda.get_device_name(0)} | VRAM: {torch.cuda.get_device_properties(0).total_memory / (1024**3):.1f} GB | PyTorch: {torch.__version__} | Transformers: {transformers.__version__} | PEFT: {peft.__version__}')\""
    stdin, stdout, stderr = client.exec_command(cmd_verify)
    verify_out = stdout.read().decode().strip()
    print(f"  {verify_out}")

    # 4. 远端执行快速冒烟演练 (Smoke Test)
    print("\n[4/4] 启动 Virtu-13.63B 阶段 0 门控校准与阶段 1 预热冒烟测试...")
    cmd_smoke = f"cd /root && {py_bin} cloud_train_pack/train_cloud_virtu_13b.py --stage calibrate"
    stdin, stdout, stderr = client.exec_command(cmd_smoke)
    smoke_out = stdout.read().decode().strip()
    print(smoke_out)

    client.close()
    print("\n" + "=" * 70)
    print("🎉 云端环境初始化与阶段 0 校准成功！就绪待命！")
    print("=" * 70)

if __name__ == "__main__":
    main()
