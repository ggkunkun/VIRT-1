# -*- coding: utf-8 -*-
"""Step1b: 确认圆是否真写入草图数据库 + 清理临时草图"""
import os
import win32com.client as w
import pythoncom

pythoncom.CoInitialize()
sw = w.GetActiveObject('SldWorks.Application')
part = sw.ActiveDoc
print('DOC', part.GetTitle)

sm = part.SketchManager
sk = sm.ActiveSketch
print('ACTIVE_SKETCH', sk)

# 多路尝试读取草图几何
for expr in ['sk.GetSketchSegments', 'sk.GetSketchPoints2', 'sk.GetSketchContours',
             'sk.GetSketchHatches', 'sk.GetArcCount']:
    try:
        fn = getattr(sk, expr.split('.', 1)[1])
        val = fn() if callable(fn) else fn
        print('OK  ', expr, '->', val if not hasattr(val, '__len__') or isinstance(val, (str, bytes)) else ('len=%d' % len(val)))
    except Exception as e:
        print('FAIL', expr, '->', type(e).__name__, e)

# 退出草图
part.InsertSketch2(False)
print('EXIT_SKETCH ok')

# 列出特征，找新加的草图
print('---FEATURES---')
f = part.FirstFeature
last = None
while f:
    print('  ', f.Name, '|', f.GetTypeName2)
    last = f
    f = f.GetNextFeature
print('LAST', last.Name if last else None)

# 检查模板是否真实存在
tmpl = sw.GetUserPreferenceStringValue(8)
print('TEMPLATE_EXISTS', os.path.exists(tmpl), tmpl)
