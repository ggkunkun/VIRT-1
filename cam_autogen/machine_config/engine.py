"""M4 机床参数自动配置引擎。

严格解耦：只看 ``NCProgram``（以及可选显式自定义机床列表/偏好型号），从程序本身逆向提取
``ProgramRequirements``，再在机床库中匹配最佳机床并计算坐标系偏置、刀位映射与控制系统后处理规则。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from cam_autogen.contracts import (
    MachineSetup, MachineSpec, NCProgram, PostProfile, ProcessType, ProgramRequirements,
)
from cam_autogen.machine_config.library import DEFAULT_REGISTRY, MachineRegistry

ENGINE_VERSION = "m4-autoconfig-1.0.0"


def extract_requirements(program: NCProgram) -> ProgramRequirements:
    """只从 NCProgram（IR + tool_table + stats）提取机床硬件与能力需求。"""
    is_lathe = program.process_type in (ProcessType.TURNING, ProcessType.TURN_MILL)
    xs: List[float] = []
    ys: List[float] = []
    zs: List[float] = []
    max_main_rpm = 0.0
    max_live_rpm = 0.0
    max_feed_mm_min = 0.0
    needs_y = False
    needs_c = False
    needs_live = False
    in_mm_min = not is_lathe
    in_live = False

    for m in program.ir:
        if m.kind == "feed_mode":
            in_mm_min = m.text == "mm_min"
        elif m.kind == "live_spindle":
            needs_live = True
            in_live = True
            if m.s is not None:
                max_live_rpm = max(max_live_rpm, float(m.s))
        elif m.kind == "live_spindle_stop":
            in_live = False
        elif m.kind in ("spindle", "css"):
            if m.s is not None and m.kind == "spindle":
                max_main_rpm = max(max_main_rpm, float(m.s))
            if m.extra.get("max_rpm"):
                max_main_rpm = max(max_main_rpm, float(m.extra["max_rpm"]))
        elif m.kind == "c_axis" or m.c is not None:
            needs_c = True
        elif m.kind in ("rapid", "linear", "arc_cw", "arc_ccw", "thread"):
            if m.x is not None:
                xs.append(float(m.x))
            if m.y is not None:
                ys.append(float(m.y))
                needs_y = True
            if m.z is not None:
                zs.append(float(m.z))
            if m.f is not None and m.kind in ("linear", "arc_cw", "arc_ccw"):
                fval = float(m.f)
                if in_mm_min or in_live:
                    max_feed_mm_min = max(max_feed_mm_min, fval)
                else:
                    # mm/rev 换算等效进给
                    rpm_ref = max(max_main_rpm, 500.0)
                    max_feed_mm_min = max(max_feed_mm_min, fval * min(rpm_ref, 4000.0))

    max_td = max((float(t["diameter"]) for t in program.tool_table), default=0.0)
    max_tl = max((float(t["length"]) for t in program.tool_table), default=0.0)
    env = {
        "x_min": round(min(xs), 3) if xs else 0.0,
        "x_max": round(max(xs), 3) if xs else 0.0,
        "y_min": round(min(ys), 3) if ys else 0.0,
        "y_max": round(max(ys), 3) if ys else 0.0,
        "z_min": round(min(zs), 3) if zs else 0.0,
        "z_max": round(max(zs), 3) if zs else 0.0,
        "max_live_rpm": round(max_live_rpm, 1),
    }
    return ProgramRequirements(
        process_type=program.process_type,
        max_rpm=round(max(max_main_rpm, max_live_rpm), 1),
        max_feed=round(max_feed_mm_min, 1),
        tools_count=len(program.tool_table),
        max_tool_diameter=round(max_td, 2),
        max_tool_length=round(max_tl, 2),
        needs_y_axis=needs_y,
        needs_c_axis=needs_c,
        needs_live_tool=needs_live,
        envelope_mm=env,
    )


def _check_fit(m: MachineSpec, req: ProgramRequirements) -> Tuple[bool, List[str], Dict[str, Any]]:
    reasons: List[str] = []
    env = req.envelope_mm
    # 1. 类型兼容性（turn_mill 可兼容 turning，不兼容 pure mill）
    if req.process_type == ProcessType.MILLING and m.kind != "mill":
        reasons.append("非铣削/加工中心")
    elif req.process_type == ProcessType.TURNING and m.kind not in ("lathe", "turn_mill"):
        reasons.append("非车床/车铣中心")
    elif req.process_type == ProcessType.TURN_MILL and m.kind != "turn_mill":
        reasons.append("非车铣复合中心")

    # 2. 轴与动力刀
    if req.needs_y_axis and not m.has_y_axis:
        reasons.append("缺少 Y 轴")
    if req.needs_c_axis and not m.has_c_axis:
        reasons.append("缺少 C 轴")
    if req.needs_live_tool and not m.live_tooling:
        reasons.append("缺少动力刀")
    live_req_rpm = float(env.get("max_live_rpm", 0.0))
    if req.needs_live_tool and m.live_tooling and live_req_rpm > m.live_tool_max_rpm:
        reasons.append(f"动力刀转速 {live_req_rpm:.0f} > 上限 {m.live_tool_max_rpm:.0f}")

    # 3. 转速/进给/刀库
    if req.max_rpm > m.max_rpm and not (req.needs_live_tool and live_req_rpm == req.max_rpm):
        # 检查主轴 rpm 是否超限
        reasons.append(f"主轴转速需求 {req.max_rpm:.0f} > {m.max_rpm:.0f}")
    if req.max_feed > m.max_feed_mm_min:
        reasons.append(f"进给需求 {req.max_feed:.0f} > {m.max_feed_mm_min:.0f}")
    if req.tools_count > m.tool_capacity:
        reasons.append(f"刀具数 {req.tools_count} > 刀库 {m.tool_capacity}")
    if req.max_tool_diameter > m.max_tool_diameter:
        reasons.append(f"最大刀径 {req.max_tool_diameter} > {m.max_tool_diameter}")
    if req.max_tool_length > m.max_tool_length:
        reasons.append(f"最大刀长 {req.max_tool_length} > {m.max_tool_length}")

    # 4. 行程校核
    travel_info: Dict[str, Any] = {}
    if m.kind == "mill":
        span_x = env["x_max"] - env["x_min"]
        span_y = env["y_max"] - env["y_min"]
        span_z = env["z_max"] - env["z_min"]
        if span_x + 20.0 > m.travel["x"]:
            reasons.append(f"X行程需求 {span_x + 20:.1f} > {m.travel['x']}")
        if span_y + 20.0 > m.travel["y"]:
            reasons.append(f"Y行程需求 {span_y + 20:.1f} > {m.travel['y']}")
        if span_z + 20.0 > m.travel["z"]:
            reasons.append(f"Z行程需求 {span_z + 20:.1f} > {m.travel['z']}")
        travel_info = {
            "x_span_mm": round(span_x, 2), "x_limit_mm": m.travel["x"],
            "y_span_mm": round(span_y, 2), "y_limit_mm": m.travel["y"],
            "z_span_mm": round(span_z, 2), "z_limit_mm": m.travel["z"],
        }
    else:
        x_neg_diam = -2.0 * m.travel.get("x_neg", 15.0)
        x_max_diam = min(2.0 * m.travel["x"] + x_neg_diam, m.max_swing_diameter or 2.0 * m.travel["x"])
        if env["x_min"] < x_neg_diam - 1e-6:
            reasons.append(f"负向X直径 {env['x_min']:.1f} 超出下限 {x_neg_diam:.1f}")
        if env["x_max"] > x_max_diam + 1e-6:
            reasons.append(f"正向X直径 {env['x_max']:.1f} 超出上限 {x_max_diam:.1f}")
        span_z = env["z_max"] - env["z_min"]
        if span_z + 20.0 > m.travel["z"]:
            reasons.append(f"Z向行程需求 {span_z + 20:.1f} > {m.travel['z']}")
        travel_info = {
            "x_min_prog_diam": env["x_min"], "x_min_limit_diam": x_neg_diam,
            "x_max_prog_diam": env["x_max"], "x_max_limit_diam": round(x_max_diam, 2),
            "z_span_mm": round(span_z, 2), "z_limit_mm": m.travel["z"],
        }
    return len(reasons) == 0, reasons, travel_info


def _score_machine(m: MachineSpec, req: ProgramRequirements, preferred_dialect: Optional[str]) -> float:
    """评分：刚性/余量适中（不过大浪费也不紧贴极限）、方言匹配加分、同级别优选。"""
    score = 70.0
    if preferred_dialect and m.dialect == preferred_dialect:
        score += 12.0
    # 车削优先选纯车床，不无谓占用昂贵车铣复合中心
    if req.process_type == ProcessType.TURNING and m.kind == "lathe":
        score += 10.0
    # 行程利用率越合理得分越高（30%~75% 最佳）
    env = req.envelope_mm
    if m.kind == "mill":
        util = max((env["x_max"] - env["x_min"]) / m.travel["x"], (env["y_max"] - env["y_min"]) / m.travel["y"])
    else:
        util = (env["z_max"] - env["z_min"]) / max(m.travel["z"], 1.0)
    score += max(0.0, 10.0 - abs(util - 0.45) * 18.0)
    # 刀库与功率余量
    rpm_margin = (m.max_rpm - req.max_rpm) / max(m.max_rpm, 1.0)
    score += min(6.0, max(0.0, rpm_margin * 10.0))
    tool_margin = (m.tool_capacity - req.tools_count) / max(m.tool_capacity, 1)
    score += min(4.0, max(0.0, tool_margin * 5.0))
    return round(score, 2)


def _compute_work_offset(m: MachineSpec, req: ProgramRequirements) -> Tuple[str, Dict[str, float], Dict[str, Any]]:
    env = req.envelope_mm
    if m.kind == "mill":
        cx = m.table_center.get("x", m.travel["x"] / 2.0)
        cy = m.table_center.get("y", m.travel["y"] / 2.0)
        g54_x = round(cx - (env["x_min"] + env["x_max"]) / 2.0, 3)
        g54_y = round(cy - (env["y_min"] + env["y_max"]) / 2.0, 3)
        # 顶安全点留在距机床上极限 -25mm 以下，底端落在下极限之上
        z_span = env["z_max"] - env["z_min"]
        g54_z = round(-max(env["z_max"] + 25.0, min(m.travel["z"] * 0.45, m.travel["z"] - 10.0 + env["z_min"])), 3)
        # 确保不超下限
        if g54_z + env["z_min"] < -m.travel["z"]:
            g54_z = round(-m.travel["z"] - env["z_min"] + 5.0, 3)
        mx_lo, mx_hi = g54_x + env["x_min"], g54_x + env["x_max"]
        my_lo, my_hi = g54_y + env["y_min"], g54_y + env["y_max"]
        mz_lo, mz_hi = g54_z + env["z_min"], g54_z + env["z_max"]
        tc = {
            "x_machine": [round(mx_lo, 2), round(mx_hi, 2)], "x_limits": [0.0, m.travel["x"]],
            "y_machine": [round(my_lo, 2), round(my_hi, 2)], "y_limits": [0.0, m.travel["y"]],
            "z_machine": [round(mz_lo, 2), round(mz_hi, 2)], "z_limits": [-m.travel["z"], 0.0],
            "within_limits": (0 <= mx_lo and mx_hi <= m.travel["x"]
                              and 0 <= my_lo and my_hi <= m.travel["y"]
                              and -m.travel["z"] <= mz_lo and mz_hi <= 0.0),
        }
        return "G54", {"x": g54_x, "y": g54_y, "z": g54_z}, tc
    # lathe / turn_mill: X0 固定在主轴回转中心，G54 Z 偏移把负 Z 加工区放在机床正向行程内
    z_home = max(abs(env["z_min"]) + 80.0, m.table_center.get("z_chuck_home", m.travel["z"] * 0.45))
    if z_home + env["z_max"] > m.travel["z"]:
        z_home = max(abs(env["z_min"]) + 10.0, m.travel["z"] - env["z_max"] - 10.0)
    z_home = round(z_home, 3)
    mz_lo, mz_hi = z_home + env["z_min"], z_home + env["z_max"]
    x_neg_diam = -2.0 * m.travel.get("x_neg", 15.0)
    x_max_diam = min(2.0 * m.travel["x"] + x_neg_diam, m.max_swing_diameter or 2.0 * m.travel["x"])
    tc = {
        "x_machine_diam": [env["x_min"], env["x_max"]], "x_limits_diam": [x_neg_diam, round(x_max_diam, 2)],
        "z_machine": [round(mz_lo, 2), round(mz_hi, 2)], "z_limits": [0.0, m.travel["z"]],
        "within_limits": (x_neg_diam - 1e-6 <= env["x_min"] and env["x_max"] <= x_max_diam + 1e-6
                          and 0.0 <= mz_lo and mz_hi <= m.travel["z"]),
    }
    return "G54", {"x": 0.0, "z": z_home}, tc


def configure_machine(
    program: NCProgram,
    preferred_model: Optional[str] = None,
    preferred_dialect: Optional[str] = None,
    registry: Optional[MachineRegistry] = None,
    custom_machines: Optional[List[MachineSpec]] = None,
) -> MachineSetup:
    """根据 NCProgram 自动选择机床、分配刀库、定义坐标系与控制系统映射规则。"""
    reg = registry or DEFAULT_REGISTRY
    pool = list(reg.list_machines())
    if custom_machines:
        by_model = {m.model: m for m in pool}
        for cm in custom_machines:
            by_model[cm.model] = cm
        pool = list(by_model.values())

    req = extract_requirements(program)
    dialect_pref = preferred_dialect or program.dialect

    feasible: List[Tuple[float, MachineSpec, Dict[str, Any]]] = []
    rejected: List[Dict[str, Any]] = []
    for m in pool:
        ok, reasons, tinfo = _check_fit(m, req)
        if ok:
            sc = _score_machine(m, req, dialect_pref)
            feasible.append((sc, m, tinfo))
        else:
            rejected.append({"model": m.model, "kind": m.kind, "dialect": m.dialect, "reasons": reasons})

    if preferred_model:
        target = next((item for item in feasible if item[1].model == preferred_model), None)
        if target is None:
            rej = next((r for r in rejected if r["model"] == preferred_model), None)
            if rej:
                raise ValueError(f"指定机床 {preferred_model!r} 不满足程序需求: {rej['reasons']}")
            raise ValueError(f"机床库中未找到型号 {preferred_model!r}")
        chosen_score, chosen, chosen_tinfo = target
    else:
        if not feasible:
            summary = "; ".join(f"{r['model']}:{r['reasons']}" for r in rejected[:5])
            raise ValueError(f"没有机床满足该程序需求（候选均被拒绝：{summary}）")
        feasible.sort(key=lambda it: (-it[0], it[1].model))
        chosen_score, chosen, chosen_tinfo = feasible[0]

    candidates = [
        {"model": m.model, "vendor": m.vendor, "controller": m.controller, "dialect": m.dialect,
         "score": sc, "travel": chosen_tinfo if m.model == chosen.model else m.travel}
        for sc, m, _ in sorted(feasible, key=lambda it: (-it[0], it[1].model))[:5]
    ]

    wo_name, wo_vals, tc_detail = _compute_work_offset(chosen, req)
    chosen_tinfo.update(tc_detail)

    pockets: List[Dict[str, Any]] = []
    tmap: Dict[str, int] = {}
    for idx, t in enumerate(program.tool_table, start=1):
        pocket = idx
        tmap[str(t["tool_id"])] = pocket
        pockets.append({
            "pocket": pocket,
            "tool_no": f"T{pocket:02d}" if chosen.kind == "mill" else f"T{pocket:02d}{pocket:02d}",
            "tool_id": t["tool_id"],
            "kind": t["kind"],
            "diameter_mm": t["diameter"],
            "length_offset_h": pocket,
            "geometry_length_mm": t["length"],
            "wear_offset_mm": 0.0,
        })

    clamp = "LIMS=" if chosen.dialect == "SIEMENS" else ("G46" if chosen.dialect == "HUAZHONG" else "G50")
    post_profile = PostProfile(
        dialect=chosen.dialect,
        machine_kind=chosen.kind,
        program_number=program.post_profile.program_number,
        work_offset=wo_name,
        coolant_on=chosen.coolant_codes.get("on", "M08"),
        coolant_off=chosen.coolant_codes.get("off", "M09"),
        spindle_max_rpm=chosen.max_rpm,
        live_spindle_cw=chosen.live_codes.get("cw", "M13"),
        live_spindle_stop=chosen.live_codes.get("stop", "M15"),
        c_axis_on=chosen.live_codes.get("c_on", "M18"),
        c_axis_off=chosen.live_codes.get("c_off", "M19"),
        home_return="SUPA" if chosen.dialect == "SIEMENS" else "G28",
        tool_number_map=tmap,
        line_numbers=True,
        line_step=5,
        decimals=3,
        max_rpm_clamp_code=clamp if chosen.kind != "mill" else None,
    )

    notes = [
        f"从 {len(pool)} 台机床中匹配到 {len(feasible)} 台合格候选，优选 {chosen.model} ({chosen.controller})",
        f"工作偏置 {wo_name}={wo_vals}，全行程校验={'通过' if tc_detail['within_limits'] else '超限'}",
    ]
    return MachineSetup(
        machine=chosen,
        match_score=chosen_score,
        candidates=candidates,
        work_offset=wo_name,
        work_offset_values=wo_vals,
        tool_pockets=pockets,
        post_profile=post_profile,
        travel_check=chosen_tinfo,
        notes=notes,
    )
