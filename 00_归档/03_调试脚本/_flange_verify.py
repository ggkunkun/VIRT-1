# -*- coding: utf-8 -*-
"""几何反读：从实体面反推圆柱半径，验证 Ø160/Ø60/6×Ø14 与厚度 14mm"""
import collections
import win32com.client as w
import pythoncom

pythoncom.CoInitialize()
try:
    sw = w.GetActiveObject('SldWorks.Application')
except Exception:
    sw = w.Dispatch('SldWorks.Application')
part = sw.ActiveDoc
print('DOC', part.GetTitle)


def g(obj, name, *args):
    if not hasattr(obj, name):
        return ('NOATTR', None)
    v = getattr(obj, name)
    if callable(v):
        try:
            return ('M', v(*args))
        except Exception as e:
            return ('ERR:%s' % type(e).__name__, None)
    return ('P', v)


bodies = part.GetBodies2(0, True)
print('BODIES', len(bodies))
body = bodies[0]

kk, box = g(body, 'GetBodyBox')
print('BBOX %s %r' % (kk, box))
if box and len(box) >= 6:
    print('  X_extent %.4f mm  Y_extent %.4f mm  Z_extent(thickness) %.4f mm'
          % ((box[3] - box[0]) * 1000, (box[4] - box[1]) * 1000, (box[5] - box[2]) * 1000))

kk, faces = g(body, 'GetFaces')
faces = faces or ()
print('FACES', len(faces))

radii = []
planar = 0
for f in faces:
    kk, surf = g(f, 'GetSurface')
    if not surf:
        continue
    kk3, cp = g(surf, 'CylinderParams')
    if cp and isinstance(cp, tuple) and len(cp) >= 7:
        radii.append(round(cp[6] * 1000, 4))   # radius in mm
    else:
        planar += 1

print('PLANAR_FACES', planar)
print('CYL_RADII_mm', sorted(radii))
cnt = collections.Counter(radii)
print('RADIUS_COUNTS', dict(cnt))
print('  -> Ø values:', sorted({round(r * 2, 4) for r in radii}))
print('RESULT', 'PASS' if (planar == 2 and dict(cnt) == {80.0: 1, 30.0: 1, 7.0: 6}) else 'CHECK')
