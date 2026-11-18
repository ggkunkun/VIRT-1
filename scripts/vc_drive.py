# -*- coding: utf-8 -*-
"""Single-process VERICUT GUI driver: isolate our window, dismiss dialogs,
optionally click Run, and screenshot. Avoids cross-call focus stealing.

Usage:
  vc_drive.py shot                       -> just bring ours to front & screenshot
  vc_drive.py run <wait_s> <out_bmp>     -> click Run then wait & screenshot
"""
import ctypes
import sys
import time

u = ctypes.windll.user32
g = ctypes.windll.gdi32
u.SetProcessDPIAware()
WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
WM_CLOSE = 0x0010
SW_MINIMIZE = 6
SW_RESTORE = 9
SW_MAXIMIZE = 3
HWND_TOPMOST, HWND_NOTOPMOST = -1, -2
SWP_NOMOVE, SWP_NOSIZE, SWP_SHOWWINDOW = 0x0002, 0x0001, 0x0040

ours = []
others = []
dialogs = []

def cb(hwnd, lp):
    if not u.IsWindowVisible(hwnd):
        return True
    n = u.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer((n or 0) + 1)
    u.GetWindowTextW(hwnd, buf, n + 1)
    t = buf.value
    cls = ctypes.create_unicode_buffer(64)
    u.GetClassNameW(hwnd, cls, 64)
    if "AE_CLOSED_IMPELLER" in t and "CGTech" in t:
        ours.append((hwnd, t))
    elif "CGTech" in t and "9.6" in t:
        others.append((hwnd, t))
    elif cls.value == "SunAwtDialog":
        dialogs.append((hwnd, t))
    return True

u.EnumWindows(WNDENUMPROC(cb), 0)
if not ours:
    print("OURS_NOT_FOUND"); sys.exit(2)
hwnd, title = ours[0]
print("OUR", hex(hwnd), title)

# close stray AWT error dialogs
for h, t in dialogs:
    u.PostMessageW(h, WM_CLOSE, 0, 0)
# minimize other VERICUT main windows (don't kill other agent's session)
for h, t in others:
    u.ShowWindow(h, SW_MINIMIZE)
    print("minimized other", hex(h), t[:50])
time.sleep(0.4)

# maximize + foreground ours. Windows blocks SetForegroundWindow from a
# background process, so perform a REAL click on our window first (grants focus
# rights), then re-assert with retry.
u.ShowWindow(hwnd, SW_MAXIMIZE)
u.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
time.sleep(0.3)
# real click near window center-top (title/3D area) to acquire foreground rights
u.SetCursorPos(760, 200)
u.mouse_event(0x0002, 0, 0, 0, 0)
time.sleep(0.08)
u.mouse_event(0x0004, 0, 0, 0, 0)
time.sleep(0.3)
fg = None
for attempt in range(15):
    u.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
    u.SetForegroundWindow(hwnd)
    u.BringWindowToTop(hwnd)
    time.sleep(0.4)
    fg = u.GetForegroundWindow()
    if fg == hwnd:
        break
fgbuf = ctypes.create_unicode_buffer(256)
u.GetWindowTextW(fg, fgbuf, 256)
print("FOREGROUND_MATCH", fg == hwnd, "attempts", attempt + 1, repr(fgbuf.value)[:70])
if fg != hwnd:
    print("FOCUS_STOLEN_ABORT"); sys.exit(3)

mode = sys.argv[1] if len(sys.argv) > 1 else "shot"
wait = int(sys.argv[2]) if len(sys.argv) > 2 else 20
out = sys.argv[3] if len(sys.argv) > 3 else "C:/Users/ADMINI~1/AppData/Local/Temp/vc_drive.bmp"

if mode == "run":
    # Run button (green ▶) near bottom-right; recompute from window rect
    r = ctypes.wintypes.RECT() if hasattr(ctypes, "wintypes") else None
    # use absolute coords determined from maximized layout (rect ~ [0,0,1920,1040])
    u.SetCursorPos(1882, 1001)
    time.sleep(0.2)
    u.mouse_event(0x0002, 0, 0, 0, 0)  # LEFTDOWN
    time.sleep(0.08)
    u.mouse_event(0x0004, 0, 0, 0, 0)  # LEFTUP
    print("CLICKED RUN at 1882,1001")
    deadline = time.time() + wait
    while time.time() < deadline:
        u.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
        time.sleep(0.5)

# screenshot
W, H = u.GetSystemMetrics(0), u.GetSystemMetrics(1)
hdc = u.GetDC(0)
memdc = g.CreateCompatibleDC(hdc)
bmp = g.CreateCompatibleBitmap(hdc, W, H)
g.SelectObject(memdc, bmp)
g.BitBlt(memdc, 0, 0, W, H, hdc, 0, 0, 0x00CC0020)
import struct
bi = bytearray(40)
struct.pack_into('<I', bi, 0, 40); struct.pack_into('<i', bi, 4, W)
struct.pack_into('<i', bi, 8, H); struct.pack_into('<H', bi, 12, 1)
struct.pack_into('<H', bi, 14, 24)
stride = ((W * 3 + 3) // 4) * 4
imgsize = stride * H
bits = ctypes.create_string_buffer(imgsize)
g.GetDIBits(memdc, bmp, 0, H, bits, ctypes.c_char_p(bytes(bi)), 0)
bfh = struct.pack('<2sIHHI', b'BM', 54 + imgsize, 0, 0, 54)
with open(out, 'wb') as f:
    f.write(bfh); f.write(bytes(bi)); f.write(bits.raw)
print("WROTE", out, W, H)
