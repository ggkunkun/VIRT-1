# -*- coding: utf-8 -*-
"""Frame-by-Frame Kinematic, Voxel Material-Removal & Auto-Diff CNC Simulator.

Couples ``CNCPanelController`` motion blocks with:
1. Sub-millimeter frame interpolation (G00/G01 linear + G02/G03 circular arcs)
2. True G41/G42 cutter radius compensation offset geometry
3. Real-time fault warnings per frame (tool wear, collision risk, tolerance drift)
4. Dexel/Radial material-removal Auto-Diff audit (Gouge Red / Excess Blue / Green)
5. Single-OP & total takt cycle-time + air-cut ratio telemetry
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from virtu_omni.manufacturing.cnc_controller_runtime import (
    CNCPanelController,
    MotionSegment,
    ToolSpec,
    WorkpieceArchetype,
    get_workpiece_archetype,
    resolve_controller_id,
)
from virtu_omni.manufacturing.fault_warning import evaluate_frame_fault_status


@dataclass
class SimFrame:
    frame_id: int
    line_no: int
    op_id: int
    time_s: float
    dt_s: float
    motion_mode: str
    wcs_xyz: Tuple[float, float, float]
    compensated_xyz: Tuple[float, float, float]
    spindle_rpm: float
    feed_mm_min: float
    tool_id: int
    comp_length: str
    comp_radius: str
    min_clearance_mm: float
    cutting_force_n: float
    deflection_mm: float
    vb_mm: float
    fault_level: str
    collision_code: str


def _unit_perp_left(dx: float, dy: float) -> Tuple[float, float]:
    n = math.hypot(dx, dy)
    if n < 1e-9:
        return (0.0, 0.0)
    return (-dy / n, dx / n)


def _apply_cutter_comp_paths(
    segments: List[MotionSegment],
    tools: Dict[int, ToolSpec],
    process_family: str,
) -> List[Dict[str, Any]]:
    """Compute true compensated XY tool-center waypoints for G41/G42 in milling."""
    out: List[Dict[str, Any]] = []
    n_seg = len(segments)

    def _seg_dir_start(seg: MotionSegment) -> Tuple[float, float]:
        if seg.motion_mode in ("G02", "G03") and (seg.arc_center_offset_ij[0] != 0.0 or seg.arc_center_offset_ij[1] != 0.0):
            rx, ry = -seg.arc_center_offset_ij[0], -seg.arc_center_offset_ij[1]
            return (-ry, rx) if seg.motion_mode == "G03" else (ry, -rx)
        return (seg.end_wcs[0] - seg.start_wcs[0], seg.end_wcs[1] - seg.start_wcs[1])

    def _seg_dir_end(seg: MotionSegment) -> Tuple[float, float]:
        if seg.motion_mode in ("G02", "G03") and (seg.arc_center_offset_ij[0] != 0.0 or seg.arc_center_offset_ij[1] != 0.0):
            # Full circle ends with same tangent as start
            cx = seg.start_wcs[0] + seg.arc_center_offset_ij[0]
            cy = seg.start_wcs[1] + seg.arc_center_offset_ij[1]
            rx, ry = seg.end_wcs[0] - cx, seg.end_wcs[1] - cy
            return (-ry, rx) if seg.motion_mode == "G03" else (ry, -rx)
        return (seg.end_wcs[0] - seg.start_wcs[0], seg.end_wcs[1] - seg.start_wcs[1])

    for i, seg in enumerate(segments):
        sx, sy, sz = seg.start_wcs
        ex, ey, ez = seg.end_wcs
        t = tools.get(seg.tool_id)
        r_comp = (t.d_radius_mm if (t and seg.d_offset_id > 0) else 0.0) if process_family == "milling" else 0.0
        sign = 1.0 if seg.comp_radius == "G41" else (-1.0 if seg.comp_radius == "G42" else 0.0)

        csx, csy = sx, sy
        cex, cey = ex, ey
        arc_cx = sx + seg.arc_center_offset_ij[0]
        arc_cy = sy + seg.arc_center_offset_ij[1]

        if process_family == "milling" and r_comp > 0.0:
            # Determine offset at segment start (if previously in comp or ramping on)
            prev_in_comp = (i > 0 and segments[i - 1].comp_radius in ("G41", "G42") and segments[i - 1].op_id == seg.op_id)
            if prev_in_comp:
                pdx, pdy = _seg_dir_end(segments[i - 1])
                px, py = _unit_perp_left(pdx, pdy)
                ps = 1.0 if segments[i - 1].comp_radius == "G41" else -1.0
                csx = sx + ps * r_comp * px
                csy = sy + ps * r_comp * py

            if sign != 0.0:
                if seg.motion_mode in ("G02", "G03") and (seg.arc_center_offset_ij[0] != 0.0 or seg.arc_center_offset_ij[1] != 0.0):
                    # Arc offset: maintain concentric arc center!
                    dx_s, dy_s = _seg_dir_start(seg)
                    ux, uy = _unit_perp_left(dx_s, dy_s)
                    csx = sx + sign * r_comp * ux
                    csy = sy + sign * r_comp * uy
                    dx_e, dy_e = _seg_dir_end(seg)
                    vx, vy = _unit_perp_left(dx_e, dy_e)
                    cex = ex + sign * r_comp * vx
                    cey = ey + sign * r_comp * vy
                elif not prev_in_comp and (i + 1) < n_seg and segments[i + 1].comp_radius == seg.comp_radius:
                    # Ramp-on move: align endpoint to normal of NEXT contour move!
                    ndx, ndy = _seg_dir_start(segments[i + 1])
                    ux, uy = _unit_perp_left(ndx, ndy)
                    cex = ex + sign * r_comp * ux
                    cey = ey + sign * r_comp * uy
                else:
                    dx, dy = _seg_dir_end(seg)
                    ux, uy = _unit_perp_left(dx, dy)
                    if not prev_in_comp:
                        csx, csy = sx, sy
                    cex = ex + sign * r_comp * ux
                    cey = ey + sign * r_comp * uy
            # Ramp-off (G40 cancel): cex, cey returns cleanly to uncompensated (ex, ey)!

        out.append({
            "seg": seg,
            "comp_start": (csx, csy, sz),
            "comp_end": (cex, cey, ez),
            "arc_center": (arc_cx, arc_cy),
        })
    return out


# ---------------------------------------------------------------------------
# Milling & Turning Target Surface Definitions for Real Auto-Diff Comparison
# ---------------------------------------------------------------------------

def _milling_target_floor(wp: WorkpieceArchetype, X: np.ndarray, Y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Return (z_target, machined_mask) for finished part vs stock."""
    stock = wp.stock_info
    z_top = float(stock["bbox_mm"]["zmax"]) if "bbox_mm" in stock else 2.0
    z_fin = np.zeros_like(X, dtype=np.float64)  # finished top datum Z=0.0

    if wp.workpiece_id == "WP-MANIFOLD-VISE":
        # Finished block [-60,60] x [-45,45]; outside [-60,60]x[-45,45] is cut down to Z=-12.0 (step shoulder)
        inside_part = (np.abs(X) <= 60.0) & (np.abs(Y) <= 45.0)
        z_fin = np.where(inside_part, 0.0, -12.0)
        # Rectangular pocket [-38,38] x [-24,24] depth Z=-8.0 with R5 inner corner radius
        # Inside pocket rectilinear zone
        in_pocket_core = (np.abs(X) <= 38.0) & (np.abs(Y) <= 24.0)
        # Subtract corner fillets (radius 5.0mm from D10 finisher inside +-38, +-24)
        cx = np.maximum(0.0, np.abs(X) - 33.0)
        cy = np.maximum(0.0, np.abs(Y) - 19.0)
        in_pocket = in_pocket_core & ((cx * cx + cy * cy) <= 25.0 + 1e-6)
        z_fin = np.where(in_pocket, -8.0, z_fin)
        # 4 holes at (+-49, +-34.5) radius 3.4..4.0mm depth Z=-16..20
        for hx, hy in ((-49.0, -34.5), (49.0, -34.5), (49.0, 34.5), (-49.0, 34.5)):
            in_h = ((X - hx) ** 2 + (Y - hy) ** 2) <= (4.0 ** 2)
            z_fin = np.where(in_h, -20.0, z_fin)
        # Evaluation mask: inside finished contour +-60 x +-45 + perimeter step
        eval_mask = (np.abs(X) <= 64.0) & (np.abs(Y) <= 49.0)
        return z_fin, eval_mask

    # WP-HOUSING-FIXTURE: top datum at Z=0 except strap clamp corridors (stay stock/unmilled at |X| in [55,85], |Y|<=15)
    z_fin = np.zeros_like(X, dtype=np.float64)
    in_bore = (X ** 2 + Y ** 2) <= (26.0 ** 2 + 1e-6)
    z_fin = np.where(in_bore, -20.0, z_fin)
    for hx, hy in ((-45.0, -38.0), (45.0, -38.0), (45.0, 38.0), (-45.0, 38.0)):
        in_h = ((X - hx) ** 2 + (Y - hy) ** 2) <= (5.5 ** 2 + 1e-6)
        z_fin = np.where(in_h, -48.0, z_fin)
    # Clamp shadows where cutter intentionally avoids clamps (|X|>=50 and |Y|<=17) stay excluded from face target
    clamp_zone = (np.abs(X) >= 48.0) & (np.abs(Y) <= 18.0)
    in_stock = (np.abs(X) <= 72.0) & (np.abs(Y) <= 56.0)
    # Also note face cutter sweeps Y=+-48 (with D63 R=31.5 -> covers |Y| in [16.5, 79.5]) and center corridor |X|<=22,|Y|<=16.5
    covered_region = (np.abs(Y) >= 18.0) | (np.abs(X) <= 45.0)
    eval_mask = in_stock & (~clamp_zone) & covered_region
    return z_fin, eval_mask


