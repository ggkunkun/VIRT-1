# -*- coding: utf-8 -*-
"""
机轮模 逆向参数化重建
母线剖面（x 轴向, r 径向, 单位 mm）逆向自 STEP:
  外轮廓: (0,11.5)-(1,12.5)-(8,12.5)-(8,25.5)-(9,26.5)-(19,26.5)-(20,25.5)-(20,12.5)-(25,12.5)-(40,10)
  内孔:   (40,4.5)-(38.5,4.5)-(38.5,3)-(1.5,3)-(1.5,4.5)-(0,4.5)
然后: 3× Ø7 @ PCD38 贯穿孔
"""
import math
import os
import time

import win32com.client as w
import pythoncom

OUT = r'D:\Virtu模型\jilunmo_rebuild.SLDPRT'

# ---------- 母线剖面 ----------
OUTER = [(0, 11.5), (1, 12.5), (8, 12.5), (8, 25.5), (9, 26.5),
         (19, 26.5), (20, 25.5), (20, 12.5), (25, 12.5), (40, 10.0)]
INNER = [(40, 4.5), (38.5, 4.5), (38.5, 3.0), (1.5, 3.0), (1.5, 4.5), (0, 4.5)]
PROFILE = OUTER + INNER

# ---------- 解析体积 ----------
def rev_vol(pts):
    """闭合多边形绕 X 轴旋转体积 = 2π ∫ r dA ... 用 Pappus: V = 2π * A * r_bar"""
    a = 0.0
    cx = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        cross = x1 * y2 - x2 * y1
        a += cross
        cx += (x1 + x2) * cross
    a *= 0.5
    cx = cx / (6 * a)
    return 2 * math.pi * abs(a) * abs(cx)      # mm³


V_BODY = rev_vol(PROFILE)
V_HOLES = 3 * math.pi * 3.5 ** 2 * (20 - 8)
V_NET = V_BODY - V_HOLES
print('PROFILE pts      %d' % len(PROFILE))
print('V_BODY_theory  %.4f mm3  (%.4f cm3)' % (V_BODY, V_BODY / 1000))
print('V_HOLES_theory %.4f mm3' % V_HOLES)
print('V_NET_theory   %.4f mm3  (%.4f cm3)' % (V_NET, V_NET / 1000))

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
if not doc:
    doc = sw.ActiveDoc
part = doc
print('DOC', part.GetTitle)

# ---------- 草图: 闭合母线 + 中心线 ----------
plane = part.FeatureByName('前视基准面')
plane.Select2(False, 0)
part.InsertSketch2(True)
sm = part.SketchManager
sm.AddToDB = True

for i in range(len(PROFILE)):
    x1, y1 = PROFILE[i]
    x2, y2 = PROFILE[(i + 1) % len(PROFILE)]
    sm.CreateLine(x1 / 1000, y1 / 1000, 0, x2 / 1000, y2 / 1000, 0)

sm.CreateCenterLine(0, 0, 0, 0.040, 0, 0)     # 旋转轴 = X 轴
sk = sm.ActiveSketch
print('LINES', sk.GetLineCount, '(expect 16 + centerline)')
part.InsertSketch2(False)

# ---------- 旋转 ----------
skf = part.FeatureByName('草图1')
part.ClearSelection2(True)
skf.Select2(False, 0)

REV_ARGS = [True, True, False, False, False, False,
            0, 0, 2 * math.pi, 0,
            False, False, 0.0, 0.0,
            0, 0.0, 0.0,
            True, True, True]
ok = False
for n in (20, 22, 23, 24):
    try:
        r = part.FeatureManager.FeatureRevolve2(*REV_ARGS[:n])
        print('FeatureRevolve2(%d) -> %r' % (n, bool(r)))
        if r:
            ok = True
            break
    except Exception as e:
        print('FeatureRevolve2(%d) ERR %s %s' % (n, type(e).__name__, str(e)[:70]))

f = part.FirstFeature
feats = []
while f:
    if f.GetTypeName2 in ('ProfileFeature', 'Extrusion', 'Revolve'):
        feats.append((f.Name, f.GetTypeName2))
    f = f.GetNextFeature
print('FEATS_AFTER_REVOLVE', feats)

if ok:
    mp = part.GetMassProperties
    print('V_REVOLVE %.4f mm3  (theory %.4f)' % (mp[3] * 1e9, V_BODY))
    d = abs(mp[3] * 1e9 - V_BODY) / V_BODY
    print('ERR %.4f%%  %s' % (d * 100, 'PASS' if d < 0.005 else 'FAIL'))
