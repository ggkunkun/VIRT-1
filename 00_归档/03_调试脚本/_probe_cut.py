# -*- coding: utf-8 -*-
"""切除方法/参数值探测：给定深度 vs 完全贯穿，以及 FeatureCut 各版本"""
import math
import win32com.client as w
import pythoncom

pythoncom.CoInitialize()
try:
    sw = w.GetActiveObject('SldWorks.Application')
except Exception:
    sw = w.Dispatch('SldWorks.Application')
part = sw.ActiveDoc
print('DOC', part.GetTitle)

V0 = part.GetMassProperties[3] * 1e9
print('V0 %.4f mm3' % V0)

skf = part.FeatureByName('草图2')
fm = part.FeatureManager


def trycall(label, fn, args):
    try:
        part.ClearSelection2(True)
        skf.Select2(False, 0)
        r = fn(*args)
        v = part.GetMassProperties[3] * 1e9
        print('%-52s -> %r  V=%.3f' % (label, bool(r), v))
        return bool(r) and abs(v - V0) > 1
    except Exception as e:
        print('%-52s -> ERR %s' % (label, str(e)[:60]))
        return False


base = [True, False, False, None, 0, None, 0.0,
        False, False, False, False, 0.0, 0.0,
        False, False, False, False,
        False, True, True,
        False, True, True]

# A. 完全贯穿 (T1=1)
a = list(base); a[3] = 1; a[5] = 0.0
trycall('FeatureCut4 T1=throughAll(1)', fm.FeatureCut4, a)

# B. 给定深度 30mm (T1=0)
b = list(base); b[3] = 0; b[5] = 0.03
if trycall('FeatureCut4 T1=blind(0) D=30mm', fm.FeatureCut4, b):
    raise SystemExit(0)

# C. 给定深度 40mm, Flip=True
c = list(base); c[1] = True; c[3] = 0; c[5] = 0.04
if trycall('FeatureCut4 T1=blind D=40 Flip=T', fm.FeatureCut4, c):
    raise SystemExit(0)

# D. 其他方法名
for nm in ('FeatureCut3', 'FeatureCut2', 'FeatureCut'):
    fn = getattr(fm, nm, None)
    if fn is None:
        print('%-52s -> NOATTR' % nm)
        continue
    for tag, arr in (('T1=1', a), ('T1=0/30', b)):
        if trycall('%s %s' % (nm, tag), fn, arr):
            raise SystemExit(0)
    for n in (20, 21, 22):
        if trycall('%s %d-args T1=0/30' % (nm, n), fn, b[:n]):
            raise SystemExit(0)
print('ALL_CUT_METHODS_FAILED')
