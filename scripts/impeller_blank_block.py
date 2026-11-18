# -*- coding: utf-8 -*-
"""包容块毛坯（milling blank）：轴对齐长方体，与机床坐标系 XYZ 一一对应。

口径来源（2026-11-17 用户指定）：
  本件在 DMG MORI NMV1500 五轴**铣床**上加工，毛坯必须是包容块（bounding block），
  不得用回转体 / 圆柱 / 锥台毛坯：
    1) 铣削从方料去除材料；回转体毛坯属车削或近净锻件口径，与本工序不符；
    2) 包容块三对面与机床 X/Y/Z 平行，装夹面即 G54 的 Z0 基准，坐标系无旋转、无偏置歧义；
    3) 块料必须完整包容设计件（含余量），写盘后按设计顶点实测自检，不包容即抛错。

尺寸口径（实测，不估算）—— 对齐正确案例 E:\samples\All\force_impeller_dmg_mori_nmv1500_fan30im_mm.vcproject：
  案例 Stock 实测（VERICUT-model 私有格式解析）：
    Stock  local z = -30 .. 0    MatrixOrigin Z=200 -> world z = 170 .. 200
    Design local z = -25 .. 0    MatrixOrigin Z=200 -> world z = 175 .. 200
    Fixture1 顶面 local z = 170，Fixture MatrixOrigin Z=0 -> world 170
  => 案例相对间距：毛坯底面 world == 夹具顶面；毛坯顶面 world == 设计件顶面（齐平）；
                    设计件底面 == 毛坯底面 + 5mm（5mm 为夹持下沉段）。
  => 案例尺寸比例：Stock XY 48.0 == Design XY 48.0（径向零余量）。

  本场景换算（夹具顶面 local z=170，设计件 local z=0..74.85）：
    XY 半宽 = max(|bbox.x|, |bbox.y|) + MARGIN_XY   (MARGIN_XY=0.0，与案例同为零余量)
    Z       = Z_BOTTOM(-5.0) .. 设计 zmax + MARGIN_TOP (MARGIN_TOP=0.0，顶面与设计件齐平)
    MatrixOrigin Z = 175  (= 夹具顶面 170 + 5mm 夹持段)，与案例拓扑等价
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "artifacts" / "aero_closed_impeller"
DESIGN = OUT / "AE_CLOSED_IMPELLER_NASA1975.stl"
STOCK = OUT / "AE_CLOSED_IMPELLER_stock_block.stl"
REPORT = OUT / "blank_block_report.json"

MARGIN_XY = 0.0        # XY 单边余量（对齐案例：Stock XY == Design XY，零余量）
MARGIN_TOP = 0.0       # 顶面留量（对齐案例：毛坯顶面与设计件顶面齐平）
Z_BOTTOM = -5.0        # 底面：夹持下沉段（毛坯底面 world 170 == 夹具顶面 world 170）
MATRIX_ORIGIN_Z = 175.0  # Stock/Design 共用的 ModelMatrix Origin Z（夹具顶面 170 + 5mm）
MATERIAL = "TC11"


def main() -> dict:
    design = trimesh.load(str(DESIGN), force="mesh")
    dmin, dmax = design.bounds
    r_max = float(np.hypot(design.vertices[:, 0], design.vertices[:, 1]).max())

    # 轴向对齐包容块：按 bbox 取半宽（不是斜向 hypot 半径），与案例 Stock XY == Design XY 同口径
    half = round(max(abs(float(dmin[0])), abs(float(dmax[0])),
                     abs(float(dmin[1])), abs(float(dmax[1]))) + MARGIN_XY, 3)
    z_top = round(float(dmax[2]) + MARGIN_TOP, 3)
    z_bot = Z_BOTTOM
    ext = (2 * half, 2 * half, round(z_top - z_bot, 3))

    box = trimesh.creation.box(extents=ext)
    box.apply_translation([0.0, 0.0, (z_top + z_bot) / 2.0])
    box.export(str(STOCK))

    # ---- 包容性自检（实测，不靠推算）----
    bmin, bmax = box.bounds
    tol = 1e-6
    encloses = bool(np.all(design.vertices >= bmin - tol) and np.all(design.vertices <= bmax + tol))
    outside = int(np.sum(np.any((design.vertices < bmin - tol) | (design.vertices > bmax + tol), axis=1)))
    stock_vol = float(box.volume)
    design_vol = float(design.volume)

    report = {
        "stock_stl": str(STOCK),
        "stock_bytes": STOCK.stat().st_size,
        "stock_shape": "bounding_block",
        "stock_material": MATERIAL,
        "machine": "DMG MORI NMV1500 (5-axis milling, X/Y/Z/B/C)",
        "orientation": "axis-aligned: faces parallel to machine X/Y/Z, no rotation",
        "stock_dims_mm": [ext[0], ext[1], ext[2]],
        "stock_origin_center_mm": [0.0, 0.0, round((z_top + z_bot) / 2.0, 3)],
        "stock_bounds_mm": {"min": [round(v, 3) for v in bmin], "max": [round(v, 3) for v in bmax]},
        "design_bounds_mm": {"min": [round(v, 3) for v in dmin], "max": [round(v, 3) for v in dmax]},
        "allowance_mm": {"xy_per_side": MARGIN_XY, "top": MARGIN_TOP, "bottom_grip": abs(Z_BOTTOM)},
        "model_matrix_origin_z": MATRIX_ORIGIN_Z,
        "world_bounds_mm": {
            "stock": [[round(v, 3) for v in bmin][0], [round(v, 3) for v in bmin][1], round(bmin[2] + MATRIX_ORIGIN_Z, 3)],
            "stock_max": [round(v, 3) for v in bmax][:2] + [round(bmax[2] + MATRIX_ORIGIN_Z, 3)],
            "design_min": [round(v, 3) for v in dmin][:2] + [round(dmin[2] + MATRIX_ORIGIN_Z, 3)],
            "design_max": [round(v, 3) for v in dmax][:2] + [round(dmax[2] + MATRIX_ORIGIN_Z, 3)],
        },
        "case_reference": {
            "vcproject": r"E:\samples\All\force_impeller_dmg_mori_nmv1500_fan30im_mm.vcproject",
            "case_stock_local": {"min": [-24.0, -23.9938, -30.0], "max": [24.0, 24.0, 0.0]},
            "case_design_local": {"min": [-24.0, -23.9728, -25.0], "max": [24.0, 23.9965, -0.0]},
            "case_fixture_top_local_z": 170.0,
            "case_step_stock_stl": "D:\\Virtu模型\\artifacts\\aero_closed_impeller\\AE_CLOSED_IMPELLER_stock_block.stl",
        },
        "encloses_design": encloses,
        "design_vertices_outside": outside,
        "watertight": bool(box.is_watertight),
        "volume_mm3": round(stock_vol, 1),
        "design_volume_mm3": round(design_vol, 1),
        "material_removal_mm3": round(stock_vol - design_vol, 1),
        "material_removal_ratio": round((stock_vol - design_vol) / stock_vol, 4),
        "basis": "measured (design bbox + vertex containment test)",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not encloses:
        raise SystemExit(f"毛坯不包容设计件：{outside} 个设计顶点落在块外")
    return report


if __name__ == "__main__":
    main()
