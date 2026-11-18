# -*- coding: utf-8 -*-
"""Side-view render of the worktable assembly: table + new fixture + blank + design.

Pure geometry from the actual STL/PLY files in WORLD coordinates, so it shows
exactly what VERICUT should display on the NMV1500 B/C table.
"""
import sys
import numpy as np
import trimesh
from PIL import Image, ImageDraw
from pathlib import Path

sys.path.insert(0, r"D:\Virtu模型\scripts")
from parse_vc_ply import parse

ART = Path(r"D:\Virtu模型\artifacts\aero_closed_impeller")
OUT = Path(r"D:\Virtu模型\temp\worktable_assembly.png")

blank = trimesh.load(ART / "AE_CLOSED_IMPELLER_stock.stl")
blank.apply_translation([0, 0, 200])
design = trimesh.load(ART / "AE_CLOSED_IMPELLER_NASA1975.stl")
design.apply_translation([0, 0, 200])
fv = parse(r"E:\vc_impeller_run\impeller_fixture.ply")
fixture = trimesh.Trimesh(vertices=fv, faces=np.arange(len(fv)).reshape(-1, 3), process=True)
# B/C table: simple disc representing NMV1500 rotary table top at z~170
table = trimesh.creation.cylinder(radius=150, height=20, sections=64)
table.apply_translation([0, 0, 160])


def project(v):
    """Side/front view: horizontal = X, vertical = Z."""
    return v[:, 0], v[:, 2]


def draw_mesh(draw, mesh, color, fill_alpha=1.0, scale=2.6, ox=500, oy=760):
    v = np.asarray(mesh.vertices)
    px = ox + v[:, 0] * scale
    py = oy - (v[:, 2] - 160) * scale
    faces = np.asarray(mesh.faces)
    order = np.argsort(v[faces, 1].mean(1))
    for fi in order:
        f = faces[fi]
        pts = [(px[f[k]], py[f[k]]) for k in range(3)]
        draw.polygon(pts, fill=color, outline=tuple(max(0, c - 30) for c in color))


W, H = 1000, 820
img = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(img)
# draw back-to-front: table, fixture, blank, design overlay
draw_mesh(d, table, (200, 200, 205))
draw_mesh(d, fixture, (110, 110, 115))
draw_mesh(d, blank, (60, 170, 120))
draw_mesh(d, design, (70, 130, 200))
# labels
d.text((30, 30), "NMV1500 worktable assembly (side view, WORLD coords)", fill="black")
d.text((30, 55), "teal=blank (tapered, conformal)  blue=design impeller  gray=fixture+table", fill="gray")
d.text((30, 90), "fixture top z=195.0 = blank bottom z=195.0 (gap 0.0mm)", fill=(20, 100, 60))
d.text((30, 112), "blank: OD264 @ bottom tapering to OD193 @ top, H=80.9mm", fill=(20, 100, 60))
img.save(OUT)
print("wrote", OUT)
