# -*- coding: utf-8 -*-
"""穷举 FeatureCut4 参数上界 + 试探其他切除入口"""
import win32com.client as w
import pythoncom

pythoncom.CoInitialize()
try:
    sw = w.GetActiveObject('SldWorks.Application')
except Exception:
    sw = w.Dispatch('SldWorks.Application')
part = sw.ActiveDoc
V0 = part.GetMassProperties[3] * 1e9
print('DOC', part.GetTitle, 'V0 %.3f' % V0)

skf = part.FeatureByName('草图2')
fm = part.FeatureManager
print('HAS FeatureCut4', hasattr(fm, 'FeatureCut4'))

# 基础 23 参 + 后面补 False
base = [True, False, False, 1, 0, 0.0, 0.0,
        False, False, False, False, 0.0, 0.0,
        False, False, False, False,
        False, True, True,
        False, True, True]

for extra in range(0, 9):
    args = base + [False] * extra
    try:
        part.ClearSelection2(True)
        skf.Select2(False, 0)
        r = fm.FeatureCut4(*args)
        v = part.GetMassProperties[3] * 1e9
        print('FeatureCut4(%2d) -> %r  V=%.3f  %s' % (len(args), bool(r), v, 'CHANGED' if abs(v - V0) > 1 else ''))
        if r and abs(v - V0) > 1:
            print('*** SUCCESS with %d args ***' % len(args))
            break
    except Exception as e:
        code = e.args[0] if e.args else 0
        tag = {0x8002000E: 'INVALID_COUNT', 0x8002000F: 'PARAMNOTFOUND'}.get(code & 0xFFFFFFFF, str(code))
        print('FeatureCut4(%2d) ERR %s' % (len(args), tag))

print('---- 其他入口 ----')
for nm in ('FeatureCut5', 'FeatureCut6', 'InsertCutBlend2', 'InsertCutBlend3', 'InsertCutBlend'):
    print('  %-20s exists=%s' % (nm, hasattr(fm, nm)))
