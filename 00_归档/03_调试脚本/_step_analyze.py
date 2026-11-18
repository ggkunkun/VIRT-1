# -*- coding: utf-8 -*-
"""STEP 逆向解析：实体类型统计 / 产品名 / 包围盒 / 圆柱面半径谱"""
import collections
import re
import sys

F = r'C:\Users\Administrator\Desktop\微型机轮模总成(P0) 6R15-6R12-6R10.step'
raw = open(F, 'rb').read()
txt = raw.decode('latin-1')

# ---- 实体类型统计 ----
types = collections.Counter(re.findall(r'#\d+\s*=\s*([A-Z_0-9]+)\s*\(', txt))
print('=== ENTITY TYPES (top 25) ===')
for k, v in types.most_common(25):
    print('  %-32s %5d' % (k, v))
print('  total entities:', sum(types.values()))

# ---- 产品 / 零件名 ----
print('\n=== PRODUCT / PART NAMES ===')
for m in re.findall(r"PRODUCT\s*\(\s*'([^']*)'\s*,\s*'([^']*)'", txt):
    nm = m[0]
    try:
        nm = nm.encode('latin-1').decode('gbk')
    except Exception:
        pass
    print('  ', nm, '|', m[1])

# ---- 包围盒 ----
pts = re.findall(r"CARTESIAN_POINT\s*\(\s*'[^']*'\s*,\s*\(\s*([-0-9.E+]+)\s*,\s*([-0-9.E+]+)\s*,\s*([-0-9.E+]+)\s*\)", txt)
xs = [float(a) for a, b, c in pts]
ys = [float(b) for a, b, c in pts]
zs = [float(c) for a, b, c in pts]
print('\n=== BOUNDING BOX (%d points) ===' % len(pts))
print('  X  %.4f .. %.4f   size %.4f' % (min(xs), max(xs), max(xs) - min(xs)))
print('  Y  %.4f .. %.4f   size %.4f' % (min(ys), max(ys), max(ys) - min(ys)))
print('  Z  %.4f .. %.4f   size %.4f' % (min(zs), max(zs), max(zs) - min(zs)))

# ---- 圆柱面半径谱 ----
print('\n=== CYLINDRICAL_SURFACE RADII ===')
cyl = {}
for m in re.finditer(r'#(\d+)\s*=\s*CYLINDRICAL_SURFACE\s*\(\s*\'[^\']*\'\s*,\s*#(\d+)\s*,\s*([-0-9.E+]+)\s*\)', txt):
    cyl['#' + m.group(1)] = float(m.group(3))
print('  count', len(cyl))
rc = collections.Counter(round(r, 4) for r in cyl.values())
for r, n in sorted(rc.items()):
    print('   R=%-10.4f  D=%-10.4f  x%d' % (r, r * 2, n))

# ---- 其他曲面 ----
print('\n=== OTHER SURFACE TYPES ===')
for t in ['B_SPLINE_SURFACE_WITH_KNOTS', 'TOROIDAL_SURFACE', 'CONICAL_SURFACE', 'SPHERICAL_SURFACE', 'PLANE']:
    print('  %-30s %d' % (t, types.get(t, 0)))
