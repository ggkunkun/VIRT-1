# -*- coding: utf-8 -*-
import os, shutil, json
import win32com.client as w, pythoncom
D=r'D:\Virtu模型\works\model_supervised'
pythoncom.CoInitialize()
try: sw=w.GetActiveObject('SldWorks.Application')
except Exception: sw=w.Dispatch('SldWorks.Application')
sw.Visible=True
def ev(): return w.VARIANT(pythoncom.VT_BYREF|pythoncom.VT_I4,0)
def reopen(name,dtype):
    p=os.path.join(D,name)
    if not os.path.exists(p): print('MISSING',name); return None
    cp=os.path.join(r'D:\Virtu模型','_chk_'+name)
    shutil.copy2(p,cp)
    try: return sw.OpenDoc6(cp,dtype,0,'',ev(),ev())
    except Exception as e: print('OPEN_ERR',name,str(e)[:80]); return None
print('=== FILES ===')
for n in ['model_part.SLDPRT','model_assembly.SLDASM','model_drawing.SLDDRW']:
    p=os.path.join(D,n); b=open(p,'rb').read(8) if os.path.exists(p) else b''
    print(' ',n,os.path.getsize(p) if os.path.exists(p) else 0,'B head',b.hex())
print('=== PART ===')
p=reopen('model_part.SLDPRT',1)
if p:
    mp=p.GetMassProperties
    print(' V_mm3 %.4f A_mm2 %.4f'%(mp[3]*1e9,mp[4]*1e6))
    fs=[];f=p.FirstFeature
    while f:
        if f.GetTypeName2 in ('ProfileFeature','Revolution','ICE'): fs.append((f.Name,f.GetTypeName2))
        f=f.GetNextFeature
    print(' FEATS',fs)
print('=== ASSEMBLY ===')
a=reopen('model_assembly.SLDASM',2)
if a:
    print(' TYPE',a.GetType,'COMPONENTS',len(a.GetComponents(False) or []))
    mp=a.GetMassProperties
    print(' V_cm3 %.4f A_cm2 %.4f M_kg %.6f'%(mp[3]*1e6,mp[4]*1e4,mp[5]))
print('=== DRAWING ===')
g=reopen('model_drawing.SLDDRW',3)
if g:
    print(' TYPE',g.GetType,'VIEW_COUNT',g.GetViewCount)
    try: print(' VIEWS',[v.Name for v in (g.GetViews or [])][:10])
    except Exception as e: print(' views_err',str(e)[:60])
