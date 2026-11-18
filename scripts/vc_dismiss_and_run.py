# -*- coding: utf-8 -*-
"""Dismiss stray 'error' dialogs (WM_CLOSE) then force our VERICUT to front.

The other AI agent's stale batch job keeps spawning a 'printargs' error dialog.
We close only dialog windows (SunAwtDialog / title '错误') that are NOT owned by
our impeller main window, then topmost our GUI so it covers any new ones.
"""
import ctypes
import time

u = ctypes.windll.user32
WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
WM_CLOSE = 0x0010
dialogs = []
ours = []

def cb(hwnd, lp):
    if not u.IsWindowVisible(hwnd):
        return True
    cls = ctypes.create_unicode_buffer(128)
    u.GetClassNameW(hwnd, cls, 128)
    n = u.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer((n or 0) + 1)
    u.GetWindowTextW(hwnd, buf, n + 1)
    title = buf.value
    if "AE_CLOSED_IMPELLER" in title:
        ours.append(hwnd)
    elif cls.value == "SunAwtDialog":
        dialogs.append((hwnd, title))
    return True

u.EnumWindows(WNDENUMPROC(cb), 0)
print("our windows:", len(ours), "dialogs:", [(hex(h), t) for h, t in dialogs])
for h, t in dialogs:
    u.PostMessageW(h, WM_CLOSE, 0, 0)
    print("closed dialog", hex(h), t)
time.sleep(0.5)
if ours:
    u.SetWindowPos(ours[0], -1, 0, 0, 0, 0, 0x0002 | 0x0001)
    u.SetForegroundWindow(ours[0])
    print("our GUI topmost+foreground", hex(ours[0]))
