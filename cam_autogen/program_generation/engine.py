"""M3 加工程序自动生成引擎。

只依赖 ``cam_autogen.contracts``，不 import 其他模块。
"""
from __future__ import annotations

import hashlib
import math
from typing import Any, Dict, List, Optional

from cam_autogen.contracts import Move, NCProgram, PostProfile, ProcessPlan, ProcessType, StockSetup
from cam_autogen.program_generation.postprocessor import render
from cam_autogen.program_generation.toolpath import build_ir

ENGINE_VERSION = "m3-iso-1.0.0"


def default_profile(plan: ProcessPlan, dialect: str = "FANUC") -> PostProfile:
    is_lathe = plan.process_type in (ProcessType.TURNING, ProcessType.TURN_MILL)
    kind = "turn_mill" if plan.process_type == ProcessType.TURN_MILL else ("lathe" if is_lathe else "mill")
    clamp = "LIMS=" if dialect == "SIEMENS" else ("G46" if dialect == "HUAZHONG" else "G50")
    return PostProfile(
        dialect=dialect,  # type: ignore[arg-type]
        machine_kind=kind,  # type: ignore[arg-type]
        home_return="SUPA" if dialect == "SIEMENS" else "G28",
        spindle_max_rpm=max([o.params.rpm for o in plan.operations] + [4000.0]),
        max_rpm_clamp_code=clamp,
    )


def _compute_stats(moves: List[Move], is_lathe: bool) -> Dict[str, Any]:
    cx = cy = cz = 0.0
    xs: List[float] = []
    ys: List[float] = []
    zs: List[float] = []
    rapid_dist = cut_dist = 0.0
    max_rpm = max_feed = 0.0
    uses_c = False
    uses_live = False
    uses_y = False
    for m in moves:
        if m.s is not None:
            max_rpm = max(max_rpm, float(m.s))
        if m.extra.get("max_rpm"):
            max_rpm = max(max_rpm, float(m.extra["max_rpm"]))
        if m.f is not None and m.kind in ("linear", "arc_cw", "arc_ccw", "thread"):
            max_feed = max(max_feed, float(m.f))
        if m.kind == "c_axis" or m.c is not None:
            uses_c = True
        if m.kind == "live_spindle":
            uses_live = True
        if m.kind in ("rapid", "linear", "arc_cw", "arc_ccw", "thread"):
            nx = m.x if m.x is not None else cx
            ny = m.y if m.y is not None else cy
            nz = m.z if m.z is not None else cz
            if m.y is not None:
                uses_y = True
            # 车削 X 为直径，实际行程半径取 X/2
            dx = (nx - cx) / 2.0 if is_lathe else (nx - cx)
            d = math.sqrt(dx * dx + (ny - cy) ** 2 + (nz - cz) ** 2)
            if m.kind == "rapid":
                rapid_dist += d
            else:
                cut_dist += d
            cx, cy, cz = nx, ny, nz
            xs.append(nx)
            if m.y is not None:
                ys.append(ny)
            zs.append(nz)
    return {
        "ir_count": len(moves),
        "rapid_distance_mm": round(rapid_dist, 2),
        "cut_distance_mm": round(cut_dist, 2),
        "x_min": round(min(xs), 3) if xs else 0.0,
        "x_max": round(max(xs), 3) if xs else 0.0,
        "y_min": round(min(ys), 3) if ys else 0.0,
        "y_max": round(max(ys), 3) if ys else 0.0,
        "z_min": round(min(zs), 3) if zs else 0.0,
        "z_max": round(max(zs), 3) if zs else 0.0,
        "max_rpm": round(max_rpm, 1),
        "max_feed_cmd": round(max_feed, 3),
        "uses_c_axis": uses_c,
        "uses_live_tool": uses_live,
        "uses_y_axis": uses_y,
    }


def generate(
    plan: ProcessPlan,
    stock_setup: Optional[StockSetup] = None,
    post_profile: Optional[PostProfile] = None,
    dialect: str = "FANUC",
) -> NCProgram:
    """生成完整 ISO NC 程序及中间表示。"""
    if not plan.operations:
        raise ValueError("工艺方案为空，无法生成加工程序")
    profile = post_profile or default_profile(plan, dialect)
    ir, tool_table = build_ir(plan, stock_setup, profile)
    text = render(ir, profile)
    is_lathe = plan.process_type in (ProcessType.TURNING, ProcessType.TURN_MILL)
    stats = _compute_stats(ir, is_lathe)
    stats["line_count"] = len(text.splitlines())
    stats["dialect"] = profile.dialect
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return NCProgram(
        part_id=plan.part_id,
        process_type=plan.process_type,
        dialect=profile.dialect,
        program_text=text,
        ir=ir,
        tool_table=tool_table,
        stats=stats,
        post_profile=profile,
        sha256=sha,
    )
