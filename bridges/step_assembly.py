# -*- coding: utf-8 -*-
"""STEP AP203 装配层级与实例位姿解析（纯标准库）。

链路：
  (REPRESENTATION_RELATIONSHIP(parent_rep, child_rep)
   REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION(#transform)
   SHAPE_REPRESENTATION_RELATIONSHIP())
        ↓ CONTEXT_DEPENDENT_SHAPE_REPRESENTATION(#rel, #pds)
  PRODUCT_DEFINITION_SHAPE → PRODUCT_DEFINITION
        → PRODUCT_DEFINITION_FORMATION → PRODUCT(name)
        ↓ ITEM_DEFINED_TRANSFORMATION(#axis_src, #axis_dst)
  AXIS2_PLACEMENT_3D(#point, #axisZ, #refX) → 4x4 位姿
"""
from __future__ import annotations

import math
import os
import re
from typing import Any, Dict, List

from bridges.step_reverse import StepModel, _CART, _NUM


def _decode(name: str) -> str:
    try:
        return name.encode("latin-1").decode("gbk")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return name


def _product_index(model: StepModel) -> Dict[int, str]:
    """pds_id -> 产品名"""
    ent = model.entities
    # PRODUCT -> formation -> definition -> definition_shape
    prod_name = {}
    for k, v in ent.items():
        if v.startswith("PRODUCT "):
            mm = re.match(r"PRODUCT\s*\(\s*'([^']*)'", v)
            if mm:
                prod_name[k] = _decode(mm.group(1))

    formation_to_product = {}
    for k, v in ent.items():
        if v.startswith("PRODUCT_DEFINITION_FORMATION"):
            ids = [int(x) for x in re.findall(r"#(\d+)", v)]
            for i in ids:
                if i in prod_name:
                    formation_to_product[k] = prod_name[i]
                    break

    def_to_product = {}
    for k, v in ent.items():
        if v.startswith("PRODUCT_DEFINITION "):
            for i in [int(x) for x in re.findall(r"#(\d+)", v)]:
                if i in formation_to_product:
                    def_to_product[k] = formation_to_product[i]
                    break

    pds_to_product = {}
    for k, v in ent.items():
        if v.startswith("PRODUCT_DEFINITION_SHAPE"):
            for i in [int(x) for x in re.findall(r"#(\d+)", v)]:
                if i in def_to_product:
                    pds_to_product[k] = def_to_product[i]
                    break
    return pds_to_product


def _placement(model: StepModel, pid: int) -> Dict[str, Any]:
    v = model.entities.get(pid, "")
    ids = [int(x) for x in re.findall(r"#(\d+)", v)]
    if not ids:
        return {}
    origin = model.point(ids[0])
    z = model.direction(ids[1]) if len(ids) > 1 else (0.0, 0.0, 1.0)
    x = model.direction(ids[2]) if len(ids) > 2 else (1.0, 0.0, 0.0)

    def norm(a):
        n = math.sqrt(sum(t * t for t in a)) or 1.0
        return tuple(t / n for t in a)

    def cross(a, b):
        return (a[1] * b[2] - a[2] * b[1],
                a[2] * b[0] - a[0] * b[2],
                a[0] * b[1] - a[1] * b[0])

    z = norm(z)
    x0 = norm(x)
    y = cross(z, x0)
    x = norm(cross(y, z))
    return {
        "origin_mm": [round(c, 5) for c in origin],
        "x_axis": [round(c, 6) for c in x],
        "y_axis": [round(c, 6) for c in y],
        "z_axis": [round(c, 6) for c in z],
        "matrix_3x4": [
            [round(x[0], 6), round(y[0], 6), round(z[0], 6), round(origin[0], 5)],
            [round(x[1], 6), round(y[1], 6), round(z[1], 6), round(origin[1], 5)],
            [round(x[2], 6), round(y[2], 6), round(z[2], 6), round(origin[2], 5)],
        ],
    }


