# -*- coding: utf-8 -*-
"""单进程探测：启动斯沃SSCNC，等待窗口出现，枚举并截图取证。"""
import os, sys, time, subprocess, ctypes
from PIL import ImageGrab

EXE = r"E:\仿真软件\2斯沃7.2（内含安装说明）\SSCNC\CNCLogin.exe"
OUT = r"D:\Virtu模型\ssnc_teaching\evidence"
os.makedirs(OUT, exist_ok=True)

def enum_windows():
    import win32gui
    res = []
    def cb(h, _):
        if win32gui.IsWindowVisible(h):
            t = win32gui.GetWindowText(h)
            cls = win32gui.GetClassName(h)
            if t.strip() and any(k in (t+cls) for k in ["斯沃","SSCNC","CNC","Swan","FANUC","登录","Login","仿真"]):
                res.append((h, cls, t))
        return True
    win32gui.EnumWindows(cb, None)
    return res

# 用 explorer 派生，避免沙箱子进程被回收
print("launching via explorer:", EXE)
subprocess.run(["explorer.exe", EXE], timeout=20)
print("waiting for window...")
found = []
for i in range(20):
    time.sleep(1)
    found = enum_windows()
    if found:
        print("window appeared at t=%ds" % (i+1))
        break

print("found windows:", found)

# 全屏截图
shot = os.path.join(OUT, "probe_launch_fullscreen.png")
img = ImageGrab.grab()
img.save(shot)
print("saved", shot, img.size)
