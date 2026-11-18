# -*- coding: utf-8 -*-
"""Step2b: 兼容属性/方法两种访问方式，验证草图几何数并退出草图"""
import win32com.client as w
import pythoncom

pythoncom.CoInitialize()
sw = w.GetActiveObject('SldWorks.Application')


def get(obj, name):
    """属性 or 方法 都能取"""
    if not hasattr(obj, name):
        return ('NOATTR', None)
    v = getattr(obj, name)
    if callable(v):
        try:
            return ('METHOD', v())
        except Exception as e:
            return ('CALLFAIL:%s' % type(e).__name__, None)
    return ('PROP', v)


def cnt(v):
    try:
        return len(v)
    except Exception:
        return v


part = sw.ActiveDoc
print('DOC', part.GetTitle)

sm = part.SketchManager
sk = sm.ActiveSketch
print('ACTIVE_SKETCH', sk)
if sk:
    for m in ['GetArcCount', 'GetLineCount', 'GetSketchSegments', 'GetSketchContours', 'GetSketchPoints2']:
        kind, val = get(sk, m)
        print('  %-20s %-10s -> %s' % (m, kind, cnt(val) if kind != 'NOATTR' else '-'))
    part.InsertSketch2(False)
    print('EXIT_SKETCH ok')

print('---FEATURES---')
f = part.FirstFeature
while f:
    if f.GetTypeName2 in ('ProfileFeature', 'Extrusion', 'RefPlane'):
        print('  ', f.Name, '|', f.GetTypeName2)
    f = f.GetNextFeature

print('---ALL DOCS---')
for d in sw.GetDocuments():
    print('  ', d.GetTitle)
