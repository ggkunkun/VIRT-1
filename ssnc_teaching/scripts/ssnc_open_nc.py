# -*- coding: utf-8 -*-
"""重试'文件->打开'：置前主窗口后发 WM_COMMAND，枚举新出现的对话框并填入 NC 路径。"""
import os, sys, time
import win32gui, win32con

MAIN = 2297508
NC = sys.argv[1] if len(sys.argv) > 1 else r"E:\仿真软件\2斯沃7.2（内含安装说明）\SSCNC\FANUC\FANUC0iM\FANUC\EX10.cnc"

def sscnc_windows():
    import win32process, subprocess, re
    out = subprocess.check_output('tasklist /FI "IMAGENAME eq sscnc.exe"', shell=True).decode("mbcs", "ignore")
    pids = set(int(m.group(1)) for m in re.finditer(r"sscnc\.exe\s+(\d+)", out, re.I))
    res = []
    def cb(h, _):
        tid, pid = win32process.GetWindowThreadProcessId(h)
        if pid in pids and win32gui.IsWindowVisible(h):
            res.append(h)
        return True
    win32gui.EnumWindows(cb, None)
    return res

before = set(sscnc_windows())
try:
    win32gui.SetForegroundWindow(MAIN)
except Exception as e:
    print("fg err", e)
time.sleep(0.5)
win32gui.SendMessage(MAIN, win32con.WM_COMMAND, 57601, 0)
time.sleep(1.5)
after = sscnc_windows()
new = [h for h in after if h not in before]
print("new windows:", [(h, win32gui.GetClassName(h), win32gui.GetWindowText(h), win32gui.GetWindowRect(h)) for h in new])

# 也检查所有 #32770 中带 Edit/ComboBoxEx32 的
cands = []
for h in after:
    if win32gui.GetClassName(h) != "#32770":
        continue
    kids = []
    def cb(x, _):
        kids.append((x, win32gui.GetClassName(x), win32gui.GetWindowText(x)))
        return True
    win32gui.EnumChildWindows(h, cb, None)
    has_edit = any(c[1] == "Edit" for c in kids)
    cands.append((h, has_edit, len(kids), win32gui.GetWindowRect(h)))
print("32770 candidates:", cands)

# 选有 Edit 的、或最大的
target = None
for h, has_edit, n, r in cands:
    if has_edit:
        target = h
        break
if target is None and cands:
    target = max(cands, key=lambda c: (c[3][2]-c[3][0])*(c[3][3]-c[3][1]))[0]
if target is None:
    print("no dialog")
    sys.exit(2)

print("using dialog", target, win32gui.GetWindowRect(target))
kids = []
def cb(x, _):
    kids.append((x, win32gui.GetClassName(x), win32gui.GetWindowText(x), win32gui.GetDlgCtrlID(x)))
    return True
win32gui.EnumChildWindows(target, cb, None)
edit = ok = None
for x, cls, t, cid in kids:
    print("   child", x, cls, repr(t[:40]), "id", cid)
    if cls == "Edit" and edit is None:
        edit = x
    if cls == "Button" and ("打开" in t or "Open" in t or "Save" in t or "保存" in t):
        ok = x
if edit:
    win32gui.SetWindowText(edit, NC)
    print("set path")
if ok:
    win32gui.SendMessage(ok, win32con.BM_CLICK, 0, 0)
    print("clicked open")
else:
    win32gui.SendMessage(target, win32con.WM_COMMAND, win32con.IDOK, 0)
    print("IDOK")
time.sleep(2)
print("dialog alive?", win32gui.IsWindow(target))
