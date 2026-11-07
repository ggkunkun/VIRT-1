# -*- coding: utf-8 -*-
"""从装配 STEP 推断零件间的真实配合候选（共面/同轴），并给出 SW 选面坐标。

坐标系：build123d 导入的子件已带装配位姿，因此这里所有点/轴都是装配坐标，
可直接喂给 IAssemblyDoc.SelectByID2。

配合语义：
  - coaxial   同轴、等半径、轴向重叠>0.5mm  -> swMateCONCENTRIC
  - coincident 法向相反、间隙<=0.05mm、投影重叠>1mm² -> swMateCOINCIDENT
  - distance  同上前提但 0.05<间隙<=0.5mm -> swMateDISTANCE(value=间隙)
"""
from __future__ import annotations

import math
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from build123d import import_step  # noqa: E402
from OCP.BRepAdaptor import BRepAdaptor_Surface  # noqa: E402
from OCP.BRepGProp import BRepGProp  # noqa: E402
from OCP.GProp import GProp_GProps  # noqa: E402
from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane  # noqa: E402


def _v(p) -> Tuple[float, float, float]:
    def g(name):
        val = getattr(p, name)
        return float(val() if callable(val) else val)
    return (g("X"), g("Y"), g("Z"))


def _dot(a, b): return sum(x * y for x, y in zip(a, b))
def _sub(a, b): return tuple(x - y for x, y in zip(a, b))
def _add(a, b): return tuple(x + y for x, y in zip(a, b))
def _mul(a, s): return tuple(x * s for x in a)
def _norm(a) -> Tuple[float, float, float]:
    n = math.sqrt(_dot(a, a))
    return tuple(x / n for x in a) if n > 1e-12 else (0.0, 0.0, 0.0)
def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _surface_points(faces_verts: List[Tuple[float, float, float]],
                    origin, axis, radius: float) -> List[Tuple[float, float, float]]:
    """圆柱面上的多个候选选点：不同角度×不同轴向位置，避开棱边/接缝。"""
    if not faces_verts:
        return []
    hs = [_dot(_sub(v, origin), axis) for v in faces_verts]
    h0, h1 = min(hs), max(hs)
    v = faces_verts[0]
    d = _sub(v, origin)
    radial = _norm(_sub(d, _mul(axis, _dot(d, axis))))
    if _dot(radial, radial) < 0.5:
        return []
    k = _cross(axis, radial)
    out = []
    for ang in (30, 60, 120, 150, 210, 240, 300, 330):
        c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        r2 = _norm(_add(_mul(radial, c), _mul(k, s)))
        for frac in (0.5, 0.3, 0.7):
            h = h0 + (h1 - h0) * frac
            out.append(_add(_add(origin, _mul(axis, h)), _mul(r2, radius)))
    return out


def face_inventory(step_path: str) -> Dict[str, Any]:
    root = import_step(step_path)
    parts = []
    for i, child in enumerate(getattr(root, "children", [])):
        planes, cyls = [], []
        for face in child.faces():
            adapt = BRepAdaptor_Surface(face.wrapped)
            kind = adapt.GetType()
            verts = [_v(v) for v in face.vertices()]
            props = GProp_GProps()
            BRepGProp.SurfaceProperties_s(face.wrapped, props)
            area = abs(props.Mass())
            if kind == GeomAbs_Plane:
                pln = adapt.Plane()
                d = pln.Axis().Direction()
                ctr = _v(face.center())
                pts = [ctr]
                for v in verts[:4]:
                    pts.append(_add(_mul(ctr, 0.6), _mul(v, 0.4)))
                planes.append({
                    "point": ctr, "normal": _v(d),
                    "area": round(area, 3), "verts": verts, "select_points": pts,
                })
            elif kind == GeomAbs_Cylinder:
                cyl = adapt.Cylinder()
                axis = _v(cyl.Axis().Direction())
                origin = _v(cyl.Axis().Location())
                r = float(cyl.Radius())
                sels = _surface_points(verts, origin, axis, r)
                hs = [_dot(_sub(v, origin), axis) for v in verts]
                cyls.append({
                    "origin": origin, "axis": axis, "radius": round(r, 4),
                    "axial": [round(min(hs), 3), round(max(hs), 3)] if hs else None,
                    "select_point": sels[0] if sels else None, "select_points": sels,
                    "area": round(area, 3),
                })
        parts.append({"index": i, "planes": planes, "cylinders": cyls,
                      "bbox": [round(v, 4) for v in (
                          child.bounding_box().min.X, child.bounding_box().min.Y,
                          child.bounding_box().min.Z, child.bounding_box().max.X,
                          child.bounding_box().max.Y, child.bounding_box().max.Z)]})
    return {"status": "ok", "parts": parts}


