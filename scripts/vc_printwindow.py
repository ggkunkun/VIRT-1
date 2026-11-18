# -*- coding: utf-8 -*-
"""Capture a specific VERICUT window via PrintWindow (works even when occluded).

Avoids the focus-stealer: we read pixels straight from the target HWND, not the
screen. Saves a BMP of the window client area.
"""
import ctypes, sys, os, struct
from ctypes import wintypes
u = ctypes.windll.user32
g = ctypes.windll.gdi32
u.SetProcessDPIAware()

hwnd = int(sys.argv[1], 0)
out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.environ.get("TEMP", "."), "vc_pw.bmp")

r = wintypes.RECT()
u.GetWindowRect(hwnd, ctypes.byref(r))
W, H = r.right - r.left, r.bottom - r.top
print("window rect", W, H)

hdc = u.GetWindowDC(hwnd)
memdc = g.CreateCompatibleDC(hdc)
bmp = g.CreateCompatibleBitmap(hdc, W, H)
g.SelectObject(memdc, bmp)
# PrintWindow: 0 = basic, 2 = PM_RENDERFULLCONTENT (better for Java/AWT)
ok = u.PrintWindow(hwnd, memdc, 0)
print("PrintWindow ok", ok)

bi = bytearray(40)
struct.pack_into('<I', bi, 0, 40)
struct.pack_into('<i', bi, 4, W)
struct.pack_into('<i', bi, 8, H)
struct.pack_into('<H', bi, 12, 1)
struct.pack_into('<H', bi, 14, 24)
stride = ((W * 3 + 3) // 4) * 4
sz = stride * H
bits = ctypes.create_string_buffer(sz)
g.GetDIBits(memdc, bmp, 0, H, bits, ctypes.c_char_p(bytes(bi)), 0)
with open(out, 'wb') as f:
    f.write(struct.pack('<2sIHHI', b'BM', 54 + sz, 0, 0, 54))
    f.write(bytes(bi)); f.write(bits.raw)
print("wrote", out, W, H)
