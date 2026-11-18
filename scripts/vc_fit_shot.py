# -*- coding: utf-8 -*-
"""Force VERICUT foreground, click machine view, press F (fit), BitBlt screen."""
import ctypes, time, os, struct
u = ctypes.windll.user32; g = ctypes.windll.gdi32
u.SetProcessDPIAware()
WND = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
TMP = os.environ.get("TEMP", "C:/Windows/Temp")

ours = []
def cb(h, l):
    if not u.IsWindowVisible(h): return True
    b = ctypes.create_unicode_buffer(256); u.GetWindowTextW(h, b, 256)
    if "AE_CLOSED_IMPELLER" in b.value and "CGTech" in b.value: ours.append(h)
    return True
u.EnumWindows(WND(cb), 0)
if not ours:
    print("NO_OURS"); raise SystemExit(2)
h = ours[0]
u.ShowWindow(h, 3)
# acquire foreground with real click
u.SetCursorPos(760, 200)
u.mouse_event(0x0002,0,0,0,0); time.sleep(0.08); u.mouse_event(0x0004,0,0,0,0)
for _ in range(12):
    u.SetWindowPos(h, -1, 0,0,0,0, 0x0002|0x0001)
    u.SetForegroundWindow(h); time.sleep(0.3)
    if u.GetForegroundWindow() == h: break
print("fg", u.GetForegroundWindow()==h, flush=True)

# click inside machine view then press 'F' (fit all)
u.SetCursorPos(850, 400)
u.mouse_event(0x0002,0,0,0,0); time.sleep(0.08); u.mouse_event(0x0004,0,0,0,0)
time.sleep(0.3)
u.keybd_event(0x46, 0, 0, 0); time.sleep(0.1); u.keybd_event(0x46, 0, 2, 0)
time.sleep(1.5)
# keep topmost during capture
u.SetWindowPos(h, -1, 0,0,0,0, 0x0002|0x0001)
time.sleep(0.3)

W, H = u.GetSystemMetrics(0), u.GetSystemMetrics(1)
hdc = u.GetDC(0); memdc = g.CreateCompatibleDC(hdc)
bmp = g.CreateCompatibleBitmap(hdc, W, H); g.SelectObject(memdc, bmp)
g.BitBlt(memdc, 0, 0, W, H, hdc, 0, 0, 0x00CC0020)
bi = bytearray(40)
struct.pack_into('<I', bi, 0, 40); struct.pack_into('<i', bi, 4, W)
struct.pack_into('<i', bi, 8, H); struct.pack_into('<H', bi, 12, 1)
struct.pack_into('<H', bi, 14, 24)
stride = ((W*3+3)//4)*4; sz = stride*H
bits = ctypes.create_string_buffer(sz)
g.GetDIBits(memdc, bmp, 0, H, bits, ctypes.c_char_p(bytes(bi)), 0)
out = os.path.join(TMP, "vc_fit_screen.bmp")
with open(out, 'wb') as f:
    f.write(struct.pack('<2sIHHI', b'BM', 54+sz, 0, 0, 54)); f.write(bytes(bi)); f.write(bits.raw)
print("wrote", out, W, H)
