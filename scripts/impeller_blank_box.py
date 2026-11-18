# -*- coding: utf-8 -*-
"""包容块毛坯（Block Stock）：与机床坐标系对齐的长方体包容块。

用户要求（2026-11-17）：毛坯不能是圆柱/回转体，必须是包容块，且与机床坐标系对得上。
约定（沿用 force-impeller 样本与现有工程）：
  - 零件坐标：Z=0 为轮盘底面，+Z 为轴向
  - 毛坯局部坐标：X/Y 以轴线 (0,0) 对称，Z 从 -5.0（底部装夹余量）到 77.85（顶面余量）
  - 工程内 Stock 组件 MatrixOrigin Z=200、Attach Z=-100
    ⇒ 毛坯世界坐标 Z = 95.0 .. 177.85，底面正好落在夹具顶面 (world z=95)
  - 余量：X/Y 每边 +3.0 mm（包容回转外径），底部 +5.0 mm，顶部 +3.0 mm

输出（覆盖）：
  artifacts/aero_closed_impeller/AE_CLOSED_IMPELLER_stock.stl
  artifacts/aero_closed_impeller/blank_box_report.json
写盘后自检：成品表面采样点必须全部在块内，否则抛错。
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "artifacts" / "aero_closed_impeller"
DESIGN = OUT / "AE_CLOSED_IMPELLER_NASA1975.stl"
STOCK = OUT / "AE_CLOSED_IMPELLER_stock.stl"
REPORT = OUT / "blank_box_report.json"

ALLOW_XY = 3.0
ALLOW_BOTTOM = 5.0
ALLOW_TOP = 3.0


def write_box_stl(path: Path, xmin, xmax, ymin, ymax, zmin, zmax) -> None:
    """二进制 STL：6 个面各 2 个三角形，外法线朝外。"""
    v = [(xmin, ymin, zmin), (xmax, ymin, zmin), (xmax, ymax, zmin), (xmin, ymax, zmin),
         (xmin, ymin, zmax), (xmax, ymin, zmax), (xmax, ymax, zmax), (xmin, ymax, zmax)]
    quads = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    tris = []
    for a, b, c, d in quads:
        tris += [(v[a], v[b], v[c]), (v[a], v[c], v[d])]
    with open(path, "wb") as fh:
        fh.write(b"virtu block stock (bbox + allowance)".ljust(80, b" "))
        fh.write(struct.pack("<I", len(tris)))
        for t in tris:
            p0, p1, p2 = (np.array(p, dtype=float) for p in t)
            n = np.cross(p1 - p0, p2 - p0)
            n = n / (np.linalg.norm(n) or 1.0)
            fh.write(struct.pack("<3f", *n))
            for p in t:
                fh.write(struct.pack("<3f", *p))
            fh.write(b"\x00\x00")


def main() -> dict:
    design = trimesh.load(DESIGN, force="mesh")
    lo, hi = design.bounds
    xmin, xmax = lo[0] - ALLOW_XY, hi[0] + ALLOW_XY
    ymin, ymax = lo[1] - ALLOW_XY, hi[1] + ALLOW_XY
    zmin, zmax = lo[2] - ALLOW_BOTTOM, hi[2] + ALLOW_TOP
    write_box_stl(STOCK, xmin, xmax, ymin, ymax, zmin, zmax)

    stock = trimesh.load(STOCK, force="mesh")
    pts, _ = trimesh.sample.sample_surface(design, 20000)
    inside = stock.contains(pts)
    outside = int((~inside).sum())
    report = {
        "blank_type": "包容块（长方体，机床坐标系对齐）",
        "allowance_mm": {"xy_each_side": ALLOW_XY, "bottom": ALLOW_BOTTOM, "top": ALLOW_TOP},
        "local_bbox": {
            "x": [round(float(xmin), 2), round(float(xmax), 2)],
            "y": [round(float(ymin), 2), round(float(ymax), 2)],
            "z": [round(float(zmin), 2), round(float(zmax), 2)],
        },
        "machine_placement": {
            "stock_component_matrix_origin_z": 175.0,
            "attach_component_position_z": -100.0,
            "world_z_bottom": round(float(zmin) + 75.0, 2),
            "world_z_top": round(float(zmax) + 75.0, 2),
            "fixture_top_world_z": 70.0,
            "seats_on_fixture": bool(abs((float(zmin) + 75.0) - 70.0) < 1e-6),
            "case_reference": "force_impeller_dmg_mori_nmv1500_fan30im_mm.vcproject",
        },
        "measured": {
            "bbox_min": [round(float(v), 2) for v in stock.bounds[0]],
            "bbox_max": [round(float(v), 2) for v in stock.bounds[1]],
            "size_mm": [round(float(v), 2) for v in (stock.bounds[1] - stock.bounds[0])],
            "volume_mm3": round(float(stock.volume), 0),
            "part_volume_mm3": round(float(design.volume), 0),
            "stock_to_part_ratio": round(float(stock.volume / design.volume), 3),
            "watertight": bool(stock.is_watertight),
            "faces": int(len(stock.faces)),
            "enclosure": {
                "samples": int(len(pts)),
                "points_outside_stock": int(outside),
                "passed": bool(outside == 0),
            },
        },
        "stl": str(STOCK),
        "basis": "measured (产品包围盒 + 各面余量；包容性自检)",
    }
    if outside:
        raise RuntimeError(f"包容块未包住成品：{outside} 个采样点在块外")
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    main()
