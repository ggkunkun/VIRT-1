#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""套料独立复核：重新读回排样 DXF，用几何布尔运算验证重叠/越界/间距/利用率。

不看排样引擎的自报数字，只看产物。退出码 0=几何合格 1=不合格 2=读图失败。
"""
import argparse, json, sys

import ezdxf
from shapely.geometry import box
from shapely.strtree import STRtree
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

SHEET_LAYER = "STOCK_FRAME"
PART_LAYER = "PARTS_CUT"


def rects(doc, layer):
    out = []
    for e in doc.modelspace().query('LWPOLYLINE[layer=="%s"]' % layer):
        pts = [(float(p[0]), float(p[1])) for p in e.get_points()]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        out.append({"x0": min(xs), "y0": min(ys), "x1": max(xs), "y1": max(ys),
                    "w": max(xs) - min(xs), "h": max(ys) - min(ys), "closed": bool(e.closed)})
    return out


def verify(path, margin, kerf):
    doc = ezdxf.readfile(path)
    sheet = rects(doc, SHEET_LAYER)
    parts = rects(doc, PART_LAYER)
    problems = []
    if len(sheet) != 1:
        problems.append({"code": "NEST-SHEET-FRAME", "detail": "STOCK_FRAME 图层应恰好 1 条闭合框，实测 %d" % len(sheet)})
        sheet = sheet[:1]
    else:
        if not sheet[0]["closed"]:
            problems.append({"code": "NEST-SHEET-FRAME", "detail": "母板外框未闭合"})
    sl = sheet[0]["x1"] if sheet else 0.0
    sw = sheet[0]["y1"] if sheet else 0.0

    polys = [box(p["x0"], p["y0"], p["x1"], p["y1"]) for p in parts]
    for i, p in enumerate(parts):
        if not p["closed"]:
            problems.append({"code": "NEST-OPEN-CONTOUR", "detail": "第 %d 个零件轮廓未闭合，无法计算展开面积" % (i + 1)})
        if sheet and (p["x0"] < -1e-9 or p["y0"] < -1e-9 or p["x1"] > sl + 1e-9 or p["y1"] > sw + 1e-9):
            problems.append({"code": "NEST-OUT-OF-SHEET", "detail": "第 %d 个零件越出母板 (x %.1f..%.1f, y %.1f..%.1f, 板 %.1f x %.1f)" % (
                i + 1, p["x0"], p["x1"], p["y0"], p["y1"], sl, sw)})

    tree = STRtree(polys)
    overlaps, tight = [], []
    for i in range(len(polys)):
        for j in range(i + 1, len(polys)):
            inter = polys[i].intersection(polys[j]).area
            if inter > 1e-6:
                overlaps.append({"pair": [i + 1, j + 1], "area_mm2": round(inter, 3)})
            elif polys[i].distance(polys[j]) < kerf - 1e-9:
                tight.append({"pair": [i + 1, j + 1], "gap_mm": round(polys[i].distance(polys[j]), 3)})
    if overlaps:
        problems.append({"code": "NEST-OVERLAP", "detail": "%d 对零件重叠，共 %.2f mm2" % (
            len(overlaps), sum(o["area_mm2"] for o in overlaps)), "pairs": overlaps})
    if tight:
        problems.append({"code": "NEST-KERF", "detail": "%d 对间距小于割缝/桥距要求 %.1f mm" % (len(tight), kerf),
                         "pairs": tight})

    part_area = sum(p["w"] * p["h"] for p in parts)
    sheet_area = sl * sw
    util = 100.0 * part_area / sheet_area if sheet_area else 0.0
    bb = None
    if parts:
        bx1 = max(p["x1"] for p in parts)
        by1 = max(p["y1"] for p in parts)
        bb = 100.0 * part_area / (bx1 * by1) if bx1 * by1 else 0.0
    return {"dxf": path.replace("\\", "/").split("/")[-1], "sheet": {"length": sl, "width": sw},
            "part_count": len(parts), "part_area_mm2": round(part_area, 2),
            "utilization_full_sheet_pct": round(util, 3),
            "utilization_bounding_pct": round(bb, 3) if bb else None,
            "declared_margin": margin, "declared_kerf": kerf,
            "problems": problems,
            "verdict": "NEST_OK" if not problems else "NEST_INVALID"}


def claimed_rate(doc):
    """读回 DIM_INFO 抬头里引擎自己写的利用率，与重算值对账。"""
    import re
    for e in doc.modelspace().query('TEXT[layer=="DIM_INFO"]'):
        txt = e.dxf.text
        for m in re.finditer(r"(\d+\.\d+)\s*%", txt):
            return float(m.group(1))
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("nest_dxf")
    ap.add_argument("--margin", type=float, default=5.0)
    ap.add_argument("--kerf", type=float, default=5.0)
    ap.add_argument("--json-out", default=None)
    a = ap.parse_args()
    try:
        rep = verify(a.nest_dxf, a.margin, a.kerf)
        doc = ezdxf.readfile(a.nest_dxf)
        rep["claimed_utilization_pct"] = claimed_rate(doc)
        if rep["claimed_utilization_pct"] is not None:
            rep["claimed_vs_recomputed_abs_diff_pct"] = round(
                abs(rep["claimed_utilization_pct"] - rep["utilization_full_sheet_pct"]), 4)
            if rep["claimed_vs_recomputed_abs_diff_pct"] > 0.5:
                rep["problems"].append({"code": "NEST-REPORT-MISMATCH",
                                       "detail": "抬头自报 %.2f%% 与按产物重算 %.2f%% 不符" % (
                                           rep["claimed_utilization_pct"], rep["utilization_full_sheet_pct"])})
                rep["verdict"] = "NEST_INVALID"
    except Exception as e:
        rep = {"verdict": "READ_FAILED", "error": str(e)}
    txt = json.dumps(rep, ensure_ascii=False, indent=1)
    if a.json_out:
        open(a.json_out, "w", encoding="utf-8").write(txt)
    sys.stdout.write(json.dumps({"verdict": rep["verdict"], "part_count": rep.get("part_count"),
                                 "util": rep.get("utilization_full_sheet_pct"),
                                 "codes": [p["code"] for p in rep.get("problems", [])]}, ensure_ascii=False) + chr(10))
    return 0 if rep["verdict"] == "NEST_OK" else (2 if rep["verdict"] == "READ_FAILED" else 1)


if __name__ == "__main__":
    sys.exit(main())
