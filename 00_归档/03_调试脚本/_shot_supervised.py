import ctypes,time
import win32com.client as w,pythoncom
pythoncom.CoInitialize()
try: sw=w.GetActiveObject('SldWorks.Application')
except Exception: sw=w.Dispatch('SldWorks.Application')
sw.Visible=True
def ev(): return w.VARIANT(pythoncom.VT_BYREF|pythoncom.VT_I4,0)
d=sw.OpenDoc6(r'D:\Virtu模型\_fzchk_model_part.SLDPRT',1,0,'',ev(),ev())
if d:
    d.ClearSelection2(True)
    try: d.ShowNamedView2('*Isometric',7)
    except Exception as e: print('iso',str(e)[:50])
    try: d.ViewZoomtofit2()
    except Exception: pass
print('ACTIVE',d.GetTitle if d else None)
u=ctypes.windll.user32;hw=[]
EP=ctypes.WINFUNCTYPE(ctypes.c_bool,ctypes.c_int,ctypes.c_void_p)
def cb(h,l):
    n=u.GetWindowTextLengthW(h)
    if n:
        b=ctypes.create_unicode_buffer(n+1);u.GetWindowTextW(h,b,n+1)
        if '_fzchk_model_part' in b.value.lower() and u.IsWindowVisible(h): hw.append(h)
    return True
u.EnumWindows(EP(cb),0)
if hw:
    t=hw[0]
    if u.IsZoomed(t): u.ShowWindow(t,9);time.sleep(0.4)
    u.SetWindowPos(t,0,0,0,1300,780,0x0040);u.SetForegroundWindow(t)
print('FRONT',hw);time.sleep(1.5)
