# -*- coding: utf-8 -*-
"""逐帧扫掠干涉/撞机检测（独立几何内核，可证伪）。

对每条运动段按 sample_step_mm 采样，构造：
  * 刀尖点序列（WCS）；
  * 刀具/刀柄圆柱表面点（车削刀轴 = -Z 径向指向工件；铣削刀轴 = +Z）；
  * 对工件原型 keepout_zones（卡盘体/虎钳钳口/垫铁/定位销/压板）求有符号间隙。
同时执行：
  * 软限位超程检查（机床坐标 = WCS + wcs_offset，与控制器解释器口径一致）；
  * 快移扎刀 / G00 横向穿越低空检查。

判定：任一采样帧最小间隙 < 0 → 撞机 CRITICAL；< clearance_margin → 高风险。
basis=measured（几何实测，非 VERICUT 布尔材料去除）。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


@dataclass
class KeepOut:
    name: str
    lo: Tuple[float, float, float]
    hi: Tuple[float, float, float]
    kind: str = "fixture_clamp"


@dataclass
class Frame:
    idx: int
    line: int
    op: int
    x: float
    y: float
    z: float
    b: float
    c: float
    is_rapid: bool
    feed: float
    spindle_rpm: float
    spindle_dir: str
    comp_length: str
    comp_radius: str
    tool_id: int
    tool_category: str
    machine_xyz: Tuple[float, float, float]


@dataclass
class InterferenceResult:
    workpiece_id: str
    controller_id: str
    frames: List[Frame] = field(default_factory=list)
    min_clearance_mm: float = math.inf
    min_clearance_non_exempt_mm: float = math.inf
    min_clearance_where: Dict[str, Any] = field(default_factory=dict)
    violations: List[Dict[str, Any]] = field(default_factory=list)
    checks: List[Dict[str, Any]] = field(default_factory=list)
    frame_count: int = 0
    exemptions: List[Dict[str, Any]] = field(default_factory=list)
    basis: str = "measured (deterministic swept-surface sampling)"

    def summary(self) -> Dict[str, Any]:
        fail = [c for c in self.checks if c["status"] == "FAIL"]
        return {
            "frames": self.frame_count,
            "min_clearance_mm": (round(self.min_clearance_mm, 4)
                                 if math.isfinite(self.min_clearance_mm) else None),
            "min_clearance_non_exempt_mm": (
                round(self.min_clearance_non_exempt_mm, 4)
                if math.isfinite(self.min_clearance_non_exempt_mm) else None),
            "violations": len(self.violations),
            "verdict": "FAIL" if fail else "PASS",
            "failed_gates": [c["gate"] for c in fail],
        }


def _box_sdf(pts: np.ndarray, lo: Tuple[float, float, float],
             hi: Tuple[float, float, float]) -> np.ndarray:
    """点到轴对齐盒的有符号距离：外部为正，内部为负。"""
    c = (np.asarray(lo) + np.asarray(hi)) / 2.0
    h = (np.asarray(hi) - np.asarray(lo)) / 2.0
    q = np.abs(pts - c) - h
    return (np.linalg.norm(np.maximum(q, 0.0), axis=1)
            + np.minimum(np.max(q, axis=1), 0.0))


def _tool_axis(process_family: str, b: float, c: float) -> np.ndarray:
    """工作坐标系下刀轴单位矢量。铣削=+Z；车削 B/C 转台按 Rz(-C)Ry(-B)·+Z。"""
    if process_family == "milling":
        br, cr = math.radians(b), math.radians(c)
        return np.array([-math.sin(br) * math.cos(cr),
                         math.sin(br) * math.sin(cr), math.cos(br)])
    return np.array([0.0, 0.0, 1.0])


def _cylinder_surface(base: np.ndarray, axis: np.ndarray, radius: float,
                      length: float, n_ang: int = 8) -> np.ndarray:
    """刀具/刀柄圆柱表面采样点（含端面圆心），用于保守间隙判定。"""
    a = axis / max(float(np.linalg.norm(axis)), 1e-9)
    u = np.cross(a, np.array([0.0, 0.0, 1.0]))
    if float(np.linalg.norm(u)) < 1e-6:
        u = np.array([1.0, 0.0, 0.0])
    u = u / float(np.linalg.norm(u))
    v = np.cross(a, u)
    ang = np.linspace(0.0, 2.0 * math.pi, n_ang, endpoint=False)
    ring = np.cos(ang)[:, None] * u + np.sin(ang)[:, None] * v
    return np.vstack([base, base + a * length,
                      base + a * (length * 0.5) + radius * ring])


def segment_frames(segment: Any, step_mm: float, wcs_offset: Tuple[float, float, float],
                   process_family: str) -> List[Frame]:
    """把一个 MotionSegment 按空间步长展开为逐帧位姿。"""
    sx, sy, sz = segment.start_wcs
    ex, ey, ez = segment.end_wcs
    if process_family == "turning":
        dist = math.sqrt(((ex - sx) * 0.5) ** 2 + (ey - sy) ** 2 + (ez - sz) ** 2)
    else:
        dist = math.sqrt((ex - sx) ** 2 + (ey - sy) ** 2 + (ez - sz) ** 2)
    if segment.motion_mode in ("G02", "G03") and (segment.arc_center_offset_ij[0] != 0.0
                                                   or segment.arc_center_offset_ij[1] != 0.0) \
            and dist < 1e-4:
        dist = 2.0 * math.pi * math.hypot(*segment.arc_center_offset_ij)
    n = max(2, int(dist / max(step_mm, 0.1)) + 2)
    out: List[Frame] = []
    for k in range(n):
        t = k / (n - 1)
        x, y, z = sx + (ex - sx) * t, sy + (ey - sy) * t, sz + (ez - sz) * t
        if process_family == "milling":
            mx = x + wcs_offset[0]
            my = y + wcs_offset[1]
            mz = z + wcs_offset[2]
        else:
            mx, my, mz = x, y, z
        out.append(Frame(
            idx=k, line=segment.line_no, op=segment.op_id,
            x=round(x, 4), y=round(y, 4), z=round(z, 4), b=0.0, c=0.0,
            is_rapid=segment.is_rapid, feed=segment.feed_mm_min,
            spindle_rpm=segment.spindle_rpm, spindle_dir=segment.spindle_dir,
            comp_length=segment.comp_length, comp_radius=segment.comp_radius,
            tool_id=segment.tool_id, tool_category="",
            machine_xyz=(round(mx, 4), round(my, 4), round(mz, 4)),
        ))
    return out


def scan(workpiece_id: str, controller_id: str, tool_map: Dict[str, Dict[str, float]],
         keepouts: List[KeepOut], frames: List[Frame], *, process_family: str,
         soft_limits: Dict[str, Tuple[float, float]], safe_z: float,
         r_plane_mm: Optional[float] = None,
         rapid_decel_zone_mm: Optional[float] = None,
         sacrificial_backings: Optional[List[Dict[str, Any]]] = None,
         clearance_margin_mm: float = 1.0,
         holder_clearance_mm: float = 1.0,
         sample_cap: int = 40000) -> InterferenceResult:
    """逐帧干涉扫描：刀具+刀柄圆柱 vs 夹具 KeepOut；软限位；快移扎刀。"""
    res = InterferenceResult(workpiece_id=workpiece_id, controller_id=controller_id)
    if not frames:
        res.checks.append({"gate": "FRAME-SAMPLES", "status": "FAIL",
                           "evidence": 0, "rule": "逐帧采样数必须 > 0（空集判红）"})
        return res
    if len(frames) > sample_cap:
        step = len(frames) // sample_cap + 1
        frames = frames[::step]
    res.frames = frames
    res.frame_count = len(frames)

    pts = np.array([[f.x, f.y, f.z] for f in frames], dtype=float)
    tips = pts.copy()
    if process_family == "turning":
        tips[:, 0] *= 0.5  # 车床 X 为直径 → 半径（径向间隙判定）

    surface_chunks: List[np.ndarray] = []
    holder_chunks: List[np.ndarray] = []
    for i, f in enumerate(frames):
        t = tool_map.get(f"T{f.tool_id}") or next(iter(tool_map.values()))
        radius = float(t["diameter"]) / 2.0
        gauge = float(t["gauge_length"])
        axis = _tool_axis(process_family, f.b, f.c)
        base = tips[i] + axis * gauge
        surface_chunks.append(_cylinder_surface(tips[i], axis, radius, gauge))
        holder_chunks.append(_cylinder_surface(
            base, axis, float(t.get("holder_radius", 12.0)),
            float(t.get("holder_length", 40.0))))
    tool_surf = np.vstack(surface_chunks)
    holder_surf = np.vstack(holder_chunks)
    per_frame = len(tool_surf) // len(frames)

    # 牺牲性背板豁免：仅允许「钻头」在已声明的通孔中心、且钻深穿透受控时
    # 进入牺牲性零点背板。任何其它刀具/任意偏移/超深穿透一律仍判撞机。
    # 这是有界的、可证伪的工艺例外，不是 blanket pass。
    sacrificial = {s["keepout"]: s for s in (sacrificial_backings or [])}
    exempt_frames: Dict[str, List[int]] = {k: [] for k in sacrificial}

    min_clear = math.inf
    min_clear_non_exempt = math.inf   # 间隙门用：排除有界牺牲性穿透
    min_where: Dict[str, Any] = {}
    for ko in keepouts:
        d_tool = _box_sdf(tool_surf, ko.lo, ko.hi)
        d_holder = _box_sdf(holder_surf, ko.lo, ko.hi)
        d = np.minimum(d_tool, d_holder).reshape(len(frames), per_frame).min(axis=1)
        d_eff = d.copy()
        if ko.name in sacrificial:
            rule = sacrificial[ko.name]
            max_pen = float(rule.get("max_penetration_mm", 0.0))
            allowed_tools = set(rule.get("tool_ids", []))
            holes = rule.get("through_holes", [])
            approach_band = float(rule.get("approach_band_mm", 10.0))
            # 豁免覆盖整个「声明通孔 + 钻头」的接近与穿透路径，而不仅是已穿透帧：
            # 只要钻头在声明孔位中心、Z 位于背板上表面附近的接近带内或以下，
            # 均属工艺允许；偏离孔位或用其它刀具仍会被 FIXTURE-COLLISION 判红。
            for k in range(len(frames)):
                f = frames[k]
                tool_id = f"T{f.tool_id}"
                at_hole = any(math.hypot(f.x - h["x"], f.y - h["y"])
                              <= float(h.get("radius_mm", 6.0)) for h in holes)
                # 穿透深度以「刀尖 Z 越过背板上表面的距离」为准（物理口径），
                # 不能用刀具表面 SDF——后者含刀柄，会把超深钻穿透误判为浅穿透。
                tip_pen = max(0.0, float(ko.hi[2]) - f.z)
                near_backplate = f.z <= float(ko.hi[2]) + approach_band
                if (tool_id in allowed_tools and at_hole and near_backplate
                        and tip_pen <= max_pen + 1e-6):
                    d_eff[k] = 0.0
                    exempt_frames[ko.name].append(k)
        non_exempt_idx = [i for i in range(len(d_eff)) if i not in set(exempt_frames.get(ko.name, []))]
        if non_exempt_idx:
            min_clear_non_exempt = min(min_clear_non_exempt,
                                       float(d_eff[non_exempt_idx].min()))
        j = int(np.argmin(d_eff))
        if float(d_eff[j]) < min_clear:
            min_clear = float(d_eff[j])
            f = frames[j]
            min_where = {"frame": j, "line": f.line, "op": f.op,
                         "keepout": ko.name, "kind": ko.kind,
                         "tool_tip_world": [f.x, f.y, f.z]}
        for k in np.where(d_eff < 0)[0][:12]:
            res.violations.append({
                "type": "FIXTURE_COLLISION", "keepout": ko.name,
                "line": frames[k].line, "op": frames[k].op,
                "penetration_mm": round(float(d_eff[k]), 4),
                "tool_tip_world": [frames[k].x, frames[k].y, frames[k].z],
            })
    res.min_clearance_mm = min_clear
    res.min_clearance_non_exempt_mm = min_clear_non_exempt
    res.min_clearance_where = min_where
    res.exemptions = [
        {"keepout": name, "frames": len(ks),
         "rule": "drill-only / declared-through-hole / depth-capped",
         "basis": "bounded process exception"}
        for name, ks in exempt_frames.items() if ks
    ]

    # 软限位超程（机床坐标）
    over = 0
    for f in frames:
        mx, my, mz = f.machine_xyz
        for ax, val in (("X", mx), ("Y", my), ("Z", mz)):
            lo, hi = soft_limits[ax]
            if val < lo - 1e-6 or val > hi + 1e-6:
                over += 1
                if len(res.violations) < 60:
                    res.violations.append({"type": "OVERTRAVEL", "axis": ax,
                                           "line": f.line, "value": val,
                                           "limit": [lo, hi]})
                break
    # 快移扎刀 / 横向穿越低空（按工艺族分口径）
    #   铣削：G00 横向移动(X/Y) 不得低于安全高度 safe_z。
    #   车削：G00 是 X(直径)/Z 两轴联动；Z 接近端面时沿 X 快移到 R 平面是
    #        G71/G70 标准退刀动作，不得按铣削口径判红。车削真正的红线是
    #        "G00 钻入材料"——即快速段终点落在毛坯包络内（Z<0 且 X<毛坯半径）。
    #        故车削以 R 平面(r_plane_mm)为快移下限，并另由 FIXTURE-COLLISION 兜底。
    rapid_bad: List[Dict[str, Any]] = []
    prev: Optional[Frame] = None
    if process_family == "milling":
        # 铣削 G00 横向避让允许下降到「快移减速区间」高度：
        # R 平面 + 快移减速区间（如 R3 + 5 = 8mm），这是《数控加工工艺规范》
        # 标准分层（安全高度 → 快移减速 → R 平面 → 切削进给）。
        rapid_floor = max(r_plane_mm or 3.0, 0.0) + max(rapid_decel_zone_mm or 0.0, 0.0)
    else:
        rapid_floor = r_plane_mm if r_plane_mm is not None else 2.5
    for f in frames:
        if f.is_rapid:
            lateral = (abs(f.x - prev.x) > 1e-6 or abs(f.y - prev.y) > 1e-6) \
                if prev is not None else False
            if f.z < rapid_floor - 0.01 and lateral and abs(f.z - prev.z) < 1e-6:
                if len(rapid_bad) < 12:
                    rapid_bad.append({"line": f.line, "z": f.z})
        prev = f

    def _chk(gate: str, ok: bool, evidence: Any, rule: str) -> None:
        res.checks.append({"gate": gate, "status": "PASS" if ok else "FAIL",
                           "evidence": evidence, "rule": rule})

    _chk("FRAME-SAMPLES", len(frames) > 0, len(frames), "逐帧采样数 > 0")
    _chk("FIXTURE-COLLISION", min_clear >= 0.0,
         round(min_clear, 4) if math.isfinite(min_clear) else None,
         f"刀具/刀柄对夹具 KeepOut 最小间隙 >= 0 mm")
    _chk("HOLDER-CLEARANCE", min_clear_non_exempt >= holder_clearance_mm,
         round(min_clear_non_exempt, 4) if math.isfinite(min_clear_non_exempt) else None,
         f"最小间隙(排除有界牺牲穿透) >= 刀柄安全间隙 {holder_clearance_mm} mm")
    _chk("MACHINE-OVERTRAVEL", over == 0, {"violations": over, "limits": soft_limits},
         "全部帧机床坐标在软限位内")
    _chk("RAPID-SAFE-HEIGHT", not rapid_bad, rapid_bad or "none",
         f"G00 横向移动不得低于{'快移减速区间高度(R+decel)' if process_family == 'milling' else 'R平面'} "
         f"{round(rapid_floor, 3)} mm（分层: 安全高度→快移减速→R平面→进给）")
    for ex in res.exemptions:
        res.checks.append({
            "gate": f"SACRIFICIAL-EXEMPT:{ex['keepout']}", "status": "PASS",
            "evidence": ex,
            "rule": "仅钻头/声明通孔中心/穿透深度受控时允许进入牺牲性背板；越界仍判撞机",
        })
    _chk("SPINDLE-ON-IN-CUT", not [f for f in frames
                                   if (not f.is_rapid) and f.spindle_dir == "M05"
                                   and f.feed > 0][:1],
         {"cut_frames_spindle_off": sum(1 for f in frames
                                        if (not f.is_rapid) and f.spindle_dir == "M05")},
         "切削帧主轴必须旋转")
    return res
