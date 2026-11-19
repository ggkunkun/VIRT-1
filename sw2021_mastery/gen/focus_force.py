# -*- coding: utf-8 -*-
"""强制把指定 pid 的主窗口提到前台（AttachThreadInput 绕过前台锁）。"""
import ctypes
import sys
import time
from ctypes import wintypes

u = ctypes.windll.user32
k = ctypes.windll.kernel32


def main(pid=None, title_kw=None, x=None, y=None, w=None, h=None):
    wins = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        p = wintypes.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        n = u.GetWindowTextLengthW(hwnd)
        if n <= 0 or not u.IsWindowVisible(hwnd):
            return True
        if pid and p.value != int(pid):
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        u.GetWindowTextW(hwnd, buf, n + 1)
        if title_kw and title_kw not in buf.value:
            return True
        r = wintypes.RECT()
        u.GetWindowRect(hwnd, ctypes.byref(r))
        if (r.right - r.left) > 300:
            wins.append((hwnd, buf.value, r))
        return True

    u.EnumWindows(cb, 0)
    if not wins:
        print("NOT_FOUND")
        return 1
    hwnd, title, r = wins[0]
    if x is not None:
        u.SetWindowPos(hwnd, 0, int(x), int(y), int(w or (r.right - r.left)), int(h or (r.bottom - r.top)), 0x0040)
    u.ShowWindow(hwnd, 9)
    time.sleep(0.2)
    fg = u.GetForegroundWindow()
    fg_tid = u.GetWindowThreadProcessId(fg, None)
    cur_tid = k.GetCurrentThreadId()
    u.AttachThreadInput(cur_tid, fg_tid, True)
    u.BringWindowToTop(hwnd)
    u.SetForegroundWindow(hwnd)
    u.SetFocus(hwnd)
    u.AttachThreadInput(cur_tid, fg_tid, False)
    time.sleep(0.5)
    r2 = wintypes.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(r2))
    print(f"FOCUSED hwnd={hwnd} title={title!r} rect=({r2.left},{r2.top},{r2.right-r2.left},{r2.bottom-r2.top}) fg={u.GetForegroundWindow()==hwnd}")
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    pid = a[0] if a and a[0].isdigit() else None
    kw = a[1] if len(a) > 1 else None
    coords = [int(v) for v in a[2:6]] if len(a) >= 6 else [None] * 4
    sys.exit(main(pid, kw, *coords))
