# -*- coding: utf-8 -*-
"""
法兰盘全自动建模（纯 COM，零鼠标点击）
参数: D=Ø160 中心孔=Ø60 厚=14mm 螺栓孔=6×Ø14 @ PCD Ø120
策略: 一个草图内画 8 个圆(外圆+中心孔+6螺栓孔) -> 一次 FeatureExtrusion3 成型
"""
import math
import os
import time

import win32com.client as w
import pythoncom

OUT = r'D:\Virtu模型\flange_D160_t14_6xM12.SLDPRT'

# ---- 参数（mm 输入，m 计算）----
D_OUT, D_BORE, T = 160.0, 60.0, 14.0
N_HOLE, D_HOLE, PCD = 6, 14.0, 120.0

R_OUT, R_BORE, R_HOLE, R_PCD = D_OUT / 2000, D_BORE / 2000, D_HOLE / 2000, PCD / 2000
T_M = T / 1000

# ---- 理论值 ----
A_ANNULUS = math.pi / 4 * ((D_OUT / 1000) ** 2 - (D_BORE / 1000) ** 2)
V_MAIN = A_ANNULUS * T_M
V_HOLES = N_HOLE * math.pi / 4 * (D_HOLE / 1000) ** 2 * T_M
V_THEORY = V_MAIN - V_HOLES
A_THEORY = (math.pi * (D_OUT / 1000) * T_M
            + math.pi * (D_BORE / 1000) * T_M
            + N_HOLE * math.pi * (D_HOLE / 1000) * T_M
            + 2 * A_ANNULUS
            - 2 * N_HOLE * math.pi / 4 * (D_HOLE / 1000) ** 2)
print('THEORY_V  %.10e m3 (%.4f cm3)' % (V_THEORY, V_THEORY * 1e6))
print('THEORY_A  %.10e m2 (%.4f cm2)' % (A_THEORY, A_THEORY * 1e4))

pythoncom.CoInitialize()
sw = None
try:
    sw = w.GetActiveObject('SldWorks.Application')
    print('COM_ATTACH GetActiveObject(ROT)')
except Exception as e:
    print('ROT empty (%s) -> Dispatch' % type(e).__name__)
    sw = w.Dispatch('SldWorks.Application')
    print('COM_ATTACH Dispatch')
sw.Visible = True

# ---- 1. 新建零件 ----
doc = None
try:
    doc = sw.NewPart()
except Exception as e:
    print('NewPart marshal err (ignorable):', type(e).__name__)
if not doc:
    doc = sw.ActiveDoc
part = doc
print('DOC', part.GetTitle, '| type', part.GetType)

# ---- 2. 草图: 8 个圆 ----
plane = part.FeatureByName('前视基准面')
plane.Select2(False, 0)
part.InsertSketch2(True)
sm = part.SketchManager
sm.AddToDB = True
sm.CreateCircle(0, 0, 0, R_OUT, 0, 0)
sm.CreateCircle(0, 0, 0, R_BORE, 0, 0)
for i in range(N_HOLE):
    a = math.radians(360.0 * i / N_HOLE)
    cx, cy = R_PCD * math.cos(a), R_PCD * math.sin(a)
    sm.CreateCircle(cx, cy, 0, cx + R_HOLE, cy, 0)
sk = sm.ActiveSketch
print('ARCS', sk.GetArcCount, '(expect 8)')
part.InsertSketch2(False)

# ---- 3. 一次拉伸 ----
skfeat = part.FeatureByName('草图1')
skfeat.Select2(False, 0)
r = part.FeatureManager.FeatureExtrusion3(
    True, False, False, 0, 0, T_M, 0.0,
    False, False, False, False, 0.0, 0.0,
    False, False, True, False,
    True, True, True,
    False, True, True)
print('EXTRUDE3', 'OK' if r else r)

# ---- 4. 验证 ----
mp = part.GetMassProperties
V, A, M = mp[3], mp[4], mp[5]
print('ACTUAL_V  %.10e m3 (%.4f cm3)' % (V, V * 1e6))
print('ACTUAL_A  %.10e m2 (%.4f cm2)' % (A, A * 1e4))
print('ACTUAL_M  %.10e kg' % M)
print('COM       (%.6f, %.6f, %.6f) m' % (mp[0], mp[1], mp[2]))
dv = abs(V - V_THEORY) / V_THEORY
da = abs(A - A_THEORY) / A_THEORY
print('ERR_V %.3e   ERR_A %.3e' % (dv, da))
print('ASSERT_VOLUME', 'PASS' if dv <= 1e-6 else 'FAIL')
print('ASSERT_AREA  ', 'PASS' if da <= 1e-6 else 'FAIL')
print('ASSERT_DV_POS', 'PASS' if V > 0 else 'FAIL')

# ---- 5. 特征树 ----
fs = []
f = part.FirstFeature
while f:
    if f.GetTypeName2 in ('ProfileFeature', 'Extrusion'):
        fs.append((f.Name, f.GetTypeName2))
    f = f.GetNextFeature
print('FEATS', fs, '| extrusion_count=%d' % sum(1 for x in fs if x[1] == 'Extrusion'))

# ---- 6. 保存 ----
if os.path.exists(OUT):
    os.remove(OUT)
saved = False
for label, fn in [
    ('Extension.SaveAs', lambda: part.Extension.SaveAs(OUT, 0, 1, None, None, None)),
    ('SaveAs4', lambda: part.SaveAs4(OUT, 0, 1, None, None)),
    ('SaveAs3', lambda: part.SaveAs3(OUT, 0, 1)),
    ('SaveAs', lambda: part.SaveAs(OUT)),
]:
    try:
        fn()
        time.sleep(1)
        if os.path.exists(OUT):
            print('SAVED via', label, os.path.getsize(OUT), 'bytes')
            saved = True
            break
        print(label, 'returned but no file')
    except Exception as e:
        print(label, 'ERR', type(e).__name__, str(e)[:80])
print('SAVE_OK', saved)
print('FINAL_TITLE', part.GetTitle)
