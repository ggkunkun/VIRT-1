# -*- coding: utf-8 -*-
import os, shutil, json, time
import win32com.client as w, pythoncom
ROOT=r'D:\Virtu模型'; D=os.path.join(ROOT,'works','from_zero')
pythoncom.CoInitialize()
try: sw=w.GetActiveObject('SldWorks.Application')
except Exception: sw=w.Dispatch('SldWorks.Application')
sw.Visible=True
def ev(): return w.VARIANT(pythoncom.VT_BYREF|pythoncom.VT_I4,0)
def reopen(name,dtype):
    p=os.path.join(D,name)
    if not os.path.exists(p): print('MISSING',name); return None
    cp=os.path.join(ROOT,'_fzchk_'+name); shutil.copy2(p,cp)
    try: return sw.OpenDoc6(cp,dtype,0,'',ev(),ev())
    except Exception as e: print('OPEN_ERR',name,str(e)[:90]); return None
print('=== ARTIFACTS (exclude SW lock files) ===')
for n in sorted(os.listdir(D)):
    if n.startswith('~$'): continue
    if os.path.splitext(n)[1].lower() in ('.sldprt','.sldasm','.slddrw'):
        p=os.path.join(D,n); b=open(p,'rb').read(8)
        print(' ',n,os.path.getsize(p),'B  head',b.hex(),'  mtime',
              time.strftime('%H:%M:%S',time.localtime(os.path.getmtime(p))))
print('=== PART ===')
p=reopen('model_part.SLDPRT',1)
if p:
    mp=p.GetMassProperties; print(' V_mm3 %.4f  A_mm2 %.4f'%(mp[3]*1e9,mp[4]*1e6))
    fs=[];f=p.FirstFeature
    while f:
        if f.GetTypeName2 in ('ProfileFeature','Revolution','ICE'): fs.append((f.Name,f.GetTypeName2))
        f=f.GetNextFeature
    print(' FEATS',fs,'BODIES',len(p.GetBodies2(0,True) or []))
print('=== ASSEMBLY ===')
a=reopen('model_assembly.SLDASM',2)
if a:
    mp=a.GetMassProperties
    print(' TYPE',a.GetType,'COMPONENTS',len(a.GetComponents(False) or []),
          ' V_cm3 %.4f  A_cm2 %.4f'%(mp[3]*1e6,mp[4]*1e4))
print('=== DRAWING ===')
g=reopen('model_drawing.SLDDRW',3)
if g: print(' TYPE',g.GetType,'VIEW_COUNT',g.GetViewCount)
print('=== SINGLE INSTANCE ===')
from bridges.feature_ops import single_case
c=single_case()
print(' procs',c.get('sldworks_process_count'),'docs',c.get('open_document_count'),
      'docs_list',c.get('open_documents'),'enum_source',c.get('document_enum_source'))
