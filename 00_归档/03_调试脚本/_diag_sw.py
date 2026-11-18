# -*- coding: utf-8 -*-
import os, sys, time
import win32com.client as w, pythoncom
pythoncom.CoInitialize()
try:
    sw = w.GetActiveObject('SldWorks.Application')
    print('CONN GetActiveObject')
except Exception as e:
    print('GAO_ERR', str(e)[:70])
    try:
        sw = w.Dispatch('SldWorks.Application')
        print('CONN Dispatch')
    except Exception as e2:
        print('DISP_ERR', str(e2)[:90]); sys.exit(1)
print('SW', sw.RevisionNumber)
docs = []
try:
    d = sw.GetFirstDocument2()
    while d:
        docs.append((d.GetTitle, d.GetType, d.GetPathName))
        d = d.GetNext
except Exception as e:
    print('ENUM_ERR', str(e)[:90])
print('OPEN_DOCS', docs)
p = sw.ActiveDoc
print('ACTIVE', p.GetTitle if p else None, '| path', p.GetPathName if p else None)
if p:
    fs=[]; f=p.FirstFeature
    while f:
        fs.append((f.Name,f.GetTypeName2)); f=f.GetNextFeature
    print('FEATS', fs[:20])
    try:
        mp=p.GetMassProperties
        print('V_mm3 %.4f  A_mm2 %.4f'%(mp[3]*1e9,mp[4]*1e6))
    except Exception as e: print('MP_ERR',str(e)[:80])
print('--- SLDPRT files ---')
for fn in ['jilunmo_revolve.SLDPRT','jilunmo_rebuild.SLDPRT','jilunmo_final.SLDPRT','flange_D160_t14_6xM12.SLDPRT']:
    q='D:/Virtu模型/'+fn
    print(' ',fn,os.path.exists(q),os.path.getsize(q) if os.path.exists(q) else 0,
          time.strftime('%H:%M:%S',time.localtime(os.path.getmtime(q))) if os.path.exists(q) else '-')
