# -*- coding: utf-8 -*-
"""Build the VERICUT OP3 station (flip setup) from the OP1/OP2 project.

Creates:
  op3_stock.stl   cylinder r137.5 x 25.85 (remaining lower band, as-flipped top)
  design_flip.stl design.stl rotated 180 deg about X
  mandrel.ply     internal mandrel: shaft r38 h60 + flange r100 h12
  OP3.vcproject   clone of proj.vcproject with:
                    Stock  -> op3_stock.stl, MatrixOrigin Z = 227   (world 127..152.85)
                    Design -> design_flip.stl, MatrixOrigin Z = 247.85 (world 73..147.85)
                    Fixture-> mandrel.ply,   MatrixOrigin Z = 160   (world 48..120)
                    NC     -> OP3_FLIP.nc
"""
from __future__ import annotations

import math
import shutil
from pathlib import Path

import numpy as np
import trimesh

RUN = Path(r"E:\vericut_impeller_run")


def box_stl(path: Path, sx: float, sy: float, z0: float, z1: float) -> None:
    m = trimesh.creation.box(extents=[sx, sy, z1 - z0])
    m.apply_translation([0.0, 0.0, (z0 + z1) / 2.0])
    m.export(path); return


def _old_cyl(path: Path, r: float, z0: float, z1: float, seg: int = 64) -> None:
    ang = np.linspace(0, 2 * math.pi, seg, endpoint=False)
    ring = np.column_stack([r * np.cos(ang), r * np.sin(ang)])
    verts = []
    faces = []
    for z in (z0, z1):
        base = len(verts)
        for x, y in ring:
            verts.append((x, y, z))
        # center vertex
        verts.append((0.0, 0.0, z))
        c = len(verts) - 1
        for i in range(seg):
            j = (i + 1) % seg
            if z == z0:
                faces.append((c, base + j, base + i))
            else:
                faces.append((c, base + i, base + j))
    # side wall
    for i in range(seg):
        j = (i + 1) % seg
        faces.append((i, j, seg + j))
        faces.append((i, seg + j, seg + i))
    m = trimesh.Trimesh(vertices=np.array(verts), faces=np.array(faces), process=True)
    m.export(path)


def cyl_ply_parts(segs: list[tuple[float, float, float]], seg: int = 48):
    """Return list of triangles for closed cylinders (r, z0, z1)."""
    tris = []
    for r, z0, z1 in segs:
        ang = [2 * math.pi * i / seg for i in range(seg)]
        ring0 = [(r * math.cos(a), r * math.sin(a), z0) for a in ang]
        ring1 = [(r * math.cos(a), r * math.sin(a), z1) for a in ang]
        c0 = (0.0, 0.0, z0)
        c1 = (0.0, 0.0, z1)
        for i in range(seg):
            j = (i + 1) % seg
            tris.append((c0, ring0[j], ring0[i]))
            tris.append((c1, ring1[i], ring1[j]))
            tris.append((ring0[i], ring0[j], ring1[j]))
            tris.append((ring0[i], ring1[j], ring1[i]))
    return tris


def normal(t):
    p0, p1, p2 = t
    u = np.subtract(p1, p0)
    v = np.subtract(p2, p0)
    n = np.cross(u, v)
    L = np.linalg.norm(n) or 1.0
    return n / L


def write_ply(path: Path, tris) -> None:
    with open(path, "w", encoding="ascii", newline="\r\n") as f:
        f.write("VERICUT-model\nVersion-3.0\n1\n1 1 1\n")
        for t in tris:
            n = normal(t)
            f.write("3\n")
            for p in t:
                f.write(f"{p[0]:.6f} {p[1]:.6f} {p[2]:.6f}\n")
            for _ in range(3):
                f.write(f"{n[0]:.6f} {n[1]:.6f} {n[2]:.6f}\n")


def main() -> None:
    box_stl(RUN / "op3_stock.stl", 264.06, 264.06, 0.0, 25.85)

    design = trimesh.load(RUN / "design.stl", force="mesh")
    flip = np.array([[1, 0, 0, 0], [0, -1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]], dtype=float)
    design.apply_transform(flip)
    design.export(RUN / "design_flip.stl")

    tris = cyl_ply_parts([(150.0, -172.0, -160.0),   # base plate on the machine table
                          (60.0, -148.0, -12.0),     # support column (no overlap with base)
                          (100.0, -12.0, 0.0),       # mandrel flange
                          (38.0, 0.0, 60.0)])        # expanding shaft in the bore
    write_ply(RUN / "mandrel.ply", tris)

    src = RUN / "proj.vcproject"
    dst = RUN / "OP3.vcproject"
    text = src.read_text(encoding="utf-8")

    # Stock
    text = text.replace("<File>E:\\vericut_impeller_run\\stock.stl</File>",
                        "<File>E:\\vericut_impeller_run\\op3_stock.stl</File>")
    # Design
    text = text.replace("<File>E:\\vericut_impeller_run\\design.stl</File>",
                        "<File>E:\\vericut_impeller_run\\design_flip.stl</File>")
    # Fixture (3 poly entries)
    text = text.replace("<File>E:\\vericut_impeller_run\\vise.ply</File>",
                        "<File>E:\\vericut_impeller_run\\mandrel.ply</File>")
    # NC
    text = text.replace("<File>E:\\vericut_impeller_run\\impeller.nc</File>",
                        "<File>E:\\vericut_impeller_run\\OP3_FLIP.nc</File>")

    # per-component ModelMatrix Z (the last MatrixOrigin inside each component block)
    import re
    def set_z(block: str, z: float) -> str:
        return re.sub(r'(<MatrixOrigin X="0" Y="0" Z=")[-\d.]+("/>)',
                      lambda m: m.group(1) + str(z) + m.group(2), block, count=1)

    def patch_component(text: str, name: str, z: float) -> str:
        m = re.search(r'(<Component Name="%s"[\s\S]*?)(?=<Component Name=|</Components>|</Component>)' % name, text)
        if not m:
            raise SystemExit(f"component {name} not found")
        block = set_z(m.group(1), z)
        return text[:m.start(1)] + block + text[m.end(1):]

    text = patch_component(text, "Stock", 227.0)
    text = patch_component(text, "Design", 247.85)
    text = patch_component(text, "Fixture", 160.0)
    dst.write_text(text, encoding="utf-8")

    # sanity: XML parses
    import xml.etree.ElementTree as ET
    ET.parse(dst)
    print("models:", (RUN / "op3_stock.stl").stat().st_size, (RUN / "design_flip.stl").stat().st_size,
          (RUN / "mandrel.ply").stat().st_size)
    print("project:", dst, dst.stat().st_size, "parse OK")


if __name__ == "__main__":
    main()


