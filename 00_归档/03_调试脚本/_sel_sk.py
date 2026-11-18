# -*- coding: utf-8 -*-
import ctypes, time
import win32com.client as w, pythoncom
pythoncom.CoInitialize()
try: sw = w.GetActiveObject('SldWorks.Application')
except Exception: sw = w.Dispatch('SldWorks.Application')
sw.Visible = True
p = sw.ActiveDoc
p.ClearSelection2(True)
sk = p.FeatureByName('草图2')
sk.Select2(False, 0)
print('SELECTED', sk.Name)
p.ViewZoomtofit2()
hw = []
EP = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_void_p)
def cb(h, l):
    n = ctypes.windll.user32.GetWindowTextLengthW(h)
    if n:
        b = ctypes.create_unicode_buffer(n+1)
        ctypes.windll.user32.GetWindowTextW(h, b, n+1)
        if 'jilunmo' in b.value.lower() and ctypes.windll.user32.IsWindowVisible(h):
            hw.append(h)
    return True
ctypes.windll.user32.EnumWindows(EP(cb), 0)
print('HWND', hw)
if hw:
    ctypes.windll.user32.ShowWindow(hw[0], 3)
    ctypes.windll.user32.SetForegroundWindow(hw[0])
    print('FRONT')
time.sleep(1.0)
