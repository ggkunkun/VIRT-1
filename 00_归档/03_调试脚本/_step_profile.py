# -*- coding: utf-8 -*-
"""STEP 逆向 v2：提取所有圆弧的圆心/半径/轴向，反推回转母线与孔系"""
import collections
import re
import math

F = r'C:\Users\Administrator\Desktop\微型机轮模总成(P0) 6R15-6R12-6R10.step'
txt = open(F, 'rb').read().decode('latin-1')

ents = {}
cur_id, buf = None, []
for line in txt.splitlines():
    m = re.match(r'^#(\d+)\s*=\s*(.*)$', line)
    if m:
        if cur_id is not None:
            ents[cur_id] = ' '.join(buf)
        cur_id, buf = int(m.group(1)), [m.group(2)]
    elif cur_id is not None:
        buf.append(line)
if cur_id is not None:
    ents[cur_id] = ' '.join(buf)

refs = {k: [int(x) for x in re.findall(r'#(\d+)', v)] for k, v in ents.items()}


def bfs(start):
    seen, stack = {start}, [start]
    while stack:
        n = stack.pop()
        for r in refs.get(n, ()):
            if r not in seen and r in ents:
                seen.add(r); stack.append(r)
    return seen


def point(pid):
    v = ents[pid]
    m = re.search(r"\(\s*'[^']*'\s*,\s*\(\s*([-0-9.E+]+)\s*,\s*([-0-9.E+]+)\s*,\s*([-0-9.E+]+)\s*\)", v)
    return tuple(float(x) for x in m.groups()) if m else (0, 0, 0)


def direction(did):
    v = ents[did]
    m = re.search(r"\(\s*'[^']*'\s*,\s*\(\s*([-0-9.E+]+)\s*,\s*([-0-9.E+]+)\s*,\s*([-0-9.E+]+)\s*\)", v)
    return tuple(float(x) for x in m.groups()) if m else (0, 0, 1)


breps = sorted(k for k, v in ents.items() if v.startswith('MANIFOLD_SOLID_BREP'))
groups = {i + 1: bfs(b) for i, b in enumerate(breps)}

for gi in (1, 5, 6):
    print('=' * 70)
    print('BODY#%d  CIRCLE 清单' % gi)
    rows = []
    for k in groups[gi]:
        v = ents[k]
        if not v.startswith('CIRCLE'):
            continue
        m = re.search(r"CIRCLE\s*\(\s*'[^']*'\s*,\s*#(\d+)\s*,\s*([-0-9.E+]+)\s*\)", v)
        if not m:
            continue
        pl = int(m.group(1)); r = float(m.group(2))
        pr = refs.get(pl, [])
        if not pr:
            continue
        loc = point(pr[0])
        ax = direction(pr[1]) if len(pr) > 1 else (0, 0, 1)
        rows.append((r, loc, ax))
    # 分类：轴线平行 X 且圆心在 X 轴上( y,z 接近 0 ) -> 母线圆弧
    mer, holes = [], []
    for r, loc, ax in rows:
        if abs(abs(ax[0]) - 1) < 1e-3 and abs(loc[1]) < 1e-3 and abs(loc[2]) < 1e-3:
            mer.append((round(loc[0], 4), round(r, 4)))
        elif abs(abs(ax[0]) - 1) < 1e-3:
            holes.append((round(loc[0], 3), round(loc[1], 4), round(loc[2], 4), round(r, 4)))
    print('  -- 母线圆弧 (x, R) --')
    for x, r in sorted(set(mer)):
        print('     x=%9.4f   R=%7.4f   Ø=%7.4f' % (x, r, r * 2))
    print('  -- 偏心圆弧 (孔) --')
    hc = collections.Counter((round(math.hypot(h[1], h[2]), 4), h[3]) for h in holes)
    for (pcd_r, r), n in sorted(hc.items()):
        print('     分布半径 R=%7.4f (PCD Ø%7.4f)  孔径 R=%6.4f (Ø%6.4f)  x%d' % (pcd_r, pcd_r * 2, r, r * 2, n))
    if holes:
        angs = sorted({round(math.degrees(math.atan2(h[2], h[1])), 2) for h in holes})
        print('     角度集合:', angs)
