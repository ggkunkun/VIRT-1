"""工序方案 → 控制系统无关的中间表示（IR: List[Move]）。

完全解耦：只依赖 ``cam_autogen.contracts``，不依赖 M1/M2/M4。
坐标约定：
  - 铣削（MILLING）：XYZ 工件坐标（mm），Z=0 为精加工顶面，毛坯顶 Z=+z_top_allow。
  - 车削 / 车铣（TURNING / TURN_MILL）：X 为直径值（mm，X=2r），Z=0 为右端面，-Z 指向卡盘；
    C 为主轴分度角（deg）。所有切削进给均显式展开为 Move，不藏在黑箱固定循环内，以便逐段校验。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from cam_autogen.contracts import Move, Operation, PostProfile, ProcessPlan, ProcessType, StockSetup

TURNING_OPS = {"face_turn", "od_rough", "od_finish", "groove", "thread", "drill_axial", "bore"}


def _z_at_top(stock_setup: Optional[StockSetup]) -> float:
    if stock_setup and "z_top_allow" in stock_setup.part_offset_in_stock:
        return float(stock_setup.part_offset_in_stock["z_top_allow"])
    if stock_setup and "z_face_allow" in stock_setup.part_offset_in_stock:
        return float(stock_setup.part_offset_in_stock["z_face_allow"])
    return 1.0


def _tool_map(plan: ProcessPlan, profile: PostProfile) -> Dict[str, int]:
    mapping = dict(profile.tool_number_map)
    for op in plan.operations:
        if op.tool.tool_id not in mapping:
            mapping[op.tool.tool_id] = len(mapping) + 1
    return mapping


def _profile_d_at(profile: List[List[float]], z: float) -> Optional[float]:
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


def _rough_z_stop(profile: List[List[float]], d_cut: float, allow_x: float) -> float:
    """从 Z=0 向 -Z 扫掠，找外轮廓（加径向余量）首次超出 d_cut 的 Z 位置。"""
    z_end = profile[-1][0]
    for (z1, d1), (z2, d2) in zip(profile, profile[1:]):
        t1, t2 = d1 + 2 * allow_x, d2 + 2 * allow_x
        if t1 > d_cut + 1e-6:
            return z1
        if t2 > d_cut + 1e-6:
            if abs(t2 - t1) < 1e-9:
                return z2
            frac = (d_cut - t1) / (t2 - t1)
            return z1 + frac * (z2 - z1)
    return z_end


def build_ir(plan: ProcessPlan, stock_setup: Optional[StockSetup], profile: PostProfile) -> Tuple[List[Move], List[Dict[str, Any]]]:
    """把工艺方案转换为完整刀轨 IR 与刀具清单。"""
    tmap = _tool_map(plan, profile)
    z_top = _z_at_top(stock_setup)
    is_lathe_family = plan.process_type in (ProcessType.TURNING, ProcessType.TURN_MILL)
    stock_d = (stock_setup.stock_dims.get("diameter") if stock_setup else None) or 60.0
    for op in plan.operations:
        if "stock_d" in op.geometry:
            stock_d = max(stock_d, float(op.geometry["stock_d"]))
    x_safe = round(max(stock_d + 40.0, 120.0), 3)
    z_safe = 60.0
    z_clear = round(z_top + 25.0, 3)

    moves: List[Move] = [
        Move(kind="comment", text=f"PART: {plan.part_id} | PROCESS: {plan.process_type.value} | MATERIAL: {plan.material}"),
        Move(kind="work_offset", text=profile.work_offset),
    ]
    if is_lathe_family and profile.max_rpm_clamp_code:
        moves.append(Move(kind="comment", text=f"MAX SPINDLE CLAMP: {int(profile.spindle_max_rpm)} RPM"))

    cur_tool: Optional[int] = None
    cur_mode: Optional[str] = None  # "turn" | "live" | "mill"
    spindle_on = False
    live_on = False
    c_on = False
    coolant_on = False
    tool_entries: Dict[int, Dict[str, Any]] = {}

    def stop_cut_aux() -> None:
        nonlocal spindle_on, live_on, coolant_on, c_on
        if coolant_on:
            moves.append(Move(kind="coolant_off"))
            coolant_on = False
        if live_on:
            moves.append(Move(kind="live_spindle_stop"))
            live_on = False
        if spindle_on:
            moves.append(Move(kind="spindle_stop"))
            spindle_on = False
        if c_on:
            moves.append(Move(kind="c_axis", text="off"))
            c_on = False

    def retract_home() -> None:
        if is_lathe_family:
            moves.append(Move(kind="safe_retract", x=x_safe, z=z_safe))
        else:
            moves.append(Move(kind="safe_retract", z=z_clear))

    for op in plan.operations:
        tno = tmap[op.tool.tool_id]
        tool_entries[tno] = {
            "tool_no": tno,
            "tool_id": op.tool.tool_id,
            "kind": op.tool.kind,
            "diameter": op.tool.diameter,
            "length": op.tool.length,
            "flutes": op.tool.flutes,
            "corner_radius": op.tool.corner_radius,
            "setup": op.setup,
        }
        desired_mode = ("live" if op.setup == "live" else "turn") if is_lathe_family else "mill"

        if cur_tool != tno or cur_mode != desired_mode:
            stop_cut_aux()
            retract_home()
            if cur_tool != tno:
                moves.append(Move(kind="tool_change", tool=tno, text=f"{op.tool.tool_id} ({op.tool.kind} D{op.tool.diameter:g})",
                                  op_id=op.op_id))
                cur_tool = tno
        moves.append(Move(kind="comment", text=f"{op.op_id}: {op.category} features={op.feature_ids}", op_id=op.op_id))

        if is_lathe_family:
            if desired_mode == "live":
                if not c_on:
                    moves.append(Move(kind="c_axis", text="on", c=0.0, op_id=op.op_id))
                    c_on = True
                if cur_mode != "live":
                    moves.append(Move(kind="feed_mode", text="mm_min", op_id=op.op_id))
                moves.append(Move(kind="live_spindle", s=op.params.rpm, text="CW", op_id=op.op_id))
                live_on = True
            else:
                if cur_mode != "turn":
                    moves.append(Move(kind="feed_mode", text="mm_rev", op_id=op.op_id))
                if op.params.constant_surface_speed:
                    moves.append(Move(kind="css", s=op.params.vc_m_min, extra={"max_rpm": min(op.params.rpm * 1.05, profile.spindle_max_rpm)},
                                      op_id=op.op_id))
                else:
                    moves.append(Move(kind="spindle", s=op.params.rpm, text="CW", op_id=op.op_id))
                spindle_on = True
            cur_mode = desired_mode
        else:
            if cur_mode is None:
                moves.append(Move(kind="feed_mode", text="mm_min", op_id=op.op_id))
                cur_mode = "mill"
            moves.append(Move(kind="spindle", s=op.params.rpm, text="CW", op_id=op.op_id))
            spindle_on = True

        if not coolant_on:
            moves.append(Move(kind="coolant", op_id=op.op_id))
            coolant_on = True

        if desired_mode == "mill":
            _emit_milling_op(op, moves, z_top, z_clear)
        elif desired_mode == "turn":
            _emit_turning_op(op, moves, stock_d, z_top, x_safe)
        else:
            _emit_live_op(op, moves, stock_d, z_top, x_safe)

    stop_cut_aux()
    retract_home()
    moves.append(Move(kind="program_end"))
    tool_table = [tool_entries[k] for k in sorted(tool_entries)]
    return moves, tool_table


# ------------------------------------------------------------------ 铣削刀轨
def _emit_milling_op(op: Operation, moves: List[Move], z_top: float, z_clear: float) -> None:
    c, g = op.category, op.geometry
    D = op.tool.diameter
    R = D / 2.0
    ap = max(op.params.ap_mm, 0.1)
    ae = max(op.params.ae_mm or (0.5 * D), 0.1)
    vf = op.params.feed_mm_min
    vf_plunge = round(max(60.0, 0.4 * vf), 1)
    z_app = round(z_top + 2.0, 3)

    def r3(v: float) -> float:
        return round(v, 3)

    if c == "face_mill":
        xmin, xmax = float(g["xmin"]), float(g["xmax"])
        ymin, ymax = float(g["ymin"]), float(g["ymax"])
        zs, ze = float(g["z_start"]), float(g["z_end"])
        n_z = max(1, math.ceil((zs - ze) / ap - 1e-9))
        dz = (zs - ze) / n_z
        x_lo, x_hi = r3(xmin - R - 3.0), r3(xmax + R + 3.0)
        ys: List[float] = []
        y = ymin + R * 0.4
        while y < ymax - R * 0.2:
            ys.append(r3(y))
            y += ae
        if not ys:
            ys = [r3((ymin + ymax) / 2)]
        else:
            last_y = r3(max(ymin, ymax - R * 0.4))
            if ys[-1] < last_y - 0.5:
                ys.append(last_y)
        for kz in range(1, n_z + 1):
            zc = r3(zs - kz * dz)
            moves.append(Move(kind="rapid", x=x_lo, y=ys[0], z=z_clear, op_id=op.op_id))
            moves.append(Move(kind="rapid", x=x_lo, y=ys[0], z=z_app, op_id=op.op_id))
            moves.append(Move(kind="linear", x=x_lo, y=ys[0], z=zc, f=vf_plunge, op_id=op.op_id))
            for idx, yy in enumerate(ys):
                tx = x_hi if idx % 2 == 0 else x_lo
                if idx > 0:
                    moves.append(Move(kind="linear", y=yy, f=vf, op_id=op.op_id))
                moves.append(Move(kind="linear", x=tx, f=vf, op_id=op.op_id))
            moves.append(Move(kind="rapid", z=z_clear, op_id=op.op_id))
        return

    if c in ("outline_profile", "contour_rough", "contour_finish"):
        if c == "outline_profile":
            x0, x1 = float(g["xmin"]), float(g["xmax"])
            y0, y1 = float(g["ymin"]), float(g["ymax"])
        else:
            cx, cy, L, W = float(g["x"]), float(g["y"]), float(g["length"]), float(g["width"])
            x0, x1, y0, y1 = cx - L / 2, cx + L / 2, cy - W / 2, cy + W / 2
        depth = float(g["depth"])
        allow = float(g.get("allowance", 0.0))
        if c == "contour_finish":
            offsets = [0.0]
        elif c == "contour_rough":
            offsets = [allow]
        else:
            n_rad = max(1, math.ceil(allow / ae - 1e-9))
            offsets = [allow - k * (allow / n_rad) for k in range(1, n_rad + 1)]
        n_z = max(1, math.ceil(depth / ap - 1e-9))
        dz = depth / n_z
        for off in offsets:
            xlo, xhi = r3(x0 - R - off), r3(x1 + R + off)
            ylo, yhi = r3(y0 - R - off), r3(y1 + R + off)
            xe, ye = r3(xlo - 3.0), r3(ylo - 3.0)
            for kz in range(1, n_z + 1):
                zc = r3(-kz * dz)
                moves.append(Move(kind="rapid", x=xe, y=ye, z=z_clear, op_id=op.op_id))
                moves.append(Move(kind="rapid", x=xe, y=ye, z=z_app, op_id=op.op_id))
                moves.append(Move(kind="linear", x=xe, y=ye, z=zc, f=vf_plunge, op_id=op.op_id))
                moves.append(Move(kind="linear", x=xlo, y=ylo, f=vf, op_id=op.op_id))
                moves.append(Move(kind="linear", x=xlo, y=yhi, f=vf, op_id=op.op_id))
                moves.append(Move(kind="linear", x=xhi, y=yhi, f=vf, op_id=op.op_id))
                moves.append(Move(kind="linear", x=xhi, y=ylo, f=vf, op_id=op.op_id))
                moves.append(Move(kind="linear", x=xlo, y=ylo, f=vf, op_id=op.op_id))
                moves.append(Move(kind="linear", x=xe, y=ye, f=vf, op_id=op.op_id))
                moves.append(Move(kind="rapid", z=z_clear, op_id=op.op_id))
        return

    if c in ("pocket_rough", "pocket_finish"):
        cx, cy = float(g["x"]), float(g["y"])
        L, W, depth = float(g["length"]), float(g["width"]), float(g["depth"])
        cr = float(g.get("corner_radius", 0.0))
        allow = 0.0 if c == "pocket_finish" else float(g.get("allowance", 0.0))
        hx = max(0.1, L / 2 - R - allow)
        hy = max(0.1, W / 2 - R - allow)
        n_z = 1 if c == "pocket_finish" else max(1, math.ceil(depth / ap - 1e-9))
        dz = depth / n_z
        ramp_dx = min(hx, max(1.0, R * 0.5))
        for kz in range(1, n_z + 1):
            zc = r3(-kz * dz)
            z_prev = r3(-(kz - 1) * dz)
            moves.append(Move(kind="rapid", x=r3(cx - ramp_dx), y=r3(cy), z=z_clear, op_id=op.op_id))
            moves.append(Move(kind="rapid", x=r3(cx - ramp_dx), y=r3(cy), z=z_app, op_id=op.op_id))
            if kz > 1:
                moves.append(Move(kind="linear", x=r3(cx - ramp_dx), y=r3(cy), z=r3(z_prev + 1.0), f=vf, op_id=op.op_id))
            # 斜坡下刀（避免垂直扎刀）
            moves.append(Move(kind="linear", x=r3(cx + ramp_dx), y=r3(cy), z=zc, f=vf_plunge, op_id=op.op_id))
            moves.append(Move(kind="linear", x=r3(cx - ramp_dx), y=r3(cy), z=zc, f=vf, op_id=op.op_id))
            if c == "pocket_rough":
                max_span = max(hx, hy)
                n_loops = max(1, math.ceil(max_span / ae))
                for k in range(1, n_loops + 1):
                    frac = k / n_loops
                    dx, dy = r3(hx * frac), r3(hy * frac)
                    moves.append(Move(kind="linear", x=r3(cx - dx), y=r3(cy - dy), f=vf, op_id=op.op_id))
                    moves.append(Move(kind="linear", x=r3(cx + dx), y=r3(cy - dy), f=vf, op_id=op.op_id))
                    moves.append(Move(kind="linear", x=r3(cx + dx), y=r3(cy + dy), f=vf, op_id=op.op_id))
                    moves.append(Move(kind="linear", x=r3(cx - dx), y=r3(cy + dy), f=vf, op_id=op.op_id))
                    moves.append(Move(kind="linear", x=r3(cx - dx), y=r3(cy - dy), f=vf, op_id=op.op_id))
            else:
                rc = max(0.0, min(cr - R, hx - 0.1, hy - 0.1))
                _emit_rounded_rect_ccw(moves, cx, cy, hx, hy, rc, vf, op.op_id)
            moves.append(Move(kind="rapid", z=z_clear, op_id=op.op_id))
        return

    if c == "slot_mill":
        x1, y1, x2, y2 = float(g["x1"]), float(g["y1"]), float(g["x2"]), float(g["y2"])
        depth, W = float(g["depth"]), float(g["width"])
        n_z = max(1, math.ceil(depth / ap - 1e-9))
        dz = depth / n_z
        L = math.hypot(x2 - x1, y2 - y1) or 1.0
        nx, ny = -(y2 - y1) / L, (x2 - x1) / L
        side = max(0.0, (W - D) / 2.0)
        offsets = [0.0] if side <= 0.05 else [-side, side]
        for off in offsets:
            sx, sy = r3(x1 + nx * off), r3(y1 + ny * off)
            ex, ey = r3(x2 + nx * off), r3(y2 + ny * off)
            moves.append(Move(kind="rapid", x=sx, y=sy, z=z_clear, op_id=op.op_id))
            moves.append(Move(kind="rapid", x=sx, y=sy, z=z_app, op_id=op.op_id))
            for kz in range(1, n_z + 1):
                zc = r3(-kz * dz)
                moves.append(Move(kind="linear", x=ex, y=ey, z=zc, f=vf_plunge, op_id=op.op_id))
                moves.append(Move(kind="linear", x=sx, y=sy, z=zc, f=vf, op_id=op.op_id))
            moves.append(Move(kind="linear", x=ex, y=ey, f=vf, op_id=op.op_id))
            moves.append(Move(kind="rapid", z=z_clear, op_id=op.op_id))
        return

    if c in ("spot_drill", "drill", "ream", "tap"):
        holes = g["holes"]
        depth = float(g["depth"])
        for h in holes:
            hx, hy = r3(float(h["x"])), r3(float(h["y"]))
            moves.append(Move(kind="rapid", x=hx, y=hy, z=z_clear, op_id=op.op_id))
            moves.append(Move(kind="rapid", x=hx, y=hy, z=z_app, op_id=op.op_id))
            if c == "spot_drill":
                moves.append(Move(kind="linear", x=hx, y=hy, z=r3(-depth), f=vf, op_id=op.op_id))
                moves.append(Move(kind="dwell", f=0.2, op_id=op.op_id))
                moves.append(Move(kind="rapid", x=hx, y=hy, z=z_app, op_id=op.op_id))
            elif c == "drill":
                peck = max(1.0, min(D, depth))
                cur = 0.0
                while cur < depth - 1e-6:
                    cur = min(depth, cur + peck)
                    moves.append(Move(kind="linear", x=hx, y=hy, z=r3(-cur), f=vf, op_id=op.op_id))
                    moves.append(Move(kind="rapid", x=hx, y=hy, z=z_app, op_id=op.op_id))
                    if cur < depth - 1e-6:
                        moves.append(Move(kind="rapid", x=hx, y=hy, z=r3(-max(0.0, cur - 0.8)), op_id=op.op_id))
            elif c == "ream":
                moves.append(Move(kind="linear", x=hx, y=hy, z=r3(-depth), f=vf, op_id=op.op_id))
                moves.append(Move(kind="linear", x=hx, y=hy, z=z_app, f=vf, op_id=op.op_id))
            else:  # tap
                pitch = float(g.get("pitch", op.tool.pitch or 1.0))
                f_tap = round(op.params.rpm * pitch, 1)
                moves.append(Move(kind="linear", x=hx, y=hy, z=r3(-depth), f=f_tap,
                                  extra={"tap_cycle": True, "r": z_app, "pitch": pitch, "rpm": op.params.rpm},
                                  op_id=op.op_id))
                moves.append(Move(kind="linear", x=hx, y=hy, z=z_app, f=f_tap, extra={"tap_retract": True}, op_id=op.op_id))
            moves.append(Move(kind="rapid", z=z_clear, op_id=op.op_id))
        return

    raise ValueError(f"M3 不支持的铣削工序: {c}")


def _emit_rounded_rect_ccw(moves: List[Move], cx: float, cy: float, hx: float, hy: float, rc: float,
                           vf: float, op_id: str) -> None:
    def r3(v: float) -> float:
        return round(v, 3)

    moves.append(Move(kind="linear", x=r3(cx - hx + rc), y=r3(cy - hy), f=vf, op_id=op_id))
    moves.append(Move(kind="linear", x=r3(cx + hx - rc), y=r3(cy - hy), f=vf, op_id=op_id))
    if rc > 0.05:
        moves.append(Move(kind="arc_ccw", x=r3(cx + hx), y=r3(cy - hy + rc), i=0.0, j=r3(rc), f=vf, op_id=op_id))
    moves.append(Move(kind="linear", x=r3(cx + hx), y=r3(cy + hy - rc), f=vf, op_id=op_id))
    if rc > 0.05:
        moves.append(Move(kind="arc_ccw", x=r3(cx + hx - rc), y=r3(cy + hy), i=r3(-rc), j=0.0, f=vf, op_id=op_id))
    moves.append(Move(kind="linear", x=r3(cx - hx + rc), y=r3(cy + hy), f=vf, op_id=op_id))
    if rc > 0.05:
        moves.append(Move(kind="arc_ccw", x=r3(cx - hx), y=r3(cy + hy - rc), i=0.0, j=r3(-rc), f=vf, op_id=op_id))
    moves.append(Move(kind="linear", x=r3(cx - hx), y=r3(cy - hy + rc), f=vf, op_id=op_id))
    if rc > 0.05:
        moves.append(Move(kind="arc_ccw", x=r3(cx - hx + rc), y=r3(cy - hy), i=r3(rc), j=0.0, f=vf, op_id=op_id))


# ------------------------------------------------------------------ 车削刀轨（X=直径）
def _emit_turning_op(op: Operation, moves: List[Move], stock_d: float, z_top: float, x_safe: float) -> None:
    c, g = op.category, op.geometry
    f_rev = round(op.params.feed_per_rev or 0.15, 4)
    ap = max(op.params.ap_mm, 0.1)

    def r3(v: float) -> float:
        return round(v, 3)

    if c == "face_turn":
        sd = float(g["stock_d"])
        zs, ze = float(g["z_start"]), float(g["z_end"])
        n_z = max(1, math.ceil((zs - ze) / ap - 1e-9))
        dz = (zs - ze) / n_z
        moves.append(Move(kind="rapid", x=r3(sd + 4.0), z=r3(zs + 2.0), op_id=op.op_id))
        for k in range(1, n_z + 1):
            zc = r3(zs - k * dz)
            moves.append(Move(kind="rapid", x=r3(sd + 2.0), z=zc, op_id=op.op_id))
            moves.append(Move(kind="linear", x=-0.8, z=zc, f=f_rev, op_id=op.op_id))
            moves.append(Move(kind="linear", x=0.0, z=r3(zc + 1.0), f=f_rev, op_id=op.op_id))
            moves.append(Move(kind="rapid", x=r3(sd + 2.0), z=r3(zc + 1.0), op_id=op.op_id))
        moves.append(Move(kind="rapid", x=x_safe, z=r3(zs + 2.0), op_id=op.op_id))
        return

    if c == "od_rough":
        sd = float(g["stock_d"])
        prof = g["profile"]
        allow_x = float(g.get("allowance_x", 0.0))
        allow_z = 0.15 if allow_x > 0 else 0.0
        min_d = min(d for _, d in prof) + 2 * allow_x
        d_cur = sd
        moves.append(Move(kind="rapid", x=r3(sd + 4.0), z=2.0, op_id=op.op_id))
        while d_cur > min_d + 1e-4:
            d_next = max(min_d, d_cur - 2 * ap)
            z_stop = _rough_z_stop(prof, d_next, allow_x)
            if z_stop < -1e-4:
                z_tgt = min(0.0, z_stop + allow_x * 0.5) if allow_x > 0 else z_stop
                moves.append(Move(kind="rapid", x=r3(d_next), z=2.0, op_id=op.op_id))
                moves.append(Move(kind="linear", x=r3(d_next), z=r3(z_tgt), f=f_rev, op_id=op.op_id))
                moves.append(Move(kind="linear", x=r3(d_next + 1.5), z=r3(z_tgt + 1.0), f=f_rev, op_id=op.op_id))
                moves.append(Move(kind="rapid", x=r3(d_next + 1.5), z=2.0, op_id=op.op_id))
            d_cur = d_next
        # 沿偏移轮廓半精清阶梯
        moves.append(Move(kind="rapid", x=r3(prof[0][1] + 2 * allow_x), z=2.0, op_id=op.op_id))
        for z, d in prof:
            moves.append(Move(kind="linear", x=r3(d + 2 * allow_x), z=r3(z + allow_z if z < 0 else z), f=f_rev, op_id=op.op_id))
        moves.append(Move(kind="linear", x=r3(prof[-1][1] + 2 * allow_x + 3.0), z=r3(prof[-1][0] + allow_z), f=f_rev, op_id=op.op_id))
        moves.append(Move(kind="rapid", x=x_safe, z=2.0, op_id=op.op_id))
        return

    if c == "od_finish":
        prof = g["profile"]
        moves.append(Move(kind="rapid", x=r3(prof[0][1]), z=2.0, op_id=op.op_id))
        moves.append(Move(kind="linear", x=r3(prof[0][1]), z=r3(prof[0][0]), f=f_rev, op_id=op.op_id))
        for z, d in prof[1:]:
            moves.append(Move(kind="linear", x=r3(d), z=r3(z), f=f_rev, op_id=op.op_id))
        moves.append(Move(kind="linear", x=r3(prof[-1][1] + 4.0), z=r3(prof[-1][0]), f=f_rev, op_id=op.op_id))
        moves.append(Move(kind="rapid", x=x_safe, z=2.0, op_id=op.op_id))
        return

    if c == "groove":
        d_bot = float(g["diameter"])
        w = float(g["width"])
        zc = float(g["z"])
        d_start = float(g["start_d"])
        tw = op.tool.diameter
        n_pl = max(1, math.ceil(w / tw - 1e-9))
        zs = [zc] if n_pl == 1 else [zc - w / 2 + tw / 2 + k * (w - tw) / (n_pl - 1) for k in range(n_pl)]
        moves.append(Move(kind="rapid", x=r3(d_start + 6.0), z=2.0, op_id=op.op_id))
        for zp in zs:
            moves.append(Move(kind="rapid", x=r3(d_start + 3.0), z=r3(zp), op_id=op.op_id))
            moves.append(Move(kind="linear", x=r3(d_bot), z=r3(zp), f=f_rev, op_id=op.op_id))
            moves.append(Move(kind="dwell", f=0.2, op_id=op.op_id))
            moves.append(Move(kind="linear", x=r3(d_start + 3.0), z=r3(zp), f=f_rev, op_id=op.op_id))
        moves.append(Move(kind="rapid", x=x_safe, z=2.0, op_id=op.op_id))
        return

    if c == "thread":
        d_nom = float(g["diameter"])
        pitch = float(g["pitch"])
        zs, ze = float(g["z_start"]), float(g["z_end"])
        depth = float(g["depth"])
        passes = int(g.get("passes", 6))
        z_lead = r3(zs + 4.0)
        moves.append(Move(kind="rapid", x=r3(d_nom + 6.0), z=z_lead, op_id=op.op_id))
        for k in list(range(1, passes + 1)) + [passes]:  # 末刀光整
            hk = depth * math.sqrt(k / passes)
            xk = r3(d_nom - 2 * hk)
            moves.append(Move(kind="rapid", x=xk, z=z_lead, op_id=op.op_id))
            moves.append(Move(kind="thread", x=xk, z=r3(ze), f=round(pitch, 4), op_id=op.op_id))
            moves.append(Move(kind="rapid", x=r3(d_nom + 6.0), z=r3(ze), op_id=op.op_id))
            moves.append(Move(kind="rapid", x=r3(d_nom + 6.0), z=z_lead, op_id=op.op_id))
        moves.append(Move(kind="rapid", x=x_safe, z=z_lead, op_id=op.op_id))
        return

    if c == "drill_axial":
        depth = float(g["depth"])
        D = op.tool.diameter
        peck = max(2.0, min(D, depth))
        moves.append(Move(kind="rapid", x=0.0, z=3.0, op_id=op.op_id))
        cur = 0.0
        while cur < depth - 1e-6:
            cur = min(depth, cur + peck)
            moves.append(Move(kind="linear", x=0.0, z=r3(-cur), f=f_rev, op_id=op.op_id))
            moves.append(Move(kind="rapid", x=0.0, z=3.0, op_id=op.op_id))
            if cur < depth - 1e-6:
                moves.append(Move(kind="rapid", x=0.0, z=r3(-max(0.0, cur - 1.0)), op_id=op.op_id))
        moves.append(Move(kind="rapid", x=x_safe, z=3.0, op_id=op.op_id))
        return

    if c == "bore":
        d0, d1, depth = float(g["d_start"]), float(g["d_final"]), float(g["depth"])
        d_cur = d0
        moves.append(Move(kind="rapid", x=r3(max(0.0, d0 - 2.0)), z=3.0, op_id=op.op_id))
        while d_cur < d1 - 1e-4:
            d_next = min(d1, d_cur + 2 * ap)
            moves.append(Move(kind="rapid", x=r3(d_next), z=3.0, op_id=op.op_id))
            moves.append(Move(kind="linear", x=r3(d_next), z=r3(-depth), f=f_rev, op_id=op.op_id))
            moves.append(Move(kind="linear", x=r3(max(0.0, d_next - 1.5)), z=r3(-depth), f=f_rev, op_id=op.op_id))
            moves.append(Move(kind="rapid", x=r3(max(0.0, d_next - 1.5)), z=3.0, op_id=op.op_id))
            d_cur = d_next
        moves.append(Move(kind="rapid", x=x_safe, z=3.0, op_id=op.op_id))
        return

    raise ValueError(f"M3 不支持的车削工序: {c}")


# ------------------------------------------------------------------ 车铣动力刀刀轨
def _emit_live_op(op: Operation, moves: List[Move], stock_d: float, z_top: float, x_safe: float) -> None:
    c, g = op.category, op.geometry
    vf = op.params.feed_mm_min
    vf_plunge = round(max(40.0, 0.4 * vf), 1)
    ap = max(op.params.ap_mm, 0.1)

    def r3(v: float) -> float:
        return round(v, 3)

    if c in ("live_keyway", "live_flat"):
        ca = float(g["c_angle"])
        z1, z2 = float(g["z1"]), float(g["z2"])
        depth = float(g["depth"])
        ds = float(g["d_surface"])
        n_x = max(1, math.ceil(depth / ap - 1e-9))
        dx_rad = depth / n_x
        moves.append(Move(kind="c_axis", c=r3(ca % 360.0), op_id=op.op_id))
        moves.append(Move(kind="rapid", x=r3(ds + 6.0), z=r3(z1), op_id=op.op_id))
        for k in range(1, n_x + 1):
            xc = r3(ds - 2 * k * dx_rad)
            moves.append(Move(kind="linear", x=xc, z=r3(z1), f=vf_plunge, op_id=op.op_id))
            moves.append(Move(kind="linear", x=xc, z=r3(z2), f=vf, op_id=op.op_id))
            moves.append(Move(kind="linear", x=r3(ds + 4.0), z=r3(z2), f=vf, op_id=op.op_id))
            if k < n_x:
                moves.append(Move(kind="rapid", x=r3(ds + 4.0), z=r3(z1), op_id=op.op_id))
        moves.append(Move(kind="rapid", x=x_safe, z=r3(z2), op_id=op.op_id))
        return

    if c == "live_drill_cross":
        ca = float(g["c_angle"])
        z = float(g["z"])
        depth = float(g["depth"])
        ds = float(g["d_surface"])
        D = op.tool.diameter
        peck = max(2.0, min(D, depth))
        x_ret = r3(max(ds + 4.0, stock_d + 2.0))
        moves.append(Move(kind="c_axis", c=r3(ca % 360.0), op_id=op.op_id))
        moves.append(Move(kind="rapid", x=x_ret, z=r3(z), op_id=op.op_id))
        cur = 0.0
        while cur < depth - 1e-6:
            cur = min(depth, cur + peck)
            moves.append(Move(kind="linear", x=r3(ds - 2 * cur), z=r3(z), f=vf, op_id=op.op_id))
            moves.append(Move(kind="rapid", x=x_ret, z=r3(z), op_id=op.op_id))
        moves.append(Move(kind="rapid", x=x_safe, z=r3(z), op_id=op.op_id))
        return

    if c == "live_drill_axial":
        depth = float(g["depth"])
        D = op.tool.diameter
        peck = max(2.0, min(D, depth))
        for h in g["holes"]:
            ca = float(h["angle"]) % 360.0
            xh = r3(2.0 * float(h["radius"]))
            moves.append(Move(kind="c_axis", c=r3(ca), op_id=op.op_id))
            moves.append(Move(kind="rapid", x=xh, z=3.0, op_id=op.op_id))
            cur = 0.0
            while cur < depth - 1e-6:
                cur = min(depth, cur + peck)
                moves.append(Move(kind="linear", x=xh, z=r3(-cur), f=vf, op_id=op.op_id))
                moves.append(Move(kind="rapid", x=xh, z=3.0, op_id=op.op_id))
        moves.append(Move(kind="rapid", x=x_safe, z=3.0, op_id=op.op_id))
        return

    raise ValueError(f"M3 不支持的动力刀工序: {c}")
