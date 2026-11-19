# -*- coding: utf-8 -*-
"""抓取SSCNC主窗口顶部菜单栏结构 + 主界面截图。"""
import os, time, subprocess, re
import win32gui, win32process, win32con
from PIL import ImageGrab

OUT = r"D:\Virtu模型\ssnc_teaching\evidence"
os.makedirs(OUT, exist_ok=True)

def target_pids():
    p = set()
    for name in ["CNCLogin.exe", "sscnc.exe"]:
        out = subprocess.check_output("tasklist /FI \"IMAGENAME eq %s\"" % name, shell=True).decode("utf-8","ignore")
        for line in out.splitlines():
            if name.lower() in line.lower():
                mm = re.search(r"\b(\d+)\s+(Console|Services)\b", line)
                if mm: p.add(int(mm.group(1)))
    return p

tps = target_pids()
hwnds = []
def cb(h, _):
    if not win32gui.IsWindow(h): return True
    tid, pid = win32process.GetWindowThreadProcessId(h)
    if pid in tps and "SwanSoft CNC" in win32gui.GetWindowText(h):
        hwnds.append(h)
    return True
win32gui.EnumWindows(cb, None)
print("main hwnds:", hwnds)
if not hwnds:
    print("NO MAIN WINDOW"); raise SystemExit(1)
main = hwnds[0]
win32gui.ShowWindow(main, win32con.SW_RESTORE)
try: win32gui.SetForegroundWindow(main)
except Exception as e: print("fg err", e)
time.sleep(1)

# 枚举主窗口的直接子窗口（菜单栏/工具栏/状态栏等）
print("=== child windows of main ===")
children = []
def ccb(h, _):
    if win32gui.IsWindow(h):
        t = win32gui.GetWindowText(h); cls = win32gui.GetClassName(h)
        r = win32gui.GetWindowRect(h)
        children.append((h, cls, t, r, win32gui.IsWindowVisible(h)))
    return True
win32gui.EnumChildWindows(main, ccb, None)
for c in children:
    if c[2].strip() or (c[4] and c[3][2]-c[3][0]>100):
        print("  cls=%-40s title=%r rect=%s vis=%s" % (c[1], c[2], c[3], c[4]))

# 用菜单API枚举顶部菜单
print("=== menu bar ===")
try:
    hmenu = win32gui.GetMenu(main)
    print("hmenu", hmenu)
    if hmenu:
        n = win32gui.GetMenuItemCount(hmenu)
        print("menu item count", n)
        for i in range(n):
            txt = win32gui.GetMenuString(hmenu, i, 0x400)  # MF_BYPOSITION
            print("  [%d] %r" % (i, txt))
except Exception as e:
    print("menu enum err", e)

# 截图（裁剪主窗口区域）
r = win32gui.GetWindowRect(main)
print("main rect", r)
img = ImageGrab.grab(bbox=(max(0,r[0]), max(0,r[1]), r[2], r[3]))
shot = os.path.join(OUT, "sscnc_main_crop.png")
img.save(shot)
print("saved", shot, img.size)
