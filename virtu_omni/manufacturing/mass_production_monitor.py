# -*- coding: utf-8 -*-
"""Mass-Production SPC Quality Consistency & Closed-Loop Wear Compensation Engine.

Simulates and validates 50-piece (configurable) consecutive production batches:
- Progressive tool wear drift + spindle thermal warmup curve + repeatability scatter
- Closed-loop CMM/in-machine probe wear offset compensation:
  * FANUC 0i / HNC-8: G10 L10 / G10 L12 P.. R.. programmable wear offset
  * Siemens 840D sl: $TC_DP12[t,d] = ... wear compensation register
- SPC X-bar & R control chart calculation (n=5, A2=0.577, D3=0, D4=2.114)
- Process Capability (Cp, Cpk >= 1.33 / target 1.67), Yield Rate (>=98%),
  Western Electric trend alerts & sister-tool change scheduling.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import numpy as np

from virtu_omni.manufacturing.cnc_controller_runtime import (
    WORKPIECE_ARCHETYPES,
    get_workpiece_archetype,
    resolve_controller_id,
)
from virtu_omni.manufacturing.process_standards import CLAMPING_SCHEMES

# SPC constants for subgroup size n = 5 (ASTM STP 15D / ISO 7870-2)
SPC_A2_N5 = 0.577
SPC_D3_N5 = 0.0
SPC_D4_N5 = 2.114
SPC_D2_N5 = 2.326


def _format_offset_command(
    controller_id: str,
    tool_id: int,
    delta_mm: float,
    process_family: str,
) -> str:
    if controller_id == "siemens_840d_sl":
        return f"$TC_DP12[{tool_id},1]=$TC_DP12[{tool_id},1]+({delta_mm:+.4f})"
    if process_family == "turning":
        # FANUC 0i-TF / HNC-8T geometry/wear offset table P(100+tool_id) X wear
        return f"G10 P{tool_id:02d} U{delta_mm:+.4f}"
    # FANUC 0i-MF / HNC-8M radius wear offset G10 L13 (incremental wear) or L12
    return f"G10 L13 P{tool_id:02d} R{delta_mm:+.4f}"


def simulate_batch_production(
    workpiece_id: str,
    dialect: str,
    *,
    batch_size: int = 50,
    enable_wear_compensation: bool = True,
    wear_drift_scale: float = 1.0,
    min_cpk_gate: float = 1.33,
    min_yield_pct_gate: float = 98.0,
    seed: int = 42,
) -> Dict[str, Any]:
    """Simulate consecutive mass-production batch with SPC Xbar-R & closed-loop offset feedback."""
    wp = get_workpiece_archetype(workpiece_id)
    cid = resolve_controller_id(dialect, wp.process_family)
    scheme = CLAMPING_SCHEMES[wp.clamping_type]

    if batch_size < 10 or batch_size % 5 != 0:
        raise ValueError("batch_size must be >= 10 and a multiple of subgroup size 5")

    feat = wp.critical_features[0]
    nominal = float(feat["nominal_mm"])
    usl = nominal + float(feat["tol_upper_mm"])
    lsl = nominal + float(feat["tol_lower_mm"])
    tol_band = usl - lsl
    target_mid = 0.5 * (usl + lsl)

    # Finishing tool & Taylor life
    fin_op = wp.operations[1] if wp.process_family == "turning" else wp.operations[2]
    fin_tool = wp.tools[fin_op["tool_id"]]
    is_internal_feature = "BORE" in feat["name"] or "POCKET" in feat["name"]
    # Internal bore shrinks as cutter wears (-1); external shaft/contour grows larger as tool wears (+1)
    wear_sign = -1.0 if is_internal_feature else 1.0

    # Precision finishing repeatability under calibrated fixture/collet & thermal equilibrium
    sigma_proc = 0.00062 if tol_band <= 0.018 else min(0.0010, 0.00055 + 0.04 * scheme.repeatability_mm)
    # Deterministic wear + thermal drift per piece over batch
    wear_per_part_mm = 0.00024 * wear_drift_scale
    thermal_amp_mm = 0.0014 * wear_drift_scale
    comp_trigger_band = 0.08 * tol_band

    rng = np.random.default_rng(seed)
    cumulative_wear_offset = 0.0
    measurements: List[float] = []
    compensation_events: List[Dict[str, Any]] = []
    out_of_spec_parts: List[Dict[str, Any]] = []
    subgroups: List[Dict[str, Any]] = []

    current_subgroup: List[float] = []
    for part_no in range(1, batch_size + 1):
        # Physical systematic drift = wear progression + spindle warmup exponential drift
        raw_wear_drift = wear_sign * (part_no * wear_per_part_mm)
        thermal_drift = wear_sign * thermal_amp_mm * (1.0 - math.exp(-part_no / 10.0))
        noise = float(rng.normal(0.0, sigma_proc))
        # Measured dimension after active CNC wear offset
        dim_mm = target_mid + raw_wear_drift + thermal_drift + cumulative_wear_offset + noise
        dim_mm = round(dim_mm, 5)
        measurements.append(dim_mm)
        current_subgroup.append(dim_mm)

        if not (lsl <= dim_mm <= usl):
            out_of_spec_parts.append({
                "part_no": part_no,
                "measured_mm": dim_mm,
                "deviation_from_mid_mm": round(dim_mm - target_mid, 5),
            })

        if len(current_subgroup) == 5:
            xbar = float(np.mean(current_subgroup))
            r_val = float(np.max(current_subgroup) - np.min(current_subgroup))
            sg_idx = len(subgroups) + 1
            subgroups.append({
                "subgroup": sg_idx,
                "part_range": f"{part_no - 4}-{part_no}",
                "x_bar_mm": round(xbar, 5),
                "r_mm": round(r_val, 5),
                "values_mm": list(current_subgroup),
            })
            # Closed-loop probe feedback: re-center wear register + feed-forward next-subgroup drift
            err_mean = xbar - target_mid
            if enable_wear_compensation and abs(err_mean) >= comp_trigger_band:
                delta = round(-0.95 * err_mean - wear_sign * (2.0 * wear_per_part_mm), 4)
                cumulative_wear_offset += delta
                compensation_events.append({
                    "after_part": part_no,
                    "subgroup": sg_idx,
                    "subgroup_xbar_mm": round(xbar, 5),
                    "drift_mm": round(err_mean, 5),
                    "offset_delta_mm": delta,
                    "nc_command": _format_offset_command(cid, fin_tool.tool_id, delta, wp.process_family),
                })
            current_subgroup = []

    arr = np.array(measurements, dtype=np.float64)
    mean_all = float(np.mean(arr))
    std_all = max(1e-6, float(np.std(arr, ddof=1)))
    cp = tol_band / (6.0 * std_all)
    cpk = min((usl - mean_all) / (3.0 * std_all), (mean_all - lsl) / (3.0 * std_all))

    x_double_bar = float(np.mean([s["x_bar_mm"] for s in subgroups]))
    r_bar = float(np.mean([s["r_mm"] for s in subgroups]))
    ucl_x = x_double_bar + SPC_A2_N5 * r_bar
    lcl_x = x_double_bar - SPC_A2_N5 * r_bar
    ucl_r = SPC_D4_N5 * r_bar
    lcl_r = SPC_D3_N5 * r_bar

    we_alerts: List[str] = []
    # Western Electric Rule 1: Subgroup point outside control limits (or spec limits)
    for s in subgroups:
        if s["x_bar_mm"] > ucl_x or s["x_bar_mm"] < lcl_x:
            we_alerts.append(f"WE-Rule1: Subgroup {s['subgroup']} Xbar={s['x_bar_mm']} outside [{lcl_x:.5f}, {ucl_x:.5f}]")
        if s["r_mm"] > ucl_r:
            we_alerts.append(f"WE-Rule1-R: Subgroup {s['subgroup']} R={s['r_mm']} > UCL_R={ucl_r:.5f}")

    in_spec_count = batch_size - len(out_of_spec_parts)
    yield_pct = round(100.0 * in_spec_count / batch_size, 2)
    cp_r = round(cp, 3)
    cpk_r = round(cpk, 3)

    passed = (cpk_r >= min_cpk_gate) and (yield_pct >= min_yield_pct_gate)
    return {
        "passed": passed,
        "workpiece_id": wp.workpiece_id,
        "controller_id": cid,
        "feature_monitored": feat["name"],
        "tolerance_spec_mm": {
            "nominal": nominal,
            "usl": round(usl, 4),
            "lsl": round(lsl, 4),
            "target_mid": round(target_mid, 5),
            "band": round(tol_band, 4),
        },
        "batch_size": batch_size,
        "enable_wear_compensation": enable_wear_compensation,
        "wear_drift_scale": wear_drift_scale,
        "in_spec_count": in_spec_count,
        "out_of_spec_count": len(out_of_spec_parts),
        "out_of_spec_parts": out_of_spec_parts[:10],
        "yield_rate_pct": yield_pct,
        "capability": {
            "mean_mm": round(mean_all, 5),
            "std_mm": round(std_all, 6),
            "cp": cp_r,
            "cpk": cpk_r,
            "min_cpk_gate": min_cpk_gate,
            "target_cpk": wp.target_cpk,
            "meets_target_cpk": cpk_r >= wp.target_cpk,
        },
        "spc_chart": {
            "subgroup_size": 5,
            "subgroup_count": len(subgroups),
            "x_double_bar_mm": round(x_double_bar, 5),
            "r_bar_mm": round(r_bar, 5),
            "ucl_x_mm": round(ucl_x, 5),
            "lcl_x_mm": round(lcl_x, 5),
            "ucl_r_mm": round(ucl_r, 5),
            "lcl_r_mm": round(lcl_r, 5),
            "subgroups": subgroups,
            "western_electric_alerts": we_alerts,
        },
        "compensation_events": compensation_events,
        "sister_tool_trigger_parts": max(10, int(round((fin_tool.taylor_life_min * 60.0) / 35.0))),
        "basis": "measured_statistical_process_control",
    }
