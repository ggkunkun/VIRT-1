# -*- coding: utf-8 -*-
"""Step3: 尝试 COM 拉伸（FeatureExtrusion3 / FeatureExtrusion2 / FeatureExtrusion）"""
import win32com.client as w
import pythoncom

pythoncom.CoInitialize()
sw = w.GetActiveObject('SldWorks.Application')
part = sw.ActiveDoc
print('DOC', part.GetTitle)
fm = part.FeatureManager

sk = part.FeatureByName('草图1')
print('SKETCH', sk.Name)

D = 0.014

def attempt(label, fn, *args):
    try:
        part.ClearSelection2(True)
        sk.Select2(False, 0)
        r = fn(*args)
        print('%-46s -> %r' % (label, r))
        return r
    except Exception as e:
        print('%-46s -> ERR %s %s' % (label, type(e).__name__, e))
        return None

# FeatureExtrusion3: 23 params
v3 = [True, False, False, 0, 0, D, 0.0,
      False, False, False, False, 0.0, 0.0,
      False, False, True, False,
      True, True, True,
      False, True, True]
attempt('FeatureExtrusion3(23) Sd=T Dir=F T1=0 D=14', fm.FeatureExtrusion3, *v3)

v3b = [True, False, False, 0, 0, D, 0.0,
       False, False, False, False, 0.0, 0.0,
       False, False, False, False,
       True, True, True,
       False, True, True]
attempt('FeatureExtrusion3(23) Trans1=F', fm.FeatureExtrusion3, *v3b)

# FeatureExtrusion2: 20 params
v2 = [True, False, False, 0, 0, D, 0.0,
      False, False, False, False, 0.0, 0.0,
      False, False, True, False,
      True, True, True]
attempt('FeatureExtrusion2(20) Sd=T D=14', fm.FeatureExtrusion2, *v2)

# 老接口 FeatureExtrusion
attempt('FeatureExtrusion(20)', fm.FeatureExtrusion, *v2)

# 结果核查
print('---VERIFY---')
f = part.FirstFeature
feats = []
while f:
    if f.GetTypeName2 in ('ProfileFeature', 'Extrusion'):
        feats.append((f.Name, f.GetTypeName2))
    f = f.GetNextFeature
print('FEATS', feats)
mp = part.GetMassProperties
if mp and len(mp) >= 6:
    print('VOLUME_m3 %.10e  (%.4f cm3)' % (mp[3], mp[3] * 1e6))
    print('AREA_m2   %.10e  (%.4f cm2)' % (mp[4], mp[4] * 1e4))
    print('MASS_kg   %.10e' % mp[5])
else:
    print('MP', mp)
