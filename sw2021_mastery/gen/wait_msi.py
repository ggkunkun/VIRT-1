# -*- coding: utf-8 -*-
"""等待 MSI 修复日志收尾，输出结论。"""
import json
import os
import subprocess
import sys
import time

LOG = sys.argv[1] if len(sys.argv) > 1 else "work/msi_src_repair.log"
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = LOG if os.path.isabs(LOG) else os.path.join(BASE, LOG)
t0 = time.time()
while time.time() - t0 < 2400:
    time.sleep(15)
    txt = ""
    if os.path.exists(LOG):
        raw = open(LOG, "rb").read()
        for enc in ("utf-16-le", "utf-8", "gbk"):
            try:
                t = raw.decode(enc)
                if t.count("\x00") < len(t) * 0.05:
                    txt = t
                    break
            except Exception:
                pass
    done = "Verbose logging stopped" in txt
    running = '"msiexec.exe"' in subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq msiexec.exe", "/NH", "/FO", "CSV"],
        capture_output=True, text=True, errors="ignore").stdout
    if done and not running:
        codes = [l for l in txt.splitlines() if "returning" in l]
        print("DONE elapsed", int(time.time() - t0))
        print("CODES", codes[-3:])
        print("TAIL")
        for l in [x for x in txt.splitlines() if x.strip()][-8:]:
            print("  ", l[:200])
        sys.exit(0)
print("TIMEOUT")
sys.exit(2)