def assembly(step_path: str) -> Dict[str, Any]:
    m = StepModel(step_path)
    ent = m.entities
    pds_to_product = _product_index(m)

    # 复合关系实体（父 rep -> 子 rep -> transform）
    rels = {}
    for k, v in ent.items():
        if "REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION" not in v:
            continue
        rr = re.search(
            r"REPRESENTATION_RELATIONSHIP\s*\(\s*'[^']*'\s*,\s*'[^']*'\s*,\s*#(\d+)\s*,\s*#(\d+)\s*\)", v)
        tr = re.search(r"REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION\s*\(\s*#(\d+)", v)
        if rr and tr:
            rels[k] = {"parent_rep": int(rr.group(1)), "child_rep": int(rr.group(2)),
                       "transform": int(tr.group(1))}

    # CDSR 把关系绑定到 product_definition_shape
    cdsr = {}
    for k, v in ent.items():
        if v.startswith("CONTEXT_DEPENDENT_SHAPE_REPRESENTATION"):
            mm = re.search(r"#(\d+)\s*,\s*#(\d+)", v)
            if mm:
                cdsr[int(mm.group(1))] = int(mm.group(2))

    # NAUO 提供显式父子
    nauo = []
    for k, v in ent.items():
        if v.startswith("NEXT_ASSEMBLY_USAGE_OCCURRENCE"):
            ids = [int(x) for x in re.findall(r"#(\d+)", v)]
            mm = re.match(r"NEXT_ASSEMBLY_USAGE_OCCURRENCE\s*\(\s*'([^']*)'", v)
            if len(ids) >= 2:
                nauo.append({"id": mm.group(1) if mm else "", "parent_pd": ids[0],
                             "child_pd": ids[1]})

    # shape_representation 名常直接就是零件名，优先于 PDS 反查
    rep_names = {}
    for k, v in ent.items():
        if v.startswith("SHAPE_REPRESENTATION"):
            mm = re.match(r"SHAPE_REPRESENTATION\s*\(\s*'([^']*)'", v)
            if mm:
                rep_names[k] = _decode(mm.group(1))

    comps = []
    for rel_id, rel in sorted(rels.items()):
        pds = cdsr.get(rel_id)
        name = (rep_names.get(rel["child_rep"])
                or pds_to_product.get(pds, "")
                or ("child_rep_%d" % rel["child_rep"]))
        tv = ent.get(rel["transform"], "")
        tids = [int(x) for x in re.findall(r"#(\d+)", tv)]
        pose = _placement(m, tids[0]) if tids else {}
        comps.append({
            "id": "NAUO%d" % (len(comps) + 1),
            "relation_entity": "#%d" % rel_id,
            "product": name,
            "child_shape_rep": "#%d" % rel["child_rep"],
            "transform_entity": "#%d" % rel["transform"],
            "pose": pose,
        })

    return {
        "status": "ok",
        "tool": "cadcam_step_assembly",
        "source": os.path.basename(step_path),
        "assembly_products": m.products(),
        "root_shape_rep": "#%d" % (next(iter(rels.values()))["parent_rep"] if rels else 0),
        "nauo_count": len(nauo),
        "component_count": len(comps),
        "components": comps,
        "shape_rep_names": {("#%d" % k): v for k, v in sorted(rep_names.items()) if v},
        "note": "pose.matrix_3x4 为列向量式 [X|Y|Z|T]，单位 mm；直接可用于装配实例定位。",
    }


def bom(step_path: str) -> Dict[str, Any]:
    """统一 BOM 提取入口（推荐新代码使用）。

    与旧 assembly() 的区别：
      * 同时支持 AP203 装配体与 AP214 单零件（旧版仅覆盖 AP203 装配链）；
      * 自动探测 GBK/UTF-8 编码，中文零件名正确解码；
      * 输出层级树 + 每零件实体/面数 + 命名特征 + 包围盒 + 摆放位姿；
      * 额外提供 dsl / prompt_context（大模型 prompt 注入用）。
    旧 assembly() 保持不变，兼容既有调用方。
    """
    from bridges.step_bom import StepBOM
    b = StepBOM(step_path)
    d = b.to_dict()
    d["tool"] = "cadcam_step_bom"
    d["dsl"] = b.to_dsl()
    d["prompt_context"] = b.to_prompt_context()
    return d


# 兼容别名：允许 `from bridges.step_assembly import assembly_bom`
assembly_bom = bom


if __name__ == "__main__":
    import json
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "wheel_mold_P0.step")
    mode = sys.argv[2] if len(sys.argv) > 2 else "assembly"
    result = bom(p) if mode == "bom" else assembly(p)
    print(json.dumps(result, ensure_ascii=False, indent=2)[:8000])
