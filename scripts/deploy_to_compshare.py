#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/deploy_to_compshare.py — Virtu 进化版云端 GPU 训练一键部署、监控与成果回传总控脚本

目标主机：cpod-1xc9awyq3yn1.podtcp.compshare.cn:29306 (NVIDIA GeForce RTX 4090 24GB)
预置基座：/model/ModelScope/Qwen/Qwen3-8B (共享云盘零下载开销)
远程目录：/root/virtu_evolution_train

支持操作：
  python scripts/deploy_to_compshare.py --upload     # 打包并上传训练套件与防污染语料
  python scripts/deploy_to_compshare.py --selftest   # 远程执行逻辑通道自检
  python scripts/deploy_to_compshare.py --smoke      # 启动 2 分钟极速冒烟验证 (验证 4090 算力)
  python scripts/deploy_to_compshare.py --start      # 启动全流程生产级训练 (SFT + DPO + 评测 + GGUF)
  python scripts/deploy_to_compshare.py --status     # 查看 GPU 占用与最近训练进度
  python scripts/deploy_to_compshare.py --logs       # 实时跟踪最近 50 行训练日志
  python scripts/deploy_to_compshare.py --stop       # 安全停止远程训练任务
  python scripts/deploy_to_compshare.py --download   # 下载训练完成的最终成果包至本地
