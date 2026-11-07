# -*- coding: utf-8 -*-
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

LOCAL_ROOT = Path(r"d:\Virtu模型")
LOCAL_LORA_DIR = LOCAL_ROOT / "checkpoints" / "virtu_toolcall_lora"
REMOTE_LORA_DIR = "/root/workspace/virtu/virtu_toolcall_lora"
REMOTE_LOG_DIR = "/root/workspace/virtu/logs"


def download():
    LOCAL_LORA_DIR.mkdir(parents=True, exist_ok=True)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=HOST, port=PORT, username=USER, password=PASS, timeout=30)
    
    sftp = client.open_sftp()
    print(f"[DOWNLOAD] 开始从远程 {REMOTE_LORA_DIR} 拷贝权重文件到本地 {LOCAL_LORA_DIR} ...")
    
    remote_files = sftp.listdir(REMOTE_LORA_DIR)
    total_size = 0
    for fname in remote_files:
        rpath = f"{REMOTE_LORA_DIR}/{fname}"
        lpath = LOCAL_LORA_DIR / fname
        stat = sftp.stat(rpath)
        # Skip subdirectories like checkpoint-*
        if str(stat)[0] == "d":
            continue
        size_mb = stat.st_size / (1024 * 1024)
        total_size += stat.st_size
        print(f"  -> 下载 {fname} ({size_mb:.2f} MB) ...", end="", flush=True)
        sftp.get(rpath, str(lpath))
        print(" [OK]")

    # 下载日志
    try:
        r_log = f"{REMOTE_LOG_DIR}/train.log"
        l_log = LOCAL_LORA_DIR / "remote_train.log"
        sftp.get(r_log, str(l_log))
        print(f"  -> 下载完整训练日志 train.log [OK]")
    except Exception as e:
        print(f"  -> 日志下载提示: {e}")

    sftp.close()
    client.close()
    print(f"\n[SUCCESS] 全部文件已成功拷贝回本地！总大小: {total_size / (1024 * 1024):.2f} MB")


if __name__ == "__main__":
    download()
