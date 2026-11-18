# -*- coding: utf-8 -*-
"""win_input.py — 真输入注入 + 前台解锁的最小工具集（ctypes 原生，不依赖 pyautogui）。

用途：当目标窗口对 BM_CLICK / WM_COMMAND / 坐标级消息全部无反应，只认「真鼠标」时，
用它把点击打到具体控件上。风险与自律：
  - **必须**通过 ``virtu_omni.computer_use.input_guard`` 授权（默认拒绝），
    避免模型侧一次幻觉调用就把操作者的光标拽走；
  - 默认点完**不复位**光标：旧实现无条件 ``SetCursorPos(old)``，连点几次就是
    "抽走—弹回—再抽走"，并发时还会把另一个执行体刚放好的光标拽回去；
  - 只允许打在**自己按 PID 找到的窗口**上（先 GetAncestor 拿根属主窗再提前台），
    绝不用标题匹配去抓用户的窗口。
"""

import ctypes
import os
import sys
import time
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

try:
    from virtu_omni.computer_use import input_guard as _INPUT_GUARD
    _INPUT_GUARD_ERROR = None
except Exception as _exc:          # pragma: no cover
    _INPUT_GUARD = None
    _INPUT_GUARD_ERROR = str(_exc)

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


def click(x, y, hold=0.08, settle=0.30, restore=False):
    """真鼠标左键点击，返回 True=已发出 / False=被闸门拒绝。

    ``restore`` 默认 False：点完不复位光标。旧实现无条件复位，一次流程里连点
    几次就是"抽走—弹回—再抽走"，并发时还会把另一个执行体刚放好的光标拽回去，
    观感上完全就是程序在抢鼠标。确需保留旧行为时显式传 ``restore=True``。

    注意：`MOUSEEVENTF_MOVE` 单独用是**相对位移**（dx,dy），拿屏幕坐标喂它会点到别处去
    （VERICUT 的 ribbon 就是这么一直点不中的）。绝对定位要 MOUSEEVENTF_ABSOLUTE + 归一化 0..65535，
    这里直接用 SetCursorPos 更不容易错。
    """
    if _INPUT_GUARD is None:
        print("[win_input] 输入闸门不可用（%s），拒绝点击" % _INPUT_GUARD_ERROR,
              file=sys.stderr)
        return False

    old = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(old))

    try:
        with _INPUT_GUARD.input_session("click", x=int(x), y=int(y),
                                        require_bounds=True, agent="win_input") as ctx:
            if ctx["dry_run"]:
                return False
            user32.SetCursorPos(int(x), int(y))
            time.sleep(0.12)
            try:
                _send(MOUSEEVENTF_LEFTDOWN)
                time.sleep(hold)
            finally:
                # 任何中断都补 UP：否则左键留在按下态，用户一动就是拖选
                _send(MOUSEEVENTF_LEFTUP)
            time.sleep(settle)
            if restore:
                user32.SetCursorPos(old.x, old.y)
    except _INPUT_GUARD.InputDenied as exc:
        print("[win_input] 点击被拒绝：%s" % exc, file=sys.stderr)
        return False
    return True


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
        if click(x, y):
            diag["clicked"] = True
            break
    else:
        # 一次都没发出去：闸门拒绝 / 急停 / 演练。不能谎报 clicked=True。
        diag["clicked"] = False
        diag["aborted"] = ("输入被闸门拒绝（VIRTU_DESKTOP_INPUT != 1，或处于急停/演练状态）")
    return diag
