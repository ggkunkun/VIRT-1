# -*- coding: utf-8 -*-
"""STEP 几何逆向工具（bridge 侧能力补齐）。

把 STEP AP203/AP214 文本解析成结构化几何谱，供上层 Agent 自主决定建模策略：
  - 实体 / 产品树、包围盒
  - 圆柱面半径谱、锥面半角、环面
  - 按 MANIFOLD_SOLID_BREP 拆件，逐件提取回转母线圆弧与偏心孔系
  - 输出可直接驱动参数化建模的 rebuild_recipe

设计约束：
  * 纯标准库，无第三方依赖，不启动任何 CAD 软件。
  * 只读输入文件；所有路径必须由调用方限制在工作区内。
  * 输出严格 JSON 可序列化，供 LLM 工具结果回喂。
"""
from __future__ import annotations

import collections
import math
import os
import re
from typing import Any, Dict, List, Tuple

_NUM = r"[-+0-9.Ee]+"
_CART = re.compile(
    r"\(\s*'[^']*'\s*,\s*\(\s*(" + _NUM + r")\s*,\s*(" + _NUM + r")\s*,\s*(" + _NUM + r")\s*\)"
)
_CIRCLE = re.compile(r"CIRCLE\s*\(\s*'[^']*'\s*,\s*#(\d+)\s*,\s*(" + _NUM + r")\s*\)")


class StepModel:
    """一次解析、多次查询的 STEP 文本模型。"""

    def __init__(self, path: str) -> None:
        self.path = os.path.abspath(path)
        with open(self.path, "rb") as fh:
            raw = fh.read()
        self.text = raw.decode("latin-1")
        self.entities: Dict[int, str] = {}
        self._parse_entities()
        self.refs: Dict[int, List[int]] = {
            k: [int(x) for x in re.findall(r"#(\d+)", v)] for k, v in self.entities.items()
        }
        self.types = collections.Counter(
            re.findall(r"#\d+\s*=\s*([A-Z_0-9]+)\s*\(", self.text)
        )

    def _parse_entities(self) -> None:
        cur_id, buf = None, []
        for line in self.text.splitlines():
            m = re.match(r"^#(\d+)\s*=\s*(.*)$", line)
            if m:
                if cur_id is not None:
                    self.entities[cur_id] = " ".join(buf)
                cur_id, buf = int(m.group(1)), [m.group(2)]
            elif cur_id is not None:
                buf.append(line)
        if cur_id is not None:
            self.entities[cur_id] = " ".join(buf)

    @staticmethod
    def etype(value: str) -> str:
        return value.split("(", 1)[0].strip()

    def reachable(self, start: int) -> set:
        seen, stack = {start}, [start]
        while stack:
            n = stack.pop()
            for r in self.refs.get(n, ()):
                if r not in seen and r in self.entities:
                    seen.add(r)
                    stack.append(r)
        return seen

    def point(self, pid: int) -> Tuple[float, float, float]:
        m = _CART.search(self.entities.get(pid, ""))
        return tuple(float(x) for x in m.groups()) if m else (0.0, 0.0, 0.0)  # type: ignore[return-value]

    def direction(self, did: int) -> Tuple[float, float, float]:
        m = _CART.search(self.entities.get(did, ""))
        return tuple(float(x) for x in m.groups()) if m else (0.0, 0.0, 1.0)  # type: ignore[return-value]

    def products(self) -> List[str]:
        out = []
        for name, _ in re.findall(r"PRODUCT\s*\(\s*'([^']*)'\s*,\s*'([^']*)'", self.text):
            try:
                name = name.encode("latin-1").decode("gbk")
            except (UnicodeDecodeError, UnicodeEncodeError):
                pass
            out.append(name)
        return out

    def bbox(self) -> Dict[str, List[float]]:
        xs, ys, zs = [], [], []
        for v in self.entities.values():
            if not v.startswith("CARTESIAN_POINT"):
                continue
            m = _CART.search(v)
            if m:
                x, y, z = (float(a) for a in m.groups())
                xs.append(x); ys.append(y); zs.append(z)
        if not xs:
            return {"min": [0, 0, 0], "max": [0, 0, 0], "size_mm": [0, 0, 0]}
        lo, hi = [min(xs), min(ys), min(zs)], [max(xs), max(ys), max(zs)]
        return {"min": lo, "max": hi, "size_mm": [round(b - a, 4) for a, b in zip(lo, hi)]}

    def cylinder_spectrum(self) -> Dict[str, int]:
        c = collections.Counter()
        for v in self.entities.values():
            if v.startswith("CYLINDRICAL_SURFACE"):
                m = re.search(r",\s*(" + _NUM + r")\s*\)\s*$", v.rstrip(" ;"))
                if m:
                    c[round(float(m.group(1)) * 2, 3)] += 1
        return {"Ø%.3f" % d: n for d, n in sorted(c.items())}

    def cone_half_angles_deg(self) -> List[float]:
        vals = set()
        for v in self.entities.values():
            if v.startswith("CONICAL_SURFACE"):
                m = re.search(r",\s*(" + _NUM + r")\s*\)\s*$", v.rstrip(" ;"))
                if m:
                    vals.add(round(math.degrees(float(m.group(1))), 3))
        return sorted(vals)

    def circle_rows(self, group: set) -> List[Tuple[float, Tuple[float, float, float], Tuple[float, float, float]]]:
        rows = []
        for k in group:
            v = self.entities[k]
            if not v.startswith("CIRCLE"):
                continue
            m = _CIRCLE.search(v)
            if not m:
                continue
            pl, r = int(m.group(1)), float(m.group(2))
            pr = self.refs.get(pl, [])
            if not pr:
                continue
            loc, ax = self.point(pr[0]), (self.direction(pr[1]) if len(pr) > 1 else (0, 0, 1))
            rows.append((r, loc, ax))
        return rows


