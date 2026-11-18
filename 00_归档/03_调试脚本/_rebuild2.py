# -*- coding: utf-8 -*-
"""
机轮模重建（第二次，带前置断言）
1. 新建零件 -> 旋转母线（含倒角/锥面，精确）
2. 断言：草图独立存在于特征树
3. FeatureCut4(27) 多布局尝试切 3×Ø7
4. 无论成败都验证体积并保存
"""
import math
import os
import time

import win32com.client as w
import pythoncom

OUT = r'D:\Virtu模型\jilunmo_rebuild.SLDPRT'

OUTER = [(0, 11.5), (1, 12.5), (8, 12.5), (8, 25.5), (9, 26.5),
         (19, 26.5), (20, 25.5), (20, 12.5), (25, 12.5), (40, 10.0)]
INNER = [(40, 4.5), (38.5, 4.5), (38.5, 3.0), (1.5, 3.0), (1.5, 4.5), (0, 4.5)]
PROFILE = OUTER + INNER

V_BODY = 37404.5875
V_HOLES = 3 * math.pi * 3.5 ** 2 * 12.0
V_TARGET = V_BODY - V_HOLES

pythoncom.CoInitialize()
try:
    sw = w.GetActiveObject('SldWorks.Application')
except Exception:
    sw = w.Dispatch('SldWorks.Application')
sw.Visible = True

doc = None
try:
    doc = sw.NewPart()
except Exception:
    pass
part = doc or sw.ActiveDoc
print('DOC', part.GetTitle)


def feats(kinds=('ProfileFeature', 'Revolution', 'Cut', 'CutExtrude', 'Extrusion')):
    out = []
    f = part.FirstFeature
    while f:
        if f.GetTypeName2 in kinds:
            out.append((f.Name, f.GetTypeName2))
        f = f.GetNextFeature
    return out


# ---------- 1. 旋转 ----------
plane = part.FeatureByName('前视基准面')
plane.Select2(False, 0)
part.InsertSketch2(True)
sm = part.SketchManager
sm.AddToDB = True
for i in range(len(PROFILE)):
    x1, y1 = PROFILE[i]
    x2, y2 = PROFILE[(i + 1) % len(PROFILE)]
    sm.CreateLine(x1 / 1000, y1 / 1000, 0, x2 / 1000, y2 / 1000, 0)
sm.CreateCenterLine(0, 0, 0, 0.040, 0, 0)
print('SK1_LINES', sm.ActiveSketch.GetLineCount)
part.InsertSketch2(False)

sk1 = part.FeatureByName('草图1')
part.ClearSelection2(True)
sk1.Select2(False, 0)
REV = [True, True, False, False, False, False,
       0, 0, 2 * math.pi, 0,
       False, False, 0.0, 0.0,
       0, 0.0, 0.0, True, True, True]
print('REVOLVE', bool(part.FeatureManager.FeatureRevolve2(*REV)))
print('V_AFTER_REV %.3f (target %.3f)' % (part.GetMassProperties[3] * 1e9, V_BODY))
print('FEATS', feats())

# ---------- 2. 孔草图 + 前置断言 ----------
pl2 = part.FeatureByName('右视基准面')
pl2.Select2(False, 0)
part.InsertSketch2(True)
R_HOLE, R_PCD = 0.0035, 0.019
for i in range(3):
    a = math.radians(120.0 * i)
    cx, cy = R_PCD * math.cos(a), R_PCD * math.sin(a)
    sm.CreateCircle(cx, cy, 0, cx + R_HOLE, cy, 0)
print('SK2_ARCS', sm.ActiveSketch.GetArcCount)
part.InsertSketch2(False)

fl = feats()
print('FEATS_AFTER_SK2', fl)
sks = [x for x in fl if x[1] == 'ProfileFeature']
print('ASSERT_SKETCH_IN_TREE', 'PASS(%d)' % len(sks) if len(sks) >= 2 else 'FAIL only %d' % len(sks))

if len(sks) < 2:
    print('ABORT: sketch not independent, cut impossible')
    raise SystemExit(1)

skf = part.FeatureByName(sks[-1][0])
print('CUT_SKETCH', skf.Name)

# ---------- 3. 切除 ----------
base = [True, False, False, 1, 0, 0.0, 0.0,
        False, False, False, False, 0.0, 0.0,
        False, False, False, False,
        False, True, True,
        False, True, True]
S4 = [0, 0.0, False, 0.0]
layouts = [
    ('insert@17', base[:17] + S4 + base[17:]),
    ('append',    base + S4),
    ('insert@18', base[:18] + S4 + base[18:]),
]


def run(lb, args):
    try:
        part.ClearSelection2(True)
        skf.Select2(False, 0)
        r = part.FeatureManager.FeatureCut4(*args)
        v = part.GetMassProperties[3] * 1e9
        print('  %-12s -> %r  V=%.3f  dV=%.3f' % (lb, bool(r), v, V_BODY - v))
        return V_BODY - v > 100
    except Exception as e:
        print('  %-12s ERR %s' % (lb, str(e)[:50]))
        return False


hit = None
for lb, a in layouts:
    if run(lb, a):
        hit = lb
        break
print('CUT_RESULT', hit or 'FAILED')

# ---------- 4. 验证 + 保存 ----------
mp = part.GetMassProperties
V = mp[3] * 1e9
print('FINAL_V %.4f mm3  target %.4f' % (V, V_TARGET if hit else V_BODY))
if hit:
    print('ERR %.5f%%  %s' % (abs(V - V_TARGET) / V_TARGET * 100,
                              'PASS' if abs(V - V_TARGET) / V_TARGET < 0.002 else 'FAIL'))
print('FEATS_FINAL', feats())

if os.path.exists(OUT):
    os.remove(OUT)
try:
    part.SaveAs3(OUT, 0, 1)
    time.sleep(1)
    print('SAVED', os.path.exists(OUT), os.path.getsize(OUT) if os.path.exists(OUT) else 0)
except Exception as e:
    print('SAVE ERR', type(e).__name__, str(e)[:60])
print('TITLE', part.GetTitle)
