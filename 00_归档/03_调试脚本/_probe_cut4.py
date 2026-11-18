# -*- coding: utf-8 -*-
"""查草图2状态 + 换切除条件再试"""
import win32com.client as w
import pythoncom

pythoncom.CoInitialize()
try:
    sw = w.GetActiveObject('SldWorks.Application')
except Exception:
    sw = w.Dispatch('SldWorks.Application')
part = sw.ActiveDoc
V0 = part.GetMassProperties[3] * 1e9
print('V0 %.3f' % V0)

skf = part.FeatureByName('草图2')
print('SKETCH', skf.Name, '| type', skf.GetTypeName2)

# 进入草图查几何
part.ClearSelection2(True)
skf.Select2(False, 0)
try:
    ed = skf.GetDefinition()
    print('DEFN', ed)
except Exception as e:
    print('GetDefinition ERR', type(e).__name__)

try:
    part.EditSketch()
    sk = part.SketchManager.ActiveSketch
    print('ARCS_IN_SK2', sk.GetArcCount if sk else None)
    part.InsertSketch2(False)
except Exception as e:
    print('EditSketch ERR', type(e).__name__, str(e)[:60])

fm = part.FeatureManager
base = [True, False, False, 1, 0, 0.0, 0.0,
        False, False, False, False, 0.0, 0.0,
        False, False, False, False,
        False, True, True,
        False, True, True]
S4 = [0, 0.0, False, 0.0]


def run(label, args):
    try:
        part.ClearSelection2(True)
        skf.Select2(False, 0)
        r = fm.FeatureCut4(*args)
        v = part.GetMassProperties[3] * 1e9
        dv = V0 - v
        print('%-30s -> %r dV=%.2f %s' % (label, bool(r), dv, 'HIT' if dv > 100 else ''))
        return dv > 100
    except Exception as e:
        print('%-30s ERR %s' % (label, str(e)[:45]))
        return False


combos = []
for flip in (False, True):
    for t1, d1 in ((0, 0.04), (0, 0.30), (1, 0.0), (6, 0.0)):
        a = list(base)
        a[1] = flip
        a[3] = t1
        a[5] = d1
        combos.append(('A flip=%d T1=%d D=%.2f' % (flip, t1, d1), a[:17] + S4 + a[17:]))
for lb, a in combos:
    if run(lb, a):
        print('>>> WINNER', lb)
        break
else:
    print('ALL_FALSE -> switch to UI')
