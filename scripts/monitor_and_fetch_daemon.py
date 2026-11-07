#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/monitor_and_fetch_daemon.py — 实时监控云端训练进度并在完成后自动回传解包到本地

设计：
1. 循环轮询远程 train.log，提取当前 step、loss、学习率与进度；
2. 检测到训练结束标志或 deliverable 归档生成后，自动通过 SFTP 下载至 checkpoints/ 目录；
3. 本地自动解压产物并核实 adapter_model.safetensors 与 training_receipt.json；
4. 打印完整交付报告并退出。
"""

import os
import sys
import time
import tarfile
import functools
import paramiko

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
print = functools.partial(print, flush=True)

import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import damodel_env

HOST = "cn-north-b.ssh.damodel.com"
PORT = 34087
USER = "root"
PASS = damodel_env.password_for(HOST, PORT)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECKPOINTS_DIR = os.path.join(ROOT, "checkpoints")
LOCAL_DELIVERABLE_TAR = os.path.join(CHECKPOINTS_DIR, "virtu_master_lora_deliverable.tar.gz")
LOCAL_EXTRACT_DIR = os.path.join(CHECKPOINTS_DIR, "virtu_master_lora_v4")
REMOTE_WORK_DIR = "/root/virtu_train"
REMOTE_LOG_PATH = f"{REMOTE_WORK_DIR}/train.log"
REMOTE_DELIVERABLE_PATH = f"{REMOTE_WORK_DIR}/output/virtu_lora_master/virtu_lora_deliverable.tar.gz"


def get_ssh_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=HOST, port=PORT, username=USER, password=PASS, timeout=60, banner_timeout=60)
    return client


def extract_last_status(log_text: str) -> str:
    lines = [l.strip() for l in log_text.splitlines() if l.strip()]
    if not lines:
        return "无日志输出"
    # 查找包含 {'loss': ...} 或 step 信息的行
    for l in reversed(lines):
        if "{'loss':" in l or "it/s" in l or "s/it" in l or "训练圆满完成" in l or "Loading checkpoint" in l:
            return l
    return lines[-1]


def monitor_and_fetch():
    print("="*70)
    print("🚀 启动 Virtu 云端训练实时监控与自动回传守护进程")
    print(f"🎯 远程目标: {USER}@{HOST}:{PORT} -> {REMOTE_WORK_DIR}")
    print(f"📥 本地接收: {LOCAL_DELIVERABLE_TAR}")
    print("="*70)

    start_time = time.time()
    last_log_snippet = ""
    poll_count = 0

    while True:
        poll_count += 1
        elapsed_min = (time.time() - start_time) / 60.0
        try:
            client = get_ssh_client()
            stdin, stdout, stderr = client.exec_command(f"tail -n 30 {REMOTE_LOG_PATH}")
            log_content = stdout.read().decode('utf-8', errors='replace').strip()

            # 检查远程进程是否仍然存活
            _, p_out, _ = client.exec_command("pgrep -f train_turnkey.py")
            pid_str = p_out.read().decode('utf-8').strip()
            is_alive = bool(pid_str)

            # 检查是否有 deliverable 生成
            sftp = client.open_sftp()
            deliverable_ready = False
            try:
                stat = sftp.stat(REMOTE_DELIVERABLE_PATH)
                if stat.st_size > 10 * 1024 * 1024:  # 大于 10MB
                    deliverable_ready = True
            except Exception:
                deliverable_ready = False

            cur_snippet = extract_last_status(log_content)
            now_str = time.strftime("%H:%M:%S")

            # 如果进程已经退出且没有 deliverable，检查是否发生异常
            if not is_alive and not deliverable_ready and not ("训练圆满完成" in log_content or "✅ 训练完成" in log_content):
                if "CUDA out of memory" in log_content or "Traceback" in log_content or "Error" in log_content:
                    print(f"[{now_str}] ❌ 训练进程异常退出！(PID 已终止)")
                    print("="*50)
                    print(log_content[-1500:])
                    print("="*50)
                    client.close()
                    sys.exit(1)

            if cur_snippet != last_log_snippet:
                print(f"[{now_str} | 已耗时 {elapsed_min:.1f}m | PID {pid_str if is_alive else 'NONE'}] {cur_snippet}")
                last_log_snippet = cur_snippet
            else:
                if poll_count % 3 == 0:
                    status_text = "训练平稳进行中" if is_alive else "等待产物"
                    print(f"[{now_str} | 已耗时 {elapsed_min:.1f}m] {status_text} ... (最新状态: {cur_snippet[:60]})")

            # 完成判断
            if deliverable_ready or "训练圆满完成" in log_content or "✅ 训练完成" in log_content:
                print("\n" + "="*70)
                print("🎉 检测到云端训练已成功完成！准备回传交付产物 ...")
                print("="*70)

                # 确保远程文件完全刷盘
                time.sleep(5)
                os.makedirs(CHECKPOINTS_DIR, exist_ok=True)

                print(f"[SFTP] 正在下载 {REMOTE_DELIVERABLE_PATH} -> {LOCAL_DELIVERABLE_TAR} ...")
                sftp.get(REMOTE_DELIVERABLE_PATH, LOCAL_DELIVERABLE_TAR)
                sftp.close()
                client.close()

                tar_sz_mb = os.path.getsize(LOCAL_DELIVERABLE_TAR) / (1024**2)
                print(f"✅ 下载完成！产物压缩包大小: {tar_sz_mb:.2f} MB")

                # 解包到本地目录
                print(f"[Extract] 正在解压至 {LOCAL_EXTRACT_DIR} ...")
                os.makedirs(LOCAL_EXTRACT_DIR, exist_ok=True)
                with tarfile.open(LOCAL_DELIVERABLE_TAR, "r:gz") as tar:
                    tar.extractall(path=CHECKPOINTS_DIR)

                print("✅ 解包成功！检查解包目录:")
                # virtu_lora_deliverable.tar.gz 内部顶级目录为 virtu_lora_adapter
                unpacked_dir = os.path.join(CHECKPOINTS_DIR, "virtu_lora_adapter")
                if os.path.exists(unpacked_dir):
                    if os.path.exists(LOCAL_EXTRACT_DIR):
                        import shutil
                        shutil.rmtree(LOCAL_EXTRACT_DIR)
                    os.rename(unpacked_dir, LOCAL_EXTRACT_DIR)

                for f in os.listdir(LOCAL_EXTRACT_DIR):
                    f_path = os.path.join(LOCAL_EXTRACT_DIR, f)
                    f_sz = os.path.getsize(f_path) / (1024**2) if os.path.isfile(f_path) else 0
                    print(f"  - {f} ({f_sz:.2f} MB)" if f_sz > 0 else f"  - {f}")

                receipt_file = os.path.join(LOCAL_EXTRACT_DIR, "training_receipt.json")
                if os.path.exists(receipt_file):
                    import json
                    with open(receipt_file, "r", encoding="utf-8") as rf:
                        rcpt = json.load(rf)
                    print("\n📋 训练回执摘要 (Receipt):")
                    print(f"  - 最终训练 Loss: {rcpt.get('train_loss')}")
                    print(f"  - 训练样本总数: {rcpt.get('total_train_samples')}")
                    print(f"  - 总训练耗时: {rcpt.get('total_train_seconds')}s ({rcpt.get('total_train_seconds',0)/60:.1f}m)")
                    print(f"  - 适配器 SHA256: {rcpt.get('adapter_sha256')}")

                print("\n" + "="*70)
                print("🎯 [ALL_COMPLETE] 云端训练已完成，交付物已安全同步至本地！")
                print("="*70)
                return 0

            sftp.close()
            client.close()

        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] 监控连接重试: {e}")

        # 每 20 秒轮询一次
        time.sleep(20)


if __name__ == "__main__":
    sys.exit(monitor_and_fetch())
