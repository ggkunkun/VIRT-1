# -*- coding: utf-8 -*-
"""提取 SSCNC 操作面板 Button1 位图，按红/绿/黄像素占比识别急停/循环启动等彩色键。"""
import ctypes, win32gui, win32con

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

class BIH(ctypes.Structure):
    _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32),
                ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16),
                ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
                ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32),
                ("biYPelsPerMeter", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32),
                ("biClrImportant", ctypes.c_uint32)]

class BM(ctypes.Structure):
    _fields_ = [("bmType", ctypes.c_long), ("bmWidth", ctypes.c_long),
                ("bmHeight", ctypes.c_long), ("bmWidthBytes", ctypes.c_long),
                ("bmPlanes", ctypes.c_ushort), ("bmBitsPixel", ctypes.c_ushort),
                ("bmBits", ctypes.c_void_p)]

def bmp_stats(hbtn):
    hbmp = user32.SendMessageW(hbtn, win32con.BM_GETIMAGE, 0, 0)
    if not hbmp:
        return None
    bm = BM()
    gdi32.GetObjectW(hbmp, ctypes.sizeof(bm), ctypes.byref(bm))
    w, h = bm.bmWidth, abs(bm.bmHeight)
    if w <= 0 or h <= 0:
        return (w, h, "empty")
    hdr = BIH()
    hdr.biSize = ctypes.sizeof(BIH); hdr.biWidth = w; hdr.biHeight = -h
    hdr.biPlanes = 1; hdr.biBitCount = 32; hdr.biCompression = 0
    stride = ((w * 4 + 3) // 4) * 4
    buf = ctypes.create_string_buffer(stride * h)
    hdc = user32.GetDC(0)
    ok = gdi32.GetDIBits(hdc, hbmp, 0, h, buf, ctypes.byref(hdr), 0)
    user32.ReleaseDC(0, hdc)
    if not ok:
        return (w, h, "dib_fail")
    red = green = yellow = 0
    total = w * h
    for i in range(0, len(buf) - 3, 4):
        b, g, r = buf[i], buf[i+1], buf[i+2]
        if r > 140 and g < 110 and b < 110: red += 1
        elif g > 120 and r < 120 and b < 120: green += 1
        elif r > 140 and g > 120 and b < 100: yellow += 1
    return (w, h, round(red/total,3), round(green/total,3), round(yellow/total,3))

RIGHT = 919760
btns = []
def cb(h, _):
    if win32gui.GetClassName(h) == "Button" and win32gui.GetWindowText(h) == "Button1":
        btns.append((h, win32gui.GetWindowRect(h)))
    return True
win32gui.EnumChildWindows(RIGHT, cb, None)
btns.sort(key=lambda b: (b[1][1], b[1][0]))
print("Button1 count:", len(btns))
for i, (h, r) in enumerate(btns):
    print(i, "id=%d" % win32gui.GetDlgCtrlID(h), r, bmp_stats(h))
