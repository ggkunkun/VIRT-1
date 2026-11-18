"""校验一：加工路径合理性校验（过切、撞刀/快进扎刀、夹具碰撞、起停安全）。"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from cam_autogen.contracts import Move, NCProgram, ProcessPlan, ProcessType, RiskItem, StockSetup

TOL_MM = 0.05


def _risk(level: str, code: str, msg: str, **loc: Any) -> RiskItem:
    return RiskItem(level=level, check="path_rationality", code=code, message=msg, location=loc)  # type: ignore[arg-type]


def _profile_d_at(profile: List[List[float]], z: float) -> Optional[float]:
    """返回 z 处成品轮廓允许的最小外径（台阶竖直面处返回小端直径，避免沿台阶面爬升时误判过切）。"""
    if not profile or z > profile[0][0] + 1e-6 or z < profile[-1][0] - 1e-6:
        return None
    best: Optional[float] = None
    for (z1, d1), (z2, d2) in zip(profile, profile[1:]):
        lo, hi = min(z1, z2), max(z1, z2)
        if lo - 1e-6 <= z <= hi + 1e-6:
            if abs(z2 - z1) < 1e-9:
                d = min(d1, d2)
            else:
                d = d1 + (d2 - d1) * (z - z1) / (z2 - z1)
            best = d if best is None else min(best, d)
    return best


def _sample_segment(x0: float, y0: float, z0: float, x1: float, y1: float, z1: float, step: float = 2.0) -> List[Tuple[float, float, float]]:
    dist = math.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2 + (z1 - z0) ** 2)
    n = max(1, min(200, int(math.ceil(dist / step))))
    return [(x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n, z0 + (z1 - z0) * k / n) for k in range(1, n + 1)]


def _in_box3d(x: float, y: float, z: float, box: List[float], r_tool: float) -> bool:
    xmin, xmax, ymin, ymax, zmin, zmax = box
    return (xmin - r_tool + TOL_MM <= x <= xmax + r_tool - TOL_MM
            and ymin - r_tool + TOL_MM <= y <= ymax + r_tool - TOL_MM
            and zmin + TOL_MM <= z <= zmax - TOL_MM)


def _in_lathe_zone(x_diam: float, z: float, box: List[float]) -> bool:
    zmin, zmax, rmin, rmax = box
    r = abs(x_diam) / 2.0
    return (zmin + TOL_MM <= z <= zmax - TOL_MM) and (rmin - TOL_MM <= r <= rmax - TOL_MM)


def verify_path(
    program: NCProgram,
    plan: Optional[ProcessPlan] = None,
    stock_setup: Optional[StockSetup] = None,
) -> Dict[str, Any]:
    """对 NCProgram.ir 逐条进行几何与安全仿真，返回结构化结果与 RiskItem 列表。"""
    risks: List[RiskItem] = []
    ir = program.ir
    if not ir:
        risks.append(_risk("CRITICAL", "EMPTY_IR", "NC程序中间表示(IR)为空"))
        return {"passed": False, "risks": risks, "stats": {}, "risk_points": []}

    is_lathe = program.process_type in (ProcessType.TURNING, ProcessType.TURN_MILL)
    z_top = 1.0
    if stock_setup:
        z_top = float(stock_setup.part_offset_in_stock.get("z_top_allow",
                      stock_setup.part_offset_in_stock.get("z_face_allow", 1.0)))

    # 从方案抽取特征边界用于过切校验
    op_map = {op.op_id: op for op in (plan.operations if plan else [])}
    tool_map = {int(t["tool_no"]): t for t in program.tool_table}
    turn_profile: List[List[float]] = []
    grooves: List[Tuple[float, float, float]] = []  # (z_lo, z_hi, d_bot)
    threads: List[Tuple[float, float, float]] = []  # (z_lo, z_hi, d_root)
    axial_hole_depth = 0.0
    axial_hole_d = 0.0
    stock_d = (stock_setup.stock_dims.get("diameter") if stock_setup else None) or 0.0
    stock_x = (stock_setup.stock_dims.get("x") if stock_setup else None) or 0.0
    stock_y = (stock_setup.stock_dims.get("y") if stock_setup else None) or 0.0
    part_box: Optional[Tuple[float, float, float, float]] = None
    holes_xy: List[Tuple[float, float, float]] = []

    if plan:
        for op in plan.operations:
            g = op.geometry
            if "profile" in g:
                turn_profile = g["profile"]
            if "stock_d" in g:
                stock_d = max(stock_d, float(g["stock_d"]))
            if op.category == "groove":
                zc, w = float(g["z"]), float(g["width"])
                grooves.append((zc - w / 2 - 0.5, zc + w / 2 + 0.5, float(g["diameter"])))
            elif op.category == "thread":
                zs, ze = float(g["z_start"]), float(g["z_end"])
                threads.append((min(zs, ze) - 0.5, max(zs, ze) + 0.5, float(g["diameter"]) - 2 * float(g["depth"])))
            elif op.category in ("drill_axial", "bore"):
                axial_hole_depth = max(axial_hole_depth, float(g["depth"]))
                axial_hole_d = max(axial_hole_d, float(g.get("d_final", g.get("diameter", 0))))
            elif op.category == "outline_profile":
                part_box = (float(g["xmin"]), float(g["xmax"]), float(g["ymin"]), float(g["ymax"]))
            if "holes" in g and not is_lathe:
                hd = float(g.get("depth", 50.0))
                for h in g["holes"]:
                    holes_xy.append((float(h["x"]), float(h["y"]), hd))

    # 仿真状态
    cx, cy, cz = (150.0, 0.0, 60.0) if is_lathe else (0.0, 0.0, z_top + 30.0)
    spindle_on = False
    live_on = False
    coolant_on = False
    c_on = False
    cur_tool_no = 1
    cur_r = float(tool_map.get(1, {}).get("diameter", 10.0)) / 2.0 if not is_lathe else 0.0
    drilled_depth: Dict[Tuple[float, float], float] = {}
    drilled_axial_sofar = 0.0
    turned_clearance: List[Tuple[float, float, float]] = []  # 记录已车削/已掏空区域用于放行后续退刀
    fixture_zones = stock_setup.fixture_zones if stock_setup else []
    risk_points: List[Dict[str, Any]] = []
    saw_end = False
    collision_count = gouge_count = plunge_count = 0

    def add_risk(level: str, code: str, msg: str, idx: int, x: float, y: float, z: float, op_id: Optional[str]) -> None:
        risks.append(_risk(level, code, msg, move_index=idx, op_id=op_id, x=round(x, 2), y=round(y, 2), z=round(z, 2)))
        risk_points.append({"level": level, "code": code, "x": round(x, 2), "y": round(y, 2), "z": round(z, 2)})

    for idx, m in enumerate(ir):
        # 数值有效性
        for attr in ("x", "y", "z", "c", "f", "s"):
            val = getattr(m, attr)
            if val is not None and not math.isfinite(float(val)):
                add_risk("CRITICAL", "NON_FINITE", f"指令 #{idx} 参数 {attr}={val} 非有限数", idx, cx, cy, cz, m.op_id)

        if m.kind == "tool_change":
            if spindle_on or live_on:
                add_risk("CRITICAL", "UNSAFE_TOOL_CHANGE", f"换刀 #{idx} 前主轴未停止", idx, cx, cy, cz, m.op_id)
            if not is_lathe and cz < z_top + 10.0:
                add_risk("HIGH", "UNSAFE_TOOL_CHANGE_Z", f"换刀 #{idx} 前 Z={cz:.2f} 未抬至安全高度", idx, cx, cy, cz, m.op_id)
            cur_tool_no = m.tool or 1
            cur_r = float(tool_map.get(cur_tool_no, {}).get("diameter", 10.0)) / 2.0 if not is_lathe else 0.0
        elif m.kind == "spindle":
            spindle_on = True
        elif m.kind == "css":
            spindle_on = True
        elif m.kind == "spindle_stop":
            spindle_on = False
        elif m.kind == "live_spindle":
            live_on = True
        elif m.kind == "live_spindle_stop":
            live_on = False
        elif m.kind == "c_axis":
            c_on = m.text != "off"
        elif m.kind == "coolant":
            coolant_on = True
        elif m.kind == "coolant_off":
            coolant_on = False
        elif m.kind == "safe_retract":
            cx = m.x if m.x is not None else cx
            cy = m.y if m.y is not None else cy
            cz = m.z if m.z is not None else (60.0 if is_lathe else z_top + 30.0)
        elif m.kind == "program_end":
            saw_end = True
            if spindle_on or live_on:
                add_risk("HIGH", "SPINDLE_ON_AT_END", "程序结束(M30)前未停主轴", idx, cx, cy, cz, m.op_id)
            if coolant_on:
                add_risk("MEDIUM", "COOLANT_ON_AT_END", "程序结束前未关闭冷却液", idx, cx, cy, cz, m.op_id)
        elif m.kind in ("rapid", "linear", "arc_cw", "arc_ccw", "thread"):
            nx = float(m.x) if m.x is not None else cx
            ny = float(m.y) if m.y is not None else cy
            nz = float(m.z) if m.z is not None else cz
            op = op_map.get(m.op_id or "")
            is_cut = m.kind != "rapid"

            if is_cut:
                if op and op.setup == "live":
                    if not live_on:
                        add_risk("CRITICAL", "LIVE_SPINDLE_OFF_CUT", f"动力刀切削 #{idx} 时动力主轴未启动", idx, nx, ny, nz, m.op_id)
                elif not spindle_on:
                    add_risk("CRITICAL", "SPINDLE_OFF_CUT", f"切削 #{idx} 时主轴未启动", idx, nx, ny, nz, m.op_id)
                if not coolant_on:
                    add_risk("LOW", "COOLANT_OFF_CUT", f"切削 #{idx} 未开启冷却液", idx, nx, ny, nz, m.op_id)
                if (m.f is not None and m.f <= 0) or (m.kind == "thread" and (m.f is None or m.f <= 0)):
                    add_risk("CRITICAL", "INVALID_FEED", f"切削 #{idx} 进给率 F={m.f} 非法", idx, nx, ny, nz, m.op_id)

            # 夹具碰撞（所有移动逐段采样）
            for sx, sy, sz in _sample_segment(cx, cy, cz, nx, ny, nz, step=3.0):
                for fz in fixture_zones:
                    if is_lathe and _in_lathe_zone(sx, sz, fz.box):
                        collision_count += 1
                        if collision_count <= 5:
                            add_risk("CRITICAL", "FIXTURE_COLLISION",
                                     f"刀轨 #{idx} 与夹具 {fz.name}({fz.kind}) 干涉 (X={sx:.2f}, Z={sz:.2f})",
                                     idx, sx, sy, sz, m.op_id)
                        break
                    if not is_lathe and _in_box3d(sx, sy, sz, fz.box, cur_r):
                        collision_count += 1
                        if collision_count <= 5:
                            add_risk("CRITICAL", "FIXTURE_COLLISION",
                                     f"刀轨 #{idx} 与夹具 {fz.name}({fz.kind}) 干涉 (X={sx:.2f}, Y={sy:.2f}, Z={sz:.2f})",
                                     idx, sx, sy, sz, m.op_id)
                        break

            # 快速下刀撞料检查
            if m.kind == "rapid":
                if not is_lathe:
                    # 仅当向 -Z 快速下行且低于毛坯顶面时检查是否处在已钻孔中心内
                    if nz < z_top - 0.1 and nz < cz:
                        key = (round(nx, 1), round(ny, 1))
                        cleared = drilled_depth.get(key, 0.0)
                        if abs(nx - cx) > 0.2 or abs(ny - cy) > 0.2 or nz < -cleared - 0.2:
                            plunge_count += 1
                            if plunge_count <= 5:
                                add_risk("CRITICAL", "RAPID_PLUNGE",
                                         f"铣削快进(G00)扎入工件 ({nx:.2f},{ny:.2f},{nz:.2f}) < 毛坯顶 {z_top}",
                                         idx, nx, ny, nz, m.op_id)
                else:
                    # 车削：若 G00 进入棒料实体内部（z < z_top - 0.1 且 |x| < stock_d - 0.2），须是在已切区域退刀或同轴孔内安全区
                    if stock_d > 0 and nz < z_top - 0.1 and abs(nx) < stock_d - 0.2:
                        in_cleared = any(z_lo <= nz <= z_hi and abs(nx) >= d_cl - 0.1 for z_lo, z_hi, d_cl in turned_clearance)
                        # 允许：1) 径向向外退刀（含径向动力钻退刀）或向 +Z 退刀；2) 已钻同轴孔深度内重新定位
                        retreating_out = ((nx >= cx + 0.1 and abs(nz - cz) < 1e-4)
                                          or (abs(nx) >= abs(cx) - 1e-6 and nz >= cz - 1e-6
                                              and (abs(nx) > abs(cx) + 0.1 or nz > cz + 0.1)))
                        in_axial_bore = (abs(nx) <= axial_hole_d + 0.2 and nz >= -drilled_axial_sofar - 0.2
                                         and (nz > cz - 0.1 or abs(nx) <= abs(cx) + 1e-6))
                        is_live_axial_retract = (op is not None and op.category == "live_drill_axial" and nz >= cz - 0.1)
                        if not (in_cleared or retreating_out or in_axial_bore or is_live_axial_retract):
                            plunge_count += 1
                            if plunge_count <= 5:
                                add_risk("CRITICAL", "RAPID_PLUNGE",
                                         f"车削快进(G00)疑似撞入毛坯 (X={nx:.2f}, Z={nz:.2f})",
                                         idx, nx, ny, nz, m.op_id)

            # 过切检查（基于 ProcessPlan 特征与轮廓）
            if is_cut and op is not None:
                if is_lathe:
                    if op.setup == "main" and op.category in ("od_rough", "od_finish") and turn_profile:
                        for sx, _, sz in _sample_segment(cx, cy, cz, nx, ny, nz, step=2.0):
                            if sz <= 0.0:
                                pd = _profile_d_at(turn_profile, sz)
                                in_groove = any(z0 <= sz <= z1 for z0, z1, _ in grooves)
                                if pd is not None and not in_groove and sx < pd - TOL_MM:
                                    gouge_count += 1
                                    if gouge_count <= 5:
                                        add_risk("CRITICAL", "GOUGE",
                                                 f"车削过切 #{idx} ({op.op_id}): Z={sz:.2f} 处 X={sx:.2f} < 成品外径 {pd:.2f}",
                                                 idx, sx, 0.0, sz, m.op_id)
                                    break
                    if op.category == "face_turn" and nz < -TOL_MM:
                        gouge_count += 1
                        add_risk("CRITICAL", "GOUGE", f"端面车削 Z={nz:.2f} < 0 过切端面", idx, nx, 0.0, nz, m.op_id)
                    # 记录已清空的外径区间与已钻同轴深度
                    if op.category in ("od_rough", "od_finish"):
                        turned_clearance.append((min(cz, nz), max(cz, nz), min(abs(cx), abs(nx))))
                    if op.category in ("drill_axial", "bore") and nz < 0:
                        drilled_axial_sofar = max(drilled_axial_sofar, -nz)
                else:
                    g = op.geometry
                    cat = op.category
                    if cat == "face_mill" and nz < float(g["z_end"]) - TOL_MM:
                        gouge_count += 1
                        add_risk("CRITICAL", "GOUGE", f"面铣 Z={nz:.2f} 超出面深 {g['z_end']:.2f}", idx, nx, ny, nz, m.op_id)
                    elif cat in ("pocket_rough", "pocket_finish"):
                        pcx, pcy, pL, pW, pd = float(g["x"]), float(g["y"]), float(g["length"]), float(g["width"]), float(g["depth"])
                        if nz < -pd - TOL_MM:
                            gouge_count += 1
                            add_risk("CRITICAL", "GOUGE", f"型腔 {op.op_id} 深度过切 Z={nz:.2f} < {-pd:.2f}", idx, nx, ny, nz, m.op_id)
                        if (nx - cur_r < pcx - pL / 2 - TOL_MM or nx + cur_r > pcx + pL / 2 + TOL_MM
                                or ny - cur_r < pcy - pW / 2 - TOL_MM or ny + cur_r > pcy + pW / 2 + TOL_MM):
                            gouge_count += 1
                            add_risk("CRITICAL", "GOUGE", f"型腔 {op.op_id} 刀具边界超出型腔壁 ({nx:.2f},{ny:.2f})", idx, nx, ny, nz, m.op_id)
                    elif cat == "outline_profile" and part_box and nz < -TOL_MM:
                        px0, px1, py0, py1 = part_box
                        for sx, sy, sz in _sample_segment(cx, cy, cz, nx, ny, nz, step=3.0):
                            if (sx + cur_r > px0 + TOL_MM and sx - cur_r < px1 - TOL_MM
                                    and sy + cur_r > py0 + TOL_MM and sy - cur_r < py1 - TOL_MM):
                                gouge_count += 1
                                if gouge_count <= 5:
                                    add_risk("CRITICAL", "GOUGE",
                                             f"外形铣 {op.op_id} 刀具侵入成品 ({sx:.2f},{sy:.2f},R={cur_r:.1f})",
                                             idx, sx, sy, sz, m.op_id)
                                break
                    elif cat in ("contour_rough", "contour_finish") and nz < -TOL_MM:
                        bx, by, bL, bW = float(g["x"]), float(g["y"]), float(g["length"]), float(g["width"])
                        for sx, sy, sz in _sample_segment(cx, cy, cz, nx, ny, nz, step=3.0):
                            if (sx + cur_r > bx - bL / 2 + TOL_MM and sx - cur_r < bx + bL / 2 - TOL_MM
                                    and sy + cur_r > by - bW / 2 + TOL_MM and sy - cur_r < by + bW / 2 - TOL_MM):
                                gouge_count += 1
                                if gouge_count <= 5:
                                    add_risk("CRITICAL", "GOUGE",
                                             f"凸台轮廓 {op.op_id} 刀具侵入凸台 ({sx:.2f},{sy:.2f})", idx, sx, sy, sz, m.op_id)
                                break
                    elif cat in ("spot_drill", "drill", "ream", "tap"):
                        h_depth = float(g["depth"])
                        if nz < -h_depth - 0.5:
                            gouge_count += 1
                            add_risk("CRITICAL", "GOUGE", f"孔加工 {op.op_id} 过深 Z={nz:.2f} < {-h_depth:.2f}", idx, nx, ny, nz, m.op_id)
                        if nz < 0:
                            key = (round(nx, 1), round(ny, 1))
                            drilled_depth[key] = max(drilled_depth.get(key, 0.0), -nz)
                            if holes_xy and not any(math.hypot(nx - hx, ny - hy) <= 0.15 for hx, hy, _ in holes_xy):
                                gouge_count += 1
                                add_risk("CRITICAL", "GOUGE", f"孔位 ({nx:.2f},{ny:.2f}) 不在规划孔坐标列表中", idx, nx, ny, nz, m.op_id)
                    elif cat == "slot_mill":
                        s_depth = float(g["depth"])
                        if nz < -s_depth - TOL_MM:
                            gouge_count += 1
                            add_risk("CRITICAL", "GOUGE", f"槽铣 {op.op_id} 深度过切 Z={nz:.2f} < {-s_depth:.2f}", idx, nx, ny, nz, m.op_id)

            cx, cy, cz = nx, ny, nz

    if not saw_end:
        risks.append(_risk("HIGH", "MISSING_PROGRAM_END", "程序末尾缺少 M30 结束指令"))

    blocking = any(r.level in ("CRITICAL", "HIGH") for r in risks)
    return {
        "passed": not blocking,
        "risks": risks,
        "stats": {
            "moves_checked": len(ir),
            "collisions": collision_count,
            "gouges": gouge_count,
            "rapid_plunges": plunge_count,
        },
        "risk_points": risk_points,
    }
