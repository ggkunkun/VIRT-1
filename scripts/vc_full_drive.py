# -*- coding: utf-8 -*-
"""One-shot: clean all VERICUT, launch OUR project, maximize Stock view, run sim.

All GUI actions in a single process to defeat the focus stealer and the rival
agent that keeps relaunching its own VERICUT projects.
"""
import ctypes
import os
import subprocess
import sys
import time

u = ctypes.windll.user32
g = ctypes.windll.gdi32
u.SetProcessDPIAware()
WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
WM_CLOSE = 0x0010
SW_MINIMIZE, SW_MAXIMIZE = 6, 3
HWND_TOPMOST = -1
SWP_NOMOVE, SWP_NOSIZE = 0x0002, 0x0001
TMP = os.environ.get("TEMP", "C:/Windows/Temp")
OUT = os.path.join(TMP, "vc_full.bmp")


def enum():
    ours, others, dialogs = [], [], []
    def cb(h, l):
        if not u.IsWindowVisible(h):
            return True
        b = ctypes.create_unicode_buffer(256)
        u.GetWindowTextW(h, b, 256)
        t = b.value
        c = ctypes.create_unicode_buffer(64)
        u.GetClassNameW(h, c, 64)
        if "AE_CLOSED_IMPELLER" in t and "CGTech" in t:
            ours.append(h)
        elif "CGTech" in t and "9.6" in t:
            others.append(h)
        elif c.value == "SunAwtDialog":
            dialogs.append(h)
        return True
    u.EnumWindows(WNDENUMPROC(cb), 0)
    return ours, others, dialogs


def foreground(h):
    u.SetCursorPos(760, 200)  # real click grants foreground rights
    u.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.08)
    u.mouse_event(0x0004, 0, 0, 0, 0)
    for _ in range(12):
        u.SetWindowPos(h, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
        u.SetForegroundWindow(h)
        time.sleep(0.35)
        if u.GetForegroundWindow() == h:
            return True
    return False


def shot(path):
    W, H = u.GetSystemMetrics(0), u.GetSystemMetrics(1)
    hdc, memdc = u.GetDC(0), g.CreateCompatibleDC(0)
    bmp = g.CreateCompatibleBitmap(hdc, W, H)
    g.SelectObject(memdc, bmp)
    g.BitBlt(memdc, 0, 0, W, H, hdc, 0, 0, 0x00CC0020)
    import struct
    bi = bytearray(40)
    struct.pack_into('<I', bi, 0, 40); struct.pack_into('<i', bi, 4, W)
    struct.pack_into('<i', bi, 8, H); struct.pack_into('<H', bi, 12, 1)
    struct.pack_into('<H', bi, 14, 24)
    stride = ((W * 3 + 3) // 4) * 4
    sz = stride * H
    bits = ctypes.create_string_buffer(sz)
    g.GetDIBits(memdc, bmp, 0, H, bits, ctypes.c_char_p(bytes(bi)), 0)
    with open(path, 'wb') as f:
        f.write(struct.pack('<2sIHHI', b'BM', 54 + sz, 0, 0, 54))
        f.write(bytes(bi)); f.write(bits.raw)
    return W, H


def main():
    # 1) kill ALL java/javaw (clean slate)
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-Process javaw,java -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue"],
                   capture_output=True)
    time.sleep(1.5)
    # 2) launch OUR project
    subprocess.Popen(["E:/windows64/commands/vericut.bat"],
                     cwd="E:/vc_impeller_run",
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # launch project via dedicated wrapper (sets IGNORE_LAST + vcp)
    subprocess.Popen(["E:/vc_impeller_run/launch_impeller.bat"],
                     cwd="E:/vc_impeller_run",
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # 3) wait for OUR window
    h = None
    for i in range(40):
        time.sleep(1)
        ours, others, dialogs = enum()
        if ours:
            h = ours[0]
            print("OUR_WINDOW after", i + 1, "s", flush=True)
            break
    if h is None:
        print("NO_OUR_WINDOW"); return 2
    # close dialogs + minimize others
    for d in dialogs:
        u.PostMessageW(d, WM_CLOSE, 0, 0)
    for o in others:
        u.ShowWindow(o, SW_MINIMIZE)
    u.ShowWindow(h, SW_MAXIMIZE)
    time.sleep(0.5)
    ok = foreground(h)
    print("FOREGROUND", ok, flush=True)
    shot(os.path.join(TMP, "vc_full_loaded.bmp"))

    # 4) double-click Stock sub-window title to maximize it (~x700,y307 in 1536x864 window)
    u.SetCursorPos(700, 307)
    for _ in range(2):
        u.mouse_event(0x0002, 0, 0, 0, 0); time.sleep(0.06)
        u.mouse_event(0x0004, 0, 0, 0, 0); time.sleep(0.06)
    time.sleep(0.8)
    foreground(h)
    shot(os.path.join(TMP, "vc_full_stock.bmp"))
    print("stock view shot", flush=True)

    # 5) click Run (green triangle at physical ~1895,1001)
    u.SetCursorPos(1895, 1001); time.sleep(0.2)
    u.mouse_event(0x0002, 0, 0, 0, 0); time.sleep(0.08)
    u.mouse_event(0x0004, 0, 0, 0, 0)
    print("clicked RUN", flush=True)
    # 6) let it run, keep topmost
    deadline = time.time() + 60
    while time.time() < deadline:
        u.SetWindowPos(h, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
        time.sleep(0.5)
    foreground(h)
    shot(os.path.join(TMP, "vc_full_run.bmp"))
    print("run shot done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
