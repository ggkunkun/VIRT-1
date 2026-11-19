# -*- coding: utf-8 -*-
"""SOLIDWORKS 2021 SP5 核心 MSI 修复（/fa：重装所有文件）。

不使用安装器 GUI，不弹窗；失败即退出码返回，交由上层决定是否转官方 IM 修复。
"""
import json
import os
import subprocess
import sys
import time

PCODE = "{9C0A2571-4AAE-4FEE-B673-038B38B85EFC}"  # SOLIDWORKS 2021 SP05 核心
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(BASE, "work", "msi_repair.log")
JSON = os.path.join(BASE, "work", "msi_repair_result.json")


def main():
    os.makedirs(os.path.join(BASE, "work"), exist_ok=True)
    # 清掉残留实例，避免文件占用
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq SLDWORKS.exe", "/NH", "/FO", "CSV"],
                         capture_output=True, text=True, errors="ignore").stdout
    killed = []
    for line in out.splitlines():
        if line.startswith('"SLDWORKS.exe"'):
            pid = line.split('","')[1]
            subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True)
            killed.append(pid)
    time.sleep(4)

    t0 = time.time()
    cmd = ["msiexec", "/fa", PCODE, "/qn", "/l*v", LOG]
    print("RUN", " ".join(cmd), flush=True)
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, errors="ignore", timeout=2700)
        rc = p.returncode
        err = (p.stderr or "")[:400]
    except subprocess.TimeoutExpired:
        rc, err = "timeout", "超过 45 分钟未完成"
    res = {"product_code": PCODE, "command": cmd, "exit_code": rc, "stderr": err,
           "killed_processes": killed, "elapsed_s": round(time.time() - t0, 1),
           "log": LOG, "log_bytes": os.path.getsize(LOG) if os.path.exists(LOG) else 0,
           "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    with open(JSON, "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print(json.dumps(res, ensure_ascii=False), flush=True)
    return 0 if rc in (0, 3010) else 1


if __name__ == "__main__":
    sys.exit(main())
