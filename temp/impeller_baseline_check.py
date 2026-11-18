# -*- coding: utf-8 -*-
"""Baseline re-measurement: design solid vs near-net blank vs sample allowances."""
import json
import sys
from pathlib import Path

import numpy as np
import trimesh

OUT = Path(r"D:\Virtu模型\artifacts\aero_closed_impeller")
DESIGN = OUT / "AE_CLOSED_IMPELLER_NASA1975.stl"
STOCK = OUT / "AE_CLOSED_IMPELLER_stock.stl"


def mesh_report(m, name):
    return {
        "name": name,
        "volume_mm3": round(float(m.volume), 1),
        "bbox_min": [round(float(v), 3) for v in m.bounds[0]],
        "bbox_max": [round(float(v), 3) for v in m.bounds[1]],
        "size_mm": [round(float(v), 3) for v in (m.bounds[1] - m.bounds[0])],
        "watertight": bool(m.is_watertight),
        "winding_consistent": bool(m.is_winding_consistent),
        "faces": int(len(m.faces)),
    }


def main():
    design = trimesh.load(DESIGN, force="mesh")
    stock = trimesh.load(STOCK, force="mesh")
    rep = {"design": mesh_report(design, "design_stl"), "stock": mesh_report(stock, "stock_stl")}

    # 1) 毛坯是否完整包裹成品：在设计表面取点，量其到毛坯表面的有符号距离（正=在毛坯内）
    pts, _ = trimesh.sample.sample_surface(design, 20000)
    sd = trimesh.proximity.signed_distance(stock, pts)
    outside = int((sd < 0).sum())
    rep["enclosure"] = {
        "samples": int(len(pts)),
        "points_outside_stock": outside,
        "min_signed_distance_mm": round(float(sd.min()), 4),
        "p01_signed_distance_mm": round(float(np.percentile(sd, 1)), 4),
        "median_signed_distance_mm": round(float(np.median(sd)), 4),
        "passed": outside == 0 and float(sd.min()) >= 0.0,
    }

    # 2) 逐层最小径向余量：同 z 分层，stock 的 r_max(z) - design 的 r_max(z)
    zmin, zmax = design.bounds[0][2], design.bounds[1][2]
    layers = []
    worst = (1e9, None)
    for z in np.linspace(zmin + 0.5, zmax - 0.5, 40):
        sd_sec = design.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
        st_sec = stock.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
        if sd_sec is None or st_sec is None:
            continue
        rd = float(np.hypot(sd_sec.vertices[:, 0], sd_sec.vertices[:, 1]).max())
        rs = float(np.hypot(st_sec.vertices[:, 0], st_sec.vertices[:, 1]).max())
        gap = rs - rd
        layers.append([round(float(z), 2), round(rd, 2), round(rs, 2), round(gap, 2)])
        if gap < worst[0]:
            worst = (gap, z)
    rep["radial_allowance"] = {
        "layers": layers,
        "min_gap_mm": round(float(worst[0]), 3),
        "min_gap_z": round(float(worst[1]), 2) if worst[1] is not None else None,
        "target_allowance_mm": 3.0,
        "passed_min_2p5": bool(worst[0] >= 2.5),
    }

    # 3) 样本反推余量对照（E:\samples force-impeller 样本的毛坯约定）
    rep["sample_reference"] = {
        "sample_stock": "E:\\samples\\Support_files\\force-impeller_stock.ply",
        "sample_design": "E:\\samples\\Support_files\\force-impeller_design.ply",
        "sample_rule": "样本毛坯=成品外径、仅底部多 5 mm 装夹段（预车盘料）",
    }
    ok = (rep["design"]["watertight"] and rep["stock"]["watertight"]
          and rep["enclosure"]["passed"] and rep["radial_allowance"]["passed_min_2p5"])
    rep["all_passed"] = bool(ok)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
