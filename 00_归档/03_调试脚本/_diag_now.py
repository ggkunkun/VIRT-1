# -*- coding: utf-8 -*-
import os, sys
import win32com.client as w, pythoncom
pythoncom.CoInitialize()
try:
    sw = w.GetActiveObject('SldWorks.Application')
    print('CONN GetActiveObject OK')
except Exception as e:
    print('GAO_ERR', str(e)[:80])
    try:
        sw = w.Dispatch('SldWorks.Application')
        print('CONN Dispatch OK')
    except Exception as e2:
        print('DISP_ERR', str(e2)[:80]); sys.exit(1)
p = sw.ActiveDoc
if not p:
    print('NO ACTIVE DOC'); sys.exit(1)
print('DOC', p.GetTitle, '| TYPE', p.GetType)
f = p.FirstFeature
while f:
    print('  FEAT', f.Name, '|', f.GetTypeName2)
    f = f.GetNextFeature
try:
    mp = p.GetMassProperties
    print('V_mm3 %.4f  A_mm2 %.4f  M_kg %.6f' % (mp[3]*1e9, mp[4]*1e6, mp[5]))
except Exception as e:
    print('MP_ERR', str(e)[:80])
try:
    b = p.GetBodies2(0, True)
    print('BODIES', len(b) if b else 0)
except Exception as e:
    print('BODY_ERR', str(e)[:80])
print('--- FILES ---')
for fn in ['jilunmo_revolve.SLDPRT','jilunmo_rebuild.SLDPRT','flange_D160_t14_6xM12.SLDPRT','_finalize.py','_rebuild2.py']:
    q = 'D:/Virtu模型/' + fn
    print('  ', fn, os.path.exists(q), os.path.getsize(q) if os.path.exists(q) else 0)
