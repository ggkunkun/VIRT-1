# -*- coding: utf-8 -*-
"""在旋转体上切 3× Ø7 @ PCD38 贯穿孔，并保存"""
import math
import os
import time

import win32com.client as w
import pythoncom

OUT = r'D:\Virtu模型\jilunmo_rebuild.SLDPRT'
V_BODY = 37404.5875
V_HOLES = 3 * math.pi * 3.5 ** 2 * 12.0
V_EXPECT = V_BODY - V_HOLES
print('EXPECT_V_AFTER_CUT %.4f mm3' % V_EXPECT)

pythoncom.CoInitialize()
try:
    sw = w.GetActiveObject('SldWorks.Application')
except Exception:
    sw = w.Dispatch('SldWorks.Application')
part = sw.ActiveDoc
print('DOC', part.GetTitle)

# ---------- 草图: 3 个 Ø7 圆 @ R19 ----------
plane = part.FeatureByName('右视基准面')
plane.Select2(False, 0)
part.InsertSketch2(True)
sm = part.SketchManager
sm.AddToDB = True
R_HOLE, R_PCD = 0.0035, 0.019
for i in range(3):
    a = math.radians(120.0 * i)
    cx, cy = R_PCD * math.cos(a), R_PCD * math.sin(a)
    sm.CreateCircle(cx, cy, 0, cx + R_HOLE, cy, 0)
sk = sm.ActiveSketch
print('ARCS', sk.GetArcCount, '(expect 3)')
part.InsertSketch2(False)

# ---------- 求草图特征名 ----------
last_sk = None
f = part.FirstFeature
while f:
    if f.GetTypeName2 == 'ProfileFeature':
        last_sk = f
    f = f.GetNextFeature
print('SKETCH', last_sk.Name)
part.ClearSelection2(True)
last_sk.Select2(False, 0)

CUT_ARGS = [True, False, False, 1, 0, 0.0, 0.0,
            False, False, False, False, 0.0, 0.0,
            False, False, False, False,
            False, True, True,
            False, True, True]

ok = False
for n in (23, 20, 22, 24):
    try:
        r = part.FeatureManager.FeatureCut4(*CUT_ARGS[:n])
        print('FeatureCut4(%d) -> %r' % (n, bool(r)))
        if r:
            ok = True
            break
    except Exception as e:
        print('FeatureCut4(%d) ERR %s %s' % (n, type(e).__name__, str(e)[:70]))

print('---FEATURES---')
f = part.FirstFeature
fs = []
while f:
    if f.GetTypeName2 in ('ProfileFeature', 'Revolution', 'Cut', 'CutExtrude'):
        fs.append((f.Name, f.GetTypeName2))
    f = f.GetNextFeature
print(fs)

mp = part.GetMassProperties
V = mp[3] * 1e9
print('V_ACTUAL %.4f mm3 (%.4f cm3)' % (V, V / 1000))
err = abs(V - V_EXPECT) / V_EXPECT
print('ERR %.5f%%  %s' % (err * 100, 'PASS' if err < 0.002 else 'FAIL'))
print('A %.4f mm2  M %.6f kg' % (mp[4] * 1e6, mp[5]))

if os.path.exists(OUT):
    os.remove(OUT)
for label, fn in [('SaveAs3', lambda: part.SaveAs3(OUT, 0, 1)),
                  ('SaveAs', lambda: part.SaveAs(OUT))]:
    try:
        fn()
        time.sleep(1)
        if os.path.exists(OUT):
            print('SAVED via', label, os.path.getsize(OUT), 'bytes')
            break
    except Exception as e:
        print(label, 'ERR', type(e).__name__, str(e)[:80])
print('TITLE', part.GetTitle)
