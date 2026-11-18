# -*- coding: utf-8 -*-
"""Step2: 清理污染草图 -> 新建零件 -> 一个草图内画 8 个圆（外圆/内孔/6螺栓孔）"""
import math
import win32com.client as w
import pythoncom

pythoncom.CoInitialize()
sw = w.GetActiveObject('SldWorks.Application')

# ---------- 1. 清理：删除刚才误插入到箱体零件里的 草图8 ----------
part = sw.ActiveDoc
print('BEFORE_DOC', part.GetTitle)
if part.GetTitle == '零件1':
    f = part.FirstFeature
    last = None
    while f:
        last = f
        f = f.GetNextFeature
    if last and last.GetTypeName2 == 'ProfileFeature':
        print('DEL_SKETCH', last.Name)
        try:
            last.Select2(False, 0)
            part.EditDelete()
            print('DELETED ok')
        except Exception as e:
            print('DEL_FAIL', type(e).__name__, e)

# ---------- 2. 新建零件 ----------
newdoc = None
try:
    newdoc = sw.NewPart()
    print('NEWPART', bool(newdoc))
except Exception as e:
    print('NEWPART_ERR', type(e).__name__, e)
if not newdoc:
    newdoc = sw.ActiveDoc
part = newdoc
print('DOC', part.GetTitle, '| features_start')

# ---------- 3. 画草图：8 个圆 ----------
R_OUT, R_BORE, R_HOLE, R_PCD, N = 0.080, 0.030, 0.007, 0.060, 6

plane = part.FeatureByName('前视基准面')
plane.Select2(False, 0)
part.InsertSketch2(True)
sm = part.SketchManager
sm.AddToDB = True

sm.CreateCircle(0, 0, 0, R_OUT, 0, 0)      # 外轮廓 Ø160
sm.CreateCircle(0, 0, 0, R_BORE, 0, 0)     # 中心孔 Ø60
for i in range(N):
    a = math.radians(360.0 * i / N)
    cx, cy = R_PCD * math.cos(a), R_PCD * math.sin(a)
    sm.CreateCircle(cx, cy, 0, cx + R_HOLE, cy, 0)   # 螺栓孔 Ø14

sk = sm.ActiveSketch
print('ARCS', sk.GetArcCount(), '| SEGS', len(sk.GetSketchSegments()), '| CONTOURS', len(sk.GetSketchContours()))
part.InsertSketch2(False)
print('EXIT_SKETCH ok')

f = part.FirstFeature
while f:
    if f.GetTypeName2 in ('ProfileFeature', 'Extrusion'):
        print('  FEAT', f.Name, '|', f.GetTypeName2)
    f = f.GetNextFeature
