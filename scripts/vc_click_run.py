# -*- coding: utf-8 -*-
"""Single-process: force VERICUT foreground, click Run button, wait, screenshot.

Self-drawn AWT canvas needs a REAL mouse click (SendInput), and the third-party
focus stealer on this machine can interleave across tool calls, so all steps
run in ONE process: topmost -> foreground -> click -> wait -> BitBlt.
"""
import ctypes
import os
import sys
import time

u = ctypes.windll.user32
g = ctypes.windll.gdi32
u.SetProcessDPIAware()

TITLE_SUBSTR = "AE_CLOSED_IMPELLER"
CLICK_X = int(sys.argv[1]) if len(sys.argv) > 1 else 1882
CLICK_Y = int(sys.argv[2]) if len(sys.argv) > 2 else 1001
WAIT_S = int(sys.argv[3]) if len(sys.argv) > 3 else 20
OUT = sys.argv[4] if len(sys.argv) > 4 else os.path.join(os.environ.get("TEMP", "."), "vc_run.bmp")

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
    print("WINDOW_NOT_FOUND"); sys.exit(2)
hwnd, title = found[0]

HWND_TOPMOST, HWND_NOTOPMOST = -1, -2
SWP_NOMOVE, SWP_NOSIZE = 0x0002, 0x0001
u.ShowWindow(hwnd, 5)
u.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
u.SetForegroundWindow(hwnd)
u.BringWindowToTop(hwnd)
time.sleep(0.6)
u.SetForegroundWindow(hwnd)
time.sleep(0.4)
fg = u.GetForegroundWindow()
fgbuf = ctypes.create_unicode_buffer(256)
u.GetWindowTextW(fg, fgbuf, 256)
print("FOREGROUND_MATCH", fg == hwnd, repr(fgbuf.value))
if fg != hwnd:
    print("ABORT: focus stolen, not clicking"); sys.exit(3)

# Real mouse click via SetCursorPos + mouse_event
MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004
u.SetCursorPos(CLICK_X, CLICK_Y)
time.sleep(0.2)
u.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
time.sleep(0.08)
u.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
print("CLICKED", CLICK_X, CLICK_Y)

# Let simulation progress, keep re-asserting topmost so stealer can't cover it
deadline = time.time() + WAIT_S
while time.time() < deadline:
    u.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
    time.sleep(0.5)

# screenshot using engine-compatible BMP (pure ctypes, same logic as cu_ui)
W, H = u.GetSystemMetrics(0), u.GetSystemMetrics(1)
hdc = u.GetDC(0)
memdc = g.CreateCompatibleDC(hdc)
bmp = g.CreateCompatibleBitmap(hdc, W, H)
g.SelectObject(memdc, bmp)
g.BitBlt(memdc, 0, 0, W, H, hdc, 0, 0, 0x00CC0020)
# Write via GetDIBits into a 40-byte BITMAPINFO buffer (byte array, no struct packing)
import struct
bi = bytearray(40)
struct.pack_into('<I', bi, 0, 40)
struct.pack_into('<i', bi, 4, W)
struct.pack_into('<i', bi, 8, H)
struct.pack_into('<H', bi, 12, 1)
struct.pack_into('<H', bi, 14, 24)
stride = ((W * 3 + 3) // 4) * 4
imgsize = stride * H
bits = ctypes.create_string_buffer(imgsize)
g.GetDIBits(memdc, bmp, 0, H, bits, ctypes.c_char_p(bytes(bi)), 0)
bfh = struct.pack('<2sIHHI', b'BM', 54 + imgsize, 0, 0, 54)
with open(OUT, 'wb') as f:
    f.write(bfh); f.write(bytes(bi)); f.write(bits.raw)
print("WROTE", OUT, W, H)
