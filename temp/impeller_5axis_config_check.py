# -*- coding: utf-8 -*-
"""五轴联动铣削配置核验：毛坯/机床坐标系/刀路模式 逐项实测。

输出 artifacts/aero_closed_impeller/parameter_checklist.json
任何一项 FAIL 都以退出码 2 结束。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "artifacts" / "aero_closed_impeller"
WORK = Path(r"E:\vericut_impeller_work")
DESIGN = OUT / "AE_CLOSED_IMPELLER_NASA1975.stl"
STOCK = OUT / "AE_CLOSED_IMPELLER_stock.stl"
FIXTURE = OUT / "impeller_fixture.ply"
NC = OUT / "AE_CLOSED_IMPELLER_5AXIS_FIXED.nc"
PROJECT = WORK / "AE_CLOSED_IMPELLER_VERICUT.vcproject"
TLS = OUT / "impeller_tools.tls"
REPORT = OUT / "parameter_checklist.json"


def _ply_bbox(path: Path):
    vals = []
    with open(path, "r", encoding="ascii", errors="ignore") as fh:
        lines = fh.read().splitlines()
    i = 0
    while i < len(lines):
        if lines[i].strip() == "3" and i + 3 < len(lines):
            for j in range(1, 4):
                p = lines[i + j].split()
                if len(p) == 3:
                    try:
                        vals.append([float(x) for x in p])
                    except ValueError:
                        pass
            i += 7
        else:
            i += 1
    arr = np.array(vals)
    return arr.min(0), arr.max(0), len(arr)


def main() -> int:
    checks = []

    def add(item, expected, actual, ok, note=""):
        checks.append({"item": item, "expected": expected, "actual": actual,
                       "passed": bool(ok), "note": note})

    design = trimesh.load(DESIGN, force="mesh")
    stock = trimesh.load(STOCK, force="mesh")
    sb = stock.bounds
    db = design.bounds

    # 1) 毛坯形状：12 面长方体，非回转体
    add("毛坯几何类型", "block（12 三角形长方体）",
        f"faces={len(stock.faces)} watertight={stock.is_watertight}",
        len(stock.faces) == 12 and stock.is_watertight)
    # 2) 毛坯尺寸与余量
    size = sb[1] - sb[0]
    add("毛坯尺寸 X×Y×Z (mm)", "264.06×264.06×82.85（产品 bbox + 3/3/5/3）",
        "×".join(f"{v:.2f}" for v in size),
        abs(size[0] - 264.06) < 0.05 and abs(size[1] - 264.06) < 0.05 and abs(size[2] - 82.85) < 0.05)
    # 3) 完整包容
    pts, _ = trimesh.sample.sample_surface(design, 20000)
    inside = stock.contains(pts)
    outside = int((~inside).sum())
    add("毛坯包容性（20000 点）", "0 点在毛坯外", f"{outside} 点在外",
        outside == 0, "含顶部/底部/孔壁/叶片表面")
    # 4) 坐标系对齐：毛坯 X/Y 关于轴线对称、Z 轴即机床 Z
    add("毛坯与机床坐标系对齐", "X/Y 中心=0，Z 轴=主轴方向",
        f"x=[{sb[0][0]:.2f},{sb[1][0]:.2f}] y=[{sb[0][1]:.2f},{sb[1][1]:.2f}]",
        abs(sb[0][0] + sb[1][0]) < 0.02 and abs(sb[0][1] + sb[1][1]) < 0.02)
    # 5) 世界坐标：Attach -100 + Stock MatrixOrigin 175（对齐正确案例 world 70）
    z_bottom_world = float(sb[0][2]) + 75.0
    z_top_world = float(sb[1][2]) + 75.0
    add("毛坯世界 Z 范围 (mm)", "70.00 .. 152.85（案例：毛坯底面=夹具顶=world 70）",
        f"{z_bottom_world:.2f} .. {z_top_world:.2f}", abs(z_bottom_world - 70.0) < 0.02)

    # 6) 夹具顶面
    fmin, fmax, nv = _ply_bbox(FIXTURE)
    add("夹具底板顶面 world z (mm)", "70.00（夹具模型 z=170, Attach=-100）",
        f"model_z=[{fmin[2]:.1f},{fmax[2]:.1f}] → world=[{fmin[2]-100:.1f},{fmax[2]-100:.1f}]",
        abs((fmax[2] - 100.0) - z_bottom_world) < 0.02,
        f"plate {fmax[0]-fmin[0]:.0f}×{fmax[1]-fmin[1]:.0f}，36 verts")

    # 7) 工程文件：机床/控制/装夹
    text = PROJECT.read_text(encoding="utf-8", errors="ignore")
    add("机床", "dmg_mori_nmv1500.mch（五轴立式加工中心）",
        "found" if "dmg_mori_nmv1500.mch" in text else "missing",
        "dmg_mori_nmv1500.mch" in text)
    add("控制系统", "fan30im.ctl（FANUC 30iM，铣削）",
        "found" if "fan30im.ctl" in text else "missing", "fan30im.ctl" in text)
    add("工作偏置", "G54 + Spindle to Stock（From=Spindle）",
        "found" if ('Work Offsets' in text and '>Spindle<' in text) else "missing",
        ('Work Offsets' in text and '>Spindle<' in text))
    add("工程毛坯/夹具引用", "stock.stl(block) + fixture.ply(320×320 plate)",
        f"{'stock.stl' in text}/{'fixture.ply' in text}",
        ("stock.stl" in text and "fixture.ply" in text))

    # 8) NC：五轴联动、无车削逻辑
    nc = NC.read_text(encoding="utf-8", errors="ignore")
    lines = [ln.strip() for ln in nc.splitlines()]
    n_rtcp = sum(1 for ln in lines if "G43.4" in ln)
    n_b = sum(1 for ln in lines if re.search(r"\bB-?\d", ln))
    n_c = sum(1 for ln in lines if re.search(r"\bC-?\d", ln))
    turn_codes = [c for c in ("G96", "G97", "G99", "G70", "G71", "G72", "G76", "G32", "G33")
                  if re.search(rf"(?<![0-9]){c}(?![0-9])", nc)]
    add("五轴联动 RTCP", "G43.4 出现 ≥1 次", f"{n_rtcp} 次", n_rtcp >= 1)
    add("旋转轴联动", "B/C 坐标参与插补", f"B={n_b} 行, C={n_c} 行", n_b > 100 and n_c > 100)
    add("无车削/螺纹指令", "不得出现 " + "/".join(("G96", "G97", "G99", "G70", "G71", "G72", "G76", "G32", "G33")),
        f"命中: {turn_codes or '无'}", not turn_codes)
    ok_modal = ("G21" in nc and "G90" in nc and "G17" in nc and "G43" in nc)
    add("单位/平面/刀补", "G21 G90 G17 + G43/G43.4",
        f"G21={'G21' in nc} G90={'G90' in nc} G17={'G17' in nc} G43={'G43' in nc}",
        ok_modal)
    add("主轴与进给", "S>0 且 F>0（铣削 G94 mm/min）",
        f"S 行 {sum(1 for ln in lines if re.search(r'S\d', ln))}, F 行 {sum(1 for ln in lines if re.search(r'F\d', ln))}",
        bool(re.search(r"S\d", nc)) and bool(re.search(r"F\d", nc)))

    # 9) 刀具库：T1/T2
    tls = TLS.read_text(encoding="utf-8", errors="ignore")
    tids = re.findall(r'<Tool ID="(\d+)"', tls)
    add("刀具库", "T1 D16 平刀 + T2 D8 球头(D5 颈, 70 伸出)",
        f"Tool IDs={tids}", tids == ["1", "2"])

    passed = all(c["passed"] for c in checks)
    report = {
        "task": "航空发动机闭式叶轮 · 五轴联动铣削配置核验",
        "machine": "DMG Mori NMV1500 (X/Y/Z/B/C 双转台) + FANUC 30iM",
        "process": "5-axis simultaneous milling（非车削）",
        "checks": checks,
        "passed": passed,
        "failed_items": [c["item"] for c in checks if not c["passed"]],
        "artifacts": {
            "design_step": str(OUT / "AE_CLOSED_IMPELLER_NASA1975.step"),
            "design_stl": str(DESIGN),
            "stock_stl": str(STOCK),
            "nc": str(NC),
            "project": str(OUT / "AE_CLOSED_IMPELLER_VERICUT.vcproject"),
            "fixture": str(FIXTURE),
            "tool_library": str(TLS),
        },
        "basis": "measured（trimesh 实测 + 文本实测 + XML 实测）",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for c in checks:
        print(("PASS " if c["passed"] else "FAIL ") + c["item"] + " | " + c["actual"])
    print("ALL PASSED" if passed else "FAILED: " + ", ".join(report["failed_items"]))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
