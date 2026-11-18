# -*- coding: utf-8 -*-
"""Capture a specific window via PrintWindow (occlusion-free) + list child controls."""
import ctypes
import json
import struct
import sys
from ctypes import wintypes

u32 = ctypes.windll.user32
g32 = ctypes.windll.gdi32
PW_RENDERFULLCONTENT = 0x00000002


def cap_window(hwnd, path):
    # restore if minimized so PrintWindow has a real surface
    if u32.IsIconic(hwnd):
        u32.ShowWindow(hwnd, 9)
        import time
        time.sleep(0.5)
    r = wintypes.RECT()
    u32.GetWindowRect(hwnd, ctypes.byref(r))
    ww = r.right - r.left
    hh = r.bottom - r.top
    if ww <= 0 or hh <= 0:
        return False, 0, 0
    hdc = u32.GetWindowDC(hwnd)
    memdc = g32.CreateCompatibleDC(hdc)
    bmp = g32.CreateCompatibleBitmap(hdc, ww, hh)
    g32.SelectObject(memdc, bmp)
    ok = u32.PrintWindow(hwnd, memdc, PW_RENDERFULLCONTENT)
    if not ok:
        g32.BitBlt(memdc, 0, 0, ww, hh, hdc, 0, 0, 0x00CC0020)
    header = struct.pack("<IiiHHIIiiII", 40, ww, -hh, 1, 32, 0, ww * hh * 4, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(ww * hh * 4)
    g32.GetDIBits(memdc, bmp, 0, hh, buf, header, 0)
    with open(path, "wb") as f:
        f.write(b"BM")
        f.write(struct.pack("<I", 14 + 40 + ww * hh * 4))
        f.write(struct.pack("<I", 0))
        f.write(struct.pack("<I", 54))
        f.write(header)
        f.write(buf.raw)
    g32.DeleteObject(bmp)
    g32.DeleteDC(memdc)
    u32.ReleaseDC(hwnd, hdc)
    return bool(ok), ww, hh


def list_children(hwnd, out, depth=0, maxdepth=4):
    EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def cb(h, _):
        cls = ctypes.create_unicode_buffer(256)
        u32.GetClassNameW(h, cls, 256)
        ln = u32.GetWindowTextLengthW(h)
        b = ctypes.create_unicode_buffer(ln + 1)
        u32.GetWindowTextW(h, b, ln + 1)
        r = wintypes.RECT()
        u32.GetWindowRect(h, ctypes.byref(r))
        out.append({"d": depth, "hwnd": h, "cls": cls.value,
                    "title": b.value[:60], "vis": bool(u32.IsWindowVisible(h)),
                    "rect": [r.left, r.top, r.right, r.bottom]})
        if depth < maxdepth:
            list_children(h, out, depth + 1, maxdepth)
        return True

    u32.EnumChildWindows(hwnd, EnumProc(cb), 0)


def main():
    hwnd = int(sys.argv[1])
    path = sys.argv[2]
    ok, w, h = cap_window(hwnd, path)
    print(json.dumps({"ok": ok, "path": path, "w": w, "h": h}, ensure_ascii=False))
    if "--children" in sys.argv:
        ch = []
        list_children(hwnd, ch)
        # only show reasonably sized visible controls
        for c in ch:
            rc = c["rect"]
            if c["vis"] and (rc[2] - rc[0]) > 40 and (rc[3] - rc[1]) > 15:
                print(f'  d{c["d"]} hwnd={c["hwnd"]} cls={c["cls"]!r} title={c["title"]!r} rect={rc}')


if __name__ == "__main__":
    main()
