# -*- coding: utf-8 -*-
"""Step1: 新建零件 + COM 直接写圆进草图数据库（不点鼠标），验证几何是否真入库"""
import win32com.client as w
import pythoncom

pythoncom.CoInitialize()
sw = w.GetActiveObject('SldWorks.Application')
tmpl = sw.GetUserPreferenceStringValue(8)
print('TEMPLATE', tmpl)

doc = sw.NewDocument(tmpl, 0, 0, 0)
print('NEWDOC_OK', bool(doc))
if not doc:
    doc = sw.ActiveDoc
part = doc
print('TITLE', part.GetTitle, '| TYPE', part.GetType)

plane = part.FeatureByName('前视基准面')
print('PLANE', plane)
plane.Select2(False, 0)
part.InsertSketch2(True)
sm = part.SketchManager
sm.AddToDB = True
print('ADDTODB', sm.AddToDB)

r1 = sm.CreateCircle(0, 0, 0, 0.08, 0, 0)
print('C_outer', r1)
r2 = sm.CreateCircle(0, 0, 0, 0.03, 0, 0)
print('C_inner', r2)

sk = sm.ActiveSketch
print('SKETCH', sk)
if sk:
    names = [m for m in dir(sk) if not m.startswith('_')]
    print('SK_MEMBERS', names)
