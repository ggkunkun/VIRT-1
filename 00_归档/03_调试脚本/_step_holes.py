# -*- coding: utf-8 -*-
"""BODY#1 孔系明细：位置/角度/刃边 x 坐标"""
import collections
import math
import re

F = r'C:\Users\Administrator\Desktop\微型机轮模总成(P0) 6R15-6R12-6R10.step'
txt = open(F, 'rb').read().decode('latin-1')

ents, cur, buf = {}, None, []
for line in txt.splitlines():
    m = re.match(r'^#(\d+)\s*=\s*(.*)$', line)
    if m:
        if cur is not None:
            ents[cur] = ' '.join(buf)
        cur, buf = int(m.group(1)), [m.group(2)]
    elif cur is not None:
        buf.append(line)
if cur is not None:
    ents[cur] = ' '.join(buf)
refs = {k: [int(x) for x in re.findall(r'#(\d+)', v)] for k, v in ents.items()}


def bfs(s):
    seen, st = {s}, [s]
    while st:
        n = st.pop()
        for r in refs.get(n, ()):
            if r not in seen and r in ents:
                seen.add(r); st.append(r)
    return seen


def pt(pid):
    m = re.search(r"\(\s*'[^']*'\s*,\s*\(\s*([-0-9.E+]+)\s*,\s*([-0-9.E+]+)\s*,\s*([-0-9.E+]+)\s*\)", ents[pid])
    return tuple(float(x) for x in m.groups()) if m else (0, 0, 0)


breps = sorted(k for k, v in ents.items() if v.startswith('MANIFOLD_SOLID_BREP'))
g1 = bfs(breps[0])

print('=== BODY#1 所有圆周刃边明细 (偏心) ===')
rows = []
for k in g1:
    v = ents[k]
    if not v.startswith('CIRCLE'):
        continue
    m = re.search(r"CIRCLE\s*\(\s*'[^']*'\s*,\s*#(\d+)\s*,\s*([-0-9.E+]+)\s*\)", v)
    if not m:
        continue
    pl, r = int(m.group(1)), float(m.group(2))
    pr = refs.get(pl, [])
    if not pr:
        continue
    loc = pt(pr[0])
    if abs(loc[1]) < 1e-3 and abs(loc[2]) < 1e-3:
        continue          # 母线圆
    rows.append((loc[0], loc[1], loc[2], r))

for x, y, z, r in sorted(rows):
    print('  x=%8.3f  y=%8.3f  z=%8.3f  R=%6.4f(Ø%6.4f)  PCD_R=%7.4f  角度=%8.2f°'
          % (x, y, z, r, r * 2, math.hypot(y, z), math.degrees(math.atan2(z, y))))

print('\n=== 汇总 ===')
grp = collections.defaultdict(list)
for x, y, z, r in rows:
    grp[(round(r, 3), round(math.hypot(y, z), 3))].append((round(x, 3), round(math.degrees(math.atan2(z, y)), 2)))
for (r, pcd), v in sorted(grp.items()):
    print('  孔 Ø%.2f @ PCD Ø%.2f : 刃边数 %d' % (r * 2, pcd * 2, len(v)))
    for x, a in sorted(set(v)):
        print('      x=%.3f  角度=%.2f°' % (x, a))