def _plane_overlap_2d(p1, p2) -> Tuple[float, float]:
    n = _norm(p1["normal"])
    x = _norm(_cross((0, 0, 1), n))
    if _dot(x, x) < 0.5:
        x = _norm(_cross((1, 0, 0), n))
    y = _cross(n, x)
    o = p1["point"]

    def bb(pts):
        if not pts:
            return None
        xs = [_dot(_sub(q, o), x) for q in pts]
        ys = [_dot(_sub(q, o), y) for q in pts]
        return min(xs), max(xs), min(ys), max(ys)

    a, b = bb(p1["verts"]), bb(p2["verts"])
    if not a or not b:
        return 0.0, 0.0
    ox = min(a[1], b[1]) - max(a[0], b[0])
    oy = min(a[3], b[3]) - max(a[2], b[2])
    return max(0.0, ox), max(0.0, oy)


def infer_mates(inv: Dict[str, Any], max_plane_mates_per_pair: int = 2) -> Dict[str, Any]:
    parts = inv["parts"]
    mates = []
    for i in range(len(parts)):
        for j in range(i + 1, len(parts)):
            cyl_hits = []
            for c1 in parts[i]["cylinders"]:
                for c2 in parts[j]["cylinders"]:
                    if abs(c1["radius"] - c2["radius"]) > 0.05:
                        continue
                    if abs(_dot(_norm(c1["axis"]), _norm(c2["axis"]))) < 0.999:
                        continue
                    v = _sub(c2["origin"], c1["origin"])
                    dist = math.sqrt(max(0.0, _dot(v, v) - _dot(v, c1["axis"]) ** 2))
                    if dist > 0.2 or not c1["axial"] or not c2["axial"]:
                        continue
                    ov = min(c1["axial"][1], c2["axial"][1]) - max(c1["axial"][0], c2["axial"][0])
                    if ov <= 0.5 or not c1["select_point"] or not c2["select_point"]:
                        continue
                    cyl_hits.append({"type": "coaxial", "a": i, "b": j,
                                     "value_mm": 0.0, "score": round(ov, 3),
                                     "radius": c1["radius"],
                                     "point_a": c1["select_points"][0],
                                     "point_b": c2["select_points"][0],
                                     "points_a": c1["select_points"],
                                     "points_b": c2["select_points"],
                                     "axis": c1["axis"]})
            cyl_hits.sort(key=lambda m: -m["score"])
            if cyl_hits:
                mates.append(cyl_hits[0])

            plane_hits = []
            for p1 in parts[i]["planes"]:
                for p2 in parts[j]["planes"]:
                    if _dot(_norm(p1["normal"]), _norm(p2["normal"])) > -0.999:
                        continue
                    gap = abs(_dot(_sub(p2["point"], p1["point"]), _norm(p1["normal"])))
                    if gap > 0.5:
                        continue
                    ox, oy = _plane_overlap_2d(p1, p2)
                    if ox <= 1.0 or oy <= 1.0:
                        continue
                    kind = "coincident" if gap <= 0.05 else "distance"
                    plane_hits.append({"type": kind, "a": i, "b": j,
                                       "value_mm": round(gap, 4),
                                       "score": round(ox * oy, 2),
                                       "normal": _norm(p1["normal"]),
                                       "point_a": p1["select_points"][0],
                                       "point_b": p2["select_points"][0],
                                       "points_a": p1["select_points"],
                                       "points_b": p2["select_points"],
                                       "overlap_mm": [round(ox, 2), round(oy, 2)]})
            plane_hits.sort(key=lambda m: -m["score"])
            # 同一对零件只取法向不同的前几个，避免同向冗余配合
            picked = []
            for m in plane_hits:
                if any(abs(_dot(m["normal"], m2["normal"])) > 0.999 for m2 in picked):
                    continue
                picked.append(m)
                if len(picked) >= max_plane_mates_per_pair:
                    break
            mates.extend(picked)
    # 无接触零件（爆炸图位姿）单独列出，由调用方决定"位姿锁定"
    touched = {m["a"] for m in mates} | {m["b"] for m in mates}
    isolated = [i for i in range(len(parts)) if i not in touched]
    return {"status": "ok", "mates": mates, "isolated_parts": isolated,
            "pair_count": len({(m["a"], m["b"]) for m in mates})}


if __name__ == "__main__":
    import json
    src = sys.argv[1]
    inv = face_inventory(src)
    out = infer_mates(inv)
    print(json.dumps(out, ensure_ascii=False, indent=2)[:6000])
