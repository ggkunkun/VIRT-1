# -*- coding: utf-8 -*-
"""快速复核 embedding 批量查询的 PowerShell 命令是否正确。"""
import os, sys, io, time, subprocess

OUT = r"D:\Virtu模型\_probe9_result.txt"

def log(*a):
    with io.open(OUT, "a", encoding="utf-8") as f:
        f.write(" ".join(str(x) for x in a) + "\n")

if os.path.exists(OUT):
    os.remove(OUT)

from bridges.software_registry import get_running_processes
procs = get_running_processes()
sld = procs.get("SLDWORKS.EXE") or procs.get("SLDWORKS.exe") or []
log("sld_pids=", sld)

if sld:
    pid_csv = ",".join(str(p) for p in sld)
    cmd = ("Get-CimInstance Win32_Process -Filter "
           f"'ProcessId={pid_csv}' | ForEach-Object {{ \"$($_.ProcessId)|$($_.CommandLine)\" }}")
    log("ps_cmd=", cmd)
    t0 = time.time()
    r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                       capture_output=True, encoding="utf-8", errors="ignore", timeout=8)
    log("elapsed=%.2fs rc=%d stdout=%r" % (time.time() - t0, r.returncode, r.stdout[:600]))
    log("stderr=%r" % r.stderr[:200])

log("DONE")
