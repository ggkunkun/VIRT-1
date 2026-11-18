# -*- coding: utf-8 -*-
"""force_fg + optional topmost for a given hwnd."""
import ctypes
import json
import sys
import time
from ctypes import wintypes

u32 = ctypes.windll.user32
k32 = ctypes.windll.kernel32

HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_SHOWWINDOW = 0x0040


def force_fg(hwnd):
    u32.ShowWindow(hwnd, 9)
    fg = u32.GetForegroundWindow()
    if fg == hwnd:
        return True
    tid_fg = u32.GetWindowThreadProcessId(fg, None) if fg else 0
    tid_me = k32.GetCurrentThreadId()
    attached = False
    if tid_fg and tid_fg != tid_me:
        attached = bool(u32.AttachThreadInput(tid_me, tid_fg, True))
    u32.BringWindowToTop(hwnd)
    u32.SetForegroundWindow(hwnd)
    if attached:
        u32.AttachThreadInput(tid_me, tid_fg, False)
    if u32.GetForegroundWindow() != hwnd:
        u32.keybd_event(0x12, 0, 0, 0)
        u32.keybd_event(0x12, 0, 2, 0)
        u32.SetForegroundWindow(hwnd)
        u32.BringWindowToTop(hwnd)
    time.sleep(0.25)
    return u32.GetForegroundWindow() == hwnd


def main():
    hwnd = int(sys.argv[1])
    topmost = "--top" in sys.argv
    if topmost:
        u32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    ok = force_fg(hwnd)
    fg = u32.GetForegroundWindow()
    ln = u32.GetWindowTextLengthW(fg)
    b = ctypes.create_unicode_buffer(ln + 1)
    u32.GetWindowTextW(fg, b, ln + 1)
    pid = wintypes.DWORD()
    u32.GetWindowThreadProcessId(fg, ctypes.byref(pid))
    print(json.dumps({"ok": ok, "foreground_hwnd": fg, "foreground_title": b.value,
                      "foreground_pid": pid.value, "topmost": topmost}, ensure_ascii=False))


if __name__ == "__main__":
    main()
