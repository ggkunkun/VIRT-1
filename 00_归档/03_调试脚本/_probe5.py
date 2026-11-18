# -*- coding: utf-8 -*-
"""探针5：按 PID 过滤枚举 SLDWORKS 窗口，定位窗口枚举失败根因。"""
import os, sys, io, ctypes, traceback

OUT = r"D:\Virtu模型\_probe5_result.txt"

def log(*a):
    with io.open(OUT, "a", encoding="utf-8") as f:
        f.write(" ".join(str(x) for x in a) + "\n")

os.chdir(r"D:\Virtu模型")
sys.path.insert(0, r"D:\Virtu模型")

if os.path.exists(OUT):
    os.remove(OUT)

import win32gui
import win32process

target_pid = 28628  # SLDWORKS PID（探针4 tasklist 实测）

all_windows = []
def cb(hwnd, _):
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
    except Exception:
        pid = 0
    all_windows.append((hwnd, pid, win32gui.GetClassName(hwnd), win32gui.GetWindowText(hwnd)[:60]))
    return True

try:
    win32gui.EnumWindows(cb, None)
    log("total_enum_windows=", len(all_windows))
    pid_hits = [w for w in all_windows if w[1] == target_pid]
    log("pid28628_windows=", pid_hits[:10])
    # 列出所有顶层窗口的标题/类名，找 solid 线索
    named = [w for w in all_windows if w[3].strip()]
    log("named_windows_count=", len(named))
    for w in named[:25]:
        log("  WIN", w)
except Exception as e:
    log("enum_exc=", repr(e))

# 检查 SLDWORKS 是否以不同窗口站/桌面运行（通过进程属性探测比较难，先看进程名）
import subprocess
r = subprocess.run(["wmic", "process", "where", "ProcessId=28628", "get", "Name,CommandLine", "/format:list"],
                   capture_output=True, encoding="gbk", errors="ignore")
log("wmic_28628=", r.stdout.strip()[:400])

log("DONE")
