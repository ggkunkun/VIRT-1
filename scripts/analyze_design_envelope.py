# -*- coding: utf-8 -*-
"""Extract the true outer-radius-vs-z envelope of the closed impeller design.

Uses trimesh section cuts at many z levels so blade tips (not just sparse
vertices) define the envelope. This is the basis for a conformal near-net blank.
"""
import numpy as np
import trimesh

DESIGN = r"D:\Virtu模型\artifacts\aero_closed_impeller\AE_CLOSED_IMPELLER_NASA1975.stl"

m = trimesh.load(DESIGN)
zmin, zmax = m.bounds[0][2], m.bounds[1][2]
print(f"design z=[{zmin:.2f},{zmax:.2f}] vol={m.volume:.0f}")

# Sample outer radius via section at each z; take max radius of the section path.
zs = np.linspace(zmin, zmax, 26)
prof = []
for z in zs:
    sec = m.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    if sec is None or len(sec.vertices) == 0:
        prof.append((z, np.nan, 0))
        continue
    v = sec.vertices
    r = np.sqrt(v[:, 0] ** 2 + v[:, 1] ** 2)
    prof.append((z, r.max(), len(v)))

print("\n z(mm)   rmax(mm)  pts")
for z, rmax, n in prof:
    print(f" {z:7.2f} {rmax:9.2f} {n:5d}")

np.save(r"D:\Virtu模型\artifacts\aero_closed_impeller\design_envelope.npy",
        np.array([(z, r) for z, r, _ in prof if not np.isnan(r)]))
print("\nsaved design_envelope.npy")
