# -*- coding: utf-8 -*-
"""Focus our VERICUT, click the CORRECT Run button (1890,942), then capture the
window via PrintWindow at intervals (works even when focus stealer takes over).
"""
import ctypes, time, os, subprocess, struct
from ctypes import wintypes
u = ctypes.windll.user32; g = ctypes.windll.gdi32
u.SetProcessDPIAware()
WND = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
TMP = os.environ.get("TEMP", "C:/Windows/Temp")


def find():
    r = []
    def cb(h, l):
        if not u.IsWindowVisible(h): return True
        b = ctypes.create_unicode_buffer(256); u.GetWindowTextW(h, b, 256)
        if "AE_CLOSED_IMPELLER" in b.value and "CGTech" in b.value: r.append(h)
        return True
    u.EnumWindows(WND(cb), 0)
    return r


def printwindow(hwnd, path):
    r = wintypes.RECT(); u.GetWindowRect(hwnd, ctypes.byref(r))
    W, H = r.right - r.left, r.bottom - r.top
    hdc = u.GetWindowDC(hwnd); memdc = g.CreateCompatibleDC(hdc)
    bmp = g.CreateCompatibleBitmap(hdc, W, H); g.SelectObject(memdc, bmp)
    u.PrintWindow(hwnd, memdc, 0)
    bi = bytearray(40)
    struct.pack_into('<I', bi, 0, 40); struct.pack_into('<i', bi, 4, W)
    struct.pack_into('<i', bi, 8, H); struct.pack_into('<H', bi, 12, 1)
    struct.pack_into('<H', bi, 14, 24)
    stride = ((W*3+3)//4)*4; sz = stride*H
    bits = ctypes.create_string_buffer(sz)
    g.GetDIBits(memdc, bmp, 0, H, bits, ctypes.c_char_p(bytes(bi)), 0)
    with open(path, 'wb') as f:
        f.write(struct.pack('<2sIHHI', b'BM', 54+sz, 0, 0, 54)); f.write(bytes(bi)); f.write(bits.raw)


ours = find()
print("ours:", [hex(h) for h in ours], flush=True)
if not ours: raise SystemExit(2)
h = ours[0]
u.ShowWindow(h, 3)
u.SetCursorPos(760, 200)
u.mouse_event(0x0002,0,0,0,0); time.sleep(0.08); u.mouse_event(0x0004,0,0,0,0)
for _ in range(10):
    u.SetWindowPos(h, -1, 0,0,0,0, 0x0002|0x0001); u.SetForegroundWindow(h); time.sleep(0.3)
    if u.GetForegroundWindow() == h: break
print("fg", u.GetForegroundWindow()==h, flush=True)
printwindow(h, os.path.join(TMP, "vrs_before.bmp"))

# CLICK CORRECT Run button at (1890, 942) - verified via crosshair
u.SetCursorPos(1890, 942); time.sleep(0.25)
u.mouse_event(0x0002,0,0,0,0); time.sleep(0.1); u.mouse_event(0x0004,0,0,0,0)
print("clicked RUN at 1890,942", flush=True)

for t in range(6):
    time.sleep(10)
    printwindow(h, os.path.join(TMP, f"vrs_t{t+1}.bmp"))
    print("captured t=", (t+1)*10, flush=True)