def _body_report(model: StepModel, brep_id: int, idx: int) -> Dict[str, Any]:
    grp = model.reachable(brep_id)
    pts, cyl, cone, circ, planes, faces, bspl = [], [], [], [], 0, 0, 0
    for k in grp:
        v = model.entities[k]
        t = model.etype(v)
        if t == "CARTESIAN_POINT":
            m = _CART.search(v)
            if m:
                pts.append(tuple(float(a) for a in m.groups()))
        elif t == "CYLINDRICAL_SURFACE":
            m = re.search(r",\s*(" + _NUM + r")\s*\)\s*$", v.rstrip(" ;"))
            if m:
                cyl.append(round(float(m.group(1)) * 2, 4))
        elif t == "CONICAL_SURFACE":
            m = re.search(r",\s*(" + _NUM + r")\s*\)\s*$", v.rstrip(" ;"))
            if m:
                cone.append(round(math.degrees(float(m.group(1))), 3))
        elif t == "CIRCLE":
            m = re.search(r",\s*(" + _NUM + r")\s*\)\s*$", v.rstrip(" ;"))
            if m:
                circ.append(round(float(m.group(1)) * 2, 4))
        elif t == "PLANE":
            planes += 1
        elif t == "ADVANCED_FACE":
            faces += 1
        elif t == "B_SPLINE_CURVE_WITH_KNOTS":
            bspl += 1

    bbox: Dict[str, List[float]] = {"min": [], "max": [], "size_mm": []}
    if pts:
        lo = [min(p[i] for p in pts) for i in range(3)]
        hi = [max(p[i] for p in pts) for i in range(3)]
        bbox = {"min": [round(v, 4) for v in lo], "max": [round(v, 4) for v in hi],
                "size_mm": [round(b - a, 4) for a, b in zip(lo, hi)]}

    # 轴线平行 X 且圆心在 X 轴上 -> 回转母线圆弧；其余 -> 偏心孔
    meridian, holes = set(), []
    for r, loc, ax in model.circle_rows(grp):
        if abs(abs(ax[0]) - 1) < 1e-3 and abs(loc[1]) < 1e-3 and abs(loc[2]) < 1e-3:
            meridian.add((round(loc[0], 4), round(r * 2, 4)))
        elif abs(abs(ax[0]) - 1) < 1e-3:
            holes.append({"x_mm": round(loc[0], 3), "y_mm": round(loc[1], 4),
                          "z_mm": round(loc[2], 4), "dia_mm": round(r * 2, 4),
                          "angle_deg": round(math.degrees(math.atan2(loc[2], loc[1])), 2)})

    hole_spec = collections.Counter(
        (round(math.hypot(h["y_mm"], h["z_mm"]) * 2, 3), h["dia_mm"]) for h in holes
    )
    return {
        "body_index": idx,
        "brep_entity": "#%d" % brep_id,
        "entity_count": len(grp),
        "faces": faces,
        "planes": planes,
        "bsplines": bspl,
        "bbox_mm": bbox,
        "cylinder_dia_mm": {"Ø%.3f" % d: n for d, n in sorted(collections.Counter(cyl).items())},
        "cone_half_angle_deg": sorted(set(cone)),
        "edge_circle_dia_mm": {"Ø%.3f" % d: n for d, n in sorted(collections.Counter(circ).items())},
        "meridian_arcs": [{"x_mm": x, "dia_mm": d} for x, d in sorted(meridian)],
        "eccentric_holes": holes,
        "hole_pattern": [{"pcd_mm": pcd, "hole_dia_mm": dia, "count": n}
                         for (pcd, dia), n in sorted(hole_spec.items())],
    }


