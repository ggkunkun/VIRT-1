# -*- coding: utf-8 -*-
"""闭式叶轮仿形毛坯（near-net blank）：按成品外轮廓等距偏置，而不是整块圆柱。

为什么不是圆柱：
    成品 Φ258.06 × 74.85，其中盖板外锥面从 (R129.03, Z24.69) 收到 (R89.58, Z74.85)。
    若用整块圆柱，仅这一圈锥面就要铣掉约 0.9×10^6 mm³ 的钛合金，
    且刀路必须先做几十毫米深的型面粗铣——既不是闭式叶轮的真实下料方式，
    也会让"流道加工"这个主题被大量荒料去除淹没。
    闭式叶轮实际用模锻/精铸毛坯：外圆、盖板锥面、轮盘背面已近净成形，
    只留 3mm 均匀余量，流道位置保留实体待五轴铣削。

做法：
    把成品子午轮廓的外边界（底面 -> 外圆 -> 盖板外锥 -> 顶面）沿外法向偏置 t，
    绕 Z 轴回转成实体；内孔为 Φ25 预铸孔（留 0.4mm 镗削余量）。

输出：
    artifacts/aero_closed_impeller/AE_CLOSED_IMPELLER_stock.stl
    artifacts/aero_closed_impeller/blank_nearnet_report.json
"""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import numpy as np
from build123d import Axis, Face, Mesher, Vector, Wire, revolve

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "artifacts" / "aero_closed_impeller"

_s = importlib.util.spec_from_file_location("geo", ROOT / "scripts" / "build_nasa_closed_impeller.py")
geo = importlib.util.module_from_spec(_s)
_s.loader.exec_module(geo)

ALLOW = 3.0          # 单边加工余量
BOTTOM = 5.0         # 底面装夹余量（与 force-impeller 样本一致）


def main() -> dict:
    # 成品外边界关键点
    A = np.array([geo.R2, geo.Z_COVER_OUT_EXIT])            # 锥面与外圆交点 (129.03, 24.69)
    Bp = np.array([geo.R_COVER_OUT_INLET, geo.Z_COVER_OUT_INLET])  # 锥面与顶面交点 (89.58, 74.85)
    d = Bp - A
    L = float(np.linalg.norm(d))
    n = np.array([d[1], -d[0]]) / L                          # 外法向（朝外上）
    A2, B2 = A + n * ALLOW, Bp + n * ALLOW

    r_od = geo.R2 + ALLOW                                    # 外圆 132.03
    z_top = float(B2[1])                                     # 顶面 76.70
    z_bot = -BOTTOM
    r_bore = geo.R_BORE + 0.4                                # 预铸孔 Φ25.8

    pts = [
        (r_bore, z_bot),
        (r_od, z_bot),
        (r_od, float(A2[1])),
        (float(A2[0]), float(A2[1])),
        (float(B2[0]), float(B2[1])),
        (r_bore, z_top),
    ]
    face = Face(Wire.make_polygon([Vector(r, 0, z) for r, z in pts], close=True))
    solid = revolve(face, Axis.Z)

    stl = OUT / "AE_CLOSED_IMPELLER_stock.stl"
    # export_stl 在本机 build123d 0.13 上静默不落盘，改用 Mesher（项目内已验证路径）
    mesher = Mesher()
    mesher.add_shape(solid, linear_deflection=0.35, angular_deflection=0.3)
    mesher.write(str(stl))
    if not stl.exists() or stl.stat().st_size < 1000:
        raise RuntimeError("毛坯 STL 未写出")

    bb = solid.bounding_box()
    part_vol = 2139178.5
    report = {
        "blank_type": "near-net offset blank（仿形毛坯，非圆柱）",
        "allowance_mm": ALLOW,
        "bottom_clamp_mm": BOTTOM,
        "bore_mm": round(2 * r_bore, 2),
        "profile_points": [[round(float(r), 3), round(float(z), 3)] for r, z in pts],
        "cone_offset_start": [round(float(A2[0]), 2), round(float(A2[1]), 2)],
        "cone_offset_end": [round(float(B2[0]), 2), round(float(B2[1]), 2)],
        "measured": {
            "bbox_min": [round(v, 2) for v in (bb.min.X, bb.min.Y, bb.min.Z)],
            "bbox_max": [round(v, 2) for v in (bb.max.X, bb.max.Y, bb.max.Z)],
            "size_mm": [round(v, 2) for v in (bb.size.X, bb.size.Y, bb.size.Z)],
            "volume_mm3": round(solid.volume, 0),
            "part_volume_mm3": part_vol,
            "stock_to_part_ratio": round(solid.volume / part_vol, 3),
            "cylinder_volume_mm3": round(math.pi * r_od ** 2 * (z_top - z_bot), 0),
        },
        "stl": str(stl),
        "basis": "measured (revolved offset profile)",
    }
    (OUT / "blank_nearnet_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    main()
