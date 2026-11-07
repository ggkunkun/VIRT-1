#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DamoModel 云端实例 SSH/SFTP 助手（非交互密码登录）。
凭证只从环境变量读取，不落盘、不打印。

常用：
  DAMODEL_PW=xxx python scripts/_ssh_damodel.py "uname -a"        # 执行命令
  python scripts/_ssh_damodel.py --put localfile /root/x/remote    # 上传单文件
  python scripts/_ssh_damodel.py --puttree localdir /root/x/remote # 上传目录树
  python scripts/_ssh_damodel.py --bg "bash scripts/cloud_launch.sh" /root/virtu_train /root/virtu_train/train.log  # 后台脱离会话启动
"""
import os
import sys
import paramiko

HOST = os.environ.get("DAMODEL_HOST", "cn-north-b.ssh.damodel.com")
PORT = int(os.environ.get("DAMODEL_PORT", "41858"))
USER = os.environ.get("DAMODEL_USER", "root")
PW = os.environ.get("DAMODEL_PW", "")


def _client() -> paramiko.SSHClient:
    if not PW:
        raise SystemExit("[FATAL] 缺少环境变量 DAMODEL_PW")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(
        hostname=HOST, port=PORT, username=USER, password=PW,
        timeout=20, look_for_keys=False, allow_agent=False,
        compress=True,
    )
    return c


def run(cmd: str, timeout: int = 1800) -> tuple[str, str, int]:
    c = _client()
    try:
        stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        rc = stdout.channel.recv_exit_status()
        return out, err, rc
    finally:
        c.close()


def _sftp_mkdir_p(sftp, remote_dir: str) -> None:
    parts = [p for p in remote_dir.split("/") if p]
    cur = ""
    for p in parts:
        cur = cur + "/" + p if cur else "/" + p
        try:
            sftp.stat(cur)
        except IOError:
            try:
                sftp.mkdir(cur)
            except IOError:
                pass  # 并发/已存在


def put(local: str, remote: str) -> None:
    c = _client()
    try:
        sftp = c.open_sftp()
        _sftp_mkdir_p(sftp, os.path.dirname(remote.rstrip("/")) or "/")
        sftp.put(local, remote)
        sftp.close()
    finally:
        c.close()
    print(f"  put {local} -> {remote}")


def put_tree(local_dir: str, remote_dir: str) -> None:
    c = _client()
    try:
        sftp = c.open_sftp()
        _sftp_mkdir_p(sftp, remote_dir.rstrip("/") or "/")
        for root, _dirs, files in os.walk(local_dir):
            rel = os.path.relpath(root, local_dir)
            rdir = remote_dir if rel == "." else os.path.join(remote_dir, rel)
            _sftp_mkdir_p(sftp, rdir)
            for f in files:
                lf = os.path.join(root, f)
                rf = os.path.join(rdir, f).replace("\\", "/")
                sftp.put(lf, rf)
                print(f"  put {lf} -> {rf}")
        sftp.close()
    finally:
        c.close()


def run_bg(cmd: str, cwd: str, log: str) -> str:
    """以 setsid 脱离会话启动（连接关闭也不被杀），输出重定向到 log。"""
    c = _client()
    try:
        full = (
            f"setsid bash -c 'cd {cwd} && {cmd} > {log} 2>&1' > /dev/null 2>&1 < /dev/null & "
            f"echo BG_PID=$!"
        )
        stdin, stdout, stderr = c.exec_command(full, timeout=30)
        out = stdout.read().decode("utf-8", "replace")
        stderr.read().decode("utf-8", "replace")
        stdout.channel.recv_exit_status()
        return out.strip()
    finally:
        c.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--put" and len(args) >= 3:
        put(args[1], args[2])
    elif args and args[0] == "--puttree" and len(args) >= 3:
        put_tree(args[1], args[2])
    elif args and args[0] == "--bg" and len(args) >= 4:
        pid = run_bg(args[1], args[2], args[3])
        print("background launched:", pid)
    elif args:
        out, err, rc = run(args[0])
        sys.stdout.write(out)
        if err:
            sys.stderr.write(err)
        sys.exit(rc)
    else:
        print("usage: ... 'cmd' | --put local remote | --puttree local remote | --bg cmd cwd log")
        sys.exit(2)
