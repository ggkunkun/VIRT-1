# -*- coding: utf-8 -*-
"""贴合外形的锥台毛坯 v3：逐层使用设计模型实测外轮廓包络。

v1 问题：子午外形只有 2 个点（外圆 + 单一直线锥面），底部形成 z=-5..26.5
的等半径直筒（占高度 ~38%），视觉上像圆柱。

v3 做法：
  - 从 design STL 用 section 逐层提取真实 r_max(z)（40 层）
  - 毛坯外廓 r_blank(z) = r_max(z) + ALLOW（径向偏置 3mm）
  - 底部加 5mm 装夹段，中心 Φ20 预铸孔（留镗削余量）
  - 直接用 numpy 生成回转网格（不依赖 build123d revolve，避免退化面）

2026-11-17 修正（实测不包容，两条）：
  1. 预铸孔原取 Φ25.8（= 半精加工后的孔口尺寸），成品孔 Φ25 已无料可镗。
     改为 Φ20（R_BORE=10.0），留 2.5 mm 径向镗削余量给 OP1c 螺旋铣孔。
  2. 顶部原用 env[-1] + ALLOW 直接连到孔口，形成斜面切掉前轮盖顶（实测
     184 个成品表面采样点落在毛坯外，最深 1.75 mm）。现按「到达成品顶面
     zmax 后再升 3 mm 收口」构造，顶部为完整包容面。

输出覆盖 AE_CLOSED_IMPELLER_stock.stl + blank_nearnet_report.json，
并在写盘后自动做包容性自检（不包容即抛错，不产出报告）。
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "artifacts" / "aero_closed_impeller"
DESIGN = OUT / "AE_CLOSED_IMPELLER_NASA1975.stl"

ALLOW = 3.0
BOTTOM = 5.0
R_BORE = 10.0   # 预铸孔 Φ20；成品孔 Φ25，OP1c 半精加工到 Φ25.8 后精镗
NSEG = 96  # circumferential segments


def extract_envelope(mesh, n_layers=40):
    zmin, zmax = mesh.bounds[0][2], mesh.bounds[1][2]
    # 顶层留 0.05 mm：与顶面相切的截面会退化成孔口小圆，导致 r_max 失真
    zs = np.linspace(zmin, zmax - 0.05, n_layers)
    prof = []
    for z in zs:
        sec = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
        if sec is None or len(sec.vertices) == 0:
            continue
        r = np.hypot(sec.vertices[:, 0], sec.vertices[:, 1])
        prof.append((float(z), float(r.max())))
    return prof


def revolve_profile(profile, nseg=NSEG):
    """Revolve a closed (r,z) polygon around Z into a watertight triangle mesh."""
    verts = []
    faces = []
    n = len(profile)
    for r, z in profile:
        for j in range(nseg):
            a = 2 * math.pi * j / nseg
            verts.append((r * math.cos(a), r * math.sin(a), z))
    V = np.array(verts)
    # side quads between consecutive profile rings (i -> i+1)
    for i in range(n):
        i2 = (i + 1) % n
        for j in range(nseg):
            j2 = (j + 1) % nseg
            a = i * nseg + j
            b = i * nseg + j2
            c = i2 * nseg + j2
            d = i2 * nseg + j
            faces.append([a, b, c])
            faces.append([a, c, d])
    return trimesh.Trimesh(vertices=V, faces=np.array(faces), process=True)


def main() -> dict:
    design = trimesh.load(DESIGN)
    env = extract_envelope(design, n_layers=40)
    print(f"envelope layers={len(env)} z=[{env[0][0]:.2f},{env[-1][0]:.2f}]")

    zmin, zmax = design.bounds[0][2], design.bounds[1][2]
    z_bot = zmin - BOTTOM
    r_bot = env[0][1] + ALLOW
    r_top = env[-1][1] + ALLOW
    z_top = zmax + ALLOW

    # closed meridian profile (r,z): 底部装夹段 -> 逐层外轮廓(+ALLOW)
    # -> 外壁到成品顶面后竖直收边 ALLOW -> 水平顶面到预铸孔。
    # 竖直收边保证顶面（前轮盖外锥面）也有 ALLOW 余量，而不是被斜面削到只剩 0.1mm。
    prof = [(r_bot, z_bot)]
    for z, r in env:
        prof.append((r + ALLOW, z))
    prof.append((r_top, zmax))       # 外壁到达成品最高点，半径仍留 ALLOW
    prof.append((r_top, z_top))      # 竖直收边 ALLOW（顶面余量）
    prof.append((R_BORE, z_top))     # 顶面收口（高于成品顶面 ALLOW）
    prof.append((R_BORE, z_bot))     # bore down to bottom
    # close back to (r_bot,z_bot) is automatic via modulo

    # remove consecutive duplicate points
    clean = []
    for p in prof:
        if not clean or abs(p[0] - clean[-1][0]) > 1e-4 or abs(p[1] - clean[-1][1]) > 1e-4:
            clean.append(p)
    prof = clean

    blank = revolve_profile(prof, NSEG)
    print(f"blank faces={len(blank.faces)} vol={blank.volume:.0f} "
          f"watertight={blank.is_watertight} windings={blank.is_winding_consistent}")

    stl = OUT / "AE_CLOSED_IMPELLER_stock.stl"
    blank.export(stl)
    if not stl.exists() or stl.stat().st_size < 1000:
        raise RuntimeError("毛坯 STL 未写出")

    # measured radial profile of the blank
    vm = trimesh.load(stl)
    vv = vm.vertices
    zz = vv[:, 2]
    rr = np.hypot(vv[:, 0], vv[:, 1])
    band_check = []
    for zc in np.linspace(0, 70, 8):
        b = np.abs(zz - zc) < 1.0
        if b.any():
            band_check.append([round(float(zc), 1), round(float(rr[b].max()), 1)])

    # 包容性自检：成品表面采样点到毛坯的有符号距离必须全部 >= 0
    pts, _ = trimesh.sample.sample_surface(design, 20000)
    sd = trimesh.proximity.signed_distance(vm, pts)
    outside = int((sd < 0).sum())
    enclosure = {
        "samples": int(len(pts)),
        "points_outside_stock": outside,
        "min_signed_distance_mm": round(float(sd.min()), 4),
        "median_signed_distance_mm": round(float(np.median(sd)), 4),
        "passed": bool(outside == 0),
    }

    report = {
        "blank_type": "贴合外形的锥台毛坯 v3（逐层实测包络 + 径向余量，非圆柱）",
        "allowance_mm": ALLOW,
        "bottom_clamp_mm": BOTTOM,
        "bore_mm": round(2 * R_BORE, 2),
        "envelope_source": "design STL section r_max(z), 40 layers",
        "profile_points": [[round(float(r), 2), round(float(z), 2)] for r, z in prof],
        "measured": {
            "bbox_min": [round(v, 2) for v in vm.bounds[0]],
            "bbox_max": [round(v, 2) for v in vm.bounds[1]],
            "size_mm": [round(v, 2) for v in (vm.bounds[1] - vm.bounds[0])],
            "volume_mm3": round(float(vm.volume), 0),
            "part_volume_mm3": round(float(design.volume), 0),
            "stock_to_part_ratio": round(float(vm.volume / design.volume), 3),
            "cylinder_volume_mm3": round(math.pi * r_bot ** 2 * (z_top - z_bot), 0),
            "blank_radial_profile_z_rmax": band_check,
            "watertight": bool(vm.is_watertight),
            "faces": len(vm.faces),
            "enclosure": enclosure,
        },
        "stl": str(stl),
        "basis": "measured (per-layer design envelope offset + containment self-check)",
    }
    if not enclosure["passed"]:
        raise RuntimeError(f"毛坯不包容成品：{outside} 个采样点在毛坯外，"
                           f"最深 {enclosure['min_signed_distance_mm']} mm")
    (OUT / "blank_nearnet_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("blank z->r:", band_check)
    print("enclosure:", enclosure)
    print("wrote", stl, stl.stat().st_size, "bytes; ratio", report["measured"]["stock_to_part_ratio"])
    return report


if __name__ == "__main__":
    main()
