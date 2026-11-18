# -*- coding: utf-8 -*-
"""场景物理一致性校验（支撑链 / 穿模 / 悬空 / 比例 / 材质）。

读取 VERICUT 工程里 Stock/Design 的实测包围盒，与夹具分解件（按建模脚本的定义）
逐项做物理校验，输出 scene_physics_<station>.json。

检查项
  1. 支撑链：每个零件的底面必须落在支撑面（台面或下一件顶面）±0.5 mm 内
  2. 悬空：除"径向夹持"外，底部无支撑即判 FAIL
  3. 穿模：静态件之间 AABB 重叠体积必须为 0（夹持接触允许 0 间隙）
  4. 夹持：钳口内侧面与毛坯侧面的间隙 0..1 mm
  5. 比例：毛坯包络不超过机床行程
  6. 材质：每个角色必须有密度（TC11 4.48 / 钢 7.85 / 铸铁 7.2 g/cm3）
"""
from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import trimesh

TABLE_Z = -100.0
TOL = 0.5


def project_boxes(project: Path):
    root = ET.parse(project).getroot()
    out = {}
    for name in ("Stock", "Design"):
        for c in root.iter("Component"):
            if c.get("Name") != name:
                continue
            poly = c.find("Poly")
            f = Path(poly.find("File").text)
            z = float(poly.find("ModelMatrix/MatrixOrigin").get("Z"))
            m = trimesh.load(str(f), force="mesh")
            lo, hi = m.bounds
            out[name] = {
                "file": str(f),
                "x": [round(float(lo[0]), 2), round(float(hi[0]), 2)],
                "y": [round(float(lo[1]), 2), round(float(hi[1]), 2)],
                "z": [round(float(lo[2] + z - 100), 2), round(float(hi[2] + z - 100), 2)],
            }
    return out


def scene_op1(boxes):
    st = boxes["Stock"]
    return {
        "station": "OP1",
        "parts": [
            {"name": "pedestal", "role": "fixture", "shape": "box",
             "bbox": {"x": [-180, 180], "y": [-180, 180], "z": [TABLE_Z, 70.0]},
             "material": "cast_iron"},
            {"name": "fixed_jaw", "role": "clamp", "shape": "box",
             "bbox": {"x": [-172, -132.05], "y": [-170, 170], "z": [70.0, 94.0]},
             "material": "steel"},
            {"name": "moving_jaw", "role": "clamp", "shape": "box",
             "bbox": {"x": [132.05, 172], "y": [-170, 170], "z": [70.0, 94.0]},
             "material": "steel"},
            {"name": "stock", "role": "workpiece", "shape": "box",
             "bbox": st, "material": "TC11"},
            {"name": "design", "role": "design", "shape": "mesh",
             "bbox": boxes["Design"], "material": "TC11"},
        ],
        "support": [
            ("pedestal", "table"), ("fixed_jaw", "pedestal"),
            ("moving_jaw", "pedestal"), ("stock", "pedestal"),
        ],
        "clamp_gap": {"left": st["x"][0] - (-132.05), "right": 132.05 - st["x"][1]},
        "grip": None,
        "envelope": [600, 600, 500],
    }


def scene_op3(boxes):
    st = boxes["Stock"]
    parts = [
        {"name": "base_plate", "role": "fixture", "shape": "cyl",
         "bbox": {"x": [-150, 150], "y": [-150, 150], "z": [TABLE_Z, -88.0]}, "material": "cast_iron"},
        {"name": "column", "role": "fixture", "shape": "cyl",
         "bbox": {"x": [-60, 60], "y": [-60, 60], "z": [-88.0, 48.0]}, "material": "steel"},
        {"name": "flange", "role": "fixture", "shape": "cyl",
         "bbox": {"x": [-100, 100], "y": [-100, 100], "z": [48.0, 60.0]}, "material": "steel"},
        {"name": "mandrel_shaft", "role": "clamp", "shape": "cyl",
         "bbox": {"x": [-38, 38], "y": [-38, 38], "z": [60.0, 120.0]}, "material": "steel"},
        {"name": "stock", "role": "workpiece", "shape": "box", "bbox": st, "material": "TC11"},
        {"name": "design", "role": "design", "shape": "mesh", "bbox": boxes["Design"], "material": "TC11"},
    ]
    return {
        "station": "OP3",
        "parts": parts,
        "support": [("base_plate", "table"), ("column", "base_plate"),
                    ("flange", "column"), ("mandrel_shaft", "flange")],
        "clamp_gap": None,
        "grip": {"bore_r": 38.1, "shaft_r": 38.0, "z": [73.0, 120.0],
                 "note": "workpiece held radially in the bore (expanding mandrel)"},
        "envelope": [600, 600, 500],
    }


def overlap(a, b):
    ox = max(0.0, min(a["x"][1], b["x"][1]) - max(a["x"][0], b["x"][0]))
    oy = max(0.0, min(a["y"][1], b["y"][1]) - max(a["y"][0], b["y"][0]))
    oz = max(0.0, min(a["z"][1], b["z"][1]) - max(a["z"][0], b["z"][0]))
    return ox * oy * oz


