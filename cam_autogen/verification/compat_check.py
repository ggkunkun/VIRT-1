"""校验二：机床参数兼容性校验（行程、转速、进给、功率、刀库、轴配置、G/M指令与方言语法）。"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

from cam_autogen.contracts import MachineSetup, NCProgram, ProcessPlan, ProcessType, RiskItem

_G_RE = re.compile(r"\b(?:G\d+(?:\.\d+)?|SUPA)\b")
_M_RE = re.compile(r"\bM\d+\b")


def _norm_gm(code: str) -> str:
    if code == "SUPA":
        return "SUPA"
    p, num = code[0], code[1:]
    if "." in num:
        return code
    return f"{p}{int(num):02d}"


def _strip_comments(line: str, dialect: str) -> str:
    if dialect == "SIEMENS":
        line = line.split(";", 1)[0]
    else:
        line = re.sub(r"\([^)]*\)", "", line)
    # 去掉字符串常量，如 T="T01"
    return re.sub(r'"[^"]*"', "", line)


def _risk(level: str, code: str, msg: str, **loc: Any) -> RiskItem:
    return RiskItem(level=level, check="machine_compatibility", code=code, message=msg, location=loc)  # type: ignore[arg-type]


def verify_machine_compatibility(
    program: NCProgram,
    setup: MachineSetup,
    plan: Optional[ProcessPlan] = None,
) -> Dict[str, Any]:
    """核验程序与目标机床参数、指令集及方言语法是否 100% 兼容。"""
    risks: List[RiskItem] = []
    m = setup.machine
    is_lathe = program.process_type in (ProcessType.TURNING, ProcessType.TURN_MILL)

    # 1. 方言与类型检查
    if program.dialect != m.dialect:
        risks.append(_risk("CRITICAL", "DIALECT_MISMATCH",
                           f"程序方言 {program.dialect} 与目标机床控制器方言 {m.dialect} 不一致"))
    if program.process_type == ProcessType.MILLING and m.kind != "mill":
        risks.append(_risk("CRITICAL", "MACHINE_KIND_MISMATCH", f"铣削程序不能运行于 {m.kind} 机床 {m.model}"))
    if program.process_type == ProcessType.TURN_MILL and m.kind != "turn_mill":
        risks.append(_risk("CRITICAL", "MACHINE_KIND_MISMATCH", f"车铣复合程序需要 turn_mill 机床，当前为 {m.kind}"))

    # 2. 轴能力与动力刀检查
    if program.stats.get("uses_y_axis") and not m.has_y_axis:
        risks.append(_risk("CRITICAL", "AXIS_CAPABILITY_MISSING", f"程序使用 Y 轴但 {m.model} 无 Y 轴"))
    if program.stats.get("uses_c_axis") and not m.has_c_axis:
        risks.append(_risk("CRITICAL", "AXIS_CAPABILITY_MISSING", f"程序使用 C 轴但 {m.model} 无 C 轴"))
    if program.stats.get("uses_live_tool") and not m.live_tooling:
        risks.append(_risk("CRITICAL", "LIVE_TOOL_MISSING", f"程序使用动力刀但 {m.model} 无动力刀功能"))

    # 3. 行程超限检查（基于 G54 偏置变换到机床坐标）
    wo = setup.work_offset_values
    g54_x = float(wo.get("x", 0.0))
    g54_y = float(wo.get("y", 0.0))
    g54_z = float(wo.get("z", 0.0))
    over_travel = 0
    for idx, mv in enumerate(program.ir):
        if mv.kind in ("rapid", "linear", "arc_cw", "arc_ccw", "thread"):
            if m.kind == "mill":
                if mv.x is not None:
                    mx = g54_x + float(mv.x)
                    if mx < -1e-6 or mx > m.travel["x"] + 1e-6:
                        over_travel += 1
                        if over_travel <= 5:
                            risks.append(_risk("CRITICAL", "OVER_TRAVEL",
                                               f"X机床坐标 {mx:.2f} 超出行程 [0, {m.travel['x']}]", move_index=idx))
                if mv.y is not None:
                    my = g54_y + float(mv.y)
                    if my < -1e-6 or my > m.travel["y"] + 1e-6:
                        over_travel += 1
                        if over_travel <= 5:
                            risks.append(_risk("CRITICAL", "OVER_TRAVEL",
                                               f"Y机床坐标 {my:.2f} 超出行程 [0, {m.travel['y']}]", move_index=idx))
                if mv.z is not None:
                    mz = g54_z + float(mv.z)
                    if mz < -m.travel["z"] - 1e-6 or mz > 1e-6:
                        over_travel += 1
                        if over_travel <= 5:
                            risks.append(_risk("CRITICAL", "OVER_TRAVEL",
                                               f"Z机床坐标 {mz:.2f} 超出行程 [{-m.travel['z']}, 0]", move_index=idx))
            else:
                x_neg_diam = -2.0 * m.travel.get("x_neg", 15.0)
                x_max_diam = min(2.0 * m.travel["x"] + x_neg_diam, m.max_swing_diameter or 2.0 * m.travel["x"])
                if mv.x is not None and (float(mv.x) < x_neg_diam - 1e-6 or float(mv.x) > x_max_diam + 1e-6):
                    over_travel += 1
                    if over_travel <= 5:
                        risks.append(_risk("CRITICAL", "OVER_TRAVEL",
                                           f"X直径坐标 {mv.x:.2f} 超出行程 [{x_neg_diam}, {x_max_diam}]", move_index=idx))
                if mv.z is not None:
                    mz = g54_z + float(mv.z)
                    if mz < -1e-6 or mz > m.travel["z"] + 1e-6:
                        over_travel += 1
                        if over_travel <= 5:
                            risks.append(_risk("CRITICAL", "OVER_TRAVEL",
                                               f"Z机床坐标 {mz:.2f} 超出行程 [0, {m.travel['z']}]", move_index=idx))

    # 4. 转速 / 进给 / 功率限制
    in_mm_min = not is_lathe
    in_live = False
    cur_rpm = 0.0
    rpm_err = feed_err = 0
    for idx, mv in enumerate(program.ir):
        if mv.kind == "feed_mode":
            in_mm_min = mv.text == "mm_min"
        elif mv.kind == "live_spindle":
            in_live = True
            cur_rpm = float(mv.s or 0.0)
            if cur_rpm > m.live_tool_max_rpm + 1e-6:
                rpm_err += 1
                risks.append(_risk("CRITICAL", "RPM_EXCEEDED",
                                   f"动力刀转速 {cur_rpm:.0f} > 机床上限 {m.live_tool_max_rpm:.0f}", move_index=idx))
        elif mv.kind == "live_spindle_stop":
            in_live = False
        elif mv.kind == "spindle":
            cur_rpm = float(mv.s or 0.0)
            if cur_rpm > m.max_rpm + 1e-6:
                rpm_err += 1
                risks.append(_risk("CRITICAL", "RPM_EXCEEDED",
                                   f"主轴转速 {cur_rpm:.0f} > 机床上限 {m.max_rpm:.0f}", move_index=idx))
        elif mv.kind == "css":
            s_max = float(mv.extra.get("max_rpm", 0.0))
            if s_max > m.max_rpm + 1e-6:
                rpm_err += 1
                risks.append(_risk("CRITICAL", "RPM_EXCEEDED",
                                   f"恒线速限速 {s_max:.0f} > 机床上限 {m.max_rpm:.0f}", move_index=idx))
        elif mv.kind in ("linear", "arc_cw", "arc_ccw") and mv.f is not None:
            fv = float(mv.f)
            f_mm_min = fv if (in_mm_min or in_live) else fv * min(max(cur_rpm, 500.0), m.max_rpm)
            if f_mm_min > m.max_feed_mm_min + 1e-6:
                feed_err += 1
                if feed_err <= 5:
                    risks.append(_risk("HIGH", "FEED_EXCEEDED",
                                       f"进给 {f_mm_min:.1f} mm/min > 机床上限 {m.max_feed_mm_min:.1f}", move_index=idx))

    if plan:
        for op in plan.operations:
            p_lim = m.live_tool_power_kw if op.setup == "live" else m.spindle_power_kw
            if op.metrics.power_kw > p_lim + 1e-6:
                risks.append(_risk("CRITICAL", "POWER_EXCEEDED",
                                   f"{op.op_id} 功率 {op.metrics.power_kw:.2f}kW > 机床额定 {p_lim:.2f}kW",
                                   op_id=op.op_id))

    # 5. 刀具库容量与尺寸限制
    if len(program.tool_table) > m.tool_capacity:
        risks.append(_risk("CRITICAL", "TOOL_CAPACITY_EXCEEDED",
                           f"刀具数量 {len(program.tool_table)} > 刀库容量 {m.tool_capacity}"))
    for t in program.tool_table:
        if float(t["diameter"]) > m.max_tool_diameter + 1e-6:
            risks.append(_risk("HIGH", "TOOL_DIAMETER_EXCEEDED",
                               f"刀具 {t['tool_id']} 直径 {t['diameter']} > 机床上限 {m.max_tool_diameter}"))
        if float(t["length"]) > m.max_tool_length + 1e-6:
            risks.append(_risk("HIGH", "TOOL_LENGTH_EXCEEDED",
                               f"刀具 {t['tool_id']} 长度 {t['length']} > 机床上限 {m.max_tool_length}"))

    # 6. 指令集与方言语法扫描
    sup_g: Set[str] = {_norm_gm(g) for g in m.supported_g}
    sup_m: Set[str] = {_norm_gm(mc) for mc in m.supported_m}
    used_g: Set[str] = set()
    used_m: Set[str] = set()
    lines = program.program_text.splitlines()
    for lno, raw in enumerate(lines, start=1):
        code_only = _strip_comments(raw, m.dialect)
        for tok in _G_RE.findall(code_only):
            nt = _norm_gm(tok)
            used_g.add(nt)
            if nt not in sup_g:
                risks.append(_risk("CRITICAL", "UNSUPPORTED_GCODE",
                                   f"第 {lno} 行指令 {tok} 不在 {m.model} 支持列表内", line=lno, gm_code=tok))
        for tok in _M_RE.findall(code_only):
            nt = _norm_gm(tok)
            used_m.add(nt)
            if nt not in sup_m:
                risks.append(_risk("CRITICAL", "UNSUPPORTED_MCODE",
                                   f"第 {lno} 行指令 {tok} 不在 {m.model} 支持列表内", line=lno, gm_code=tok))
        if m.dialect == "FANUC" and (";" in raw or "LIMS=" in code_only):
            risks.append(_risk("HIGH", "DIALECT_SYNTAX_ERROR", f"FANUC 程序第 {lno} 行出现非法的西门子语法", line=lno))
        if m.dialect == "SIEMENS" and "(" in raw.split(";", 1)[0]:
            risks.append(_risk("HIGH", "DIALECT_SYNTAX_ERROR", f"SIEMENS 程序第 {lno} 行出现括号注释", line=lno))
        if m.dialect == "HUAZHONG" and ("LIMS=" in code_only or (lno == 1 and raw.strip() == "%")):
            risks.append(_risk("HIGH", "DIALECT_SYNTAX_ERROR", f"华中程序第 {lno} 行格式不符合 HNC 规范", line=lno))

    blocking = any(r.level in ("CRITICAL", "HIGH") for r in risks)
    return {
        "passed": not blocking,
        "machine": m.model,
        "controller": m.controller,
        "dialect": m.dialect,
        "used_g_codes": sorted(used_g),
        "used_m_codes": sorted(used_m),
        "over_travel_count": over_travel,
        "risks": risks,
    }
