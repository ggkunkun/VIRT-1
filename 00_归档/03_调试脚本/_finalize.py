# -*- coding: utf-8 -*-
import ctypes, os, time
import win32com.client as w, pythoncom
pythoncom.CoInitialize()
try: sw = w.GetActiveObject('SldWorks.Application')
except Exception: sw = w.Dispatch('SldWorks.Application')
sw.Visible = True
p = sw.ActiveDoc
print('DOC', p.GetTitle)
p.ClearSelection2(True)
try:
    p.ShowNamedView2('*Isometric', 7)
except Exception as e: print('iso', e)
p.ViewZoomtofit2()

mp = p.GetMassProperties
print('V %.4f mm3 (%.4f cm3)' % (mp[3]*1e9, mp[3]*1e6))
print('A %.4f mm2' % (mp[4]*1e6))
print('M %.6f kg' % mp[5])
b = p.GetBodies2(0, True)
print('BODIES', len(b) if b else 0)
if b:
    box = b[0].GetBodyBox()
    print('BBOX X %.3f..%.3f  Y %.3f..%.3f  Z %.3f..%.3f' % tuple(v*1000 for v in box))
    print('FACES', len(b[0].GetFaces()))
fs = []
f = p.FirstFeature
while f:
    if f.GetTypeName2 in ('ProfileFeature','Revolution','Cut','Extrusion'):
        fs.append((f.Name, f.GetTypeName2))
    f = f.GetNextFeature
print('FEATS', fs)

OUT = r'D:\Virtu模型\jilunmo_revolve.SLDPRT'
try:
    p.SaveAs3(OUT, 0, 1); time.sleep(1)
    print('SAVED', os.path.exists(OUT), os.path.getsize(OUT) if os.path.exists(OUT) else 0)
except Exception as e:
    print('SAVE ERR', type(e).__name__, str(e)[:70])

hw = []
EP = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_void_p)
def cb(h, l):
    n = ctypes.windll.user32.GetWindowTextLengthW(h)
    if n:
        bb = ctypes.create_unicode_buffer(n+1)
        ctypes.windll.user32.GetWindowTextW(h, bb, n+1)
        if 'jilunmo' in bb.value.lower() and ctypes.windll.user32.IsWindowVisible(h):
            hw.append(h)
    return True
ctypes.windll.user32.EnumWindows(EP(cb), 0)
if hw:
    ctypes.windll.user32.SetForegroundWindow(hw[0])
    print('FRONT')
time.sleep(1.2)
