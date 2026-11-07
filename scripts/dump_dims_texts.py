#!/usr/bin/env python
"""Print the drawing's dimensions and texts grouped spatially, to find the
per-part dimensions and the stated overall length (总长)."""
from __future__ import annotations

import json
import sys
from collections import defaultdict

p = sys.argv[1] if len(sys.argv) > 1 else r"D:\Virtu模型\runs\hkgb_3924_guard_20261102\drawing_analysis.json"
d = json.load(open(p, encoding="utf-8"))
m = [l for l in d["layouts"] if l["name"] == "Model"][0]

print("=== DIMENSIONS ===")
for i, dm in enumerate(m["dims"]):
    p1 = dm["defpoint"]
    p2 = dm["defpoint2"]
    p3 = dm["defpoint3"]
    print(f"{i:3d} meas={str(dm['measurement']):>12} ovr={dm['text']!r:>14} "
          f"p1={[round(v,2) for v in p1] if p1 else None} "
          f"p2={[round(v,2) for v in p2] if p2 else None} "
          f"p3={[round(v,2) for v in p3] if p3 else None} rot={dm['rotation']}")

print()
print("=== TEXTS (sorted by x, then y) ===")
ts = sorted(m["texts"], key=lambda t: (round(t["pos"][0], 1), -t["pos"][1]))
for t in ts:
    txt = t["text"].replace("\n", "\\n")
    if not txt:
        continue
    print(f"x={round(t['pos'][0],1):>10} y={round(t['pos'][1],1):>9} {t['kind']:<5} {t['layer'][:18]:<18} {txt!r}")
