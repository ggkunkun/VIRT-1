# -*- coding: utf-8 -*-
"""把已保存的法兰盘重新打开并缩放到合适视图，供截图复核"""
import ctypes
import os
import time

import win32com.client as w
import pythoncom

F = r'D:\Virtu模型\flange_D160_t14_6xM12.SLDPRT'
print('FILE_EXISTS', os.path.exists(F), os.path.getsize(F) if os.path.exists(F) else 0)

pythoncom.CoInitialize()
try:
    sw = w.GetActiveObject('SldWorks.Application')
    print('ATTACH ROT')
except Exception:
    sw = w.Dispatch('SldWorks.Application')
    print('ATTACH Dispatch')
sw.Visible = True

part = sw.ActiveDoc
title = part.GetTitle if part else None
print('ACTIVEDOC', title)

if not title or 'flange' not in title:
    errs = w.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warns = w.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    part = sw.OpenDoc6(F, 1, 0, '', errs, warns)
    print('OPENED', bool(part), 'errs', errs.value, 'warns', warns.value)
else:
    print('ALREADY_OPEN')

part.ClearSelection2(True)
part.ViewZoomtofit2()
# 切等轴测视图
try:
    part.ShowNamedView2('*Isometric', 7)
    part.ViewZoomtofit2()
    print('ISO_VIEW ok')
except Exception as e:
    print('ISO_ERR', type(e).__name__, e)

mp = part.GetMassProperties
print('RECHECK_V %.10e m3 (%.4f cm3)' % (mp[3], mp[3] * 1e6))

# 枚举实体几何做二次确认
try:
    bodies = part.GetBodies2(0, True)
    print('BODIES', len(bodies) if bodies else 0)
except Exception as e:
    print('BODIES_ERR', type(e).__name__)

# 置前
hwnds = []
EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_void_p)


def cb(hwnd, lp):
    n = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    if n:
        buf = ctypes.create_unicode_buffer(n + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, n + 1)
        if 'flange' in buf.value.lower() and ctypes.windll.user32.IsWindowVisible(hwnd):
            hwnds.append(hwnd)
    return True


ctypes.windll.user32.EnumWindows(EnumProc(cb), 0)
print('HWNDS', hwnds)
if hwnds:
    ctypes.windll.user32.ShowWindow(hwnds[0], 3)
    ctypes.windll.user32.SetForegroundWindow(hwnds[0])
    print('BROUGHT_TO_FRONT')
time.sleep(1)
print('DONE')
