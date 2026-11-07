# -*- coding: utf-8 -*-
"""STEP B-Rep 特征树语义解析（纯标准库，只读）。

STEP 没有 CAD 意义上的「特征树」，只有边界表示。这里把
  PRODUCT → NAUO → MANIFOLD_SOLID_BREP → CLOSED_SHELL
          → ADVANCED_FACE → FACE_BOUND → EDGE_LOOP
          → ORIENTED_EDGE → EDGE_CURVE → 解析几何
还原成层级拓扑 + 面级参数，供 Agent 自己读懂并推断建模方法。
本模块只给事实与线索，**不下任何建模结论**。
"""
from __future__ import annotations

import collections
import math
import os
import re
from typing import Any, Dict, List

from bridges.step_reverse import StepModel, _CART, _NUM
from bridges.step_assembly import assembly as assembly_tree

_SURF_TYPES = ("CYLINDRICAL_SURFACE", "CONICAL_SURFACE", "TOROIDAL_SURFACE",
               "PLANE", "B_SPLINE_SURFACE_WITH_KNOTS", "SPHERICAL_SURFACE")
_CURVE_TYPES = ("CIRCLE", "LINE", "B_SPLINE_CURVE_WITH_KNOTS", "ELLIPSE")


def _tail_numbers(v: str, n: int = 2) -> List[float]:
    """取实体末尾括号内最后 n 个数值。"""
    m = re.search(r"\(([^()]*)\)\s*;?\s*$", v.rstrip())
    if not m:
        return []
    vals = re.findall(_NUM, m.group(1))
    out = []
    for x in vals[-n:]:
        try:
            out.append(float(x))
        except ValueError:
            pass
    return out


def _surface(model: StepModel, sid: int) -> Dict[str, Any]:
    v = model.entities.get(sid, "")
    t = model.etype(v)
    if t not in _SURF_TYPES:
        return {"type": t or "UNKNOWN"}
    refs = [int(x) for x in re.findall(r"#(\d+)", v)]
    out: Dict[str, Any] = {"type": t}
    # 轴向：AXIS2_PLACEMENT_3D(#point, #dirZ, #dirX)
    if refs:
        pv = model.entities.get(refs[0], "")
        pids = [int(x) for x in re.findall(r"#(\d+)", pv)]
        if pids:
            out["origin_mm"] = [round(c, 4) for c in model.point(pids[0])]
            if len(pids) > 1:
                out["axis"] = [round(c, 5) for c in model.direction(pids[1])]
    nums = _tail_numbers(v, 2)
    if t == "CYLINDRICAL_SURFACE" and len(nums) >= 1:
        r = nums[-1]
        out["radius_mm"] = round(r, 4)
        out["diameter_mm"] = round(r * 2, 4)
    elif t == "CONICAL_SURFACE" and len(nums) >= 2:
        out["radius_mm"] = round(nums[-2], 4)
        out["half_angle_deg"] = round(math.degrees(nums[-1]), 3)
    elif t == "TOROIDAL_SURFACE" and len(nums) >= 2:
        out["major_radius_mm"] = round(nums[-2], 4)
        out["minor_radius_mm"] = round(nums[-1], 4)
    return out


def _curve(model: StepModel, cid: int) -> Dict[str, Any]:
    v = model.entities.get(cid, "")
    t = model.etype(v)
    out: Dict[str, Any] = {"type": t or "UNKNOWN"}
    if t == "CIRCLE":
        m = re.search(r",\s*(" + _NUM + r")\s*\)\s*$", v.rstrip(" ;"))
        refs = [int(x) for x in re.findall(r"#(\d+)", v)]
        if m:
            out["radius_mm"] = round(float(m.group(1)), 4)
            out["diameter_mm"] = round(float(m.group(1)) * 2, 4)
        if refs:
            pv = model.entities.get(refs[0], "")
            pids = [int(x) for x in re.findall(r"#(\d+)", pv)]
            if pids:
                out["center_mm"] = [round(c, 4) for c in model.point(pids[0])]
                if len(pids) > 1:
                    out["axis"] = [round(c, 5) for c in model.direction(pids[1])]
    return out


