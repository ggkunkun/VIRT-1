# -*- coding: utf-8 -*-
"""探针7：验证门禁拆除后 desktop_controller 全链路快速返回。"""
import os, sys, io, time

OUT = r"D:\Virtu模型\_probe7_result.txt"

def log(*a):
    with io.open(OUT, "a", encoding="utf-8") as f:
        f.write(" ".join(str(x) for x in a) + "\n")

os.chdir(r"D:\Virtu模型")
sys.path.insert(0, r"D:\Virtu模型")

if os.path.exists(OUT):
    os.remove(OUT)

# 0) get_running_processes 本身不再挂起
from bridges.software_registry import get_running_processes
t0 = time.time()
procs = get_running_processes(timeout_s=15)
log("get_running_processes elapsed=%.2fs count=%d sld=%s" % (time.time() - t0, len(procs), procs.get("SLDWORKS.exe")))

from bridges.desktop_controller import DesktopController
ctl = DesktopController()

t0 = time.time()
hwnd = ctl.find_software_window("solidworks")
log("find_software_window(solidworks)=%s elapsed=%.2fs" % (hwnd, time.time() - t0))

t0 = time.time()
diag = ctl.diagnose_software_window("solidworks")
log("diagnose(solidworks)=%s elapsed=%.2fs" % (diag, time.time() - t0))

t0 = time.time()
r = ctl.type_text("")
log("type_text('')=%s elapsed=%.2fs" % (r, time.time() - t0))

t0 = time.time()
d = ctl.dismiss_all_dialogs(timeout_s=12)
log("dismiss_all_dialogs=%s elapsed=%.2fs" % ({k: v for k, v in d.items() if k != "results"}, time.time() - t0))

# preflight_apps 直接验证（原挂起点）
t0 = time.time()
try:
    import agent_chain_executor as chain_exec
    rep = chain_exec.preflight_apps()
    log("preflight_apps=%s elapsed=%.2fs" % (rep, time.time() - t0))
except Exception as e:
    log("preflight_apps_EXC=%r elapsed=%.2fs" % (e, time.time() - t0))

# 其余五软件（未运行 → not_running，快速返回）
for sw in ["sscnc", "cimco", "autocad", "vericut", "nx"]:
    t0 = time.time()
    d2 = ctl.diagnose_software_window(sw)
    log("diagnose(%s)=status:%s pids:%s elapsed=%.2fs" % (sw, d2.get("status"), d2.get("pids"), time.time() - t0))

log("DONE")
