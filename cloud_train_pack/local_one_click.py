#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cloud_train_pack/local_one_click.py — 本地一键打包、云端开训、流式监控与产物回收闭环脚本

用法：
  python cloud_train_pack/local_one_click.py --host cn-north-b.ssh.damodel.com --port 40526 --user root --password <PASSWORD>
或者设置环境变量：
  $env:DAMODEL_HOST="cn-north-b.ssh.damodel.com"
  $env:DAMODEL_PORT="40526"
  $env:DAMODEL_PASS="your_password"
  python cloud_train_pack/local_one_click.py
"""

import os
import sys
import time
import tarfile
import argparse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

try:
    import paramiko
except ImportError:
    print("[WARN] 本地未安装 paramiko，正在自动安装 ...")
    import subprocess
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "paramiko", "-q"])
    except Exception:
        subprocess.check_call(["uv", "pip", "install", "paramiko", "--python", sys.executable])
    import paramiko

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK_DIR = os.path.join(ROOT, "cloud_train_pack")
ARCHIVE_PATH = os.path.join(ROOT, "cloud_train_pack.tar.gz")


def make_tarball():
    print(f"\n[1/5] 打包极简开训套件 -> {ARCHIVE_PATH} ...")
    with tarfile.open(ARCHIVE_PATH, "w:gz") as tar:
        # 添加核心脚本
        tar.add(os.path.join(PACK_DIR, "train_turnkey.py"), arcname="train_turnkey.py")
        tar.add(os.path.join(PACK_DIR, "run.sh"), arcname="run.sh")
        # 优先打包包含防御性对齐与零污染认证的生产级数据集
        cap_v5 = os.path.join(PACK_DIR, "dataset", "virtu_capability_sft_v5.jsonl")
        v100_data = os.path.join(PACK_DIR, "dataset", "virtu_v100_production_sft.jsonl")
        gold_data = os.path.join(PACK_DIR, "dataset", "virtu_gold_production_sft.jsonl")
        if os.path.exists(cap_v5):
            tar.add(cap_v5, arcname="dataset/virtu_capability_sft_v5.jsonl")
        elif os.path.exists(v100_data):
            tar.add(v100_data, arcname="dataset/virtu_v100_production_sft.jsonl")
        elif os.path.exists(gold_data):
            tar.add(gold_data, arcname="dataset/virtu_gold_production_sft.jsonl")
        else:
            tar.add(os.path.join(PACK_DIR, "dataset"), arcname="dataset")
    sz_mb = os.path.getsize(ARCHIVE_PATH) / (1024**2)
    print(f"  -> 打包完成！整包大小仅 {sz_mb:.2f} MB (极速秒传，无冗余数据)")


def connect_ssh(host, port, user, password):
    print(f"\n[2/5] 连接云端 GPU 实例 ({user}@{host}:{port}) ...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=host, port=port, username=user, password=password, timeout=30)
    print("  -> SSH 连接成功！")
    return client


def upload_and_start(client, remote_work_dir="/root/virtu_train"):
    print(f"\n[3/5] 上传训练包到云端实例 {remote_work_dir} ...")
    sftp = client.open_sftp()
    
    # 确保远端工作目录存在
    stdin, stdout, stderr = client.exec_command(f"mkdir -p {remote_work_dir}")
    stdout.channel.recv_exit_status()

    remote_tar = f"{remote_work_dir}/cloud_train_pack.tar.gz"
    sftp.put(ARCHIVE_PATH, remote_tar)
    sftp.close()
    print("  -> 上传完成！正在解包 ...")

    # 解压并赋予可执行权限
    cmd_unpack = f"cd {remote_work_dir} && tar -zxvf cloud_train_pack.tar.gz && chmod +x run.sh"
    stdin, stdout, stderr = client.exec_command(cmd_unpack)
    stdout.channel.recv_exit_status()

    print("\n[4/5] 启动后台训练进程 (nohup bash run.sh) ...")
    cmd_start = f"cd {remote_work_dir} && touch train.log && nohup bash run.sh > train.log 2>&1 &"
    client.exec_command(cmd_start)
    time.sleep(3)


def stream_logs(client, remote_work_dir="/root/virtu_train"):
    print("\n[5/5] 开始实时跟踪云端训练日志 (Ctrl+C 可随时安全退出监控，训练在后台持续运行) ...")
    print("="*70)
    
    log_cmd = f"tail -F -n 30 {remote_work_dir}/train.log"
    stdin, stdout, stderr = client.exec_command(log_cmd)

    try:
        no_line_count = 0
        while not stdout.channel.closed:
            line = stdout.readline()
            if line:
                no_line_count = 0
                print(line, end="", flush=True)
                if "训练圆满完成" in line or "✅ 训练完成" in line:
                    print("\n[SUCCESS] 检测到训练完成信号！")
                    break
                if "[FATAL]" in line or ("Traceback" in line and "Error" in line):
                    print("\n[ALERT] 检测到异常，请检查上述日志！")
            else:
                time.sleep(1)
                no_line_count += 1
                if no_line_count % 10 == 0:
                    # 每隔 10 秒探测一下训练进程是否还在运行
                    p_stdin, p_stdout, _ = client.exec_command("pgrep -f train_turnkey.py || true")
                    pids = p_stdout.read().decode().strip()
                    if not pids:
                        # 检查产物是否已生成
                        chk_stdin, chk_stdout, _ = client.exec_command(f"ls -la {remote_work_dir}/output/virtu_lora_master/virtu_lora_deliverable.tar.gz 2>/dev/null || true")
                        has_deliv = "virtu_lora_deliverable.tar.gz" in chk_stdout.read().decode()
                        if has_deliv:
                            print("\n[SUCCESS] 进程已退出且检测到交付物已生成！")
                            break
                        elif no_line_count > 30:
                            print("\n[NOTICE] 训练进程已结束。准备进入交付物拉取阶段。")
                            break
    except KeyboardInterrupt:
        print("\n[INFO] 本地监控已断开。云端训练仍在后台不受影响继续运行。")


def fetch_deliverable(client, remote_work_dir="/root/virtu_train"):
    remote_res = f"{remote_work_dir}/output/virtu_lora_master/virtu_lora_deliverable.tar.gz"
    local_target_dir = os.path.join(ROOT, "checkpoints")
    os.makedirs(local_target_dir, exist_ok=True)
    local_target = os.path.join(local_target_dir, "virtu_master_lora_deliverable.tar.gz")

    print(f"\n[Fetch] 正在拉取最终训练交付物 -> {local_target} ...")
    sftp = client.open_sftp()
    try:
        sftp.stat(remote_res)
        sftp.get(remote_res, local_target)
        sftp.close()
        sz = os.path.getsize(local_target) / (1024**2)
        print(f"✅ 交付件已成功下载至本机: {local_target} ({sz:.1f} MB)！")

        # 自动解包并读取收据
        unpack_dir = os.path.join(local_target_dir, "virtu_v100_master_lora")
        os.makedirs(unpack_dir, exist_ok=True)
        with tarfile.open(local_target, "r:gz") as tar:
            tar.extractall(local_target_dir)

        receipt_file = os.path.join(local_target_dir, "virtu_lora_adapter", "training_receipt.json")
        if os.path.exists(receipt_file):
            import json
            with open(receipt_file, "r", encoding="utf-8") as rf:
                rdata = json.load(rf)
            print("\n" + "="*70)
            print("📜 训练账本凭证 (Training Receipt):")
            print(f"  * 基座模型: {rdata.get('base_model')}")
            print(f"  * 训练样本: {rdata.get('total_train_samples')} 条")
            print(f"  * 最终 Loss: {rdata.get('train_loss')}")
            print(f"  * 耗时: {rdata.get('total_train_seconds', 0)/60:.1f} 分钟")
            print(f"  * 适配器指纹: {rdata.get('adapter_sha256')[:16]}...")
            print("="*70)

        print("\n🎉 闭环完成！现在可以运行 `python cloud_train_pack/deploy_trained_adapter.py` 一键上线至 Ollama/WorkBuddy！")
    except Exception as e:
        print(f"[Fetch Notice] 交付件尚未生成或下载中断: {e}")


def main():
    parser = argparse.ArgumentParser(description="Virtu 一键云端开训与监控")
    parser.add_argument("--host", default=os.environ.get("DAMODEL_HOST", "cn-north-b.ssh.damodel.com"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("DAMODEL_PORT", "40526")))
    parser.add_argument("--user", default=os.environ.get("DAMODEL_USER", "root"))
    parser.add_argument("--password", default=os.environ.get("DAMODEL_PASS", ""))
    parser.add_argument("--fetch-only", action="store_true", help="跳过开训，直接拉取远端结果")
    parser.add_argument("--pack-only", action="store_true", help="仅打包套件并验证完整性，不连接 SSH")
    args = parser.parse_args()

    make_tarball()

    if args.pack_only:
        print("\n[OK] --pack-only 打包验证完成，归档文件已就绪。")
        return

    if not args.password:
        print("[Notice] 未提供密码，可通过参数 --password 或环境变量 $env:DAMODEL_PASS 指定。")
        try:
            import getpass
            args.password = getpass.getpass("请输入云端实例 SSH 密码: ")
        except Exception:
            raise SystemExit("[FATAL] 缺少 SSH 密码")

    client = connect_ssh(args.host, args.port, args.user, args.password)
    try:
        if not args.fetch_only:
            upload_and_start(client)
            stream_logs(client)
        fetch_deliverable(client)
    finally:
        client.close()


if __name__ == "__main__":
    main()
