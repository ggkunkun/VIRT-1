# -*- coding: utf-8 -*-
"""通过 ShellExecuteW(runas) 以提升权限执行 MSI 修复，并轮询日志判断完成。

本机 UAC 为静默提升（ConsentPromptBehaviorAdmin=0），不需要点击。
"""
import ctypes
import os
import subprocess
import sys
import time

PCODE = "{9C0A2571-4AAE-4FEE-B673-038B38B85EFC}"
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(BASE, "work", "msi_repair_elevated.log")
RESULT = os.path.join(BASE, "work", "msi_repair_elevated.json")

params = (f'/i {PCODE} REINSTALL=ALL REINSTALLMODE=vomus SLDIM=1 REBOOT=ReallySuppress '
          f'/qn /l*v "{LOG}"')

ctypes.windll.shell32.ShellExecuteW(None, "runas", "msiexec.exe", params, None, 0)
print("launched elevated msiexec", flush=True)

t0 = time.time()
last_size = -1
stable = 0
while time.time() - t0 < 3000:
    time.sleep(10)
    running = subprocess.run(["tasklist", "/FI", "IMAGENAME eq msiexec.exe", "/NH", "/FO", "CSV"],
                             capture_output=True, text=True, errors="ignore").stdout
    has = '"msiexec.exe"' in running
    size = os.path.getsize(LOG) if os.path.exists(LOG) else 0
    if size == last_size:
        stable += 1
    else:
        stable = 0
        last_size = size
    print(f"t={int(time.time()-t0)}s msiexec={has} log={size} stable={stable}", flush=True)
    if not has and size > 0 and stable >= 2:
        break

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
ok = "returning 0" in txt or "returning 3010" in txt
tail = [l for l in txt.splitlines() if l.strip()][-6:]
print("OK" if ok else "CHECK", "elapsed", int(time.time() - t0))
for l in tail:
    print("  ", l[:200])
import json
with open(RESULT, "w", encoding="utf-8", newline="\n") as f:
    json.dump({"ok": ok, "log": LOG, "log_bytes": len(raw) if txt else 0,
               "elapsed_s": int(time.time() - t0), "tail": tail}, f, ensure_ascii=False, indent=2)
