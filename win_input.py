# -*- coding: utf-8 -*-
"""win_input.py — 真输入注入 + 前台解锁的最小工具集（ctypes 原生，不依赖 pyautogui）。

用途：当目标窗口对 BM_CLICK / WM_COMMAND / 坐标级消息全部无反应，只认「真鼠标」时，
用它把点击打到具体控件上。风险与自律：
  - 会短暂移动光标，点后必须复位；
  - 只允许打在**自己按 PID 找到的窗口**上（先 GetAncestor 拿根属主窗再提前台），
    绝不用标题匹配去抓用户的窗口。
"""

import ctypes
import time
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000
GA_ROOT = 2
GA_ROOTOWNER = 3


def root_window(h):
    """控件所属的**顶层窗**（不是 owner 链根：GA_ROOTOWNER 会把宿主主框提上来，
    反而盖住浮动面板——斯沃踩过这个坑）。"""
    return user32.GetAncestor(h, GA_ROOT)
SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_void_p)]


class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("pad", ctypes.c_byte * 32)]

    _fields_ = [("type", wintypes.DWORD), ("ii", _U)]


user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT
user32.GetSystemMetrics.restype = ctypes.c_int
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, ctypes.c_uint]


def _send(flags, x=0, y=0):
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.ii.mi = MOUSEINPUT(x, y, 0, flags, 0, None)
    return user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def window_rect(h):
    r = wintypes.RECT()
    user32.GetWindowRect(h, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def center(h):
    l, t, rr, b = window_rect(h)
    return (l + rr) // 2, (t + b) // 2


def root_owner(h):
    return user32.GetAncestor(h, GA_ROOTOWNER)


def force_foreground(h):
    """用 AttachThreadInput 偷一次前台权，把 h 的根属主窗顶到最前。返回是否成功。"""
    hg = root_window(h) or h
    fg = user32.GetForegroundWindow()
    ft = user32.GetWindowThreadProcessId(fg, None)
    ct = kernel32.GetCurrentThreadId()
    user32.AttachThreadInput(ct, ft, True)
    user32.ShowWindow(hg, 9)          # SW_RESTORE
    user32.BringWindowToTop(hg)
    user32.SetForegroundWindow(hg)
    user32.SetActiveWindow(hg)
    user32.SetWindowPos(hg, 0, 0, 0, 0, 0, 0x0001 | 0x0002)  # HWND_TOP + NOSIZE|NOMOVE
    user32.AttachThreadInput(ct, ft, False)
    time.sleep(0.35)
    return user32.GetForegroundWindow() == hg, hg


def is_point_on_window(x, y, h):
    """点击前自检：屏幕上 (x,y) 这个点真的是 h 吗？（防止打在别人窗口上）"""
    pt = wintypes.POINT(x, y)
    under = user32.WindowFromPoint(pt)
    cur = under
    while cur:
        if cur == h:
            return True, under
        cur = user32.GetAncestor(cur, 1)  # GA_PARENT
    return False, under


def click(x, y, hold=0.08, settle=0.30):
    """真鼠标左键点击，点后把光标复位。

    注意：`MOUSEEVENTF_MOVE` 单独用是**相对位移**（dx,dy），拿屏幕坐标喂它会点到别处去
    （VERICUT 的 ribbon 就是这么一直点不中的）。绝对定位要 MOUSEEVENTF_ABSOLUTE + 归一化 0..65535，
    这里直接用 SetCursorPos 更不容易错。
    """
    old = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(old))
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.12)
    _send(MOUSEEVENTF_LEFTDOWN)
    time.sleep(hold)
    _send(MOUSEEVENTF_LEFTUP)
    time.sleep(settle)
    user32.SetCursorPos(old.x, old.y)


def click_control(h, tries=2, wake=True):
    """对某控件做「提前台 → 命中自检 → 真点击」，返回诊断字典。"""
    import win32gui
    diag = {"hwnd": h, "rect": window_rect(h), "text": win32gui.GetWindowText(h)}
    if wake:
        ok, hg = force_foreground(h)
        diag["foreground_ok"] = ok
        diag["root_window"] = hg
    x, y = center(h)
    mine, under = is_point_on_window(x, y, h)
    diag["point"] = (x, y)
    diag["point_hits_self"] = mine
    diag["window_under_point"] = under
    if not mine:
        diag["aborted"] = "屏幕该点不属于目标控件，放弃点击（避免误操别的窗口）"
        return diag
    for _ in range(tries):
        click(x, y)
    diag["clicked"] = True
    return diag