def analyze(step_path: str, max_bodies: int = 6, detail: bool = False) -> Dict[str, Any]:
    model = StepModel(step_path)
    breps = sorted(k for k, v in model.entities.items() if v.startswith("MANIFOLD_SOLID_BREP"))
    bodies = [_body_report(model, b, i + 1) for i, b in enumerate(breps[:max_bodies])]

    # 汇总重建配方：回转件以「母线圆弧数」为第一关键字，避免误选孔多但无母线的块体
    rep = max(bodies, key=lambda b: (len(b["meridian_arcs"]), len(b["eccentric_holes"])), default={})
    recipe = {
        "strategy": "revolve_meridian_profile_then_axial_holes",
        "axis": "X",
        "meridian_arcs": rep.get("meridian_arcs", []),
        "hole_pattern": rep.get("hole_pattern", []),
        "hole_angles_deg": sorted({h["angle_deg"] for h in rep.get("eccentric_holes", [])}),
        "note": "一个草图旋转成型回转体；偏心孔需第二草图轴向切除。母线圆弧的 x 为轴向站位，dia 为该站位直径。",
    }

    if not detail:
        # 精简模式：保留决策所需几何，去掉逐孔坐标与实体计数噪声，控制回喂体积 < 6KB
        slim = []
        for b in bodies:
            slim.append({
                "body_index": b["body_index"],
                "faces": b["faces"],
                "bbox_mm": b["bbox_mm"],
                "cylinder_dia_mm": b["cylinder_dia_mm"],
                "cone_half_angle_deg": b["cone_half_angle_deg"],
                "meridian_arcs": b["meridian_arcs"],
                "hole_pattern": b["hole_pattern"],
                "hole_angles_deg": sorted({h["angle_deg"] for h in b["eccentric_holes"]}),
            })
        bodies = slim

    return {
        "status": "ok",
        "tool": "cadcam_step_reverse",
        "source": os.path.basename(step_path),
        "source_bytes": os.path.getsize(step_path),
        "entity_count": len(model.entities),
        "entity_types_top": dict(model.types.most_common(20 if detail else 12)),
        "products": model.products(),
        "global_bbox_mm": model.bbox(),
        "cylinder_dia_spectrum": model.cylinder_spectrum(),
        "cone_half_angles_deg": model.cone_half_angles_deg(),
        "solid_count": len(breps),
        "detail_mode": bool(detail),
        "bodies": bodies,
        "rebuild_recipe": recipe,
    }


