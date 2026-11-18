# -*- coding: utf-8 -*-
"""Generate a TRUE near-net blank for the closed impeller.

Problem with v1 blank: it was a smooth surface of revolution (cylinder + cone),
so the blade passages were completely solid -> the user correctly saw "still a
cylinder". A real closed-impeller blank is a cast/forged near-net shape that
already carries the blade form with a thin uniform allowance for 5-axis finish.

Method: morphological dilation of the design solid on a voxel grid. This is a
Minkowski sum with a cube; it offsets ALL surfaces (including blade flanks and
passage floors) outward by ~allowance, producing a conformal stock envelope.
We then:
  - keep bottom clamp extension (z below part by 5 mm, full outer radius)
  - re-open the central bore slightly smaller than design (pre-cast hole)
  - simplify + watertight check + export STL

Outputs:
  AE_CLOSED_IMPELLER_stock.stl (overwrites v1)
  blank_nearnet_report.json (v2, with measured evidence)
"""
from __future__ import annotations

import json
import numpy as np
import trimesh
from scipy import ndimage
from pathlib import Path

ART = Path(r"D:\Virtu模型\artifacts\aero_closed_impeller")


def voxelize_parity(mesh, xs, ys, zs):
    """Voxelize a watertight mesh via project-to-XY parity ray casting, vectorized.

    For each (x,y) grid column, cast a +Z ray; count how many mesh triangles'
    XY-projections cover that (x,y) with intersection-z below each voxel. Odd
    count => inside. Fully numpy, bounded memory (~nx*ny*MAXHITS), no rtree.
    """
    nx, ny, nz = len(xs), len(ys), len(zs)
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    px, py = X.ravel(), Y.ravel()
    ncol = len(px)
    MAXHITS = 64
    z_hits = np.full((ncol, MAXHITS), np.inf)
    hit_cnt = np.zeros(ncol, dtype=np.int32)

    tris = np.asarray(mesh.triangles, dtype=float)  # (T,3,3)
    eps = 1e-10
    # process triangles in small batches to bound temporaries
    B = 64
    for t0 in range(0, len(tris), B):
        tb = tris[t0:t0 + B]
        ax, ay, az = tb[:, 0, 0, None], tb[:, 0, 1, None], tb[:, 0, 2, None]
        bx, by, bz = tb[:, 1, 0, None], tb[:, 1, 1, None], tb[:, 1, 2, None]
        cx, cy, cz = tb[:, 2, 0, None], tb[:, 2, 1, None], tb[:, 2, 2, None]
        denom = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        for j in range(len(tb)):
            d = float(denom[j, 0])
            if abs(d) < eps:
                continue
            axj, ayj, azj = ax[j, 0], ay[j, 0], az[j, 0]
            bxj, byj, bzj = bx[j, 0], by[j, 0], bz[j, 0]
            cxj, cyj, czj = cx[j, 0], cy[j, 0], cz[j, 0]
            l1 = ((byj - cyj) * (px - cxj) + (cxj - bxj) * (py - cyj)) / d
            l2 = ((cyj - ayj) * (px - cxj) + (axj - cxj) * (py - cyj)) / d
            l3 = 1.0 - l1 - l2
            inside = (l1 >= -eps) & (l2 >= -eps) & (l3 >= -eps)
            idx = np.nonzero(inside)[0]
            if idx.size == 0:
                continue
            zint = l1[idx] * azj + l2[idx] * bzj + l3[idx] * czj
            slot = hit_cnt[idx]
            ok = slot < MAXHITS
            if ok.any():
                z_hits[idx[ok], slot[ok]] = zint[ok]
            hit_cnt[idx] += 1

    mat = np.zeros((nx, ny, nz), dtype=bool)
    for k, zc in enumerate(zs):
        below = np.count_nonzero(z_hits < zc, axis=1)
        mat[:, :, k] = (below % 2 == 1).reshape(nx, ny)
    return mat
DESIGN = ART / "AE_CLOSED_IMPELLER_NASA1975.stl"
OUT = ART / "AE_CLOSED_IMPELLER_stock.stl"
REPORT = ART / "blank_nearnet_report.json"

ALLOW = 3.0          # radial/axial stock allowance (mm)
BOTTOM_CLAMP = 5.0   # clamp material below part bottom (mm)
BORE_R = 12.9        # pre-cast bore radius (design bore ~12.9 -> keep small)
PITCH = 1.5          # voxel size (mm)


