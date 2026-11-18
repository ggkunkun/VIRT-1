# -*- coding: utf-8 -*-
"""探针4：定位窗口枚举失败根因（桌面/窗口站/枚举条件对比）。"""
import os, sys, io, ctypes, traceback

OUT = r"D:\Virtu模型\_probe4_result.txt"

def log(*a):
    with io.open(OUT, "a", encoding="utf-8") as f:
        f.write(" ".join(str(x) for x in a) + "\n")

os.chdir(r"D:\Virtu模型")
sys.path.insert(0, r"D:\Virtu模型")

if os.path.exists(OUT):
    os.remove(OUT)

# 0. 当前线程桌面
user32 = ctypes.windll.user32
hdesk = user32.GetThreadDesktop(ctypes.windll.kernel32.GetCurrentThreadId())
name_buf = ctypes.create_unicode_buffer(256)
user32.GetUserObjectInformationW(hdesk, 2, name_buf, 512, None)  # UOI_NAME=2
log("thread_desktop=", name_buf.value)

hws = user32.GetProcessWindowStation()
ws_buf = ctypes.create_unicode_buffer(256)
user32.GetUserObjectInformationW(hws, 2, ws_buf, 512, None)
log("window_station=", ws_buf.value)

# 1. EnumWindows 当前状态
import win32gui
win_count = [0]
sld_hits = []
def cb(hwnd, _):
    if win32gui.IsWindowVisible(hwnd):
        win_count[0] += 1
        t = win32gui.GetWindowText(hwnd)
        if t.strip():
            sld_hits.append((hwnd, t[:50], win32gui.GetClassName(hwnd)))
    return True
try:
    win32gui.EnumWindows(cb, None)
    log("enum_visible_windows=", win_count[0])
    log("first10_titles=", [h[1] for h in sld_hits[:10]])
    solid_hits = [h for h in sld_hits if "solid" in h[1].lower() or "sld" in h[1].lower()]
    log("solid_like_hits=", solid_hits[:5])
except Exception as e:
    log("enum_exc=", repr(e))

# 2. 尝试 OpenDesktop default + SetThreadDesktop 后重新枚举
try:
    import win32service
    import win32con
    d = win32service.OpenDesktop("default", 0, False, win32con.MAXIMUM_ALLOWED)
    ok = d.SetThreadDesktop()
    log("attach_default_ok=", ok)
except Exception as e:
    log("attach_exc=", repr(e))

win_count2 = [0]
def cb2(hwnd, _):
    if win32gui.IsWindowVisible(hwnd):
        win_count2[0] += 1
    return True
try:
    win32gui.EnumWindows(cb2, None)
    log("after_attach_visible_windows=", win_count2[0])
except Exception as e:
    log("enum2_exc=", repr(e))

# 3. 用 tasklist 确认 SLDWORKS 进程存在
import subprocess
r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq SLDWORKS.exe", "/FO", "CSV", "/NH"],
                   capture_output=True, encoding="gbk", errors="ignore")
log("tasklist_sldworks=", r.stdout.strip()[:200])

log("DONE")