def list_step_files(workspace_root: str, name_contains: str = "", limit: int = 12) -> Dict[str, Any]:
    out = []
    for base, _dirs, files in os.walk(workspace_root):
        if any(seg in base for seg in (".git", "node_modules", "__pycache__", ".venv",
                                       "runs", "external")):
            continue
        for fn in files:
            if fn.lower().endswith((".step", ".stp")):
                if name_contains and name_contains.lower() not in fn.lower():
                    continue
                q = os.path.join(base, fn)
                out.append({"path": q, "name": fn, "bytes": os.path.getsize(q)})
    out.sort(key=lambda x: (0 if os.sep + "assets" + os.sep in x["path"] else 1, -x["bytes"]))
    return {"status": "ok", "count": min(len(out), limit),
            "total_matched": len(out), "files": out[:limit],
            "hint": "选择后把 path 原样传给 action=analyze 的 step_path"}


def reverse_step(step_path: str = "", action: str = "analyze",
                 workspace_root: str = "", max_bodies: int = 6,
                 name_contains: str = "", detail: bool = False) -> Dict[str, Any]:
    """工具入口；由 bridges.tool_calling_specs.execute_tool_call 调用。"""
    if action == "list" or (not step_path and action not in ("assembly", "features", "bom")):
        return list_step_files(workspace_root or os.getcwd(), name_contains=name_contains)
    if not step_path:
        step_path = os.path.join(workspace_root or os.getcwd(), "assets", "wheel_mold_P0.step")
    if not os.path.isfile(step_path):
        return {"status": "error", "message": "STEP 文件不存在: %s" % step_path,
                "hint": "先调用 action=list 查看工作区内可用的 STEP 文件"}
    try:
        if action == "assembly":
            from bridges.step_assembly import assembly as asm_tree
            return asm_tree(step_path)
        if action == "bom":
            # P0 解法：STEP→结构化 BOM（AP203/AP214 统一、中文名自动解码、
            # 含层级/实体面数/包围盒/摆放位姿）。供大模型推理前注入 prompt。
            from bridges.step_bom import StepBOM
            bom = StepBOM(step_path)
            return {
                "status": "ok",
                "tool": "cadcam_step_reverse",
                "action": "bom",
                "source": os.path.basename(step_path),
                "ap_version": bom.ap_version,
                "encoding": bom.encoding,
                "is_assembly": len(bom.nauo) > 0,
                "bom": bom.to_dict(),
                "dsl": bom.to_dsl(),
                "prompt_context": bom.to_prompt_context(),
            }
        if action == "features":
            from bridges.step_features import features as feat_tree
            return feat_tree(step_path, detail=detail)
        base_res = analyze(step_path, max_bodies=max_bodies, detail=detail)
        # 融合 StepReverseEngine 高阶工业级特征树、构件族推断与理论物理体积
        try:
            from virtu_omni.engine.step_reverse_engine import StepReverseEngine
            s_eng = StepReverseEngine(workspace_root=workspace_root)
            adv = s_eng.analyze_step(step_path)
            base_res.update({
                "part_family": adv.part_family,
                "theoretical_volume_mm3": adv.theoretical_volume_mm3,
                "key_dimensions": adv.key_dimensions,
                "reconstruction_vba": adv.reconstruction_vba,
                "success": adv.success,
            })
        except Exception:
            pass
        return base_res
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "message": "%s: %s" % (type(exc).__name__, exc)}


if __name__ == "__main__":
    import json
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "wheel_mold_P0.step")
    print(json.dumps(reverse_step(p), ensure_ascii=False, indent=2)[:6000])
