# -*- coding: utf-8 -*-
"""Force a VERICUT window to the foreground + topmost and screenshot atomically.

Works around the documented third-party focus-stealer on this machine: all
steps (find window, topmost, foreground, BitBlt) run in ONE process so the
stealer cannot interleave between tool calls.
"""
import ctypes
import os
import sys
import time

u = ctypes.windll.user32
g = ctypes.windll.gdi32
u.SetProcessDPIAware()

TITLE_SUBSTR = sys.argv[1] if len(sys.argv) > 1 else "AE_CLOSED_IMPELLER"
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.environ.get("TEMP", "."), "vc_fg.bmp")

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
found = []

def cb(hwnd, lp):
    if not u.IsWindowVisible(hwnd):
        return True
    n = u.GetWindowTextLengthW(hwnd)
    if n == 0:
        return True
    buf = ctypes.create_unicode_buffer(n + 1)
    u.GetWindowTextW(hwnd, buf, n + 1)
    if TITLE_SUBSTR.lower() in buf.value.lower():
        found.append((hwnd, buf.value))
    return True

u.EnumWindows(WNDENUMPROC(cb), 0)
if not found:
    print("WINDOW_NOT_FOUND", TITLE_SUBSTR)
    sys.exit(2)

hwnd, title = found[0]
print("FOUND", hex(hwnd), title)

HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SHOWWINDOW = 5

u.ShowWindow(hwnd, SHOWWINDOW)
u.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
u.SetForegroundWindow(hwnd)
u.BringWindowToTop(hwnd)
time.sleep(0.8)
# Re-assert in case the stealer fired once.
u.SetForegroundWindow(hwnd)
time.sleep(0.5)

# confirm foreground
fg = u.GetForegroundWindow()
fgbuf = ctypes.create_unicode_buffer(256)
u.GetWindowTextW(fg, fgbuf, 256)
print("FOREGROUND", hex(fg), fgbuf.value, "MATCH", fg == hwnd)

# BitBlt full screen
W = u.GetSystemMetrics(0)
H = u.GetSystemMetrics(1)
hdc = u.GetDC(0)
memdc = g.CreateCompatibleDC(hdc)
bmp = g.CreateCompatibleBitmap(hdc, W, H)
g.SelectObject(memdc, bmp)
g.BitBlt(memdc, 0, 0, W, H, hdc, 0, 0, 0x00CC0020)

class BITMAPFILEHEADER(ctypes.Structure):
    _fields_ = [("bfType", ctypes.c_ushort), ("bfSize", ctypes.c_uint32),
                ("bfReserved1", ctypes.c_ushort), ("bfReserved2", ctypes.c_ushort),
                ("bfOffBits", ctypes.c_uint32)]
class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32),
                ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_ushort),
                ("biBitCount", ctypes.c_ushort), ("biCompression", ctypes.c_uint32),
                ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32),
                ("biYPelsPerMeter", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32),
                ("biClrImportant", ctypes.c_uint32)]

stride = ((W * 3 + 3) // 4) * 4
imgsize = stride * H
bmi = BITMAPINFOHEADER(40, W, H, 1, 24, 0, imgsize, 0, 0, 0, 0)
bits = ctypes.create_string_buffer(imgsize)
g.GetDIBits(memdc, bmp, 0, H, bits, ctypes.byref(bmi), 0)
bfh = BITMAPFILEHEADER(0x4D42, 54 + imgsize, 0, 0, 54)
with open(OUT, "wb") as f:
    f.write(bytes(bfh))
    f.write(bytes(bmi))
    f.write(bits.raw)
print("WROTE", OUT, W, H)
