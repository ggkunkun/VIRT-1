# -*- coding: utf-8 -*-
"""Generate a fixture sized for our Ø264 closed-impeller blank.

The sample's force-impeller fixtures (Ø80/129/170, up to z=170) are for a tiny
Ø48 part and visually dominate the table as a tall stepped shaft. Our blank:
  local z = -5..75.9, MatrixOrigin Z=200 -> world z = 195..275.9
So the fixture must be a shallow disc whose TOP is at world z=195 (right under
the blank bottom) and whose bottom seats on the B/C table (world z~170).

We build ONE fixture ply: a stepped disc from z=170 to z=195:
  - base Ø200, z=170..185 (bolts to table)
  - top  Ø270, z=185..195 (supports the Ø264 blank rim)
with a central clearance bore Ø30.

VERICUT PLY format: 'VERICUT-model / Version-3.0', triangle soup (3 + 3 verts + 3 normals).
"""
from __future__ import annotations

import numpy as np
from pathlib import Path

DST = Path(r"D:\Virtu模型\artifacts\aero_closed_impeller\impeller_fixture.ply")


def emit_plate(f, x0, x1, y0, y1, z0, z1):
    """Write a solid rectangular fixture plate as triangles (outer faces only)."""
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    quads = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    tris = []
    for a, b, c, d in quads:
        tris += [(v[a], v[b], v[c]), (v[a], v[c], v[d])]
    for t in tris:
        f.write("3\n")
        for p in t:
            f.write(f"{p[0]:.6f} {p[1]:.6f} {p[2]:.6f}\n")
        for _ in range(3):
            f.write("0.000000 0.000000 1.000000\n")


def main():
    with open(DST, "w", encoding="ascii", newline="\r\n") as f:
        f.write("VERICUT-model\nVersion-3.0\n1\n1 1 1\n")
        # 与官方 force-impeller 正确案例对齐：夹具顶面 world z = 70
        # （案例 fixture1 模型 z=-1..170，Attach=-100 → 顶面 70；毛坯底面同高）
        # 五轴 B/C 转台上的方形夹具底板：320 x 320，模型 z=145..170 → world 45..70
        emit_plate(f, -160.0, 160.0, -160.0, 160.0, 145.0, 170.0)
    print("wrote", DST, DST.stat().st_size, "bytes")

    # verify by parsing
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from parse_vc_ply import parse
    v = parse(str(DST))
    print("verts", len(v), "bbox", np.round(v.max(0) - v.min(0), 1).tolist(),
          "z=[%.1f,%.1f]" % (v[:, 2].min(), v[:, 2].max()))


if __name__ == "__main__":
    main()
