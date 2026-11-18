# -*- coding: utf-8 -*-
"""Step4: 删除冗余拉伸特征，只保留第一个，并复核体积不变"""
import win32com.client as w
import pythoncom

pythoncom.CoInitialize()
sw = w.GetActiveObject('SldWorks.Application')
part = sw.ActiveDoc
print('DOC', part.GetTitle)


def list_feats():
    out = []
    f = part.FirstFeature
    while f:
        if f.GetTypeName2 in ('ProfileFeature', 'Extrusion'):
            out.append(f)
        f = f.GetNextFeature
    return out


print('BEFORE', [(f.Name, f.GetTypeName2) for f in list_feats()])
mp = part.GetMassProperties
print('BEFORE_V %.10e m3  (%.4f cm3)' % (mp[3], mp[3] * 1e6))

# 从尾部删，直到只剩一个 Extrusion
while True:
    xs = [f for f in list_feats() if f.GetTypeName2 == 'Extrusion']
    if len(xs) <= 1:
        break
    victim = xs[-1]
    print('DEL', victim.Name)
    part.ClearSelection2(True)
    victim.Select2(False, 0)
    try:
        part.EditDelete()
    except Exception as e:
        print('  ERR', type(e).__name__, e)
        break

print('AFTER', [(f.Name, f.GetTypeName2) for f in list_feats()])
mp = part.GetMassProperties
print('AFTER_V  %.10e m3  (%.4f cm3)' % (mp[3], mp[3] * 1e6))
print('AFTER_A  %.10e m2  (%.4f cm2)' % (mp[4], mp[4] * 1e4))
print('AFTER_M  %.10e kg' % mp[5])
print('COM      (%.6f, %.6f, %.6f) m' % (mp[0], mp[1], mp[2]))
