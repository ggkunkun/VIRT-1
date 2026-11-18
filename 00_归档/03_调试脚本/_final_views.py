# -*- coding: utf-8 -*-
import ctypes, time, sys
import win32com.client as w, pythoncom
pythoncom.CoInitialize()
try: sw=w.GetActiveObject('SldWorks.Application')
except Exception: sw=w.Dispatch('SldWorks.Application')
sw.Visible=True
def ev(): return w.VARIANT(pythoncom.VT_BYREF|pythoncom.VT_I4,0)
DRW=r'D:\Virtu模型\_verify_wheel_mold_assembly.SLDDRW'
ASM=r'D:\Virtu模型\_verify_wheel_mold_assembly.SLDASM'
g=sw.OpenDoc6(DRW,3,0,'',ev(),ev())
print('DRAWING',g.GetTitle if g else None,'TYPE',g.GetType if g else None)
if g:
    for label,fn in (('GetViewCount_attr',lambda:g.GetViewCount),('GetViews',lambda:g.GetViews())):
        try:
            v=fn(); print(' ',label,'=',len(v) if hasattr(v,'__len__') and not isinstance(v,int) else v)
            if label=='GetViews' and v:
                print('   names',[x.Name for x in v][:12])
        except Exception as e: print(' ',label,'ERR',str(e)[:80])
    try:
        v=g.GetFirstView(); names=[]; guard=0
        while v and guard<20:
            guard+=1
            try: names.append(v.Name)
            except Exception: names.append('?')
            try: v=v.GetNextView()
            except Exception as e: print('  nextview err',str(e)[:60]); break
        print('  ENUM',names)
    except Exception as e: print('  ENUM_ERR',str(e)[:80])

def front(keyword, w=1290,h=800):
    u=ctypes.windll.user32; hw=[]
    EP=ctypes.WINFUNCTYPE(ctypes.c_bool,ctypes.c_int,ctypes.c_void_p)
    def cb(h,l):
        n=u.GetWindowTextLengthW(h)
        if n:
            b=ctypes.create_unicode_buffer(n+1); u.GetWindowTextW(h,b,n+1)
            if keyword.lower() in b.value.lower() and u.IsWindowVisible(h): hw.append(h)
        return True
    u.EnumWindows(EP(cb),0)
    if hw:
        t=hw[0]
        if u.IsZoomed(t): u.ShowWindow(t,9); time.sleep(0.4)
        u.SetWindowPos(t,0,0,0,w,h,0x0040); u.SetForegroundWindow(t)
    print('FRONT',keyword,hw)
    time.sleep(1.3)

front('_verify_wheel_mold_assembly - 图纸1')