def _turning_target_radius(z_arr: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Finished shaft radius profile R(z) for WP-SHAFT-3JAW along Z in [-54.0, 0.0]."""
    r_fin = np.full_like(z_arr, 28.0, dtype=np.float64)
    # Evaluate strictly along turned domain Z in [-53.5, 0.0] (allow chamfer margins)
    mask = (z_arr >= -53.8) & (z_arr <= -0.2)
    for i, z in enumerate(z_arr):
        if z > 0.0:
            r_fin[i] = 0.0
        elif z >= -1.0:
            r_fin[i] = 13.0 + (-z) * 1.0  # 1x45 chamfer 13 -> 14
        elif z >= -15.5:
            r_fin[i] = 14.0
        elif z >= -18.5:
            # 3mm groove tool (width 3mm centered around Z=-17.0..Z=-18.5)
            r_fin[i] = 12.5
        elif z >= -19.0:
            r_fin[i] = 14.0 + (-z - 18.0) * 5.0
        elif z >= -34.0:
            r_fin[i] = 20.0
        elif z >= -35.0:
            r_fin[i] = 24.0 + (-z - 34.0) * 1.0
        elif z >= -54.0:
            r_fin[i] = 25.0
    return r_fin, mask


# ---------------------------------------------------------------------------
# Full Frame-by-Frame Simulator + Auto-Diff Analyzer
# ---------------------------------------------------------------------------

def simulate_program_frames(
    workpiece_id: str,
    dialect: str,
    nc_text: str,
    *,
    frame_step_mm: float = 1.0,
    gouge_tol_mm: float = 0.035,
    excess_tol_mm: float = 0.15,
    capture_frame_limit: int = 4000,
) -> Dict[str, Any]:
    """Simulate NC program frame-by-frame with voxel removal, fault checks & Auto-Diff."""
    wp = get_workpiece_archetype(workpiece_id)
    cid = resolve_controller_id(dialect, wp.process_family)
    ctrl = CNCPanelController(
        cid,
        process_family=wp.process_family,
        tool_table=wp.tools,
        soft_limit_1={
            "X": wp.safety_policy.soft_limit_x_mm,
            "Y": wp.safety_policy.soft_limit_y_mm,
            "Z": wp.safety_policy.soft_limit_z_mm,
        },
    )
    ctrl.load_program(nc_text)
    exec_res = ctrl.execute()
    comp_items = _apply_cutter_comp_paths(ctrl.segments, wp.tools, wp.process_family)

    # Setup voxel/dexel stock grid for real geometric material removal verification
    if wp.process_family == "milling":
        pitch = 1.0
        xs = np.arange(-85.0, 86.0, pitch)
        ys = np.arange(-65.0, 66.0, pitch)
        GX, GY = np.meshgrid(xs, ys, indexing="xy")
        z_stock_top = float(wp.stock_info.get("bbox_mm", {}).get("zmax", 2.5))
        Z_cur = np.full_like(GX, z_stock_top, dtype=np.float64)
        Z_fin, eval_mask = _milling_target_floor(wp, GX, GY)
    else:
        z_bins = np.arange(-55.0, 2.5, 0.25)
        R_cur = np.full_like(z_bins, 28.0, dtype=np.float64)
        R_fin, eval_mask = _turning_target_radius(z_bins)

    frames: List[SimFrame] = []
    op_stats: Dict[int, Dict[str, Any]] = {}
    tool_cut_time: Dict[int, float] = {}
    warnings_list: List[Dict[str, Any]] = []
    critical_events: List[Dict[str, Any]] = []

    t_elapsed = 0.0
    frame_id = 0
    min_clearance_global = 999.0
    max_fc = 0.0
    max_deflect = 0.0
    max_vb = 0.0

    # Map operation cutting ap/feed for force & tolerance checks
    op_cutting_map = {op["op_id"]: op for op in wp.operations}

    for item in comp_items:
        seg: MotionSegment = item["seg"]
        cs = item["comp_start"]
        ce = item["comp_end"]
        ac = item["arc_center"]
        tool = wp.tools.get(seg.tool_id) or next(iter(wp.tools.values()))

        op_s = op_stats.setdefault(seg.op_id, {
            "op_id": seg.op_id,
            "tool_id": tool.tool_id,
            "tool_code": tool.code,
            "total_time_s": 0.0,
            "cutting_time_s": 0.0,
            "rapid_time_s": 0.0,
            "frame_count": 0,
        })
        op_s["total_time_s"] += seg.duration_s
        if seg.is_rapid:
            op_s["rapid_time_s"] += seg.duration_s
        else:
            op_s["cutting_time_s"] += seg.duration_s

        # Determine number of frames at <= frame_step_mm spatial resolution
        is_arc = seg.motion_mode in ("G02", "G03") and (seg.arc_center_offset_ij[0] != 0.0 or seg.arc_center_offset_ij[1] != 0.0)
        if is_arc:
            r_arc = math.hypot(cs[0] - ac[0], cs[1] - ac[1])
            a0 = math.atan2(cs[1] - ac[1], cs[0] - ac[0])
            a1 = math.atan2(ce[1] - ac[1], ce[0] - ac[0])
            da = (a1 - a0)
            if seg.motion_mode == "G03":
                if da <= 1e-6:
                    da += 2.0 * math.pi
            else:
                if da >= -1e-6:
                    da -= 2.0 * math.pi
            arc_len = abs(da) * max(1.0, r_arc)
            n_steps = max(4, min(72, int(math.ceil(arc_len / max(0.5, frame_step_mm)))))
        else:
            dx = (ce[0] - cs[0]) * (0.5 if wp.process_family == "turning" else 1.0)
            dy = ce[1] - cs[1]
            dz = ce[2] - cs[2]
            seg_len = math.sqrt(dx * dx + dy * dy + dz * dz)
            n_steps = max(1, min(60, int(math.ceil(seg_len / max(0.5, frame_step_mm)))))

        dt = seg.duration_s / n_steps if n_steps > 0 else 0.0
        op_meta = op_cutting_map.get(seg.op_id, {})
        ap_nom = float(op_meta.get("doc_mm", 0.5))
        f_unit = float(op_meta.get("cutting", {}).get("fz_mm", op_meta.get("cutting", {}).get("f_rev_mm", 0.1)))
        tol_band = min((f.get("tol_upper_mm", 0.03) - f.get("tol_lower_mm", 0.0) for f in wp.critical_features), default=0.030)

        for k in range(1, n_steps + 1):
            frac = k / n_steps
            if is_arc:
                ang = a0 + da * frac
                px = ac[0] + r_arc * math.cos(ang)
                py = ac[1] + r_arc * math.sin(ang)
                pz = cs[2] + (ce[2] - cs[2]) * frac
                wx = ac[0] + math.hypot(seg.start_wcs[0] - ac[0], seg.start_wcs[1] - ac[1]) * math.cos(ang)
                wy = ac[1] + math.hypot(seg.start_wcs[0] - ac[0], seg.start_wcs[1] - ac[1]) * math.sin(ang)
                wz = pz
            else:
                px = cs[0] + (ce[0] - cs[0]) * frac
                py = cs[1] + (ce[1] - cs[1]) * frac
                pz = cs[2] + (ce[2] - cs[2]) * frac
                wx = seg.start_wcs[0] + (seg.end_wcs[0] - seg.start_wcs[0]) * frac
                wy = seg.start_wcs[1] + (seg.end_wcs[1] - seg.start_wcs[1]) * frac
                wz = seg.start_wcs[2] + (seg.end_wcs[2] - seg.start_wcs[2]) * frac

            t_elapsed += dt
            if not seg.is_rapid and seg.is_cutting_zone:
                tool_cut_time[tool.tool_id] = tool_cut_time.get(tool.tool_id, 0.0) + dt

            # Carve material into voxel / radial grid if spindle active and feed move
            if (not seg.is_rapid) and seg.spindle_dir != "M05":
                if wp.process_family == "milling":
                    r_eff = tool.diameter_mm * 0.5
                    # Bounding subslice for speed (<0.1ms per frame)
                    ix0 = int(max(0, math.floor((px - r_eff + 85.0))))
                    ix1 = int(min(GX.shape[1], math.ceil((px + r_eff + 85.0)) + 1))
                    iy0 = int(max(0, math.floor((py - r_eff + 65.0))))
                    iy1 = int(min(GX.shape[0], math.ceil((py + r_eff + 65.0)) + 1))
                    if ix1 > ix0 and iy1 > iy0:
                        sub_x = GX[iy0:iy1, ix0:ix1]
                        sub_y = GY[iy0:iy1, ix0:ix1]
                        hit = ((sub_x - px) ** 2 + (sub_y - py) ** 2) <= (r_eff ** 2 + 1e-6)
                        sub_z = Z_cur[iy0:iy1, ix0:ix1]
                        sub_z[hit] = np.minimum(sub_z[hit], pz)
                else:
                    # Turning: px is programmed diameter -> radius = px / 2
                    r_tip = max(0.0, px * 0.5)
                    w_nose = 1.5 if tool.category == "turn_groove" else max(0.4, tool.corner_radius_mm)
                    # Note grooving tool has 3.0mm width centered or trailing tool tip; apply tool nose footprint
                    if tool.category == "turn_groove":
                        hit = (z_bins >= pz - 1.55) & (z_bins <= pz + 1.55)
                    else:
                        hit = np.abs(z_bins - pz) <= max(0.3, w_nose)
                    if np.any(hit):
                        R_cur[hit] = np.minimum(R_cur[hit], r_tip)

            # Sample fault status on segment endpoints and periodic frames (every 4th frame or always on cut/rapid-near)
            if k == n_steps or k == 1 or (frame_id % 4 == 0):
                fault = evaluate_frame_fault_status(
                    material_id=wp.material_id,
                    tool=tool,
                    xyz=(px, py, pz),
                    keepout_zones=wp.keepout_zones,
                    cumulative_cut_s=tool_cut_time.get(tool.tool_id, 0.0),
                    process_family=wp.process_family,
                    is_rapid=seg.is_rapid,
                    is_cutting_zone=seg.is_cutting_zone,
                    ap_mm=ap_nom,
                    feed_per_unit_mm=f_unit,
                    tolerance_band_mm=tol_band,
                    stock_top_z=float(wp.stock_info.get("bbox_mm", {}).get("zmax", 2.0)),
                )
                clr = fault["collision"]["min_clearance_mm"]
                min_clearance_global = min(min_clearance_global, clr)
                fc = fault["tolerance"]["cutting_force_fc_n"]
                defl = fault["tolerance"]["deflection_mm"]
                vb = fault["wear"]["vb_mm"]
                max_fc = max(max_fc, fc)
                max_deflect = max(max_deflect, defl)
                max_vb = max(max_vb, vb)

                if fault["overall_level"] == "CRITICAL":
                    critical_events.append({
                        "frame_id": frame_id,
                        "line_no": seg.line_no,
                        "op_id": seg.op_id,
                        "xyz": (round(px, 3), round(py, 3), round(pz, 3)),
                        "fault": fault,
                    })
                elif fault["overall_level"] == "WARN":
                    warnings_list.append({
                        "frame_id": frame_id,
                        "line_no": seg.line_no,
                        "op_id": seg.op_id,
                        "fault": fault["collision"] if fault["collision"]["level"] == "WARN" else fault["tolerance"],
                    })

                if len(frames) < capture_frame_limit:
                    frames.append(SimFrame(
                        frame_id=frame_id,
                        line_no=seg.line_no,
                        op_id=seg.op_id,
                        time_s=round(t_elapsed, 4),
                        dt_s=round(dt, 4),
                        motion_mode=seg.motion_mode,
                        wcs_xyz=(round(wx, 3), round(wy, 3), round(wz, 3)),
                        compensated_xyz=(round(px, 3), round(py, 3), round(pz, 3)),
                        spindle_rpm=seg.spindle_rpm,
                        feed_mm_min=seg.feed_mm_min,
                        tool_id=seg.tool_id,
                        comp_length=seg.comp_length,
                        comp_radius=seg.comp_radius,
                        min_clearance_mm=clr,
                        cutting_force_n=fc,
                        deflection_mm=defl,
                        vb_mm=vb,
                        fault_level=fault["overall_level"],
                        collision_code=fault["collision"]["code"],
                    ))
            frame_id += 1
            op_s["frame_count"] += 1

    # Compute Auto-Diff comparison against true finished geometry
    if wp.process_family == "milling":
        diff = Z_cur[eval_mask] - Z_fin[eval_mask]
    else:
        diff = R_cur[eval_mask] - R_fin[eval_mask]
    total_pts = max(1, int(diff.size))
    # diff < -gouge_tol_mm => RED (gouge); diff > excess_tol_mm => BLUE (excess)
    red_pts = int(np.sum(diff < -gouge_tol_mm))
    blue_pts = int(np.sum(diff > excess_tol_mm))
    green_pts = total_pts - red_pts - blue_pts

    red_pct = round(100.0 * red_pts / total_pts, 3)
    blue_pct = round(100.0 * blue_pts / total_pts, 3)
    green_pct = round(100.0 * green_pts / total_pts, 3)
    max_gouge_mm = round(float(max(0.0, -np.min(diff))), 4) if diff.size else 0.0
    max_excess_mm = round(float(max(0.0, np.max(diff))), 4) if diff.size else 0.0

    autodiff_passed = (red_pts == 0 and green_pct >= 96.0)
    collision_free = (len(critical_events) == 0 and min_clearance_global > 0.0)
    controller_alarm_free = (exec_res["alarm_count"] == 0)

    total_cycle_s = round(t_elapsed, 2)
    op_breakdown = []
    for oid in sorted(op_stats):
        st_o = op_stats[oid]
        tot = round(st_o["total_time_s"], 2)
        cut = round(st_o["cutting_time_s"], 2)
        rap = round(st_o["rapid_time_s"], 2)
        op_breakdown.append({
            "op_id": oid,
            "tool_id": st_o["tool_id"],
            "tool_code": st_o["tool_code"],
            "total_time_s": tot,
            "cutting_time_s": cut,
            "rapid_time_s": rap,
            "cutting_duty_pct": round(100.0 * cut / max(0.01, tot), 1),
            "frames": st_o["frame_count"],
        })

    passed = autodiff_passed and collision_free and controller_alarm_free
    return {
        "passed": passed,
        "workpiece_id": wp.workpiece_id,
        "controller_id": cid,
        "vericut_ctl_file": ctrl.profile.vericut_ctl_file,
        "total_frames_evaluated": frame_id,
        "captured_frames_count": len(frames),
        "sample_frames": [asdict(f) for f in frames[:20]],
        "collision_free": collision_free,
        "min_clearance_mm": round(min_clearance_global, 3),
        "critical_fault_count": len(critical_events),
        "critical_faults": critical_events[:10],
        "warning_count": len(warnings_list),
        "controller_alarms": exec_res["alarms"],
        "autodiff_metrics": {
            "red_gouge_pct": red_pct,
            "blue_excess_pct": blue_pct,
            "green_in_tol_pct": green_pct,
            "max_gouge_mm": max_gouge_mm,
            "max_excess_mm": max_excess_mm,
            "evaluated_dexels": total_pts,
            "autodiff_passed": autodiff_passed,
        },
        "physics_peaks": {
            "max_cutting_force_n": round(max_fc, 1),
            "max_deflection_mm": round(max_deflect, 5),
            "max_flank_vb_mm": round(max_vb, 4),
        },
        "cycle_time": {
            "total_cycle_s": total_cycle_s,
            "takt_target_s": wp.takt_target_s,
            "takt_compliant": total_cycle_s <= wp.takt_target_s,
            "op_breakdown": op_breakdown,
        },
        "basis": "measured_frame_voxel_simulation",
    }
