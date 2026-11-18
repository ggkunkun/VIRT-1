# -*- coding: utf-8 -*-
"""Focus CIMCO, click a ribbon tab by capture-relative coords, capture result."""
import ctypes
import json
import sys
import time
from ctypes import wintypes

sys.path.insert(0, r"D:\Virtu模型\_cu_test")
from _focus import force_fg  # noqa: E402
from _wincap import cap_window  # noqa: E402

u32 = ctypes.windll.user32
HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_SHOWWINDOW = 0x0040


def click(x, y):
    u32.SetCursorPos(x, y)
    time.sleep(0.15)
    u32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.05)
    u32.mouse_event(0x0004, 0, 0, 0, 0)


def main():
    hwnd = int(sys.argv[1])
    rx = int(sys.argv[2])  # capture-relative x
    ry = int(sys.argv[3])
    out = sys.argv[4]
    u32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    force_fg(hwnd)
    time.sleep(0.4)
    r = wintypes.RECT()
    u32.GetWindowRect(hwnd, ctypes.byref(r))
    sx = r.left + rx
    sy = r.top + ry
    click(sx, sy)
    time.sleep(2.0)
    ok, w, h = cap_window(hwnd, out)
    print(json.dumps({"ok": True, "winrect": [r.left, r.top, r.right, r.bottom],
                      "click": [sx, sy], "captured": ok}, ensure_ascii=False))


if __name__ == "__main__":
    main()
