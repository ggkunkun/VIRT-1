"""工艺规划：特征 → 工序草案（类别、刀具、几何、需求）。不含参数优化。"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from cam_autogen.contracts import Feature, ProcessType, ToolSpec, WorkpieceSpec
from cam_autogen.optimization import catalog as cat

FACE_ALLOW = 1.0          # 端面/顶面加工余量 mm
FINISH_ALLOW_TURN = 0.3   # 车削精车径向余量（单边）
FINISH_ALLOW_MILL = 0.2   # 铣削精铣侧壁余量


@dataclass
class OpDraft:
    category: str
    feature_ids: List[str]
    tool: ToolSpec
    geometry: Dict[str, Any]
    ra_req: Optional[float] = None
    tol_req: Optional[float] = None
    finishing: bool = False
    setup: str = "main"
    notes: List[str] = field(default_factory=list)


def _feat_ra(f: Feature, wp: WorkpieceSpec) -> float:
    return f.ra_um or wp.general_ra_um


def _feat_tol(f: Feature, wp: WorkpieceSpec) -> float:
    return f.tolerance_mm or wp.general_tolerance_mm


def _needs_finish(f: Feature, wp: WorkpieceSpec) -> bool:
    return _feat_ra(f, wp) <= 1.6 or _feat_tol(f, wp) <= 0.05


# ------------------------------------------------------------------ 车削轮廓
def build_turn_profile(wp: WorkpieceSpec) -> List[List[float]]:
    """由 od_cylinder / od_taper / chamfer_od 生成外轮廓折线 [[z, d], ...]，z 从 0 递减。"""
    segs: List[Tuple[float, float, float, float]] = []  # (z_start, z_end, d_start, d_end)
    for f in wp.features:
        p = f.params
        if f.type == "od_cylinder":
            segs.append((p.get("z_start", 0.0), p["z_end"], p["diameter"], p["diameter"]))
        elif f.type == "od_taper":
            segs.append((p.get("z_start", 0.0), p["z_end"], p["d_start"], p["d_end"]))
    if not segs:
        d = wp.envelope.diameter or 0
        L = wp.envelope.length or 0
        return [[0.0, d], [-L, d]] if d and L else []
    segs.sort(key=lambda s: -s[0])
    pts: List[List[float]] = []
    for zs, ze, ds, de in segs:
        pts.append([zs, ds])
        pts.append([ze, de])
    for f in wp.features:
        if f.type != "chamfer_od":
            continue
        size, zc = f.params.get("size", 0.5), f.params.get("z", 0.0)
        for i, (z, d) in enumerate(pts):
            if abs(z - zc) < 1e-6 and (i == 0 or pts[i - 1][0] != z or pts[i - 1][1] < d) and d - 2 * size > 0:
                pts[i] = [z, d - 2 * size]
                pts.insert(i + 1, [z - size, d])
                break
    return pts


def profile_d_at(profile: List[List[float]], z: float) -> Optional[float]:
    """轮廓在 z 处的直径（阶梯处取较小者=材料保留更多一侧的保守值取 max？此处取包络最大值以防误判过切）。"""
    if not profile or z > profile[0][0] + 1e-9 or z < profile[-1][0] - 1e-9:
        return None
    best: Optional[float] = None
    for (z1, d1), (z2, d2) in zip(profile, profile[1:]):
        lo, hi = min(z1, z2), max(z1, z2)
        if lo - 1e-9 <= z <= hi + 1e-9:
            d = d1 if abs(z2 - z1) < 1e-12 else d1 + (d2 - d1) * (z - z1) / (z2 - z1)
            if abs(z2 - z1) < 1e-12:
                d = max(d1, d2)
            best = d if best is None else max(best, d)
    return best


def turn_volume(profile: List[List[float]], stock_d: float, allow: float = 0.0) -> float:
    vol = 0.0
    for (z1, d1), (z2, d2) in zip(profile, profile[1:]):
        dz = abs(z1 - z2)
        if dz < 1e-12:
            continue
        dm = (d1 + d2) / 2 + 2 * allow
        vol += math.pi / 4 * max(0.0, stock_d ** 2 - dm ** 2) * dz
    return vol


# ------------------------------------------------------------------ 规划
def plan_operations(wp: WorkpieceSpec, ptype: ProcessType) -> Tuple[List[OpDraft], List[str]]:
    notes: List[str] = []
    if wp.envelope.type == "cylindrical" and ptype in (ProcessType.TURNING, ProcessType.TURN_MILL):
        ops = _plan_turning(wp, notes)
        if ptype == ProcessType.TURN_MILL:
            ops += _plan_live(wp, notes)
    elif wp.envelope.type == "prismatic":
        ops = _plan_milling(wp, notes)
    else:
        # 回转体但被判为铣削：按棱柱体规划会丢失外圆，显式拒绝
        raise ValueError(f"包络 {wp.envelope.type} 与工艺 {ptype.value} 不一致，无法规划")
    if not ops:
        raise ValueError("未生成任何工序：特征集合与工艺类型不匹配")
    return ops, notes


def _plan_turning(wp: WorkpieceSpec, notes: List[str]) -> List[OpDraft]:
    ops: List[OpDraft] = []
    stock_d = wp.stock.diameter or (wp.envelope.diameter or 0) + 2.0
    profile = build_turn_profile(wp)
    face_f = [f for f in wp.features if f.type == "face"]
    ops.append(OpDraft("face_turn", [f.id for f in face_f] or ["_stock_face"], cat.TURN_ROUGH,
                       {"stock_d": stock_d, "z_start": FACE_ALLOW, "z_end": 0.0},
                       ra_req=min([_feat_ra(f, wp) for f in face_f] or [wp.general_ra_um])))
    od = [f for f in wp.features if f.type in ("od_cylinder", "od_taper", "chamfer_od")]
    if od and profile:
        z_min = profile[-1][0]
        dmin = min(d for _, d in profile)
        radial = (stock_d - dmin) / 2
        fin = any(_needs_finish(f, wp) for f in od)
        allow = FINISH_ALLOW_TURN if fin else 0.0
        if radial - allow > 0.05:
            ops.append(OpDraft("od_rough", [f.id for f in od], cat.TURN_ROUGH,
                               {"stock_d": stock_d, "profile": profile, "allowance_x": allow, "z_min": z_min,
                                "radial_depth": radial - allow, "volume": turn_volume(profile, stock_d, allow)},
                               ra_req=None if fin else min(_feat_ra(f, wp) for f in od),
                               tol_req=None if fin else min(_feat_tol(f, wp) for f in od)))
        if fin:
            length = sum(math.hypot(z2 - z1, (d2 - d1) / 2) for (z1, d1), (z2, d2) in zip(profile, profile[1:]))
            ops.append(OpDraft("od_finish", [f.id for f in od], cat.TURN_FINISH,
                               {"profile": profile, "allowance": allow, "length": length, "stock_d": stock_d},
                               ra_req=min(_feat_ra(f, wp) for f in od), tol_req=min(_feat_tol(f, wp) for f in od),
                               finishing=True))
    for f in wp.features:
        p = f.params
        if f.type == "groove_od":
            start_d = profile_d_at(profile, p["z"]) or stock_d
            ops.append(OpDraft("groove", [f.id], cat.groove_tool(p.get("width", 3)),
                               {"diameter": p["diameter"], "width": p.get("width", 3), "z": p["z"], "start_d": start_d},
                               ra_req=_feat_ra(f, wp), tol_req=_feat_tol(f, wp)))
    for f in wp.features:
        p = f.params
        if f.type == "thread_od":
            h = 0.6134 * p["pitch"]
            ops.append(OpDraft("thread", [f.id], cat.thread_tool(p["pitch"]),
                               {"diameter": p["diameter"], "pitch": p["pitch"], "z_start": p.get("z_start", 0.0),
                                "z_end": p["z_end"], "depth": round(h, 4)}, ra_req=_feat_ra(f, wp)))
    for f in wp.features:
        p = f.params
        if f.type == "bore_axial" or (f.type in ("hole", "thread_hole") and f.on_axis):
            d, depth = p["diameter"], p["depth"]
            tight = _feat_tol(f, wp) <= 0.05 or _feat_ra(f, wp) <= 1.6
            if d >= 12:
                dd = max(x for x in cat.DRILLS if x <= d - 2.0)
                ops.append(OpDraft("drill_axial", [f.id], cat.drill(dd, depth), {"diameter": dd, "depth": depth},
                                   ra_req=6.3))
                ops.append(OpDraft("bore", [f.id], cat.boring_bar(dd, depth),
                                   {"d_start": dd, "d_final": d, "depth": depth}, ra_req=_feat_ra(f, wp),
                                   tol_req=_feat_tol(f, wp), finishing=True))
            else:
                ops.append(OpDraft("drill_axial", [f.id], cat.drill(d, depth), {"diameter": d, "depth": depth},
                                   ra_req=max(_feat_ra(f, wp), 3.2)))
                if tight:
                    notes.append(f"{f.id}: Ø{d} 小孔精度要求高，车床上建议铰孔（当前钻削，Ra 按 3.2 计）")
    return ops


def _plan_live(wp: WorkpieceSpec, notes: List[str]) -> List[OpDraft]:
    ops: List[OpDraft] = []
    profile = build_turn_profile(wp)
    part_d = wp.envelope.diameter or 0
    axial_holes: Dict[Tuple[float, float], List[Dict[str, float]]] = {}
    for f in wp.features:
        p = f.params
        if f.type in ("keyway", "slot", "pocket"):
            z_c = p.get("z_center", p.get("z", -10.0))
            length, width, depth = p.get("length", 20), p.get("width", 6), p.get("depth", 3)
            d_surf = profile_d_at(profile, z_c) or part_d
            tool = cat.pick_end_mill(width, depth, "live_end_mill")
            ops.append(OpDraft("live_keyway", [f.id], tool,
                               {"c_angle": p.get("angle", 0.0), "z1": z_c + length / 2 - width / 2,
                                "z2": z_c - length / 2 + width / 2, "width": width, "depth": depth, "d_surface": d_surf},
                               ra_req=_feat_ra(f, wp), tol_req=_feat_tol(f, wp), setup="live"))
        elif f.type in ("flat", "planar_face", "polygon"):
            sides = int(p.get("sides", 1)) if f.type == "polygon" else 1
            z_c = p.get("z_center", -p.get("length", 10) / 2)
            length = p.get("length", 10)
            d_surf = profile_d_at(profile, z_c) or part_d
            if f.type == "polygon":
                depth = (d_surf - p["across_flats"]) / 2
                width = d_surf
            else:
                depth = p.get("depth", 1.0)
                width = p.get("width", 2 * math.sqrt(max(0.0, (d_surf / 2) ** 2 - (d_surf / 2 - depth) ** 2)))
            tool = cat.pick_end_mill(min(12.0, max(6.0, length)), depth, "live_end_mill")
            for k in range(sides):
                ops.append(OpDraft("live_flat", [f.id], tool,
                                   {"c_angle": p.get("angle", 0.0) + k * 360.0 / sides, "z1": z_c + length / 2,
                                    "z2": z_c - length / 2, "width": width, "depth": depth, "d_surface": d_surf},
                                   ra_req=_feat_ra(f, wp), tol_req=_feat_tol(f, wp), setup="live"))
        elif f.type == "cross_hole":
            d_surf = profile_d_at(profile, p["z"]) or part_d
            depth = d_surf + 2 if p.get("through", 1.0) else p.get("depth", d_surf / 2)
            ops.append(OpDraft("live_drill_cross", [f.id], cat.drill(p["diameter"], depth, "live_drill"),
                               {"c_angle": p.get("angle", 0.0), "z": p["z"], "diameter": p["diameter"],
                                "depth": depth, "d_surface": d_surf}, ra_req=max(_feat_ra(f, wp), 3.2), setup="live"))
        elif f.type in ("hole", "thread_hole") and not f.on_axis:
            key = (p["diameter"], p["depth"])
            axial_holes.setdefault(key, []).append({"id": f.id, "ra": _feat_ra(f, wp),
                                                    "radius": p.get("radius", part_d / 4), "angle": p.get("angle", 0.0)})
    for (d, depth), holes in axial_holes.items():
        f_ids = [h["id"] for h in holes]
        ra_min = min(h["ra"] for h in holes)
        pts = [{"radius": h["radius"], "angle": h["angle"]} for h in holes]
        ops.append(OpDraft("live_drill_axial", f_ids, cat.drill(d, depth, "live_drill"),
                           {"holes": pts, "diameter": d, "depth": depth},
                           ra_req=max(ra_min, 3.2), setup="live"))
    return ops


def _plan_milling(wp: WorkpieceSpec, notes: List[str]) -> List[OpDraft]:
    ops: List[OpDraft] = []
    px, py, pz = wp.envelope.x or 0, wp.envelope.y or 0, wp.envelope.z or 0
    sx, sy = wp.stock.x or px, wp.stock.y or py
    planar = [f for f in wp.features if f.type in ("planar_face", "face")]
    face_depth = FACE_ALLOW + max([f.params.get("depth", 0.0) for f in planar] or [0.0])
    fm = cat.face_mill(min(sx, sy))
    ops.append(OpDraft("face_mill", [f.id for f in planar] or ["_stock_top"], fm,
                       {"xmin": -(sx - px) / 2, "xmax": px + (sx - px) / 2, "ymin": -(sy - py) / 2,
                        "ymax": py + (sy - py) / 2, "z_start": FACE_ALLOW, "z_end": FACE_ALLOW - face_depth},
                       ra_req=min([_feat_ra(f, wp) for f in planar] or [wp.general_ra_um])))
    # 外形：毛坯大于零件时铣外轮廓（深度留 5mm 供虎钳夹持，底部需二次装夹）
    if sx - px > 0.2 or sy - py > 0.2:
        extra_below = (wp.stock.z or pz) - pz - FACE_ALLOW
        depth = pz + 0.5 if extra_below >= 5 else max(1.0, pz - 5.0)
        if extra_below < 5:
            notes.append("外形仅铣至距底 5mm（虎钳夹持），底部需二次装夹完成")
        allow = max(sx - px, sy - py) / 2
        tool = cat.pick_end_mill(16, depth)
        ops.append(OpDraft("outline_profile", ["_outline"], tool,
                           {"xmin": 0.0, "xmax": px, "ymin": 0.0, "ymax": py, "depth": depth, "allowance": allow},
                           ra_req=wp.general_ra_um))
    for f in wp.features:
        p = f.params
        if f.type == "contour":
            depth = p["depth"]
            tool = cat.pick_end_mill(16, depth)
            ops.append(OpDraft("contour_rough", [f.id], tool,
                               {"x": p["x"], "y": p["y"], "length": p["length"], "width": p["width"], "depth": depth,
                                "xmin": 0.0, "xmax": px, "ymin": 0.0, "ymax": py,
                                "allowance": FINISH_ALLOW_MILL if _needs_finish(f, wp) else 0.0},
                               ra_req=None if _needs_finish(f, wp) else _feat_ra(f, wp)))
            if _needs_finish(f, wp):
                ops.append(OpDraft("contour_finish", [f.id], tool,
                                   {"x": p["x"], "y": p["y"], "length": p["length"], "width": p["width"],
                                    "depth": depth, "allowance": FINISH_ALLOW_MILL},
                                   ra_req=_feat_ra(f, wp), tol_req=_feat_tol(f, wp), finishing=True))
    for f in wp.features:
        p = f.params
        if f.type == "pocket":
            L, W, depth, cr = p["length"], p["width"], p["depth"], p.get("corner_radius", 0.0)
            fin = _needs_finish(f, wp)
            rough_max = min(W * 0.6, 2 * cr if cr > 0 else W * 0.6)
            if fin:
                rough_max = min(W * 0.6, max(rough_max, 3.0))
            tool = cat.pick_end_mill(rough_max, depth)
            allow = FINISH_ALLOW_MILL if fin else 0.0
            ops.append(OpDraft("pocket_rough", [f.id], tool,
                               {"x": p["x"], "y": p["y"], "length": L, "width": W, "depth": depth,
                                "corner_radius": cr, "allowance": allow},
                               ra_req=None if fin else _feat_ra(f, wp), tol_req=None if fin else _feat_tol(f, wp)))
            if cr > 0 and tool.diameter / 2 > cr + 1e-9 and not fin:
                notes.append(f"{f.id}: 粗铣刀半径大于圆角，圆角处由精铣保证")
            if fin:
                ftool = cat.pick_end_mill(min(W * 0.6, 2 * cr) if cr > 0 else W * 0.6, depth)
                ops.append(OpDraft("pocket_finish", [f.id], ftool,
                                   {"x": p["x"], "y": p["y"], "length": L, "width": W, "depth": depth,
                                    "corner_radius": cr, "allowance": allow},
                                   ra_req=_feat_ra(f, wp), tol_req=_feat_tol(f, wp), finishing=True))
        elif f.type in ("slot", "keyway"):
            W, depth = p["width"], p["depth"]
            tool = cat.pick_end_mill(W, depth)
            ops.append(OpDraft("slot_mill", [f.id], tool,
                               {"x1": p["x1"], "y1": p["y1"], "x2": p["x2"], "y2": p["y2"], "width": W, "depth": depth},
                               ra_req=_feat_ra(f, wp), tol_req=_feat_tol(f, wp)))
    holes = [f for f in wp.features if f.type in ("hole", "thread_hole", "bore_axial")]
    if holes:
        ops.append(OpDraft("spot_drill", [f.id for f in holes], cat.spot_drill(),
                           {"holes": [{"x": f.params["x"], "y": f.params["y"]} for f in holes], "depth": 1.5},
                           ra_req=12.5))
        groups: Dict[Tuple[str, float, float], List[Feature]] = {}
        for f in holes:
            p = f.params
            if f.type == "thread_hole":
                nom = round(p["diameter"])
                pitch, tdd = cat.TAP_DRILL.get(nom, (p.get("pitch", 1.0), p["diameter"] - p.get("pitch", 1.0)))
                groups.setdefault(("drill", tdd, p["depth"] + 3), []).append(f)
                groups.setdefault(("tap", float(nom), p["depth"]), []).append(f)
            else:
                d = p["diameter"]
                tight = _feat_tol(f, wp) <= 0.03 or _feat_ra(f, wp) <= 1.6
                if tight:
                    groups.setdefault(("drill", round(d - 0.2, 1), p["depth"]), []).append(f)
                    groups.setdefault(("ream", d, p["depth"]), []).append(f)
                else:
                    groups.setdefault(("drill", d, p["depth"]), []).append(f)
        for (kind, d, depth), fs in sorted(groups.items(), key=lambda kv: ({"drill": 0, "ream": 1, "tap": 2}[kv[0][0]], kv[0][1])):
            pts = [{"x": f.params["x"], "y": f.params["y"]} for f in fs]
            if kind == "drill":
                tool = cat.drill(d, depth)
                ops.append(OpDraft("drill", [f.id for f in fs], tool,
                                   {"holes": pts, "diameter": tool.diameter, "depth": depth}, ra_req=6.3))
            elif kind == "ream":
                ops.append(OpDraft("ream", [f.id for f in fs], cat.reamer(d, depth),
                                   {"holes": pts, "diameter": d, "depth": depth},
                                   ra_req=min(_feat_ra(f, wp) for f in fs), tol_req=min(_feat_tol(f, wp) for f in fs),
                                   finishing=True))
            else:
                pitch = cat.TAP_DRILL.get(int(d), (fs[0].params.get("pitch", 1.0), 0))[0]
                ops.append(OpDraft("tap", [f.id for f in fs], cat.tap(d, pitch, depth),
                                   {"holes": pts, "diameter": d, "pitch": pitch, "depth": depth}, ra_req=3.2))
    for f in wp.features:
        if f.type == "chamfer_edge":
            notes.append(f"{f.id}: 棱边倒角按去毛刺处理，未生成独立刀路")
    return ops