def main() -> int:
    design = trimesh.load(DESIGN)
    print(f"design: faces={len(design.faces)} vol={design.volume:.0f} "
          f"watertight={design.is_watertight}")

    # Manual voxelization via ray-based contains (avoids trimesh subdivide bug).
    bmin, bmax = design.bounds
    # Only need a thin margin for dilation; bottom clamp is added separately.
    pad = ALLOW + 1
    origin = bmin - pad
    extent = (bmax - bmin) + 2 * pad
    nx, ny, nz = np.ceil(extent / PITCH).astype(int) + 1
    print("voxel grid:", (nx, ny, nz))

    xs = origin[0] + np.arange(nx) * PITCH
    ys = origin[1] + np.arange(ny) * PITCH
    zs = origin[2] + np.arange(nz) * PITCH
    mat = voxelize_parity(design, xs, ys, zs)
    # sanity: voxel solid volume vs mesh volume should be within a few %
    vox_vol = int(mat.sum()) * PITCH ** 3
    print(f"voxel matrix filled={int(mat.sum())} vol={vox_vol} "
          f"vs design {design.volume:.0f} ratio={vox_vol / design.volume:.3f}")

    # dilation iterations ~ allowance / pitch
    iters = max(1, int(round(ALLOW / PITCH)))
    dil = ndimage.binary_dilation(mat, iterations=iters)
    print(f"dilated iters={iters} filled={int(dil.sum())} "
          f"(+{int(dil.sum()-mat.sum())} voxels)")

    # Convert back to mesh; matrix_to_marching_cubes origin uses transform
    mesh = trimesh.voxel.ops.matrix_to_marching_cubes(dil, pitch=PITCH)
    # matrix axes order is x,y,z with origin at (0,0,0); translate by grid origin
    mesh.apply_translation(origin)

    # Add bottom clamp slab: extend full-radius material below z=0 by BOTTOM_CLAMP.
    bounds = mesh.bounds
    zmin = bounds[0][2]
    # Build a cylinder at the max radius below zmin
    rmax = np.sqrt((bounds[:, 0] ** 2 + bounds[:, 1] ** 2)).max()
    clamp = trimesh.creation.cylinder(radius=rmax, height=BOTTOM_CLAMP,
                                      sections=64)
    # place clamp from zmin-BOTTOM_CLAMP to zmin
    clamp.apply_translation([0, 0, zmin - BOTTOM_CLAMP / 2])
    merged = mesh.union(clamp)

    # Re-open pre-cast bore through the whole blank
    zlo = merged.bounds[0][2] - 1
    zhi = merged.bounds[1][2] + 1
    bore = trimesh.creation.cylinder(radius=BORE_R, height=(zhi - zlo),
                                     sections=48)
    bore.apply_translation([0, 0, (zlo + zhi) / 2])
    blank = merged.difference(bore)

    # Cleanup: drop degenerate faces via update_faces mask
    good = blank.nondegenerate_faces()
    blank.update_faces(good)
    blank.remove_unreferenced_vertices()
    print(f"blank: faces={len(blank.faces)} vol={blank.volume:.0f} "
          f"watertight={blank.is_watertight}")

    # Evidence: angular radial profile at several z -> should show blade lobes
    v = blank.vertices
    r = np.sqrt(v[:, 0] ** 2 + v[:, 1] ** 2)
    th = np.arctan2(v[:, 1], v[:, 0])
    z = v[:, 2]
    zr = z.max() - z.min()
    prof = {}
    for label, zc in [("lower", z.min() + 0.25 * zr),
                      ("mid", z.min() + 0.5 * zr),
                      ("upper", z.min() + 0.75 * zr)]:
        band = np.abs(z - zc) < 0.05 * zr
        rb, tb = r[band], th[band]
        if len(rb) < 10:
            prof[label] = None
            continue
        edges = np.linspace(-np.pi, np.pi, 37)
        sect = []
        for k in range(36):
            m = (tb >= edges[k]) & (tb < edges[k + 1])
            sect.append(float(rb[m].max()) if m.any() else np.nan)
        prof[label] = {
            "r_min": round(float(np.nanmin(sect)), 2),
            "r_max": round(float(np.nanmax(sect)), 2),
            "angular_variation_mm": round(float(np.nanmax(sect) - np.nanmin(sect)), 2),
            "sectors": [round(x, 1) for x in sect],
        }
        print(f"  {label}: r={prof[label]['r_min']}..{prof[label]['r_max']} "
              f"angular_var={prof[label]['angular_variation_mm']}mm")

    # Export (Mesher is more reliable than export_stl on this machine)
    from build123d import Mesher  # noqa
    blank.export(OUT)

    report = {
        "blank_type": "near-net conformal blank with blade-passage preform (voxel dilation of design)",
        "method": "morphological dilation of design solid + bottom clamp + pre-cast bore",
        "allowance_mm": ALLOW,
        "bottom_clamp_mm": BOTTOM_CLAMP,
        "precast_bore_diameter_mm": 2 * BORE_R,
        "voxel_pitch_mm": PITCH,
        "dilation_iterations": iters,
        "measured": {
            "blank_bbox": np.round(blank.bounds[1] - blank.bounds[0], 2).tolist(),
            "blank_volume_mm3": round(float(blank.volume)),
            "blank_faces": len(blank.faces),
            "design_volume_mm3": round(float(design.volume)),
            "stock_to_part_ratio": round(float(blank.volume / design.volume), 3),
            "watertight": bool(blank.is_watertight),
            "angular_radial_profile": prof,
        },
        "stl": str(OUT),
        "basis": "measured (design-derived conformal offset)",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", OUT, OUT.stat().st_size, "bytes")
    print("wrote", REPORT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