def _solid_report(model: StepModel, brep: int, idx: int) -> Dict[str, Any]:
    grp = model.reachable(brep)
    # shell -> face ids
    brep_v = model.entities[brep]
    brep_refs = [int(x) for x in re.findall(r"#(\d+)", brep_v)]
    shell = brep_refs[0] if brep_refs else None
    face_ids = []
    if shell:
        sv = model.entities.get(shell, "")
        face_ids = [int(x) for x in re.findall(r"#(\d+)", sv)
                    if int(x) in model.entities
                    and model.etype(model.entities[int(x)]) == "ADVANCED_FACE"]
    if not face_ids:
        face_ids = sorted(k for k in grp if model.etype(model.entities[k]) == "ADVANCED_FACE")

    surfaces, bounds, loops, edge_curves = [], 0, 0, []
    for fid in face_ids:
        fv = model.entities[fid]
        fr = [int(x) for x in re.findall(r"#(\d+)", fv)]
        # 最后一个 ref 是 surface（前面是 face_bound）
        surf_id = None
        for r in reversed(fr):
            if r in model.entities and model.etype(model.entities[r]) in _SURF_TYPES:
                surf_id = r
                break
        surfaces.append(_surface(model, surf_id) if surf_id else {"type": "UNKNOWN"})
        for r in fr:
            if r in model.entities:
                rt = model.etype(model.entities[r])
                if rt in ("FACE_OUTER_BOUND", "FACE_BOUND"):
                    bounds += 1
                elif rt == "EDGE_LOOP":
                    loops += 1

    for k in grp:
        v = model.entities[k]
        if model.etype(v) == "EDGE_CURVE":
            cr = [int(x) for x in re.findall(r"#(\d+)", v)]
            cid = None
            for r in reversed(cr):
                if r in model.entities and model.etype(model.entities[r]) in _CURVE_TYPES:
                    cid = r
                    break
            edge_curves.append(_curve(model, cid) if cid else {"type": "UNKNOWN"})

    sfc = collections.Counter(s["type"] for s in surfaces)
    egc = collections.Counter(e["type"] for e in edge_curves)
    cyl_d = collections.Counter(s["diameter_mm"] for s in surfaces
                                if s["type"] == "CYLINDRICAL_SURFACE" and "diameter_mm" in s)
    cones = sorted({s["half_angle_deg"] for s in surfaces
                    if s["type"] == "CONICAL_SURFACE" and "half_angle_deg" in s})
    circles = [e for e in edge_curves if e["type"] == "CIRCLE"]

    return {
        "solid_index": idx,
        "brep": "#%d" % brep,
        "shell": "#%d" % shell if shell else None,
        "face_count": len(face_ids),
        "face_bound_count": bounds,
        "edge_loop_count": loops,
        "edge_curve_count": len(edge_curves),
        "face_type_counts": dict(sfc),
        "edge_curve_type_counts": dict(egc),
        "cylinder_diameters_mm": {"Ø%.3f" % d: n for d, n in sorted(cyl_d.items())},
        "cone_half_angles_deg": cones,
        "circle_edge_diameters_mm": {"Ø%.3f" % d: n for d, n in
                                     sorted(collections.Counter(
                                         e["diameter_mm"] for e in circles
                                         if "diameter_mm" in e).items())},
        "sample_faces": surfaces[:6],
    }


