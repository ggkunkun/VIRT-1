# -*- coding: utf-8 -*-
"""枚举所有窗口(含隐藏类名)，定位SSCNC/CNCLogin进程窗口并置前截图。"""
import os, time, ctypes
import win32gui, win32process, win32con
from PIL import ImageGrab

OUT = r"D:\Virtu模型\ssnc_teaching\evidence"
os.makedirs(OUT, exist_ok=True)

# 目标进程PID
import subprocess
def pids_of(name):
    out = subprocess.check_output(["tasklist", "/FI", "IMAGENAME eq %s" % name], shell=True).decode("utf-8", "ignore")
    import re
    return set(re.findall(r"\b%d+\b", "")) | set(int(m) for m in re.findall(r"(%s)\s+(\d+)" % name, out, re.I) for m in [m[1]])

def target_pids():
    p = set()
    for name in ["CNCLogin.exe", "sscnc.exe"]:
        out = subprocess.check_output("tasklist /FI \"IMAGENAME eq %s\"" % name, shell=True).decode("utf-8","ignore")
        import re
        for line in out.splitlines():
            if name.lower() in line.lower():
                mm = re.search(r"\b(\d+)\s+(Console|Services)\b", line)
                if mm: p.add(int(mm.group(1)))
    return p

tps = target_pids()
print("target PIDs:", tps)

rows = []
def cb(h, _):
    if not win32gui.IsWindow(h): return True
    tid, pid = win32process.GetWindowThreadProcessId(h)
    title = win32gui.GetWindowText(h)
    cls = win32gui.GetClassName(h)
    vis = win32gui.IsWindowVisible(h)
    rect = win32gui.GetWindowRect(h)
    if pid in tps:
        rows.append((h, pid, cls, title, vis, rect, win32gui.IsIconic(h)))
    return True
win32gui.EnumWindows(cb, None)
for r in rows:
    print("HWND=%s PID=%s cls=%s vis=%s iconic=%s rect=%s title=%r" % (r[0],r[1],r[2],r[4],r[6],r[5],r[3]))

# 找到主窗口（可见、面积最大）
cand = [r for r in rows if r[4] and not r[6] and (r[5][2]-r[5][0])>200]
if cand:
    main = max(cand, key=lambda r:(r[5][2]-r[5][0])*(r[5][3]-r[5][1]))
    print("MAIN:", main[0], main[3], main[5])
    try:
        win32gui.ShowWindow(main[0], win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(main[0])
        time.sleep(1.5)
    except Exception as e:
        print("foreground err", e)
    shot = os.path.join(OUT, "sscnc_main.png")
    ImageGrab.grab().save(shot)
    print("saved", shot)
else:
    print("no visible SSCNC window; saving desktop")
    shot = os.path.join(OUT, "sscnc_none.png")
    ImageGrab.grab().save(shot)
    print("saved", shot)
