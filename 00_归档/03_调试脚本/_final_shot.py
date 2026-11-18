# -*- coding: utf-8 -*-
import ctypes, time
import win32com.client as w, pythoncom
pythoncom.CoInitialize()
try: sw = w.GetActiveObject('SldWorks.Application')
except Exception: sw = w.Dispatch('SldWorks.Application')
sw.Visible = True
P = r'D:\Virtu模型\jilunmo_final.SLDPRT'
d = sw.OpenDoc6(P, 1, 0, '', w.VARIANT(pythoncom.VT_BYREF|pythoncom.VT_I4,0), w.VARIANT(pythoncom.VT_BYREF|pythoncom.VT_I4,0))
if not d: d = sw.ActiveDoc
print('ACTIVE', d.GetTitle if d else None)
d.ClearSelection2(True)
d.ShowNamedView2('*Isometric', 7)
d.ViewZoomtofit2()
u = ctypes.windll.user32
hw=[]
EP = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_void_p)
def cb(h,l):
    n=u.GetWindowTextLengthW(h)
    if n:
        b=ctypes.create_unicode_buffer(n+1); u.GetWindowTextW(h,b,n+1)
        if 'jilunmo_final' in b.value.lower() and u.IsWindowVisible(h): hw.append(h)
    return True
u.EnumWindows(EP(cb),0)
print('HWND',hw)
if hw:
    t=hw[0]
    if u.IsZoomed(t):
        u.ShowWindow(t,9); time.sleep(0.5)
    u.SetWindowPos(t,0,0,0,1290,760,0x0040)
    u.SetForegroundWindow(t)
    print('FRONT')
time.sleep(1.5)
