#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
云端训练完成后的闭环第 3 步（由自动化定时触发）：
  1. 从 DAMODEL_PW 环境变量取得 SSH 密码，连云端
  2. 查 training_receipt.json 是否 status==COMPLETED（以及进程是否退出）
  3. 未完成 -> 打印 NOT_DONE 并退出（自动化下次再试）
  4. 完成   -> tar 打包 adapter(排除中间 checkpoint) -> SFTP 拉回本地
            -> 解压 -> 调用 deploy_local_sft.py --adapter-dir ... --switch --run-eval
            -> 成功后写 DEPLOYED.flag（凭据文件不由脚本管理）
用法（建议在 venv 下运行，确保有 paramiko）：
  D:/Virtu模型/.venv/Scripts/python.exe scripts/_train_done_pull_deploy.py
"""
import os
import sys
import shutil
import tarfile
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
ART_DIR = os.path.normpath(os.path.join(ROOT, "..", "cloud_artifacts"))
DEPLOYED_FLAG = os.path.join(ART_DIR, "DEPLOYED.flag")

REMOTE_OUT = "/root/virtu_train/out/virtu_hardened_v1_lora"
REMOTE_RECEIPT = REMOTE_OUT + "/training_receipt.json"
REMOTE_TARBALL = "/tmp/cad_cam_boundary_lora.tar.gz"
LOCAL_TAR = os.path.join(ART_DIR, "cad_cam_boundary_lora.tar.gz")
LOCAL_ADAPTER = os.path.join(ART_DIR, "cad_cam_boundary_lora")


def log(m):
    print(m, flush=True)


def main():
    if os.path.exists(DEPLOYED_FLAG):
        log("ALREADY_DEPLOYED: 已部署过，跳过（flag=%s）" % DEPLOYED_FLAG)
        return

    if not os.environ.get("DAMODEL_PW"):
        log("NO_CREDENTIALS: 缺少 DAMODEL_PW 环境变量，无法 SSH 拉取。")
        raise SystemExit(2)

    sys.path.insert(0, ROOT)
    import _ssh_damodel as S

    # 1) 查 receipt + 进程
    out, err, rc = S.run(
        "echo '=== RECEIPT ==='; cat %s 2>/dev/null; "
        "echo; echo '=== PROC ==='; pgrep -af train_virtu_v100.py || echo NO_PROC" % REMOTE_RECEIPT,
        timeout=60,
    )
    if "COMPLETED" not in out:
        log("NOT_DONE: 云端 receipt 尚未标记 COMPLETED（或训练进程仍在跑）。稍后重试。")
        return
    log("TRAINING_COMPLETED: 云端训练已完成，开始拉取 adapter。")

    # 2) 云端打包（排除中间 checkpoint，省流量）
    pk, pkerr, pkrc = S.run(
        "cd /root/virtu_train/out && tar czf %s --exclude='virtu_hardened_v1_lora/checkpoint-*' virtu_hardened_v1_lora"
        % REMOTE_TARBALL,
        timeout=300,
    )
    if pkrc != 0:
        log("TAR_FAILED: rc=%s err=%s" % (pkrc, pkerr[:500]))
        return

    # 3) SFTP 下载
    os.makedirs(ART_DIR, exist_ok=True)
    c = S._client()
    try:
        sftp = c.open_sftp()
        sftp.get(REMOTE_TARBALL, LOCAL_TAR)
        sftp.close()
    finally:
        c.close()
    log("DOWNLOADED: %s" % LOCAL_TAR)

    # 4) 解压（剥离远程顶层目录名 virtu_hardened_v1_lora，统一落到 LOCAL_ADAPTER=cad_cam_boundary_lora）
    if os.path.isdir(LOCAL_ADAPTER):
        shutil.rmtree(LOCAL_ADAPTER)
    os.makedirs(LOCAL_ADAPTER, exist_ok=True)
    with tarfile.open(LOCAL_TAR) as tf:
        for m in tf.getmembers():
            parts = m.name.split("/")
            if len(parts) <= 1:
                continue  # 跳过顶层目录自身
            rel = "/".join(parts[1:])
            if not rel:
                continue
            dest = os.path.join(LOCAL_ADAPTER, rel)
            if m.isdir():
                os.makedirs(dest, exist_ok=True)
            elif m.isfile():
                os.makedirs(os.path.dirname(dest) or LOCAL_ADAPTER, exist_ok=True)
                with tf.extractfile(m) as src, open(dest, "wb") as dfh:
                    shutil.copyfileobj(src, dfh)
            # 忽略 symlink / 特殊文件
    log("EXTRACTED: %s" % LOCAL_ADAPTER)

    # 5) 本地部署 + 重评测
    deploy = os.path.join(ROOT, "deploy_local_sft.py")
    cmd = [sys.executable, deploy, "--adapter-dir", LOCAL_ADAPTER, "--switch", "--run-eval"]
    log("DEPLOY+EVAL: " + " ".join(cmd))
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0:
        log("DEPLOY_FAILED: returncode=%d（请查看上方部署脚本输出定位）" % r.returncode)
        return

    # 6) 标记完成。凭据生命周期由调用方管理，本脚本不删除凭据文件。
    with open(DEPLOYED_FLAG, "w", encoding="utf-8") as f:
        f.write("deployed after training COMPLETED\n")
    log("DONE: adapter 已部署并重新评测。请查看评测结果，重点对比边界项 53.45 -> 目标 >=80。")


if __name__ == "__main__":
    main()
