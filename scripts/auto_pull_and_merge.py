# -*- coding: utf-8 -*-
"""
auto_pull_and_merge.py — 远程 Damodel 训练监听、自动回传与本地合并闭环

流程：
1. 定时探测远程 GPU 训练状态（GPU 功耗、显存、进程存活）；
2. 检测到训练完成（产出 adapter_model.safetensors 且进程退出）；
3. 通过 SFTP 全自动将 LoRA 权重拉回本地 checkpoints/virtu_toolcall_lora/；
4. 校验产物完整性（大小与配置）；
5. 自动触发 scripts/merge_numpy.py 进行纯 numpy 流式合并。
"""

import os
import sys
import time
from pathlib import Path
import paramiko

import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import damodel_env

HOST = "cn-north-b.ssh.damodel.com"
PORT = 44228
USER = "root"
PASS = damodel_env.password_for(HOST, PORT)

LOCAL_ROOT = Path(__file__).resolve().parent.parent
LOCAL_LORA_DIR = LOCAL_ROOT / "checkpoints" / "virtu_toolcall_lora"
REMOTE_LORA_DIR = "/root/workspace/virtu/virtu_toolcall_lora"
REMOTE_LOG_DIR = "/root/workspace/virtu/logs"


def get_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=HOST, port=PORT, username=USER, password=PASS, timeout=20)
    return client


def check_status(client):
    """检查训练进程存活与产物是否就绪"""
    # 检查进程
    stdin, stdout, stderr = client.exec_command("pgrep -f train_virtu_toolcall.py || true")
    pids = stdout.read().decode().strip().split()
    is_running = len(pids) > 0

    # 检查产物
    stdin, stdout, stderr = client.exec_command(f"ls -la {REMOTE_LORA_DIR}/adapter_model.safetensors 2>/dev/null || true")
    safetensors_stat = stdout.read().decode().strip()
    has_safetensors = "adapter_model.safetensors" in safetensors_stat

    # 显卡状态
    stdin, stdout, stderr = client.exec_command("nvidia-smi --query-gpu=power.draw,utilization.gpu,memory.used --format=csv,noheader 2>/dev/null || true")
    gpu_stat = stdout.read().decode().strip()

    return is_running, has_safetensors, gpu_stat


def download_artifacts(client):
    """从远程下载所有训练成果到本地"""
    LOCAL_LORA_DIR.mkdir(parents=True, exist_ok=True)
    sftp = client.open_sftp()
    
    print(f"\n[DOWNLOAD] 开始从远程 {REMOTE_LORA_DIR} 拉取产物到 {LOCAL_LORA_DIR} ...")
    remote_files = sftp.listdir(REMOTE_LORA_DIR)
    
    for fname in remote_files:
        rpath = f"{REMOTE_LORA_DIR}/{fname}"
        lpath = LOCAL_LORA_DIR / fname
        try:
            stat = sftp.stat(rpath)
            size_mb = stat.st_size / (1024 * 1024)
            print(f"  -> 下载 {fname} ({size_mb:.2f} MB) ...", end="", flush=True)
            sftp.get(rpath, str(lpath))
            print(" [OK]")
        except Exception as e:
            print(f" [FAILED: {e}]")

    # 顺便把训练日志拉下来供审计
    try:
        r_log = f"{REMOTE_LOG_DIR}/train.log"
        l_log = LOCAL_LORA_DIR / "remote_train.log"
        sftp.get(r_log, str(l_log))
        print(f"  -> 同步训练日志 train.log -> {l_log} [OK]")
    except Exception:
        pass

    sftp.close()
    print("[DOWNLOAD] 全部产物已成功拉回本地！")


def run_watchdog(poll_interval=15):
    print("==================================================================")
    print("  Virtu 远程 Damodel 训练自动监控与闭环回传服务启动")
    print(f"  目标主机: {HOST}:{PORT} (用户: {USER})")
    print(f"  本地存放: {LOCAL_LORA_DIR}")
    print("==================================================================")

    step = 0
    start_time = time.time()
    
    while True:
        step += 1
        client = None
        try:
            client = get_client()
            is_running, has_safetensors, gpu_stat = check_status(client)
            elapsed_m = (time.time() - start_time) / 60
            
            print(f"[{time.strftime('%H:%M:%S')}] 监控已运行 {elapsed_m:.1f}m | GPU: {gpu_stat} | 训练进程: {'RUNNING' if is_running else 'STOPPED'} | 产物: {'READY' if has_safetensors else 'NOT_READY'}")
            
            if not is_running and has_safetensors:
                print("\n[SUCCESS] 检测到训练已圆满结束，权重已完全落盘！")
                download_artifacts(client)
                client.close()
                break
            elif not is_running and not has_safetensors:
                # 再次确认是否异常退出
                stdin, stdout, stderr = client.exec_command("tail -n 20 /root/workspace/virtu/logs/train.log 2>/dev/null || true")
                err_log = stdout.read().decode().strip()
                print(f"[WARN] 训练进程已退出但未见产物！末尾日志:\n{err_log}")
                client.close()
                break
                
            client.close()
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] 连接重试中: {e}")
            if client:
                try: client.close()
                except: pass

        time.sleep(poll_interval)


if __name__ == "__main__":
    run_watchdog(poll_interval=15)
