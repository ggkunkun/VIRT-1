# -*- coding: utf-8 -*-
"""STEP 导入 v3：正确的 byref VARIANT 参数"""
import os
import time

import win32com.client as w
import pythoncom

TMP = os.path.join(os.environ.get('TEMP', r'C:\Windows\Temp'), 'step_in.step')
pythoncom.CoInitialize()
try:
    sw = w.GetActiveObject('SldWorks.Application')
except Exception:
    sw = w.Dispatch('SldWorks.Application')
sw.Visible = True

doc = None


def errvar():
    return w.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)


# A) LoadFile4 + importData + byref errors
try:
    imp = sw.GetImportFileData(TMP)
    ev = errvar()
    doc = sw.LoadFile4(TMP, '', imp, ev)
    print('A LoadFile4(imp,var) ->', bool(doc), 'err', ev.value)
except Exception as e:
    print('A ERR', type(e).__name__, str(e)[:140])

# B) LoadFile2
if not doc:
    try:
        doc = sw.LoadFile2(TMP, '')
        print('B LoadFile2 ->', bool(doc))
    except Exception as e:
        print('B ERR', type(e).__name__, str(e)[:140])

# C) LoadFile
if not doc:
    try:
        doc = sw.LoadFile(TMP, '')
        print('C LoadFile ->', bool(doc))
    except Exception as e:
        print('C ERR', type(e).__name__, str(e)[:140])

if not doc:
    print('ALL_FAILED'); raise SystemExit(2)

time.sleep(1.5)
print('TITLE', doc.GetTitle)
print('TYPE', doc.GetType, '(2=assembly 1=part)')

if doc.GetType == 2:
    comps = doc.GetComponents(False)
    print('COMPONENTS', len(comps) if comps else 0)
    for c in (comps or [])[:10]:
        print('   ', c.Name2)
else:
    bodies = doc.GetBodies2(0, True)
    print('BODIES', len(bodies) if bodies else 0)
    for i, b in enumerate(bodies or []):
        try:
            box = b.GetBodyBox()
            print('  BODY%d %s faces=%s bbox %.2f x %.2f x %.2f mm'
                  % (i, b.Name, len(b.GetFaces()),
                     (box[3] - box[0]) * 1000, (box[4] - box[1]) * 1000, (box[5] - box[2]) * 1000))
        except Exception as e:
            print('  BODY%d err %s' % (i, type(e).__name__))
mp = doc.GetMassProperties
if mp and len(mp) >= 6:
    print('TOTAL_V %.4f cm3  A %.4f cm2  M %.4f kg' % (mp[3] * 1e6, mp[4] * 1e4, mp[5]))
print('DONE')
