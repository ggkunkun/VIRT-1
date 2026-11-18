# -*- coding: utf-8 -*-
"""探针6：验证 desktop_controller 门禁拆除效果。"""
import os, sys, io, time

OUT = r"D:\Virtu模型\_probe6_result.txt"

def log(*a):
    with io.open(OUT, "a", encoding="utf-8") as f:
        f.write(" ".join(str(x) for x in a) + "\n")

os.chdir(r"D:\Virtu模型")
sys.path.insert(0, r"D:\Virtu模型")

if os.path.exists(OUT):
    os.remove(OUT)

from bridges.desktop_controller import DesktopController
ctl = DesktopController()

t0 = time.time()
hwnd = ctl.find_software_window("solidworks")
log("find_software_window(solidworks)=", hwnd, "elapsed=%.1fs" % (time.time() - t0))

t0 = time.time()
diag = ctl.diagnose_software_window("solidworks")
log("diagnose(solidworks)=", diag, "elapsed=%.1fs" % (time.time() - t0))

t0 = time.time()
r = ctl.type_text("")
log("type_text('')=", r, "elapsed=%.1fs" % (time.time() - t0))

t0 = time.time()
d = ctl.dismiss_all_dialogs(timeout_s=12)
log("dismiss_all_dialogs=", {k: v for k, v in d.items() if k != "results"}, "elapsed=%.1fs" % (time.time() - t0))

# 其余五软件诊断（未运行时也应给出明确结论，不再抛异常）
for sw in ["sscnc", "cimco", "autocad", "vericut", "nx"]:
    t0 = time.time()
    d2 = ctl.diagnose_software_window(sw)
    log("diagnose(%s)=" % sw, d2, "elapsed=%.1fs" % (time.time() - t0))

log("DONE")
