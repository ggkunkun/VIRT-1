# -*- coding: utf-8 -*-
"""STEP 导入 v2：ASCII 路径 + GetImportFileData + 多种兜底"""
import os
import shutil
import time

import win32com.client as w
import pythoncom

SRC = r'C:\Users\Administrator\Desktop\微型机轮模总成(P0) 6R15-6R12-6R10.step'
TMP = os.path.join(os.environ.get('TEMP', r'C:\Windows\Temp'), 'step_in.step')
shutil.copyfile(SRC, TMP)
print('COPIED ->', TMP, os.path.getsize(TMP))

pythoncom.CoInitialize()
try:
    sw = w.GetActiveObject('SldWorks.Application')
    print('ATTACH ROT')
except Exception:
    sw = w.Dispatch('SldWorks.Application')
    print('ATTACH Dispatch')
sw.Visible = True

doc = None

# --- 方案1: GetImportFileData + LoadFile4 ---
try:
    imp = sw.GetImportFileData(TMP)
    print('ImportData obj ->', bool(imp), imp)
    doc = sw.LoadFile4(TMP, '', imp, None)
    print('LoadFile4(with importData) ->', bool(doc))
except Exception as e:
    print('S1 ERR', type(e).__name__, str(e)[:150])

# --- 方案2: OpenDoc6 as PART ---
if not doc:
    for dt in (1, 2, 0):
        try:
            e1 = w.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            e2 = w.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            doc = sw.OpenDoc6(TMP, dt, 1, '', e1, e2)
            print('OpenDoc6 type=%d ->' % dt, bool(doc), 'err', e1.value, 'warn', e2.value)
            if doc:
                break
        except Exception as e:
            print('OpenDoc6 type=%d ERR' % dt, type(e).__name__, str(e)[:100])

# --- 方案3: LoadFile4 不给 ImportData ---
if not doc:
    try:
        doc = sw.LoadFile4(TMP, '', None)
        print('LoadFile4(3-arg) ->', bool(doc))
    except Exception as e:
        print('S3 ERR', type(e).__name__, str(e)[:120])

if not doc:
    print('IMPORT FAILED'); raise SystemExit(1)

time.sleep(1)
print('TITLE', doc.GetTitle)
print('TYPE', doc.GetType, '(2=assembly 1=part)')
print('PATH', doc.GetPathName)
