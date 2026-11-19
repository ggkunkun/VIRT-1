# -*- coding: utf-8 -*-
"""SSCNC 登录驱动：选择 FANUC 0iM + DEMO 模式 + RUN，进入仿真主界面。
所有鼠标动作经 ActionEngine -> input_guard 仲裁（需 VIRTU_DESKTOP_INPUT=1）。"""
import os, sys, time, ctypes
import win32gui, win32con

os.environ.setdefault("VIRTU_DESKTOP_INPUT", "1")
os.environ.setdefault("VIRTU_DESKTOP_AGENT", "ssnc_verify")
sys.path.insert(0, r"D:\Virtu模型")
from virtu_omni.computer_use.action import ActionEngine

eng = ActionEngine()

def click_hwnd(hwnd):
    r = win32gui.GetWindowRect(hwnd)
    cx, cy = (r[0] + r[2]) // 2, (r[1] + r[3]) // 2
    res = eng.click(cx, cy)
    print("click", hwnd, (cx, cy), res.get("status"), res.get("verdict_code"))
    return res

def find_login():
    hits = []
    def cb(h, _):
        if win32gui.IsWindowVisible(h) and win32gui.GetClassName(h) == "ClassName_CCCStartDlg":
            hits.append(h)
        return True
    win32gui.EnumWindows(cb, None)
    return hits[0] if hits else None

def main():
    dlg = find_login()
    if not dlg:
        print("login dialog not found; is CNCLogin running?")
        return 2
    print("dialog", dlg, win32gui.GetWindowRect(dlg))

    # 1) 系统下拉框：找第一个 ComboBox（数控系统）
    combos = []
    def ccb(h, _):
        if win32gui.GetClassName(h) == "ComboBox":
            combos.append(h)
        return True
    win32gui.EnumChildWindows(dlg, ccb, None)
    sys_combo = combos[0]
    win32gui.SendMessage(sys_combo, win32con.CB_SETCURSEL, 3, 0)  # FANUC 0iM
    # 通知父窗口 CBN_SELCHANGE
    cid = win32gui.GetDlgCtrlID(sys_combo)
    win32gui.SendMessage(dlg, win32con.WM_COMMAND, (win32con.CBN_SELCHANGE << 16) | cid, sys_combo)
    print("combo set FANUC 0iM, items combos:", combos)

    # 2) 点 DEMO 按钮
    demo = None
    def dcb(h, _):
        nonlocal demo
        if win32gui.GetClassName(h) == "Button" and "DEMO" in win32gui.GetWindowText(h):
            demo = h
        return True
    win32gui.EnumChildWindows(dlg, dcb, None)
    if demo:
        click_hwnd(demo)
        time.sleep(0.5)

    # 3) 点 RUN
    run = None
    def rcb(h, _):
        nonlocal run
        if win32gui.GetClassName(h) == "Button" and "RUN" in win32gui.GetWindowText(h):
            run = h
        return True
    win32gui.EnumChildWindows(dlg, rcb, None)
    if run:
        click_hwnd(run)
    else:
        print("RUN button not found")
        return 3

    # 4) 等待 sscnc.exe 主窗口
    for i in range(30):
        time.sleep(1)
        wins = []
        def wcb(h, _):
            cls = win32gui.GetClassName(h)
            if cls == "ClassName_Swansoft_CNC_Simulation" and win32gui.IsWindowVisible(h):
                wins.append((h, win32gui.GetWindowText(h), win32gui.GetWindowRect(h)))
            return True
        win32gui.EnumWindows(wcb, None)
        if wins:
            print("SSCNC main window:", wins)
            return 0
        # 登录框可能还在（密码错误等），打印其状态
        if i % 5 == 4:
            print("waiting... login still?", bool(find_login()), "wins:", wins)
    print("timeout waiting for main window")
    return 4

if __name__ == "__main__":
    sys.exit(main())
