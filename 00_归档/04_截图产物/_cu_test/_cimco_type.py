# -*- coding: utf-8 -*-
"""Single-process: focus CIMCO, click editor, type G-code, capture via PrintWindow."""
import ctypes
import json
import sys
import time
from ctypes import wintypes

sys.path.insert(0, r"D:\Virtu模型\_cu_test")
from _focus import force_fg  # noqa: E402
from _acad_test import kbd_unicode, tap_vk, VK_RETURN, VK_CONTROL  # noqa: E402
from _wincap import cap_window  # noqa: E402

u32 = ctypes.windll.user32
HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_SHOWWINDOW = 0x0040

GCODE = [
    "%",
    "O0001 (SQUARE POCKET)",
    "G21 G90 G54",
    "G0 X0 Y0 Z5",
    "G1 Z-2 F100",
    "G1 X50 Y0",
    "G1 X50 Y50",
    "G1 X0 Y50",
    "G1 X0 Y0",
    "G0 Z5",
    "M30",
    "%",
]


def click(x, y):
    u32.SetCursorPos(x, y)
    time.sleep(0.15)
    u32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.05)
    u32.mouse_event(0x0004, 0, 0, 0, 0)


def main():
    hwnd = int(sys.argv[1])
    editor_hwnd = int(sys.argv[2])
    out = sys.argv[3]
    u32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    ok = force_fg(hwnd)
    time.sleep(0.4)
    # create a new document first
    tap_vk(ord("N"), mods=(VK_CONTROL,))
    time.sleep(1.5)
    r = wintypes.RECT()
    u32.GetWindowRect(editor_hwnd, ctypes.byref(r))
    cx = (r.left + r.right) // 2
    cy = r.top + 60
    click(cx, cy)
    time.sleep(0.5)
    for line in GCODE:
        kbd_unicode(line)
        time.sleep(0.04)
        tap_vk(VK_RETURN)
        time.sleep(0.04)
    time.sleep(0.8)
    okc, w, h = cap_window(hwnd, out)
    print(json.dumps({"ok": True, "foreground_ok": ok, "click": [cx, cy],
                      "captured": okc, "size": [w, h], "lines": len(GCODE)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
