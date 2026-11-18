# -*- coding: utf-8 -*-
"""VERICUT fixture: table pedestal + vice jaws for the closed-impeller blank.

Grounded on the official force-impeller sample (dmg_mori_nmv1500):
  - machine table surface (Attach origin)      world z = -100
  - sample fixture stack height                = 170 mm  -> part bottom at +70
  - stock must be raised above the trunnion, otherwise the table occludes it
    and the 5-axis tool cannot reach the OD

This fixture therefore is a continuous chain (no floating gap):
  pedestal  : x -160..160, y -160..160, z model 0..170   -> world -100..70
  fixed jaw : x -172..-132.05, y -170..170, z model 170..195 -> world 70..95
  moving jaw: x  132.05..172,  y -170..170, z model 170..195 -> world 70..95
  stock     : 264.06 x 264.06 x 82.85, ModelMatrix Z=175 -> world 70..152.85

Clearance checks:
  - stock bottom (70) == pedestal top (70); jaws grip the lower 25 mm
  - lowest cone pass world z = 70 + 29.88 = 99.88 > jaw top 95  (4.88 mm)
"""
from __future__ import annotations

import math
from pathlib import Path

DST = Path(r"D:\Virtu模型\artifacts\aero_closed_impeller\impeller_vise.ply")


def box_tris(x0, x1, y0, y1, z0, z1):
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    quads = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    tris = []
    for a, b, c, d in quads:
        tris += [(v[a], v[b], v[c]), (v[a], v[c], v[d])]
    return tris


def normal(t):
    p0, p1, p2 = t
    ux, uy, uz = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
    vx, vy, vz = p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    L = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    return nx / L, ny / L, nz / L


def main() -> None:
    parts = [
        box_tris(-160.0, 160.0, -160.0, 160.0, 0.0, 170.0),      # pedestal to table
        box_tris(-172.0, -132.05, -170.0, 170.0, 170.0, 195.0),  # fixed jaw
        box_tris(132.05, 172.0, -170.0, 170.0, 170.0, 195.0),    # moving jaw
    ]
    with open(DST, "w", encoding="ascii", newline="\r\n") as f:
        f.write("VERICUT-model\nVersion-3.0\n1\n1 1 1\n")
        for tris in parts:
            for t in tris:
                nx, ny, nz = normal(t)
                f.write("3\n")
                for p in t:
                    f.write(f"{p[0]:.6f} {p[1]:.6f} {p[2]:.6f}\n")
                for _ in range(3):
                    f.write(f"{nx:.6f} {ny:.6f} {nz:.6f}\n")
    print("wrote", DST, DST.stat().st_size, "bytes; triangles", sum(len(p) for p in parts))


if __name__ == "__main__":
    main()
