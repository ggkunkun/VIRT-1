# -*- coding: utf-8 -*-
"""Parse VERICUT ASCII 'VERICUT-model Version-3.0' PLY (triangle soup).

Format:
  VERICUT-model
  Version-3.0
  <n>
  <a> <b> <c>
  then repeated: "3" + 3 vertex lines + 3 normal lines
Returns vertices, faces.
"""
import sys
import numpy as np


def parse(path):
    lines = [ln.strip() for ln in open(path, encoding="utf-8", errors="replace")]
    i = 0
    assert "VERICUT" in lines[0], lines[0]
    i = 2  # skip version section marker
    # Actually header: [0]=VERICUT-model [1]=Version-3.0 [2]=n [3]=a b c
    i = 3
    verts = []
    while i < len(lines):
        if lines[i] == "3":
            # next 3 lines are vertices
            for k in range(1, 4):
                parts = lines[i + k].split()
                verts.append([float(parts[0]), float(parts[1]), float(parts[2])])
            i += 7  # 3 marker + 3 verts + 3 normals
        else:
            i += 1
    return np.array(verts)


if __name__ == "__main__":
    for p in sys.argv[1:]:
        v = parse(p)
        r = np.sqrt(v[:, 0] ** 2 + v[:, 1] ** 2)
        th = np.arctan2(v[:, 1], v[:, 0])
        z = v[:, 2]
        print(f"=== {p}")
        print(f"  verts={len(v)} bbox={np.round(v.max(0)-v.min(0),3).tolist()} "
              f"z=[{z.min():.2f},{z.max():.2f}]")
        # mid-height angular radial profile -> blades/passages?
        zc = (z.max() + z.min()) / 2
        band = np.abs(z - zc) < 0.06 * (z.max() - z.min())
        rb, tb = r[band], th[band]
        if len(rb):
            edges = np.linspace(-np.pi, np.pi, 25)
            prof = []
            for k in range(24):
                m = (tb >= edges[k]) & (tb < edges[k + 1])
                prof.append(rb[m].max() if m.any() else np.nan)
            print(f"  mid-band(r): min={rb.min():.2f} max={rb.max():.2f} std={rb.std():.2f}")
            print("  theta->rmax:", np.round(prof, 1).tolist())