def features(step_path: str, detail: bool = False) -> Dict[str, Any]:
    m = StepModel(step_path)
    breps = sorted(k for k, v in m.entities.items() if v.startswith("MANIFOLD_SOLID_BREP"))
    solids = [_solid_report(m, b, i + 1) for i, b in enumerate(breps)]
    asm = assembly_tree(step_path)

    gf = collections.Counter()
    gc = collections.Counter()
    for s in solids:
        gf.update(s["face_type_counts"])
        gc.update(s["edge_curve_type_counts"])

    truth = {
        "product_count": len(m.products()),
        "nauo_count": asm["nauo_count"],
        "assembly_component_count": asm["component_count"],
        "solid_count": len(breps),
        "closed_shell_count": sum(1 for v in m.entities.values() if v.startswith("CLOSED_SHELL")),
        "advanced_face_count": gf.get("ADVANCED_FACE", 0) + sum(s["face_count"] for s in solids) * 0,
        "face_total": sum(s["face_count"] for s in solids),
        "face_type_counts": dict(gf),
        "edge_curve_type_counts": dict(gc),
        "edge_curve_total": sum(s["edge_curve_count"] for s in solids),
    }
    # 面类型计数以全局实体统计为准，避免按 solid 归属重复计数
    gtype = collections.Counter(re.findall(r"#\d+\s*=\s*([A-Z_0-9]+)\s*\(", m.text))
    truth["entity_type_counts"] = {k: gtype[k] for k in
                                   ("ADVANCED_FACE", "CLOSED_SHELL", "MANIFOLD_SOLID_BREP",
                                    "CYLINDRICAL_SURFACE", "CONICAL_SURFACE",
                                    "TOROIDAL_SURFACE", "PLANE", "CIRCLE", "LINE",
                                    "B_SPLINE_CURVE_WITH_KNOTS", "EDGE_CURVE", "ORIENTED_EDGE")}

    out: Dict[str, Any] = {
        "status": "ok",
        "tool": "cadcam_step_features",
        "source": os.path.basename(step_path),
        "note": "STEP 是 B-Rep 边界表示，不含 CAD 特征树；以下是还原出的层级拓扑与面级参数。请自行推断应如何建模，本工具不给结论。",
        "products": m.products(),
        "assembly_tree": {
            "root": asm["root_shape_rep"],
            "component_count": asm["component_count"],
            "components": [{"id": c["id"], "product": c["product"],
                            "origin_mm": c["pose"].get("origin_mm")}
                           for c in asm["components"]],
        },
        "global_topology": truth,
        "solids": solids,
        "inference_clues": [
            "同轴圆柱面族 + 圆柱端面通常对应回转体分段；锥面半角 45° 常见于倒角，9.46° 常见于长锥/拔模。",
            "环面 (TOROIDAL_SURFACE) 通常来自圆角过渡；样条曲线通常来自自由曲面型腔。",
            "轴向平行 X 且圆心偏离轴线的 CIRCLE 边，通常是孔；圆心在轴线上的是回转母线轮廓。",
            "多个 MANIFOLD_SOLID_BREP 共用相同母线几何但角度不同，可能是分段模的多个扇区。",
            "NEXT_ASSEMBLY_USAGE_OCCURRENCE 与 ITEM_DEFINED_TRANSFORMATION 给出组件实例位姿，可用于装配定位。",
        ],
        "ground_truth_for_acceptance": {
            "solid_count": len(breps),
            "advanced_face_count": truth["entity_type_counts"]["ADVANCED_FACE"],
            "cylindrical_surface_count": truth["entity_type_counts"]["CYLINDRICAL_SURFACE"],
            "conical_surface_count": truth["entity_type_counts"]["CONICAL_SURFACE"],
            "toroidal_surface_count": truth["entity_type_counts"]["TOROIDAL_SURFACE"],
            "plane_count": truth["entity_type_counts"]["PLANE"],
            "circle_count": truth["entity_type_counts"]["CIRCLE"],
            "line_count": truth["entity_type_counts"]["LINE"],
            "spline_curve_count": truth["entity_type_counts"]["B_SPLINE_CURVE_WITH_KNOTS"],
            "assembly_component_count": asm["component_count"],
            "product_count": len(m.products()),
            "cone_half_angles_deg": sorted({a for s in solids for a in s["cone_half_angles_deg"]}),
            "all_cylinder_diameters_mm": sorted({d for s in solids
                                                 for d in s["cylinder_diameters_mm"]}),
        },
    }
    if detail:
        out["all_face_surfaces"] = [
            {"solid": s["solid_index"], "surfaces": s["sample_faces"]} for s in solids]
    else:
        for s in out["solids"]:
            s.pop("sample_faces", None)
    return out


if __name__ == "__main__":
    import json
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "wheel_mold_P0.step")
    print(json.dumps(features(p), ensure_ascii=False, indent=2)[:9000])