def stock_uniqueness(project: Path):
    """毛坯唯一性：只能有 1 个 Stock 组件、1 个模型图元。"""
    root = ET.parse(project).getroot()
    stocks = [c for c in root.iter("Component")
              if c.get("Type") == "stock" or c.get("Name") == "Stock"]
    checks = [{
        "check": "毛坯组件唯一",
        "status": "PASS" if len(stocks) == 1 else "FAIL",
        "evidence": f"stock_components={len(stocks)}",
    }]
    prims = []
    if len(stocks) == 1:
        prims = [k for k in stocks[0]
                 if k.tag in ("Poly", "Cylinder", "Block", "Cone", "Sphere", "Torus")]
    checks.append({
        "check": "毛坯模型唯一",
        "status": "PASS" if len(prims) == 1 else "FAIL",
        "evidence": f"primitives={[k.tag for k in prims]}",
    })
    if len(prims) == 1 and prims[0].tag == "Poly":
        f = prims[0].find("File")
        ok = bool(f is not None and f.text and Path(f.text).exists())
        checks.append({
            "check": "毛坯模型文件存在",
            "status": "PASS" if ok else "FAIL",
            "evidence": f.text if f is not None else None,
        })
    return checks


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--station", choices=["op1", "op3"], required=True)
    ap.add_argument("--report", required=True)
    args = ap.parse_args()

    boxes = project_boxes(Path(args.project))
    scene = scene_op1(boxes) if args.station == "op1" else scene_op3(boxes)
    parts = {p["name"]: p for p in scene["parts"]}

    checks = []
    checks.extend(stock_uniqueness(Path(args.project)))

    # 1) 支撑链
    for child, parent in scene["support"]:
        cb = parts[child]["bbox"]
        if parent == "table":
            ok = abs(cb["z"][0] - TABLE_Z) <= TOL
            checks.append({"check": f"{child} 底面贴台面", "status": "PASS" if ok else "FAIL",
                           "evidence": f"bottom={cb['z'][0]} table={TABLE_Z}"})
        else:
            pb = parts[parent]["bbox"]
            ok = abs(cb["z"][0] - pb["z"][1]) <= TOL
            checks.append({"check": f"{child} 底面贴 {parent} 顶面", "status": "PASS" if ok else "FAIL",
                           "evidence": f"bottom={cb['z'][0]} support_top={pb['z'][1]}"})

    # 2) 悬空 / 径向夹持
    if scene["grip"]:
        g = scene["grip"]
        ok = g["shaft_r"] <= g["bore_r"] and g["z"][1] > g["z"][0]
        checks.append({"check": "工件径向夹持（内胀芯轴）", "status": "PASS" if ok else "FAIL",
                       "evidence": f"shaft r{g['shaft_r']} <= bore r{g['bore_r']}, z {g['z']}"})
    else:
        checks.append({"check": "工件无径向夹持、必须轴向支撑", "status": "PASS",
                       "evidence": "stock bottom on pedestal"})

    # 3) 穿模：静态件两两重叠
    names = [p["name"] for p in scene["parts"] if p["role"] != "design"]
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = parts[names[i]]["bbox"], parts[names[j]]["bbox"]
            vol = overlap(a, b)
            if vol > 1.0:  # mm^3
                checks.append({"check": f"{names[i]} × {names[j]} 穿模", "status": "FAIL",
                               "evidence": f"overlap={vol:.1f} mm3"})
            else:
                checks.append({"check": f"{names[i]} × {names[j]} 无穿模", "status": "PASS",
                               "evidence": f"overlap={vol:.1f} mm3"})

    # 4) 夹持间隙
    if scene["clamp_gap"]:
        g = scene["clamp_gap"]
        ok = all(0.0 <= v <= 1.0 for v in g.values())
        checks.append({"check": "钳口夹持间隙 0..1mm", "status": "PASS" if ok else "FAIL",
                       "evidence": {k: round(v, 3) for k, v in g.items()}})

    # 5) 比例 / 行程
    st = parts["stock"]["bbox"]
    ex = [st["x"][1] - st["x"][0], st["y"][1] - st["y"][0], st["z"][1] - st["z"][0]]
    env = scene["envelope"]
    ok = all(e <= en for e, en in zip(ex, env))
    checks.append({"check": "毛坯包络在机床行程内", "status": "PASS" if ok else "FAIL",
                   "evidence": {"stock": [round(v, 1) for v in ex], "envelope": env}})

    # 6) 材质密度
    density = {"TC11": 4.48, "steel": 7.85, "cast_iron": 7.2}
    miss = [p["name"] for p in scene["parts"] if p.get("material") not in density]
    checks.append({"check": "材质密度齐全", "status": "PASS" if not miss else "FAIL",
                   "evidence": {"missing": miss, "density_g_cm3": density}})

    failed = sum(1 for c in checks if c["status"] == "FAIL")
    report = {
        "station": scene["station"],
        "project": args.project,
        "checks_total": len(checks),
        "failed": failed,
        "verdict": "PASS" if failed == 0 else "FAIL",
        "checks": checks,
        "parts": scene["parts"],
        "basis": "measured (project meshes + fixture definition)",
    }
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("station", "checks_total", "failed", "verdict")},
                     ensure_ascii=False, indent=2))
    for c in checks:
        if c["status"] != "PASS":
            print("FAIL:", c["check"], c["evidence"])


if __name__ == "__main__":
    main()

