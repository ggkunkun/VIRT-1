# -*- coding: utf-8 -*-
import ctypes, time, sys
import win32com.client as w, pythoncom
pythoncom.CoInitialize()
try: sw=w.GetActiveObject('SldWorks.Application')
except Exception: sw=w.Dispatch('SldWorks.Application')
sw.Visible=True
def ev(): return w.VARIANT(pythoncom.VT_BYREF|pythoncom.VT_I4,0)
key=sys.argv[1]
kw=sys.argv[2]
u=ctypes.windll.user32
if key=='asm':
    d=sw.OpenDoc6(r'D:\Virtu模型\_verify_wheel_mold_assembly.SLDASM',2,0,'',ev(),ev())
    if d:
        d.ClearSelection2(True)
        try: d.ShowNamedView2('*Isometric',7)
        except Exception as e: print('ISO_ERR',str(e)[:60])
        try: d.ViewZoomtofit2()
        except Exception as e: print('ZOOM_ERR',str(e)[:60])
else:
    d=sw.OpenDoc6(r'D:\Virtu模型\_verify_wheel_mold_assembly.SLDDRW',3,0,'',ev(),ev())
    if d:
        try: d.ViewZoomtofit2()
        except Exception as e: print('ZOOM_ERR',str(e)[:60])
print('ACTIVE',d.GetTitle if d else None)
hw=[]
EP=ctypes.WINFUNCTYPE(ctypes.c_bool,ctypes.c_int,ctypes.c_void_p)
def cb(h,l):
    n=u.GetWindowTextLengthW(h)
    if n:
        b=ctypes.create_unicode_buffer(n+1); u.GetWindowTextW(h,b,n+1)
        if kw.lower() in b.value.lower() and u.IsWindowVisible(h): hw.append(h)
    return True
u.EnumWindows(EP(cb),0)
if hw:
    t=hw[0]
    if u.IsZoomed(t): u.ShowWindow(t,9); time.sleep(0.4)
    u.SetWindowPos(t,0,0,0,1500,940,0x0040); u.SetForegroundWindow(t)
print('FRONT',hw)
time.sleep(1.6)
