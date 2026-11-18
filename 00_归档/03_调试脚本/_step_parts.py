# -*- coding: utf-8 -*-
"""STEP 逆向测量：按 MANIFOLD_SOLID_BREP 拆件，逐件统计包围盒/面数/圆柱半径/环面/锥面"""
import collections
import re
import sys

F = r'C:\Users\Administrator\Desktop\微型机轮模总成(P0) 6R15-6R12-6R10.step'
txt = open(F, 'rb').read().decode('latin-1')

# ---------- 1. 行级解析实体 ----------
ents = {}
cur_id = None
buf = []
for line in txt.splitlines():
    m = re.match(r'^#(\d+)\s*=\s*(.*)$', line)
    if m:
        if cur_id is not None:
            ents[cur_id] = ' '.join(buf)
        cur_id = int(m.group(1))
        buf = [m.group(2)]
    elif cur_id is not None:
        buf.append(line)
if cur_id is not None:
    ents[cur_id] = ' '.join(buf)
print('PARSED_ENTITIES', len(ents))

# ---------- 2. 建引用图 ----------
refs = {}
for k, v in ents.items():
    refs[k] = [int(x) for x in re.findall(r'#(\d+)', v)]


def bfs(start):
    seen = {start}
    stack = [start]
    while stack:
        n = stack.pop()
        for r in refs.get(n, ()):
            if r not in seen and r in ents:
                seen.add(r)
                stack.append(r)
    return seen


def etype(k):
    v = ents[k]
    return v.split('(', 1)[0].strip()


breps = [k for k, v in ents.items() if v.startswith('MANIFOLD_SOLID_BREP')]
print('MANIFOLD_SOLID_BREP', len(breps))

print('\n' + '=' * 78)
for bi, b in enumerate(sorted(breps)):
    grp = bfs(b)
    pts, cyl, tor, cone, circ, planes, faces, bspl = [], [], [], [], [], 0, 0, 0
    for k in grp:
        v = ents[k]
        t = etype(k)
        if t == 'CARTESIAN_POINT':
            mm = re.search(r"\(\s*'[^']*'\s*,\s*\(\s*([-0-9.E+]+)\s*,\s*([-0-9.E+]+)\s*,\s*([-0-9.E+]+)\s*\)", v)
            if mm:
                pts.append((float(mm.group(1)), float(mm.group(2)), float(mm.group(3))))
        elif t == 'CYLINDRICAL_SURFACE':
            mm = re.search(r",\s*([-0-9.E+]+)\s*\)$", v.rstrip(' ;'))
            if mm:
                cyl.append(round(float(mm.group(1)), 4))
        elif t == 'TOROIDAL_SURFACE':
            mm = re.search(r",\s*([-0-9.E+]+)\s*,\s*([-0-9.E+]+)\s*\)\s*$", v.rstrip(' ;'))
            if mm:
                tor.append((round(float(mm.group(1)), 3), round(float(mm.group(2)), 3)))
        elif t == 'CONICAL_SURFACE':
            mm = re.search(r",\s*([-0-9.E+]+)\s*\)\s*$", v.rstrip(' ;'))
            if mm:
                cone.append(round(float(mm.group(1)), 4))
        elif t == 'CIRCLE':
            mm = re.search(r",\s*([-0-9.E+]+)\s*\)\s*$", v.rstrip(' ;'))
            if mm:
                circ.append(round(float(mm.group(1)), 4))
        elif t == 'PLANE':
            planes += 1
        elif t == 'ADVANCED_FACE':
            faces += 1
        elif t == 'B_SPLINE_CURVE_WITH_KNOTS':
            bspl += 1

    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]; zs = [p[2] for p in pts]
    print('BODY#%d  ent=%d  faces=%d  planes=%d  bspline=%d' % (bi + 1, len(grp), faces, planes, bspl))
    if xs:
        print('   BBOX  X %.3f..%.3f (%.3f)  Y %.3f..%.3f (%.3f)  Z %.3f..%.3f (%.3f)'
              % (min(xs), max(xs), max(xs) - min(xs), min(ys), max(ys), max(ys) - min(ys),
                 min(zs), max(zs), max(zs) - min(zs)))
    cc = collections.Counter(cyl)
    print('   CYL   ' + (', '.join('R%.2f(Ø%.2f)x%d' % (r, r * 2, n) for r, n in sorted(cc.items())) or '-'))
    tc = collections.Counter(tor)
    print('   TOR   ' + (', '.join('R%.2f/r%.2f x%d' % (a, bb, n) for (a, bb), n in sorted(tc.items())) or '-'))
    if cone:
        print('   CONE  half-angles ' + str(sorted(set(cone))))
    nc = collections.Counter(circ)
    print('   EDGE_CIRC ' + (', '.join('R%.2f(Ø%.2f)x%d' % (r, r * 2, n) for r, n in sorted(nc.items())) or '-'))
    print('-' * 78)
