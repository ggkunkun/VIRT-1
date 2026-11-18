# -*- coding: utf-8 -*-
import win32com.client as w, pythoncom
pythoncom.CoInitialize()
try: sw = w.GetActiveObject('SldWorks.Application')
except Exception: sw = w.Dispatch('SldWorks.Application')
p = sw.ActiveDoc
print('DOC', p.GetTitle)
f = p.FirstFeature
while f:
    print('  %-20s | %s' % (f.Name, f.GetTypeName2))
    f = f.GetNextFeature
b = p.GetBodies2(0, True)
print('BODIES', len(b) if b else 0)
mp = p.GetMassProperties
print('V %.4f mm3  A %.4f mm2' % (mp[3]*1e9, mp[4]*1e6))
