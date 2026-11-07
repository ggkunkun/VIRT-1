# -*- coding: utf-8 -*-
"""用 OCP/build123d 把装配 STEP 拆成「本地坐标系」单件 STEP，并测体积/包围盒。

与手工字节拆分（bridges/step_split.py）的区别：几何由 OCCT 重新序列化，
是干净的单件 STEP，SolidWorks 翻译器可直接吃；同时给出精确体积
（mm³）作为 SW 质量属性的独立对账基准。

坐标约定：build123d 导入的装配子件已带装配位姿（assembly coords）。
本模块用 BOM 4x4 位姿求逆，把子件移回本地坐标系；SW 里再用同一 4x4
插入，二者互为反证。
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from build123d import import_step  # noqa: E402
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform  # noqa: E402
from OCP.STEPControl import STEPControl_Writer, STEPControl_StepModelType  # noqa: E402
from OCP.TopExp import TopExp_Explorer  # noqa: E402
from OCP.TopAbs import TopAbs_FACE, TopAbs_SOLID  # noqa: E402
from OCP.gp import gp_Trsf  # noqa: E402

from bridges.step_bom import StepBOM  # noqa: E402


def _count(shape, kind) -> int:
    exp, n = TopExp_Explorer(shape, kind), 0
    while exp.More():
        n += 1
        exp.Next()
    return n


def _inverse_transform(shape, matrix: List[List[float]]):
    r = [[matrix[i][j] for j in range(3)] for i in range(3)]
    t = [matrix[i][3] for i in range(3)]
    ri = [[r[j][i] for j in range(3)] for i in range(3)]  # 正交阵转置
    ti = [-sum(ri[i][j] * t[j] for j in range(3)) for i in range(3)]
    trsf = gp_Trsf()
    trsf.SetValues(ri[0][0], ri[0][1], ri[0][2], ti[0],
                   ri[1][0], ri[1][1], ri[1][2], ti[1],
                   ri[2][0], ri[2][1], ri[2][2], ti[2])
    return BRepBuilderAPI_Transform(shape, trsf, True).Shape()


def extract_parts(step_path: str, out_dir: str) -> Dict[str, Any]:
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    out_dir = os.path.abspath(out_dir)
    bom = StepBOM(step_path)
    kids = [c for c in bom.tree[0].get("children", []) if c.get("solids", 0) > 0]
    root = import_step(step_path)
    children = list(getattr(root, "children", []))
    if len(children) != len(kids):
        return {"status": "error",
                "message": "OCP children %d != BOM parts %d" % (len(children), len(kids))}

    records = []
    for i, (child, node) in enumerate(zip(children, kids)):
        wrapped = child.wrapped
        faces = _count(wrapped, TopAbs_FACE)
        solids = _count(wrapped, TopAbs_SOLID)
        bb = child.bounding_box()
        bbox_asm = [round(v, 4) for v in (bb.min.X, bb.min.Y, bb.min.Z,
                                          bb.max.X, bb.max.Y, bb.max.Z)]
        placement = node.get("placement")
        if not placement:
            return {"status": "error", "message": "BOM part %d has no placement" % i}
        local = _inverse_transform(wrapped, placement["matrix"])
        out_path = os.path.join(out_dir, "sw_part_%d.step" % i)
        writer = STEPControl_Writer()
        writer.Transfer(local, STEPControl_StepModelType.STEPControl_AsIs)
        writer.Write(out_path)

        # 多实体零件：3D Interconnect 不吃 compound，按实体另存，SW 侧逐个导入成多体
        solid_shapes = list(child.solids()) if hasattr(child, "solids") else []
        solid_files, solid_volumes = [], []
        if len(solid_shapes) > 1:
            for k, s in enumerate(solid_shapes):
                s_local = _inverse_transform(s.wrapped, placement["matrix"])
                s_path = os.path.join(out_dir, "sw_part_%d_solid_%d.step" % (i, k))
                w2 = STEPControl_Writer()
                w2.Transfer(s_local, STEPControl_StepModelType.STEPControl_AsIs)
                w2.Write(s_path)
                solid_files.append(s_path)
                solid_volumes.append(round(s.volume, 3))

        chk = import_step(out_path)
        cb = chk.bounding_box()
        bbox_local = [round(v, 4) for v in (cb.min.X, cb.min.Y, cb.min.Z,
                                           cb.max.X, cb.max.Y, cb.max.Z)]
        vol_local = round(chk.volume, 3)
        vol_asm = round(child.volume, 3)
        ok = (abs(vol_local - vol_asm) <= max(1e-3, abs(vol_asm) * 1e-6)
              and _count(chk.wrapped, TopAbs_FACE) == _count(local, TopAbs_FACE))
        records.append({
            "index": i, "name": node["name"], "step_file": out_path,
            "solids": solids, "faces": faces, "bom_faces": node["faces"],
            "face_match": faces == node["faces"],
            "volume_mm3": vol_local, "volume_assembly_mm3": vol_asm,
            "bbox_assembly_mm": bbox_asm, "bbox_local_mm": bbox_local,
            "placement": placement, "roundtrip_ok": ok,
            "solid_files": solid_files, "solid_volumes_mm3": solid_volumes,
            "bytes": os.path.getsize(out_path),
        })
    ok = all(r["roundtrip_ok"] and r["face_match"] for r in records)
    return {"status": "ok" if ok else "error", "source": os.path.basename(step_path),
            "part_count": len(records), "parts": records,
            "elapsed_s": round(time.time() - t0, 2)}


if __name__ == "__main__":
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        os.path.dirname(src), "parts_occ")
    print(json.dumps(extract_parts(src, out), ensure_ascii=False, indent=2))
