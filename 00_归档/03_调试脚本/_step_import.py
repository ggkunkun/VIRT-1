# -*- coding: utf-8 -*-
"""STEP 导入 SolidWorks，并做实体级逆向测量"""
import os
import time

import win32com.client as w
import pythoncom

F = r'C:\Users\Administrator\Desktop\微型机轮模总成(P0) 6R15-6R12-6R10.step'
print('EXISTS', os.path.exists(F), os.path.getsize(F))

pythoncom.CoInitialize()
try:
    sw = w.GetActiveObject('SldWorks.Application')
    print('ATTACH ROT')
except Exception:
    sw = w.Dispatch('SldWorks.Application')
    print('ATTACH Dispatch')
sw.Visible = True

t0 = time.time()
doc = None
# 1) LoadFile4
try:
    doc = sw.LoadFile4(F, '', None, None)
    print('LoadFile4 ->', bool(doc))
except Exception as e:
    print('LoadFile4 ERR', type(e).__name__, str(e)[:120])

# 2) OpenDoc6 兜底
if not doc:
    try:
        e1 = w.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        e2 = w.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        doc = sw.OpenDoc6(F, 0, 1, '', e1, e2)
        print('OpenDoc6 ->', bool(doc), 'err', e1.value, 'warn', e2.value)
    except Exception as e:
        print('OpenDoc6 ERR', type(e).__name__, str(e)[:120])

print('ELAPSED %.2fs' % (time.time() - t0))
if not doc:
    print('IMPORT FAILED'); raise SystemExit(1)

print('TITLE', doc.GetTitle)
print('TYPE', doc.GetType, '(2=assembly,1=part)')

if doc.GetType == 2:
    comps = doc.GetComponents(False)
    print('TOPDOC_IS_ASSEMBLY comps=', len(comps) if comps else 0)
    for c in (comps or []):
        print('   COMP', c.Name2)
    part = None
else:
    part = doc

# 实体清单
if part is not None:
    bodies = part.GetBodies2(0, True)
    print('BODIES', len(bodies) if bodies else 0)
    for i, b in enumerate(bodies or []):
        try:
            nm = b.Name
        except Exception:
            nm = '?'
        try:
            box = b.GetBodyBox()
            dims = ((box[3] - box[0]) * 1000, (box[4] - box[1]) * 1000, (box[5] - box[2]) * 1000)
        except Exception as e:
            dims = ('err', type(e).__name__)
        try:
            nf = len(b.GetFaces())
        except Exception:
            nf = '?'
        print('  BODY%-2d %-22s faces=%-4s bbox=%.2f x %.2f x %.2f mm' % (i, nm, nf, *dims) if isinstance(dims[0], float) else '  BODY%d %s faces=%s bbox=%r' % (i, nm, nf, dims))

mp = doc.GetMassProperties
if mp and len(mp) >= 6:
    print('TOTAL_V %.6f cm3  A %.4f cm2  M %.4f kg' % (mp[3] * 1e6, mp[4] * 1e4, mp[5]))
print('DONE')
