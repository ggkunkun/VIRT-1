# -*- coding: utf-8 -*-
"""Render design vs old v1 blank vs new v2 blank for visual verification."""
import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

ART = Path(r"D:\Virtu模型\artifacts\aero_closed_impeller")
OUT = Path(r"D:\Virtu模型\temp\blank_compare_v2.png")
OUT.parent.mkdir(parents=True, exist_ok=True)

MODELS = [
    ("DESIGN (shrouded impeller)", ART / "AE_CLOSED_IMPELLER_NASA1975.stl", (80, 150, 220)),
    ("BLANK v3 (per-layer envelope)", ART / "AE_CLOSED_IMPELLER_stock.stl", (90, 190, 110)),
    ("DESIGN vs BLANK overlay", None, (150, 100, 160)),
]

# v1 is gone (overwritten); reconstruct from report profile as solid of revolution
import json
rep = json.loads((ART / "blank_nearnet_report.json").read_text(encoding="utf-8"))


def render(mesh, color, size=460):
    if mesh is None:
        img = Image.new("RGB", (size, size), "white")
        d = ImageDraw.Draw(img)
        d.text((20, 20), "v1 overwritten", fill="gray")
        return img
    # simple software projection: isometric-ish, z up
    v = np.asarray(mesh.vertices)
    # rotate around z by 35deg then tilt
    a = np.deg2rad(35)
    Rz = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
    t = np.deg2rad(20)
    Rx = np.array([[1, 0, 0], [0, np.cos(t), -np.sin(t)], [0, np.sin(t), np.cos(t)]])
    vv = v @ Rz.T @ Rx.T
    # normalize
    mn, mx = vv.min(0), vv.max(0)
    span = (mx - mn).max()
    center = (mn + mx) / 2
    vv = (vv - center) / span * (size * 0.78)
    px = vv[:, 0] + size / 2
    py = -vv[:, 2] + size / 2
    # depth = y
    depth = vv[:, 1]
    img = Image.new("RGB", (size, size), "white")
    draw = ImageDraw.Draw(img)
    faces = np.asarray(mesh.faces)
    # painter's sort
    order = np.argsort(depth[faces].mean(1))
    col = color
    dark = tuple(int(c * 0.65) for c in col)
    for fi in order:
        f = faces[fi]
        pts = [(px[f[k]], py[f[k]]) for k in range(3)]
        n = np.cross(vv[f[1]] - vv[f[0]], vv[f[2]] - vv[f[0]])
        shade = 0.55 + 0.45 * abs(n[1]) / (np.linalg.norm(n) + 1e-9)
        c = tuple(int(min(255, cc * shade)) for cc in col)
        draw.polygon(pts, fill=c, outline=dark, width=1)
    return img


panels = []
for name, path, color in MODELS:
    if name.startswith("DESIGN vs"):
        # overlay: design translucent + blank wireframe-ish different shade
        dmesh = trimesh.load(ART / "AE_CLOSED_IMPELLER_NASA1975.stl")
        bmesh = trimesh.load(ART / "AE_CLOSED_IMPELLER_stock.stl")
        img = render(dmesh, (80, 150, 220))
        img2 = render(bmesh, (220, 140, 40))
        arr1 = np.asarray(img).astype(float)
        arr2 = np.asarray(img2).astype(float)
        overlay = Image.fromarray((0.5 * arr1 + 0.5 * arr2).astype(np.uint8))
        panels.append((name, overlay))
        continue
    m = trimesh.load(path) if path and path.exists() else None
    panels.append((name, render(m, color)))

W = 460 * 3
canvas = Image.new("RGB", (W, 520), "white")
d = ImageDraw.Draw(canvas)
for i, (name, img) in enumerate(panels):
    canvas.paste(img, (i * 460, 40))
    d.text((i * 460 + 10, 12), name, fill="black")
canvas.save(OUT)
print("wrote", OUT)
