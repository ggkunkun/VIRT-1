# -*- coding: utf-8 -*-
"""FeatureCut4 27 参布局探测：确定 4 个新增参数的位置"""
import win32com.client as w
import pythoncom

pythoncom.CoInitialize()
try:
    sw = w.GetActiveObject('SldWorks.Application')
except Exception:
    sw = w.Dispatch('SldWorks.Application')
part = sw.ActiveDoc
V0 = part.GetMassProperties[3] * 1e9
print('V0 %.3f  expect drop 1385.44' % V0)

skf = part.FeatureByName('草图2')
fm = part.FeatureManager

base = [True, False, False, 1, 0, 0.0, 0.0,
        False, False, False, False, 0.0, 0.0,
        False, False, False, False,
        False, True, True,
        False, True, True]
START4 = [0, 0.0, False, 0.0]


def run(label, args):
    try:
        part.ClearSelection2(True)
        skf.Select2(False, 0)
        r = fm.FeatureCut4(*args)
        v = part.GetMassProperties[3] * 1e9
        dv = V0 - v
        print('%-34s n=%d -> %r  dV=%.2f  %s' % (label, len(args), bool(r), dv, 'HIT' if dv > 100 else ''))
        return dv > 100
    except Exception as e:
        print('%-34s ERR %s' % (label, str(e)[:50]))
        return False


cands = [
    ('A insert@17', base[:17] + START4 + base[17:]),
    ('B append end', base + START4),
    ('C insert@3',  base[:3] + START4 + base[3:]),
    ('D insert@18', base[:18] + START4 + base[18:]),
    ('E insert@4',  base[:4] + START4 + base[4:]),
    ('F insert@6',  base[:6] + START4 + base[6:]),
]
for lb, a in cands:
    if run(lb, a):
        print('>>> WINNER', lb)
        break