"""

from __future__ import annotations

import argparse
import os
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

HOST = "cpod-1xc9awyq3yn1.podtcp.compshare.cn"
PORT = 29306
USER = "root"
PASSWORD = "3NP6G214m098WXoQ"
BASE_MODEL = "/model/ModelScope/Qwen/Qwen3-8B"
REMOTE_DIR = "/root/virtu_evolution_train"
LOCAL_ARCHIVE = ROOT / "cloud_train_evolution_pack.tar.gz"


def get_ssh_client():
    import paramiko
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=HOST,
        port=PORT,
        username=USER,
        password=PASSWORD,
        timeout=30,
        banner_timeout=30
    )
    return client


def make_tarball() -> Path:
    print("[1/3] 正在打包 cloud_train_evolution_pack.tar.gz ...")
    with tarfile.open(LOCAL_ARCHIVE, "w:gz") as tar:
        tar.add(str(ROOT / "cloud_train_pack"), arcname="cloud_train_pack")
        tar.add(str(ROOT / "scripts" / "virtu_tokenize.py"), arcname="scripts/virtu_tokenize.py")
        tar.add(str(ROOT / "scripts" / "hf_to_gguf_numpy.py"), arcname="scripts/hf_to_gguf_numpy.py")
        tar.add(str(ROOT / "virtu_eval"), arcname="virtu_eval")
        tar.add(str(ROOT / "data" / "benchmark"), arcname="data/benchmark")
    sz_mb = LOCAL_ARCHIVE.stat().st_size / (1024 * 1024)
    print(f"  -> 打包完成！归档体积: {sz_mb:.2f} MB")
    return LOCAL_ARCHIVE


def upload_pack():
    make_tarball()
    print(f"[2/3] 连接云端服务器: {USER}@{HOST}:{PORT} ...")
    client = get_ssh_client()
    sftp = client.open_sftp()

    client.exec_command(f"mkdir -p {REMOTE_DIR}")
    remote_tar = f"{REMOTE_DIR}/cloud_train_evolution_pack.tar.gz"
    print(f"[3/3] 上传至云端 {remote_tar} ...")
    sftp.put(str(LOCAL_ARCHIVE), remote_tar)
    sftp.close()

    print("  -> 正在云端解压并赋予脚本权限...")
    client.exec_command(f"cd {REMOTE_DIR} && tar -zxvf cloud_train_evolution_pack.tar.gz && chmod +x cloud_train_pack/*.sh")
    client.close()
    print("🎉 上传与部署就绪！")


def check_status():
    client = get_ssh_client()
    cmd = f"""
    echo "=== GPU 状态与显存占用 ==="
    nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu --format=csv,noheader
    echo "=== 训练进程 ==="
    ps aux | grep -E "train_cloud_virtu_evolution|run_evolution_train" | grep -v grep || echo "无正在运行的训练进程"
    echo "=== 最近日志 ==="
    tail -n 20 {REMOTE_DIR}/train.log 2>/dev/null || echo "暂无 train.log"
    """
    _, out, _ = client.exec_command(cmd)
    print(out.read().decode("utf-8", errors="replace"))
    client.close()


def show_logs(lines: int = 40):
    client = get_ssh_client()
    cmd = f"tr '\\r' '\\n' < {REMOTE_DIR}/train.log 2>/dev/null | grep -v 'Loading weights:' | tail -n {lines}"
    _, out, _ = client.exec_command(cmd)
    print(out.read().decode("utf-8", errors="replace"))
    client.close()


def stop_training():
    client = get_ssh_client()
    print("正在终止远程训练进程...")
    client.exec_command("pkill -9 -f train_cloud_virtu_evolution 2>/dev/null; pkill -9 -f run_evolution_train 2>/dev/null")
    time.sleep(2)
    print("  -> 进程已清理！")
    client.close()


def run_remote_command(cmd_args: str, background: bool = False):
    client = get_ssh_client()
    py_exec = "/usr/local/miniconda3/envs/py312/bin/python"
    sh_exec = f"{REMOTE_DIR}/cloud_train_pack/run_evolution_train.sh"

    # 优先使用 py312 环境
    env_prefix = f"export ECT_PYTHON={py_exec} && export VIRTU_BASE={BASE_MODEL} && cd {REMOTE_DIR}"

    if background:
        stop_training()
        full_cmd = f"{env_prefix} && nohup bash {sh_exec} --base={BASE_MODEL} {cmd_args} > train.log 2>&1 &"
        print(f"后台启动训练: {full_cmd}")
        client.exec_command(full_cmd)
        time.sleep(3)
        print("🎉 任务已在后台成功挂起！开始实时监控日志 (30s)...")
        for i in range(6):
            time.sleep(5)
            _, out, _ = client.exec_command(f"tail -n 15 {REMOTE_DIR}/train.log 2>/dev/null")
            content = out.read().decode("utf-8", errors="replace").strip()
            print(f"--- [T+{ (i+1)*5 }s] ---")
            print(content)
            if "开始执行 QLoRA" in content or "Trainer" in content or "Profile 选定" in content:
                print("\n🚀 成功进入模型训练流水线！")
                break
    else:
        full_cmd = f"{env_prefix} && bash {sh_exec} --base={BASE_MODEL} {cmd_args}"
        print(f"前台执行: {full_cmd}")
        stdin, stdout, stderr = client.exec_command(full_cmd, get_pty=True)
        for line in stdout:
            print(line, end="")
    client.close()


def download_artifacts(include_gguf: bool = False):
    client = get_ssh_client()
    sftp = client.open_sftp()
    remote_output = f"{REMOTE_DIR}/cloud_train_pack/output"
    local_output = ROOT / "cloud_train_pack" / "output"
    local_output.mkdir(parents=True, exist_ok=True)

    print(f"正在扫描远端成果目录: {remote_output} ...")
    try:
        files = sftp.listdir(remote_output)
    except Exception as e:
        print(f"未找到远端输出目录或无成果物: {e}")
        client.close()
        return

    print(f"发现远端成果: {files}")
    valid_exts = [".tar.gz", ".sha256", ".json", ".md"]
    if include_gguf:
        valid_exts.append(".gguf")

    for fname in sorted(files):
        if any(fname.endswith(ext) for ext in valid_exts):
            rpath = f"{remote_output}/{fname}"
            lpath = local_output / fname
            sz_mb = sftp.stat(rpath).st_size / (1024 * 1024)
            print(f"  -> 正在下载 {fname} ({sz_mb:.2f} MB) -> {lpath} ...")
            sftp.get(rpath, str(lpath))
    sftp.close()
    client.close()
    print("🎉 成果物已成功同步回本地！")


def main():
    parser = argparse.ArgumentParser(description="Virtu 进化版云端 GPU 训练一键总控")
    parser.add_argument("--upload", action="store_true", help="重新打包并上传训练套件")
    parser.add_argument("--selftest", action="store_true", help="远程执行逻辑自检")
    parser.add_argument("--smoke", action="store_true", help="远程执行极速冒烟验证 (2分钟)")
    parser.add_argument("--start", action="store_true", help="启动全流程生产级训练")
    parser.add_argument("--status", action="store_true", help="查看远程 GPU 与训练状态")
    parser.add_argument("--logs", action="store_true", help="查看最近训练日志")
    parser.add_argument("--stop", action="store_true", help="停止远程训练")
    parser.add_argument("--download", action="store_true", help="下载远程成果包 (报告、Adapter、Modelfile 与账本)")
    parser.add_argument("--include-gguf", action="store_true", help="配合 --download 一同下载 4.6GB GGUF 模型")
    args = parser.parse_args()

    if args.upload:
        upload_pack()
    elif args.selftest:
        run_remote_command("--selftest", background=False)
    elif args.smoke:
        run_remote_command("--smoke", background=True)
    elif args.start:
        run_remote_command("--epochs 2.0 --dpo-epochs 1.0", background=True)
    elif args.status:
        check_status()
    elif args.logs:
        show_logs(50)
    elif args.stop:
        stop_training()
    elif args.download:
        download_artifacts(include_gguf=args.include_gguf)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
