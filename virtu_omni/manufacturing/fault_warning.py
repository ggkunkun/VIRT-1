# -*- coding: utf-8 -*-
"""Industrial CNC Fault Warning & Early Interlock Engine.

Provides three closed-loop mass-production fault detectors:
1. Tool Wear Warning (Taylor life exhaustion + ISO 3685 VB flank wear + load growth)
2. Collision Risk Warning (swept tool/holder vs chuck/vise/fixture keep-outs + G00 plunge)
3. Out-of-Tolerance Warning (Kienzle cutting force + cantilever deflection + thermal/wear vs IT band)
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple

from virtu_omni.manufacturing.cnc_controller_runtime import KeepOutBox, ToolSpec
from virtu_omni.manufacturing.process_standards import get_material_spec

WarningLevel = Literal["NORMAL", "WARN", "CRITICAL"]


@dataclass
class FaultWarningResult:
    channel: Literal["TOOL_WEAR", "COLLISION_RISK", "TOLERANCE_DRIFT"]
    level: WarningLevel
    code: str
    message: str
    metric_value: float
    threshold_warn: float
    threshold_critical: float
    recommended_action: str


# ---------------------------------------------------------------------------
# 1. Tool Wear Warning (Taylor Life + ISO 3685 Flank Wear VB)
# ---------------------------------------------------------------------------

def evaluate_tool_wear(
    tool: ToolSpec,
    cumulative_cut_s: float,
    *,
    vb_limit_mm: float = 0.30,
    vc_actual_m_min: Optional[float] = None,
    taylor_life_min: Optional[float] = None,
) -> Dict[str, Any]:
    """Evaluate tool wear progression and trigger WARN (>=80% / VB>=0.20mm) or CRITICAL (>=95% / VB>=0.28mm)."""
    life_s = max(60.0, float(taylor_life_min or tool.taylor_life_min) * 60.0)
    wear_ratio = max(0.0, float(cumulative_cut_s) / life_s)
    # Typical progressive flank wear curve (initial break-in 0.04mm + linear zone up to VB_limit at 100% life)
    if wear_ratio <= 0.0:
        vb_mm = 0.0
    elif wear_ratio < 0.15:
        vb_mm = round(0.04 * (wear_ratio / 0.15), 4)
    elif wear_ratio <= 1.0:
        vb_mm = round(0.04 + (vb_limit_mm - 0.04) * ((wear_ratio - 0.15) / 0.85), 4)
    else:
        vb_mm = round(vb_limit_mm + 0.12 * (wear_ratio - 1.0), 4)

    spindle_load_multiplier = round(1.0 + 1.65 * vb_mm, 3)

    if wear_ratio >= 0.95 or vb_mm >= 0.28:
        level: WarningLevel = "CRITICAL"
        code = "WEAR-CRITICAL-95"
        action = f"立即触发工序末停机换刀/启用备用姐妹刀(T{tool.tool_id:02d}), 禁止继续首件批量切削"
    elif wear_ratio >= 0.80 or vb_mm >= 0.20 or spindle_load_multiplier >= 1.33:
        level = "WARN"
        code = "WEAR-WARN-80"
        action = f"刀具寿命达 {wear_ratio*100:.1f}% (VB={vb_mm:.3f}mm), 预备刀库备刀并执行磨耗偏置复检"
    else:
        level = "NORMAL"
        code = "WEAR-OK"
        action = "刀具处于正常稳定磨损区"

    return {
        "channel": "TOOL_WEAR",
        "tool_id": tool.tool_id,
        "tool_code": tool.code,
        "level": level,
        "code": code,
        "wear_ratio": round(wear_ratio, 4),
        "vb_mm": vb_mm,
        "vb_limit_mm": vb_limit_mm,
        "spindle_load_multiplier": spindle_load_multiplier,
        "remaining_life_s": round(max(0.0, life_s - cumulative_cut_s), 1),
        "recommended_action": action,
        "vc_actual_m_min": vc_actual_m_min,
    }


# ---------------------------------------------------------------------------
# 2. Collision Risk Warning (Swept Cutter/Holder vs Keep-Out & G00 Plunge)
# ---------------------------------------------------------------------------

def _cylinder_box_clearance(
    cx: float,
    cy: float,
    z_bot: float,
    z_top: float,
    radius: float,
    box: KeepOutBox,
) -> float:
    """Exact 3D signed clearance between vertical cylinder and AABB KeepOutBox."""
    # Closest point on AABB XY rectangle to circle center (cx, cy)
    qx = max(box.xmin, min(cx, box.xmax))
    qy = max(box.ymin, min(cy, box.ymax))
    d_xy = math.hypot(cx - qx, cy - qy) - radius
    # Vertical interval distance
    if z_top < box.zmin:
        d_z = box.zmin - z_top
    elif z_bot > box.zmax:
        d_z = z_bot - box.zmax
    else:
        d_z = max(z_bot - box.zmax, box.zmin - z_top)  # negative or zero overlap

    if d_xy <= 0.0 and d_z <= 0.0:
        # Volumetric overlap: return negative signed penetration depth
        return max(d_xy, d_z)
    if d_xy > 0.0 and d_z <= 0.0:
        return d_xy
    if d_z > 0.0 and d_xy <= 0.0:
        return d_z
    return math.hypot(d_xy, d_z)


def evaluate_collision_risk(
    xyz: Tuple[float, float, float],
    tool: ToolSpec,
    keepout_zones: Sequence[KeepOutBox],
    *,
    process_family: str = "milling",
    is_rapid: bool = False,
    stock_top_z: float = 2.0,
    stock_max_od: float = 56.0,
    rapid_decel_zone_mm: float = 5.0,
    near_miss_threshold_mm: float = 2.0,
    prev_xyz: Optional[Tuple[float, float, float]] = None,
    stock_xy_bounds: Optional[Tuple[float, float, float, float]] = None,
    local_surface_limit: Optional[float] = None,
) -> Dict[str, Any]:
    """Check physical interference for cutter, shank & holder plus G00 plunge check."""
    x, y, z = xyz
    r_cut = tool.diameter_mm * 0.5
    r_holder = tool.holder_diameter_mm * 0.5
    flute_top = z + tool.flute_length_mm
    holder_top = z + tool.gauge_length_mm

    # Turning lathe: tool approaches radially in X (diameter programmed!), chuck jaw occupies Z <= -60
    if process_family == "turning":
        r_pt = x * 0.5
        min_clr = float("inf")
        closest_zone = "none"
        for box in keepout_zones:
            tool_z_left = z - (tool.diameter_mm * 0.25)
            d_z = tool_z_left - box.zmax if tool_z_left > box.zmax else (box.zmin - z if z < box.zmin else tool_z_left - box.zmax)
            if r_pt < box.xmax:
                clr = d_z
            else:
                clr = math.hypot(max(0.0, d_z), r_pt - box.xmax) if d_z > 0 else (r_pt - box.xmax)
            if clr < min_clr:
                min_clr = clr
                closest_zone = box.name
        eff_od = local_surface_limit if local_surface_limit is not None else stock_max_od
        if prev_xyz is not None:
            dx_in = x - prev_xyz[0]
            dz_in = z - prev_xyz[2]
            approaching = (dx_in < -0.05) or (dz_in < -0.05)
        else:
            approaching = True
        g00_plunge = is_rapid and approaching and (z < 0.0 and x < eff_od - 0.2)
    else:
        min_clr = float("inf")
        closest_zone = "none"
        for box in keepout_zones:
            c_cut = _cylinder_box_clearance(x, y, z, flute_top, r_cut, box)
            c_hold = _cylinder_box_clearance(x, y, flute_top, holder_top, r_holder, box)
            clr = min(c_cut, c_hold)
            if clr < min_clr:
                min_clr = clr
                closest_zone = box.name
        eff_top = local_surface_limit if local_surface_limit is not None else stock_top_z
        if prev_xyz is not None:
            moving_down = (z - prev_xyz[2]) < -0.05
        else:
            moving_down = True
        if stock_xy_bounds is not None:
            s_xmin, s_xmax, s_ymin, s_ymax = stock_xy_bounds
            in_stock_xy = (
                (s_xmin - r_cut + 0.1) <= x <= (s_xmax + r_cut - 0.1)
                and (s_ymin - r_cut + 0.1) <= y <= (s_ymax + r_cut - 0.1)
            )
        else:
            in_stock_xy = True
        g00_plunge = is_rapid and moving_down and in_stock_xy and (z < eff_top - 0.5)

    if not math.isfinite(min_clr):
        min_clr = 999.0

    if g00_plunge:
        return {
            "channel": "COLLISION_RISK",
            "level": "CRITICAL",
            "code": "COLLISION-G00-PLUNGE",
            "min_clearance_mm": round(min_clr, 3),
            "closest_zone": closest_zone,
            "g00_plunge_detected": True,
            "recommended_action": "检测到G00快速下刀/越过快移减速区间直接进入毛坯区, 立即E-STOP并改为G01进给接近!",
        }

    if min_clr <= 0.0:
        return {
            "channel": "COLLISION_RISK",
            "level": "CRITICAL",
            "code": "COLLISION-KEEPOUT-INTERFERENCE",
            "min_clearance_mm": round(min_clr, 3),
            "closest_zone": closest_zone,
            "g00_plunge_detected": False,
            "recommended_action": f"刀具/刀柄与装夹禁区 {closest_zone} 发生干涉 ({min_clr:.3f}mm), 立即触发急停与抬刀退避!",
        }

    if min_clr < near_miss_threshold_mm:
        return {
            "channel": "COLLISION_RISK",
            "level": "WARN",
            "code": "COLLISION-NEAR-MISS",
            "min_clearance_mm": round(min_clr, 3),
            "closest_zone": closest_zone,
            "g00_plunge_detected": False,
            "recommended_action": f"距禁区 {closest_zone} 最小间隙仅 {min_clr:.3f}mm (<{near_miss_threshold_mm:.1f}mm), 建议核查避让路径/换用长颈刀柄",
        }

    return {
        "channel": "COLLISION_RISK",
        "level": "NORMAL",
        "code": "COLLISION-CLEAR",
        "min_clearance_mm": round(min_clr, 3),
        "closest_zone": closest_zone,
        "g00_plunge_detected": False,
        "recommended_action": "避让间隙充裕, 无碰撞干涉风险",
    }


# ---------------------------------------------------------------------------
# 3. Out-of-Tolerance Risk Warning (Force Deflection + Wear + Thermal Drift)
# ---------------------------------------------------------------------------

def evaluate_tolerance_risk(
    material_id: str,
    tool: ToolSpec,
    *,
    ap_mm: float,
    feed_per_tooth_or_rev_mm: float,
    tolerance_band_mm: float = 0.030,
    vb_mm: float = 0.05,
    overhang_mm: Optional[float] = None,
    thermal_drift_mm: float = 0.002,
) -> Dict[str, Any]:
    """Compute Kienzle cutting force, cantilever deflection & predict IT tolerance conformance."""
    mat = get_material_spec(material_id)
    h = max(0.02, float(feed_per_tooth_or_rev_mm))
    ap = max(0.05, float(ap_mm))
    # Kienzle Fc = kc1.1 * ap * h^(1 - mc), with mc=0.25 typical, magnified by flank wear
    kc = mat.specific_cutting_force_kc11_mpa * (h ** (-0.25)) * (1.0 + 1.5 * vb_mm)
    fc_n = round(kc * ap * h, 1)
    fr_n = round(0.45 * fc_n, 1)  # radial deflection force component

    # Beam overhang & stiffness
    is_turning = tool.category.startswith("turn_")
    d_beam = tool.shank_diameter_mm if is_turning else max(4.0, tool.diameter_mm * 0.85)
    e_gpa = 210.0 if is_turning or tool.diameter_mm >= 40.0 else 580.0
    l_over = float(overhang_mm or (45.0 if is_turning else max(24.0, tool.flute_length_mm * 1.15)))
    i_mm4 = (math.pi * (d_beam ** 4)) / 64.0
    # E in N/mm^2 (= MPa = GPa * 1000)
    deflection_mm = (fr_n * (l_over ** 3)) / (3.0 * (e_gpa * 1000.0) * max(1.0, i_mm4))

    # Effective half-tolerance (bilateral error budget around nominal center)
    half_tol = max(0.004, abs(tolerance_band_mm) * 0.5)
    # Note flank wear shifts finish surface outward by ~0.10 * vb (partially compensated if monitored),
    # while spring-pass finishing sees small ap (<=0.25mm) and low fz
    wear_uncomp_mm = max(0.0, (vb_mm - 0.10) * 0.05) if vb_mm > 0.10 else 0.0
    predicted_error_mm = round(deflection_mm + wear_uncomp_mm + abs(thermal_drift_mm), 5)
    tol_usage_ratio = round(predicted_error_mm / half_tol, 4)

    if tol_usage_ratio >= 0.90:
        level: WarningLevel = "CRITICAL"
        code = "TOL-CRITICAL-OUT-OF-SPEC"
        action = f"预测误差 {predicted_error_mm:.4f}mm 达公差半带 {half_tol:.4f}mm 的 {tol_usage_ratio*100:.1f}%, 立即减半切深 ap 并启用精光/补偿"
    elif tol_usage_ratio >= 0.70:
        level = "WARN"
        code = "TOL-WARN-DRIFT"
        action = f"公差占用率达 {tol_usage_ratio*100:.1f}%, 建议增加无火花弹簧光刀(Spring Pass)或微调G10偏置"
    else:
        level = "NORMAL"
        code = "TOL-OK"
        action = "加工变形与热漂移在公差受控范围内"

    return {
        "channel": "TOLERANCE_DRIFT",
        "level": level,
        "code": code,
        "cutting_force_fc_n": fc_n,
        "radial_force_fr_n": fr_n,
        "deflection_mm": round(deflection_mm, 5),
        "predicted_error_mm": predicted_error_mm,
        "half_tolerance_mm": round(half_tol, 4),
        "tolerance_usage_ratio": tol_usage_ratio,
        "recommended_action": action,
    }


def evaluate_frame_fault_status(
    *,
    material_id: str,
    tool: ToolSpec,
    xyz: Tuple[float, float, float],
    keepout_zones: Sequence[KeepOutBox],
    cumulative_cut_s: float,
    process_family: str,
    is_rapid: bool,
    is_cutting_zone: bool,
    ap_mm: float,
    feed_per_unit_mm: float,
    tolerance_band_mm: float = 0.030,
    stock_top_z: float = 2.0,
    is_finishing: bool = True,
    prev_xyz: Optional[Tuple[float, float, float]] = None,
    stock_xy_bounds: Optional[Tuple[float, float, float, float]] = None,
    local_surface_limit: Optional[float] = None,
    roughing_allowance_mm: float = 0.40,
) -> Dict[str, Any]:
    """Run all 3 industrial fault-warning channels on a simulation frame."""
    wear = evaluate_tool_wear(tool, cumulative_cut_s)
    coll = evaluate_collision_risk(
        xyz, tool, keepout_zones,
        process_family=process_family,
        is_rapid=is_rapid,
        stock_top_z=stock_top_z,
        prev_xyz=prev_xyz,
        stock_xy_bounds=stock_xy_bounds,
        local_surface_limit=local_surface_limit,
    )
    eff_tol_band = tolerance_band_mm if is_finishing else max(tolerance_band_mm, roughing_allowance_mm * 2.0)
    tol = evaluate_tolerance_risk(
        material_id, tool,
        ap_mm=(ap_mm if is_cutting_zone else 0.05),
        feed_per_tooth_or_rev_mm=feed_per_unit_mm,
        tolerance_band_mm=eff_tol_band,
        vb_mm=wear["vb_mm"],
    )
    rank = {"NORMAL": 0, "WARN": 1, "CRITICAL": 2}
    worst = max([wear, coll, tol], key=lambda x: rank[x["level"]])
    return {
        "overall_level": worst["level"],
        "wear": wear,
        "collision": coll,
        "tolerance": tol,
    }
