# -*- coding: utf-8 -*-
"""Focus OUR already-loaded VERICUT, click Run, monitor, capture. Fast, single process."""
import ctypes, time, os, subprocess
u = ctypes.windll.user32; g = ctypes.windll.gdi32
u.SetProcessDPIAware()
TMP = os.environ.get("TEMP", "C:/Windows/Temp")
WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

def find_ours():
    r = []
    def cb(h, l):
        if not u.IsWindowVisible(h): return True
        b = ctypes.create_unicode_buffer(256); u.GetWindowTextW(h, b, 256)
        if "AE_CLOSED_IMPELLER" in b.value and "CGTech" in b.value: r.append(h)
        return True
    u.EnumWindows(WNDENUMPROC(cb), 0)
    return r

def shot(path):
    W, H = u.GetSystemMetrics(0), u.GetSystemMetrics(1)
    hdc = u.GetDC(0); memdc = g.CreateCompatibleDC(0)
    bmp = g.CreateCompatibleBitmap(hdc, W, H); g.SelectObject(memdc, bmp)
    g.BitBlt(memdc, 0, 0, W, H, hdc, 0, 0, 0x00CC0020)
    import struct
    bi = bytearray(40)
    struct.pack_into('<I', bi, 0, 40); struct.pack_into('<i', bi, 4, W)
    struct.pack_into('<i', bi, 8, H); struct.pack_into('<H', bi, 12, 1)
    struct.pack_into('<H', bi, 14, 24)
    stride = ((W*3+3)//4)*4; sz = stride*H
    bits = ctypes.create_string_buffer(sz)
    g.GetDIBits(memdc, bmp, 0, H, bits, ctypes.c_char_p(bytes(bi)), 0)
    with open(path, 'wb') as f:
        f.write(struct.pack('<2sIHHI', b'BM', 54+sz, 0, 0, 54)); f.write(bytes(bi)); f.write(bits.raw)

ours = find_ours()
print("ours:", [hex(h) for h in ours], flush=True)
if not ours:
    print("NO_OURS"); raise SystemExit(2)
h = ours[0]
u.ShowWindow(h, 3)  # maximize
u.SetCursorPos(760, 200)
u.mouse_event(0x0002,0,0,0,0); time.sleep(0.08); u.mouse_event(0x0004,0,0,0,0)
for _ in range(10):
    u.SetWindowPos(h, -1, 0,0,0,0, 0x0002|0x0001)
    u.SetForegroundWindow(h); time.sleep(0.3)
    if u.GetForegroundWindow() == h: break
print("foreground", u.GetForegroundWindow()==h, flush=True)
shot(os.path.join(TMP, "vcr_before.bmp"))

# click Run (measured green triangle center ~1895,1001)
u.SetCursorPos(1895, 1001); time.sleep(0.2)
u.mouse_event(0x0002,0,0,0,0); time.sleep(0.08); u.mouse_event(0x0004,0,0,0,0)
print("clicked RUN", flush=True)

for t in range(6):
    deadline = time.time() + 10
    while time.time() < deadline:
        u.SetWindowPos(h, -1, 0,0,0,0, 0x0002|0x0001)
        time.sleep(0.5)
    shot(os.path.join(TMP, f"vcr_t{t+1}.bmp"))
    print("shot t=", (t+1)*10, flush=True)
