# -*- coding: utf-8 -*-
"""Measure the official force-impeller sample layout (correct case)."""
import json
from pathlib import Path

import numpy as np

SUPPORT = Path(r"E:\samples\Support_files")
FILES = ["force-impeller_fixture1.ply", "force-impeller_fixture2.ply",
         "force-impeller_fixture3.ply", "force-impeller_stock.ply",
         "force-impeller_design.ply"]


def bbox(p):
    vals = []
    for ln in open(p, encoding="ascii", errors="ignore"):
        s = ln.split()
        if len(s) == 3:
            try:
                vals.append([float(x) for x in s])
            except ValueError:
                pass
    a = np.array(vals)
    return a.min(0), a.max(0), len(a)


out = {}
for f in FILES:
    p = SUPPORT / f
    if not p.exists():
        out[f] = None
        continue
    lo, hi, n = bbox(p)
    out[f] = {"min": np.round(lo, 2).tolist(), "max": np.round(hi, 2).tolist(),
              "verts": int(n), "size": np.round(hi - lo, 2).tolist()}
print(json.dumps(out, ensure_ascii=False, indent=2))
