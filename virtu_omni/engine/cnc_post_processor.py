# -*- coding: utf-8 -*-
"""cnc_post_processor.py — 真实多控制器、多轴及车铣复合 CNC 后处理器（CL 中间表示 -> 方言 NC）。

支持机床类型与运动学能力：
  * 三轴铣削 (milling_3axis): X/Y/Z 线性插补 + 固定循环
  * 四轴分度 (milling_4axis_indexed): 3+1 旋转轴分度定位与锁紧 (M11/M10)
  * 四轴联动 (milling_4axis_simultaneous): X/Y/Z + 单旋转轴 (A/B/C) 同步切削进给
  * 五轴 3+2 定位 (milling_5axis_3plus2): FANUC G68.2+G53.1/G69、Siemens CYCLE800、Heidenhain PLANE SPATIAL
  * 五轴联动 (milling_5axis_simultaneous): FANUC G43.4/G49、Siemens TRAORI/TRAFOOF、Heidenhain FUNCTION TCPM (AC/BC/AB)
  * 车削中心 (turning): X/Z 车削粗精循环 (FANUC G71/G70、Siemens CYCLE95)
  * 车铣复合 (mill_turn_off_axis_milling / mill_turn_y_axis_milling):
    C 轴分度与极坐标插补 (G12.1/TRANSMIT)、圆柱插补 (G07.1/TRACYL)、Y 轴偏心铣、B 轴摆头复合
  * 复合加工中心副主轴接料 (subspindle_transfer): 主副主轴同步接料、W 轴移送、G55 背加工

设计公理（测量宪法 §8）：
  1. 每个方言发射器都配 ``validate_dialect`` 结构门——空程序 / 缺主轴 / 缺循环 /
     五轴误用 TRAORI/G43.4 / RTCP或倾斜面或极坐标未配对取消 / 副主轴先松主卡盘 一律判红。
  2. ``round_trip_coords`` 与 ``round_trip_pose`` 把发射出的 NC 重新解析回坐标，
     与 CL 逐点核对（±tol），证明同一刀路在三种方言下线性与旋转坐标一致。
  3. 诚实边界：这是 CL->方言的**语法/坐标**后处理器，不含具体机床的运动学标定、
     RTCP 摆长补偿、螺距误差表或实体碰撞仿真；生产下机仍须真实后处理文件与 VERICUT 仿真取证。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

SUPPORTED_DIALECTS = ("fanuc", "siemens", "heidenhain")
_COORD_TOL_MM = 1e-3
_ROTARY_AXES = ("A", "B", "C")
_ALL_POSE_AXES = ("X", "Y", "Z", "A", "B", "C", "W")


# ===========================================================================
# 1. CL 中间表示（与控制器无关的多轴/车铣刀位数据）
# ===========================================================================
@dataclass
class CLMove:
    """直线/圆弧刀位。mode: rapid|feed|arc_cw|arc_ccw。坐标绝对 mm/deg，缺省为模态继承。"""
    mode: str
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    i: Optional[float] = None   # 圆弧圆心增量（FANUC I/J 风格）
    j: Optional[float] = None
    f: Optional[float] = None   # 进给 mm/min 或 mm/rev
    a: Optional[float] = None
    b: Optional[float] = None
    c: Optional[float] = None
    w: Optional[float] = None


@dataclass
class CLToolChange:
    tool_id: int
    diameter_mm: float = 0.0
    length_mm: float = 0.0


@dataclass
class CLSpindle:
    rpm: int
    direction: str = "cw"       # cw|ccw|stop


@dataclass
class CLCoolant:
    on: bool = True


@dataclass
class CLCycle:
    """固定循环。kind: drill|peck|tap。z_depth 为孔底绝对坐标，r_plane 为参考平面。"""
    kind: str
    x: float
    y: float
    z_depth: float
    r_plane: float
    peck_q: float = 0.0
    dwell_s: float = 0.0
    feed: float = 100.0


@dataclass
class CLRotaryIndex:
    """四轴分度 (3+1) 或五轴旋转轴独立定位与锁紧。"""
    a: Optional[float] = None
    b: Optional[float] = None
    c: Optional[float] = None
    clamp: bool = True


@dataclass
class CLWorkplaneTilt:
    """五轴 3+2 倾斜工作平面 (G68.2 / CYCLE800 / PLANE SPATIAL)。"""
    euler_a: float = 0.0
    euler_b: float = 0.0
    euler_c: float = 0.0
    origin: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    active: bool = True
    rotary_pair: str = "AC"


@dataclass
class CLRTCP:
    """五轴联动刀尖点跟随 (G43.4/G43.5 / TRAORI / FUNCTION TCPM)。"""
    active: bool = True
    tool_offset_h: int = 1
    vector_mode: bool = False


@dataclass
class CLTurningCycle:
    """车削粗精复合循环 (FANUC G71/G70 / Siemens CYCLE95)。"""
    stock_d: float
    steps: List[Tuple[float, float]]
    total_len: float
    u_depth: float = 1.5
    r_retract: float = 0.5
    u_finish: float = 0.4
    w_finish: float = 0.1
    feed_rough: float = 0.25
    feed_finish: float = 0.12
    p_start: int = 10
    q_end: Optional[int] = None


@dataclass
class CLMillTurnMode:
    """车铣复合模式与插补切换 (车削 / C轴极坐标 / 圆柱插补 / Y轴动力刀 / B轴摆头)。"""
    mode: str = "milling"               # turning | milling
    live_rpm: int = 0
    c_axis_engage: bool = True
    interpolation: str = "cartesian"    # cartesian | polar | cylindrical
    cylinder_radius_mm: float = 0.0
    b_head_angle_deg: Optional[float] = None
    active: bool = True
    turning_rpm: int = 1200


@dataclass
class CLSubspindleTransfer:
    """复合加工中心主/副主轴同步接料与背加工切换。"""
    z_pickup_mm: float = -35.0
    w_home_mm: float = 0.0
    sync_rpm: int = 0
    cutoff: bool = True
    w_pickup_mm: float = -120.0
    back_wcs: str = "G55"


@dataclass
class CLProgram:
    name: str = "VIRTU"
    units: str = "mm"           # mm|inch
    five_axis: bool = False
    wcs: str = "G54"
    ops: List[Any] = field(default_factory=list)
    machine_type: str = "milling_3axis"
    rotary_axes: Tuple[str, ...] = ()
    has_y_axis: Optional[bool] = None


# ===========================================================================
# 2. CL 级安全门（先于方言发射；可证伪）
# ===========================================================================
def _turning_profile_targets(cycle: CLTurningCycle) -> List[Tuple[float, float]]:
    targets: List[Tuple[float, float]] = []
    z = 0.0
    for d, length in cycle.steps:
        z -= float(length)
        targets.append((float(d), z))
    if abs(z) < float(cycle.total_len) - 1e-9:
        targets.append((float(cycle.stock_d), -float(cycle.total_len)))
    return targets


def validate_program(prog: CLProgram) -> Dict[str, Any]:
    """CL 级模态/多轴/车铣安全门。空程序、无主轴、快速扎刀、RTCP/倾斜面未配对一律判红。"""
    violations: List[str] = []
    if not prog.ops:
        violations.append("EMPTY_PROGRAM: 刀位程序为空，禁止发射")

    has_spindle = False
    spindle_active = False
    turning_spindle_active = False
    live_tool_active = False
    has_feed = False
    r_plane: Optional[float] = None
    rtcp_active = False
    rtcp_ever_opened = False
    tilt_active = False
    tilt_ever_opened = False
    polar_active = False
    cylindrical_active = False
    clamped_rotary: Dict[str, bool] = {}
    rotary_axes_in_moves: set[str] = set()
    has_rotary_index = False
    has_turning_cycle = False

    prev_rot: Dict[str, float] = {"A": 0.0, "B": 0.0, "C": 0.0}
    for op in prog.ops:
        if isinstance(op, CLSpindle):
            if op.direction in ("cw", "ccw") and op.rpm > 0:
                has_spindle = True
                spindle_active = True
                if prog.machine_type in ("turning", "lathe") or prog.machine_type.startswith("mill_turn") or prog.machine_type == "subspindle_transfer":
                    turning_spindle_active = True
            elif op.direction == "stop":
                spindle_active = False
                turning_spindle_active = False
                live_tool_active = False
        elif isinstance(op, CLMillTurnMode):
            if op.mode == "milling":
                if op.active:
                    if op.live_rpm > 0:
                        has_spindle = True
                        spindle_active = True
                        live_tool_active = True
                        turning_spindle_active = False
                    else:
                        spindle_active = False
                        live_tool_active = False
                    if op.interpolation == "polar":
                        polar_active = True
                    elif op.interpolation == "cylindrical":
                        if op.cylinder_radius_mm <= 0:
                            violations.append("CYLINDRICAL_RADIUS_INVALID: 圆柱插补半径必须为正")
                        cylindrical_active = True
                else:
                    if op.interpolation == "polar":
                        polar_active = False
                    elif op.interpolation == "cylindrical":
                        cylindrical_active = False
                    live_tool_active = False
                    spindle_active = False
            elif op.mode == "turning":
                if polar_active:
                    polar_active = False
                if cylindrical_active:
                    cylindrical_active = False
                live_tool_active = False
                if op.active and op.turning_rpm > 0:
                    has_spindle = True
                    spindle_active = True
                    turning_spindle_active = True
                else:
                    spindle_active = False
                    turning_spindle_active = False
        elif isinstance(op, CLRotaryIndex):
            has_rotary_index = True
            for axis, val in (("A", op.a), ("B", op.b), ("C", op.c)):
                if val is not None:
                    prev_rot[axis] = float(val)
                    clamped_rotary[axis] = bool(op.clamp)
        elif isinstance(op, CLWorkplaneTilt):
            if op.active:
                if rtcp_active:
                    violations.append("RTCP_AND_TILT_PLANE_CONFLICT: 不可在 RTCP 开启状态下激活 3+2 倾斜平面")
                tilt_active = True
                tilt_ever_opened = True
            else:
                tilt_active = False
        elif isinstance(op, CLRTCP):
            if op.active:
                if tilt_active:
                    violations.append("RTCP_AND_TILT_PLANE_CONFLICT: 激活 RTCP 前必须先取消 3+2 倾斜工作平面")
                rtcp_active = True
                rtcp_ever_opened = True
            else:
                rtcp_active = False
        elif isinstance(op, CLTurningCycle):
            has_turning_cycle = True
            if op.u_depth <= 0 or op.r_retract <= 0 or op.stock_d <= 0 or op.total_len <= 0:
                violations.append("TURNING_CYCLE_INVALID_PARAMS: G71/CYCLE95 切深/退刀/毛坯尺寸必须为正")
            if not op.steps or any(d <= 0 or d >= op.stock_d or L <= 0 for d, L in op.steps):
                violations.append("TURNING_CYCLE_INVALID_STEPS: 台阶直径必须小于毛坯直径且长度大于 0")
            if sum(L for _, L in op.steps) > op.total_len + 1e-6:
                violations.append("TURNING_CYCLE_LENGTH_EXCEEDED: 台阶总长超出零件总长")
            if not spindle_active:
                violations.append("NO_SPINDLE: 车削循环前未启动主轴")
        elif isinstance(op, CLSubspindleTransfer):
            if abs(float(op.w_pickup_mm) - float(op.w_home_mm)) < 1e-3:
                violations.append("SUBSPINDLE_NO_TRANSFER_STROKE: 副主轴接料行程为零")
            if op.sync_rpm < 0:
                violations.append("SUBSPINDLE_NEGATIVE_SYNC_RPM: 同步转速不可为负")
        elif isinstance(op, CLCycle):
            r_plane = op.r_plane
            if not spindle_active:
                violations.append("NO_SPINDLE: 固定循环前未启动主轴")
        elif isinstance(op, CLMove):
            if op.mode == "rapid" and op.z is not None:
                if r_plane is not None and op.z < r_plane - _COORD_TOL_MM:
                    violations.append(
                        f"RAPID_PLUNGE: G00 快速下刀 Z={op.z} 低于参考平面 {r_plane}，撞刀风险")
                elif op.z < -_COORD_TOL_MM:
                    violations.append(
                        f"RAPID_NEGATIVE_Z: G00 快速下刀 Z={op.z} < 0，撞刀风险")
            moved_rotary: List[str] = []
            for axis, val in (("A", op.a), ("B", op.b), ("C", op.c)):
                if val is not None:
                    rotary_axes_in_moves.add(axis)
                    if abs(float(val) - prev_rot[axis]) > 1e-6:
                        moved_rotary.append(axis)
                    elif op.mode in ("feed", "arc_cw", "arc_ccw"):
                        # Explicit rotary word in feed block counts as active axis participation
                        moved_rotary.append(axis)
                    prev_rot[axis] = float(val)
            if op.mode in ("feed", "arc_cw", "arc_ccw"):
                has_feed = True
                if not spindle_active:
                    violations.append("NO_SPINDLE: 存在切削进给但未启动主轴 (M03/M04)")
                for axis in moved_rotary:
                    if clamped_rotary.get(axis) and not rtcp_active:
                        violations.append(
                            f"ROTARY_AXIS_CLAMPED_DURING_FEED: 旋转轴 {axis} 处于锁紧状态却执行切削进给")
                if len(set(moved_rotary)) >= 2 and not rtcp_active:
                    violations.append("FIVE_AXIS_RTCP_NOT_ACTIVE: 五轴联动进给块未开启 RTCP/TRAORI/TCPM")
                if (prog.machine_type.startswith("mill_turn") or prog.machine_type == "subspindle_transfer") and has_turning_cycle:
                    y_off_center = op.y is not None and abs(float(op.y)) > 1e-9
                    if turning_spindle_active and not live_tool_active and ("C" in moved_rotary or y_off_center):
                        violations.append(
                            "MILL_TURN_SPINDLE_MODE_CONFLICT: 车削主轴状态下未切换动力头模式即执行 C/Y 轴铣削")

    if has_feed and not has_spindle:
        violations.append("NO_SPINDLE: 存在切削进给但未启动主轴 (M03/M04)")
    if rtcp_active:
        violations.append("FIVE_AXIS_RTCP_NOT_CANCELED: 五轴 RTCP 未配对关闭 (缺 G49/TRAFOOF/FUNCTION RESET TCPM)")
    if tilt_active:
        violations.append("WORKPLANE_TILT_NOT_CANCELED: 五轴 3+2 倾斜平面未配对关闭 (缺 G69/CYCLE800()/PLANE RESET)")
    if polar_active:
        violations.append("POLAR_INTERPOLATION_NOT_CANCELED: 极坐标插补未配对取消 (缺 G13.1/TRAFOOF)")
    if cylindrical_active:
        violations.append("CYLINDRICAL_INTERPOLATION_NOT_CANCELED: 圆柱插补未配对取消 (缺 G07.1 C0/TRAFOOF)")
    if prog.machine_type == "milling_3axis" and not prog.five_axis:
        if rtcp_ever_opened or tilt_ever_opened or rotary_axes_in_moves or has_rotary_index:
            violations.append("THREE_AXIS_MACHINE_MULTIAXIS_MISUSE: 三轴机床程序误用多轴/旋转轴指令")
    if prog.machine_type == "milling_5axis_3plus2" and not (tilt_ever_opened or has_rotary_index):
        violations.append("FIVE_AXIS_3PLUS2_NO_WORKPLANE_OR_INDEX: 五轴 3+2 程序缺少倾斜工作平面或旋转定位")
    if prog.machine_type == "milling_5axis_simultaneous" and not rtcp_ever_opened:
        violations.append("FIVE_AXIS_RTCP_NOT_ACTIVE: 五轴联动程序未开启 RTCP/TRAORI/TCPM")

    violations = list(dict.fromkeys(violations))
    return {"passed": not violations, "violations": violations, "basis": "measured"}


# ===========================================================================
# 3. 方言发射器
# ===========================================================================
def _fmt(v: float) -> str:
    formatted = f"{float(v):.3f}".rstrip("0").rstrip(".")
    return "0" if formatted in ("", "-0") else formatted


def _uses_y_axis(prog: CLProgram) -> bool:
    if prog.has_y_axis is not None:
        return bool(prog.has_y_axis)
    if prog.machine_type in ("turning", "lathe", "mill_turn_off_axis_milling", "mill_turn_c_axis"):
        for op in prog.ops:
            if isinstance(op, CLMove) and op.y is not None and abs(float(op.y)) > 1e-9:
                return True
        return False
    return True


def _resolve_poses(prog: CLProgram) -> List[Tuple[CLMove, Dict[str, float]]]:
    """前向填充全模态位姿 (X, Y, Z, A, B, C, W)，供多轴回读核对。"""
    cur = {axis: 0.0 for axis in _ALL_POSE_AXES}
    out: List[Tuple[CLMove, Dict[str, float]]] = []
    for op in prog.ops:
        if isinstance(op, CLRotaryIndex):
            for axis, val in (("A", op.a), ("B", op.b), ("C", op.c)):
                if val is not None:
                    cur[axis] = float(val)
            continue
        if isinstance(op, CLMillTurnMode) and op.b_head_angle_deg is not None and op.active:
            cur["B"] = float(op.b_head_angle_deg)
            continue
        if not isinstance(op, CLMove):
            continue
        for axis, val in (("X", op.x), ("Y", op.y), ("Z", op.z),
                          ("A", op.a), ("B", op.b), ("C", op.c), ("W", op.w)):
            if val is not None:
                cur[axis] = float(val)
        out.append((op, dict(cur)))
    return out


def _resolve_moves(prog: CLProgram) -> List[Tuple[CLMove, float, float, float]]:
    """把模态坐标前向填充，返回 (move, x, y, z) 显式序列（供发射与回读核对）。"""
    return [(op, pose["X"], pose["Y"], pose["Z"]) for op, pose in _resolve_poses(prog)]


def _resolved_lookup(prog: CLProgram) -> Dict[int, Dict[str, float]]:
    return {id(op): pose for op, pose in _resolve_poses(prog)}


def _emit_turning_profile_fanuc(cycle: CLTurningCycle) -> List[str]:
    p = int(cycle.p_start)
    n = p
    x_start = cycle.stock_d + 2.0
    cur_d = cycle.steps[0][0]
    prof = [f"N{n} G00 X{_fmt(cur_d)}"]
    n += 10
    prof.append(f"N{n} G01 Z0 F{_fmt(cycle.feed_finish)}")
    for d, z_end in _turning_profile_targets(cycle):
        if abs(d - cur_d) > 1e-9:
            n += 10
            prof.append(f"N{n} G01 X{_fmt(d)}")
            cur_d = d
        n += 10
        prof.append(f"N{n} G01 Z{_fmt(z_end)}")
    n += 10
    prof.append(f"N{n} G01 X{_fmt(x_start)}")
    q = cycle.q_end or n
    if cycle.q_end is not None and q != n:
        prof[-1] = f"N{q} G01 X{_fmt(x_start)}"
    return [
        "(TURNING_CYCLE_BEGIN)",
        "G99",
        f"G00 X{_fmt(x_start)} Z2",
        f"G71 U{_fmt(cycle.u_depth)} R{_fmt(cycle.r_retract)}",
        f"G71 P{p} Q{q} U{_fmt(cycle.u_finish)} W{_fmt(cycle.w_finish)} F{_fmt(cycle.feed_rough)}",
        *prof,
        f"G70 P{p} Q{q}",
        "(TURNING_CYCLE_END)",
    ]


def _emit_turning_profile_siemens(cycle: CLTurningCycle) -> List[str]:
    p = int(cycle.p_start)
    n = p
    x_start = cycle.stock_d + 2.0
    cur_d = cycle.steps[0][0]
    prof = [f"N{n} G0 X={_fmt(cur_d)}"]
    n += 10
    prof.append(f"N{n} G1 Z=0 F{_fmt(cycle.feed_finish)}")
    for d, z_end in _turning_profile_targets(cycle):
        if abs(d - cur_d) > 1e-9:
            n += 10
            prof.append(f"N{n} G1 X={_fmt(d)}")
            cur_d = d
        n += 10
        prof.append(f"N{n} G1 Z={_fmt(z_end)}")
    n += 10
    prof.append(f"N{n} G1 X={_fmt(x_start)}")
    return [
        "G95",
        "; TURNING_CYCLE_BEGIN",
        f"G0 X={_fmt(x_start)} Z=2",
        *prof,
        (f'CYCLE95("TURN_PROF",{_fmt(cycle.u_depth)},{_fmt(cycle.u_finish)},'
         f'{_fmt(cycle.w_finish)},,{_fmt(cycle.feed_rough)},{_fmt(cycle.feed_finish)},'
         f'{_fmt(cycle.feed_finish)},9,0,0,0)'),
        "; TURNING_CYCLE_END",
    ]


def emit_fanuc(prog: CLProgram) -> str:
    resolved = _resolved_lookup(prog)
    uses_y = _uses_y_axis(prog)
    polar_active = False
    is_turning_like = prog.machine_type in ("turning", "lathe")
    plane = "G18" if is_turning_like else "G17"
    unit_code = "G21" if prog.units == "mm" else "G20"
    lines = ["%", f"O0001 ({prog.name})", f"{unit_code} G90 {prog.wcs} {plane} G40 G80"]
    for op in prog.ops:
        if isinstance(op, CLToolChange):
            if is_turning_like or prog.machine_type.startswith("mill_turn") or prog.machine_type == "subspindle_transfer":
                lines.append(f"T{op.tool_id:02d}{op.tool_id:02d} (D{_fmt(op.diameter_mm)})")
            else:
                lines.append(f"T{op.tool_id:02d} M06 (D{_fmt(op.diameter_mm)})")
        elif isinstance(op, CLSpindle):
            if op.direction == "stop":
                lines.append("M05")
            else:
                m = "M03" if op.direction == "cw" else "M04"
                lines.append(f"S{op.rpm} {m}")
        elif isinstance(op, CLCoolant):
            lines.append("M08" if op.on else "M09")
        elif isinstance(op, CLRotaryIndex):
            rot_words = [f"{ax}{_fmt(val)}" for ax, val in (("A", op.a), ("B", op.b), ("C", op.c)) if val is not None]
            if rot_words:
                lines.append("M11 (ROTARY UNCLAMP)")
                lines.append("G00 " + " ".join(rot_words))
                if op.clamp:
                    lines.append("M10 (ROTARY CLAMP)")
        elif isinstance(op, CLWorkplaneTilt):
            if op.active:
                ox, oy, oz = op.origin
                lines.append(
                    f"G68.2 X{_fmt(ox)} Y{_fmt(oy)} Z{_fmt(oz)} "
                    f"I{_fmt(op.euler_a)} J{_fmt(op.euler_b)} K{_fmt(op.euler_c)}"
                )
                lines.append("G53.1")
            else:
                lines.append("G69")
        elif isinstance(op, CLRTCP):
            if op.active:
                code = "G43.5" if op.vector_mode else "G43.4"
                lines.append(f"{code} H{int(op.tool_offset_h):02d}")
            else:
                lines.append("G49")
        elif isinstance(op, CLTurningCycle):
            lines.extend(_emit_turning_profile_fanuc(op))
        elif isinstance(op, CLMillTurnMode):
            if op.mode == "milling":
                if op.active:
                    lines.append("M05")
                    if op.c_axis_engage:
                        lines.append("M200 (C-AXIS ENGAGE)")
                    lines.append("G98")
                    if op.b_head_angle_deg is not None:
                        lines.append(f"M11 (B-HEAD UNCLAMP)")
                        lines.append(f"G00 B{_fmt(op.b_head_angle_deg)}")
                        lines.append("M10 (B-HEAD CLAMP)")
                    lines.append(f"G97 S{op.live_rpm} M03 P12 (LIVE TOOL CW)")
                    if op.interpolation == "polar":
                        lines.append("G12.1")
                        polar_active = True
                    elif op.interpolation == "cylindrical":
                        lines.append(f"G07.1 C{_fmt(op.cylinder_radius_mm)}")
                else:
                    if op.interpolation == "polar":
                        lines.append("G13.1")
                        polar_active = False
                    elif op.interpolation == "cylindrical":
                        lines.append("G07.1 C0")
                    lines.append("M05 P12")
                    if op.c_axis_engage:
                        lines.append("M201 (C-AXIS DISENGAGE)")
            else:
                if polar_active:
                    lines.append("G13.1")
                    polar_active = False
                if op.interpolation == "cylindrical":
                    lines.append("G07.1 C0")
                lines.append("G99")
                if op.active and op.turning_rpm > 0:
                    lines.append(f"G97 S{op.turning_rpm} M03")
        elif isinstance(op, CLSubspindleTransfer):
            lines.append("(SUBSPINDLE_TRANSFER_BEGIN)")
            lines.append("G98")
            lines.append("M269 (SUBSPINDLE UNCLAMP)")
            if op.sync_rpm > 0:
                lines.append(f"M203 S{op.sync_rpm} (SYNC SPINDLES)")
            lines.append(f"G00 W{_fmt(op.w_home_mm + 20.0)}")
            lines.append(f"G01 W{_fmt(op.w_pickup_mm)} F500")
            lines.append("M268 (SUBSPINDLE CLAMP)")
            lines.append("M69 (MAIN CHUCK UNCLAMP)")
            lines.append(f"G01 W{_fmt(op.w_home_mm)} F800")
            lines.append(f"{op.back_wcs} (BACK-WORKING WCS)")
            lines.append("(SUBSPINDLE_TRANSFER_END)")
        elif isinstance(op, CLMove):
            pose = resolved[id(op)]
            g = {"rapid": "G00", "feed": "G01", "arc_cw": "G02", "arc_ccw": "G03"}[op.mode]
            words = [g, f"X{_fmt(pose['X'])}"]
            if polar_active:
                words.append(f"C{_fmt(pose['Y'])}")
            elif uses_y:
                words.append(f"Y{_fmt(pose['Y'])}")
            words.append(f"Z{_fmt(pose['Z'])}")
            if not polar_active:
                for ax, val in (("A", op.a), ("B", op.b), ("C", op.c), ("W", op.w)):
                    if val is not None:
                        words.append(f"{ax}{_fmt(val)}")
            else:
                for ax, val in (("A", op.a), ("B", op.b), ("W", op.w)):
                    if val is not None:
                        words.append(f"{ax}{_fmt(val)}")
            if op.mode in ("arc_cw", "arc_ccw"):
                if op.i is not None:
                    words.append(f"I{_fmt(op.i)}")
                if op.j is not None:
                    words.append(f"J{_fmt(op.j)}")
            if op.f is not None:
                words.append(f"F{_fmt(op.f)}")
            lines.append(" ".join(words))
        elif isinstance(op, CLCycle):
            g = {"drill": "G81", "peck": "G83", "tap": "G84"}[op.kind]
            words = [g, f"X{_fmt(op.x)}", f"Y{_fmt(op.y)}", f"Z{_fmt(op.z_depth)}",
                     f"R{_fmt(op.r_plane)}"]
            if op.kind == "peck" and op.peck_q:
                words.append(f"Q{_fmt(op.peck_q)}")
            words.append(f"F{_fmt(op.feed)}")
            lines.append(" ".join(words))
    lines += ["G80", "M09", "M05", "M30", "%"]
    return "\n".join(lines) + "\n"


def emit_siemens(prog: CLProgram) -> str:
    resolved = _resolved_lookup(prog)
    uses_y = _uses_y_axis(prog)
    polar_active = False
    is_turning_like = prog.machine_type in ("turning", "lathe")
    plane = "G18" if is_turning_like else "G17"
    has_explicit_rtcp = any(isinstance(o, CLRTCP) for o in prog.ops)
    lines = [f";{prog.name}", f";UNITS {'MM' if prog.units == 'mm' else 'INCH'}",
             ("G71" if prog.units == "mm" else "G70") + f" G90 {prog.wcs} {plane} G40"]
    if prog.five_axis and not has_explicit_rtcp:
        lines.append("TRAORI")
    for op in prog.ops:
        if isinstance(op, CLToolChange):
            lines.append(f"T{op.tool_id} D1")
        elif isinstance(op, CLSpindle):
            if op.direction == "stop":
                lines.append("M05")
            else:
                m = "M03" if op.direction == "cw" else "M04"
                lines.append(f"S{op.rpm} {m}")
        elif isinstance(op, CLCoolant):
            lines.append("M08" if op.on else "M09")
        elif isinstance(op, CLRotaryIndex):
            rot_words = [f"{ax}={_fmt(val)}" for ax, val in (("A", op.a), ("B", op.b), ("C", op.c)) if val is not None]
            if rot_words:
                lines.append("M11 ;ROTARY UNCLAMP")
                lines.append("G0 " + " ".join(rot_words))
                if op.clamp:
                    lines.append("M10 ;ROTARY CLAMP")
        elif isinstance(op, CLWorkplaneTilt):
            if op.active:
                ox, oy, oz = op.origin
                lines.append(
                    f'CYCLE800(1,"TABLE",100000,57,{_fmt(ox)},{_fmt(oy)},{_fmt(oz)},'
                    f'{_fmt(op.euler_a)},{_fmt(op.euler_b)},{_fmt(op.euler_c)},0,0,0,1,1,1)'
                )
            else:
                lines.append("CYCLE800()")
        elif isinstance(op, CLRTCP):
            lines.append("TRAORI" if op.active else "TRAFOOF")
        elif isinstance(op, CLTurningCycle):
            lines.extend(_emit_turning_profile_siemens(op))
        elif isinstance(op, CLMillTurnMode):
            if op.mode == "milling":
                if op.active:
                    lines.append("M05")
                    if op.c_axis_engage:
                        lines.append("SPOS=0")
                    lines.append("G94")
                    if op.b_head_angle_deg is not None:
                        lines.append("M11 ;B-HEAD UNCLAMP")
                        lines.append(f"G0 B={_fmt(op.b_head_angle_deg)}")
                        lines.append("M10 ;B-HEAD CLAMP")
                    lines.append("SETMS(2)")
                    lines.append(f"S{op.live_rpm} M03")
                    if op.interpolation == "polar":
                        lines.append("TRANSMIT")
                        polar_active = True
                    elif op.interpolation == "cylindrical":
                        lines.append(f"TRACYL({_fmt(2.0 * op.cylinder_radius_mm)})")
                else:
                    if op.interpolation in ("polar", "cylindrical"):
                        lines.append("TRAFOOF")
                        polar_active = False
                    lines.append("M05")
                    lines.append("SETMS(1)")
            else:
                if polar_active or op.interpolation in ("polar", "cylindrical"):
                    lines.append("TRAFOOF")
                    polar_active = False
                lines.append("SETMS(1)")
                lines.append("G95")
                if op.active and op.turning_rpm > 0:
                    lines.append(f"S{op.turning_rpm} M03")
        elif isinstance(op, CLSubspindleTransfer):
            lines.append("; SUBSPINDLE_TRANSFER_BEGIN")
            lines.append("G94")
            lines.append("M269")
            if op.sync_rpm > 0:
                lines.append(f"M203 S{op.sync_rpm}")
            lines.append(f"G0 W={_fmt(op.w_home_mm + 20.0)}")
            lines.append(f"G1 W={_fmt(op.w_pickup_mm)} F500")
            lines.append("M268")
            lines.append("M69")
            lines.append(f"G1 W={_fmt(op.w_home_mm)} F800")
            lines.append(f"{op.back_wcs}")
            lines.append("; SUBSPINDLE_TRANSFER_END")
        elif isinstance(op, CLMove):
            pose = resolved[id(op)]
            g = {"rapid": "G0", "feed": "G1", "arc_cw": "G2", "arc_ccw": "G3"}[op.mode]
            words = [g, f"X={_fmt(pose['X'])}"]
            if uses_y or polar_active:
                words.append(f"Y={_fmt(pose['Y'])}")
            words.append(f"Z={_fmt(pose['Z'])}")
            for ax, val in (("A", op.a), ("B", op.b), ("C", op.c), ("W", op.w)):
                if val is not None:
                    words.append(f"{ax}={_fmt(val)}")
            if op.mode in ("arc_cw", "arc_ccw"):
                if op.i is not None:
                    words.append(f"I={_fmt(op.i)}")
                if op.j is not None:
                    words.append(f"J={_fmt(op.j)}")
            if op.f is not None:
                words.append(f"F{_fmt(op.f)}")
            lines.append(" ".join(words))
        elif isinstance(op, CLCycle):
            lines.append(f"G0 X={_fmt(op.x)} Y={_fmt(op.y)}")
            rtp = op.r_plane + 2.0
            sdis = 2.0
            if op.kind == "drill":
                lines.append(f"CYCLE81({_fmt(rtp)}, {_fmt(op.r_plane)}, {_fmt(sdis)}, "
                             f"{_fmt(op.z_depth)}, )")
            elif op.kind == "peck":
                lines.append(f"CYCLE83({_fmt(rtp)}, {_fmt(op.r_plane)}, {_fmt(sdis)}, "
                             f"{_fmt(op.z_depth)}, , {_fmt(op.peck_q)}, , , , )")
            elif op.kind == "tap":
                lines.append(f"CYCLE84({_fmt(rtp)}, {_fmt(op.r_plane)}, {_fmt(sdis)}, "
                             f"{_fmt(op.z_depth)}, , , {_fmt(op.feed)}, )")
    if prog.five_axis and not has_explicit_rtcp:
        lines.append("TRAFOOF")
    lines += ["M09", "M05", "M30"]
    return "\n".join(lines) + "\n"


def emit_heidenhain(prog: CLProgram) -> str:
    resolved = _resolved_lookup(prog)
    uses_y = _uses_y_axis(prog)
    polar_active = False
    name = re.sub(r"[^A-Za-z0-9_]", "", prog.name)[:12] or "VIRTU"
    unit = "MM" if prog.units == "mm" else "INCH"
    lines = [f"BEGIN PGM {name} {unit}",
             "BLK FORM 0.1 Z X+0 Y+0 Z-50",
             "BLK FORM 0.2 X+100 Y+100 Z+0"]
    prev_x = prev_y = 0.0
    for op in prog.ops:
        if isinstance(op, CLToolChange):
            lines.append(f"TOOL CALL {op.tool_id} Z S0")
        elif isinstance(op, CLSpindle):
            if op.direction == "stop":
                lines.append("L Z+0 R0 FMAX M5")
            else:
                lines.append(f"TOOL CALL 1 Z S{op.rpm}")
        elif isinstance(op, CLCoolant):
            lines.append("M8" if op.on else "M9")
        elif isinstance(op, CLRotaryIndex):
            rot_words = [f"{ax}{float(val):+.3f}" for ax, val in (("A", op.a), ("B", op.b), ("C", op.c)) if val is not None]
            if rot_words:
                lines.append("; ROTARY_INDEX_UNCLAMP")
                lines.append("L " + " ".join(rot_words) + " R0 FMAX")
                if op.clamp:
                    lines.append("; ROTARY_INDEX_CLAMP")
        elif isinstance(op, CLWorkplaneTilt):
            if op.active:
                lines.append(
                    f"PLANE SPATIAL SPA{op.euler_a:+.3f} SPB{op.euler_b:+.3f} "
                    f"SPC{op.euler_c:+.3f} TURN FMAX SEQ+"
                )
            else:
                lines.append("PLANE RESET STAY")
        elif isinstance(op, CLRTCP):
            if op.active:
                lines.append("FUNCTION TCPM F TCP AXIS POS PATHCTRL AXIS")
            else:
                lines.append("FUNCTION RESET TCPM")
        elif isinstance(op, CLTurningCycle):
            lines.append("; TURNING_CYCLE_BEGIN")
            lines.append("FUNCTION MODE TURN")
            lines.append("CYCL DEF 810 TURN CONTOUR LONG")
            lines.append("  Q215=0 ;MACHINING OPERATION")
            lines.append(f"  Q460={_fmt(op.stock_d)} ;STOCK DIAMETER")
            lines.append(f"  Q463={_fmt(op.u_depth)} ;MAX CUTTING DEPTH")
            lines.append(f"  Q478={_fmt(op.feed_rough)} ;ROUGHING FEED")
            lines.append(f"  Q479={_fmt(op.feed_finish)} ;FINISHING FEED")
            for d, z_end in _turning_profile_targets(op):
                lines.append(f"; TURN_STEP X={_fmt(d)} Z={_fmt(z_end)}")
            lines.append("; TURNING_CYCLE_END")
        elif isinstance(op, CLMillTurnMode):
            if op.mode == "milling":
                if op.active:
                    lines.append("FUNCTION MODE MILL")
                    lines.append(f"TOOL CALL 2 Z S{op.live_rpm}")
                    if op.b_head_angle_deg is not None:
                        lines.append("; B-HEAD_INDEX")
                        lines.append(f"L B{op.b_head_angle_deg:+.3f} R0 FMAX")
                    if op.interpolation == "polar":
                        lines.append("FUNCTION POLAR ON")
                        polar_active = True
                    elif op.interpolation == "cylindrical":
                        lines.append(f"FUNCTION CYLINDER R{_fmt(op.cylinder_radius_mm)}")
                else:
                    if op.interpolation == "polar":
                        lines.append("FUNCTION POLAR OFF")
                        polar_active = False
                    elif op.interpolation == "cylindrical":
                        lines.append("FUNCTION CYLINDER OFF")
                    lines.append("M5")
            else:
                if polar_active:
                    lines.append("FUNCTION POLAR OFF")
                    polar_active = False
                lines.append("FUNCTION MODE TURN")
                lines.append(f"TOOL CALL 1 Z S{op.turning_rpm}")
        elif isinstance(op, CLSubspindleTransfer):
            lines.append("; SUBSPINDLE_TRANSFER_BEGIN")
            lines.append("M269")
            lines.append("M268")
            lines.append("M69")
            lines.append(f"{op.back_wcs}")
            lines.append(f"; W_PICKUP={_fmt(op.w_pickup_mm)} W_HOME={_fmt(op.w_home_mm)}")
            lines.append("; SUBSPINDLE_TRANSFER_END")
        elif isinstance(op, CLMove):
            pose = resolved[id(op)]
            x, y, z = pose["X"], pose["Y"], pose["Z"]
            words = ["L", f"X{x:+.3f}"]
            if uses_y or polar_active:
                words.append(f"Y{y:+.3f}")
            words.append(f"Z{z:+.3f}")
            for ax, val in (("A", op.a), ("B", op.b), ("C", op.c), ("W", op.w)):
                if val is not None:
                    words.append(f"{ax}{float(val):+.3f}")
            if op.mode == "rapid":
                words.append("R0 FMAX")
            else:
                words.append("R0")
                if op.f is not None:
                    words.append(f"F{_fmt(op.f)}")
            if op.mode in ("arc_cw", "arc_ccw"):
                dr = "DR+" if op.mode == "arc_ccw" else "DR-"
                if op.i is not None or op.j is not None:
                    # Heidenhain CC 是绝对圆心 = 弧起点 + 增量 (I,J)
                    lines.append(f"CC X{prev_x + (op.i or 0):+.3f} Y{prev_y + (op.j or 0):+.3f}")
                words.append(dr)
            lines.append(" ".join(words))
            prev_x, prev_y = x, y
        elif isinstance(op, CLCycle):
            lines.append(f"L X{op.x:+.3f} Y{op.y:+.3f} R0 FMAX")
            cycl = {"drill": 200, "peck": 203, "tap": 207}[op.kind]
            label = {"drill": "DRILLING", "peck": "UNIVERSAL PECKING", "tap": "TAPPING"}[op.kind]
            lines.append(f"CYCL DEF {cycl} {label}")
            lines.append("  Q200=2 ;SET-UP CLEARANCE")
            lines.append(f"  Q201={op.z_depth:+.3f} ;DEPTH")
            lines.append(f"  Q206={_fmt(op.feed)} ;FEED RATE FOR PLNGNG")
            if op.kind == "peck":
                lines.append(f"  Q202={_fmt(op.peck_q)} ;PLUNGING DEPTH")
            lines.append(f"  Q203={_fmt(op.r_plane)} ;SURFACE COORDINATE")
            lines.append("  Q204=50 ;2ND SET-UP CLEARANCE")
            lines.append("CYCL CALL")
    lines += ["L Z+50 R0 FMAX M5", f"END PGM {name} {unit}"]
    return "\n".join(lines) + "\n"


_EMITTERS = {"fanuc": emit_fanuc, "siemens": emit_siemens, "heidenhain": emit_heidenhain}


# ===========================================================================
# 4. 方言结构门（可证伪：植入坏样本必须判红）
# ===========================================================================
def _ordered_pair_missing(text: str, open_pat: str, close_pat: str) -> Tuple[bool, bool]:
    """Return (missing_open, missing_or_early_close)."""
    m_open = re.search(open_pat, text, re.M)
    if not m_open:
        return True, True
    m_close = re.search(close_pat, text[m_open.end():], re.M)
    return False, (m_close is None)


def validate_dialect(dialect: str, nc_text: str, prog: CLProgram) -> Dict[str, Any]:
    if dialect not in _EMITTERS:
        return {"passed": False, "violations": [f"UNKNOWN_DIALECT: {dialect}"], "basis": "measured"}
    text = nc_text.strip()
    violations: List[str] = []
    if not text:
        violations.append("EMPTY_NC: 发射结果为空")

    has_cycle = any(isinstance(o, CLCycle) for o in prog.ops)
    has_feed = any(isinstance(o, CLMove) and o.mode == "feed" for o in prog.ops)
    has_rtcp = any(isinstance(o, CLRTCP) and o.active for o in prog.ops)
    has_tilt = any(isinstance(o, CLWorkplaneTilt) and o.active for o in prog.ops)
    has_turn = any(isinstance(o, CLTurningCycle) for o in prog.ops)
    has_polar = any(isinstance(o, CLMillTurnMode) and o.active and o.interpolation == "polar" for o in prog.ops)
    has_cyl = any(isinstance(o, CLMillTurnMode) and o.active and o.interpolation == "cylindrical" for o in prog.ops)
    has_subspindle = any(isinstance(o, CLSubspindleTransfer) for o in prog.ops)

    if dialect == "fanuc":
        if not text.startswith("%"):
            violations.append("FANUC_NO_TAPE: 缺少 % 带符号")
        if "M30" not in text:
            violations.append("FANUC_NO_END: 缺少 M30 程序结束")
        if has_feed and not re.search(r"\bM0?3\b|\bM0?4\b", text):
            violations.append("FANUC_NO_SPINDLE: 有切削进给但缺 M03/M04")
        if has_cycle and not re.search(r"\bG8[134]\b", text):
            violations.append("FANUC_NO_CYCLE: 有固定循环但缺 G81/G83/G84")
        if has_rtcp:
            mo, mc = _ordered_pair_missing(text, r"\bG43\.[45]\b", r"\bG49\b")
            if mo:
                violations.append("FANUC_NO_RTCP: 五轴联动缺少 G43.4/G43.5")
            elif mc:
                violations.append("FANUC_RTCP_NO_CANCEL: 五轴 RTCP 缺少 G49 取消")
        if not prog.five_axis and prog.machine_type == "milling_3axis":
            if re.search(r"\bG43\.[45]\b|\bG68\.2\b", text):
                violations.append("FANUC_3AXIS_MULTIAXIS_MISUSE: 三轴程序误用 G43.4/G68.2")
        if has_tilt:
            mo, mc = _ordered_pair_missing(text, r"\bG68\.2\b", r"\bG69\b")
            if mo:
                violations.append("FANUC_NO_TILT_PLANE: 3+2 缺少 G68.2")
            elif mc:
                violations.append("FANUC_TILT_NO_CANCEL: 3+2 倾斜平面缺少 G69 取消")
        if has_turn and not (re.search(r"\bG71\b", text) and re.search(r"\bG70\b", text)):
            violations.append("FANUC_NO_TURNING_CYCLE: 缺 G71/G70 车削循环")
        if has_polar:
            mo, mc = _ordered_pair_missing(text, r"\bG12\.1\b", r"\bG13\.1\b")
            if mo or mc:
                violations.append("FANUC_POLAR_UNPAIRED: 极坐标插补 G12.1/G13.1 未配对")
        if has_cyl:
            mo, mc = _ordered_pair_missing(text, r"\bG0?7\.1\s+C[1-9]\d*(?:\.\d+)?\b", r"\bG0?7\.1\s+C0(?:\.0+)?\b")
            if mo or mc:
                violations.append("FANUC_CYLINDRICAL_UNPAIRED: 圆柱插补 G07.1 C../C0 未配对")
        if has_subspindle:
            mo, mc = _ordered_pair_missing(text, r"\bM268\b", r"\bM69\b")
            if mo or mc:
                violations.append("FANUC_SUBSPINDLE_CLAMP_ORDER: 副主轴接料必须先 M268 夹紧再 M69 松主卡盘")
    elif dialect == "siemens":
        if "M30" not in text:
            violations.append("SIEMENS_NO_END: 缺少 M30")
        if has_feed and not re.search(r"\bM0?3\b|\bM0?4\b", text):
            violations.append("SIEMENS_NO_SPINDLE: 有切削进给但缺 M03/M04")
        if has_cycle and not re.search(r"CYCLE8[134]", text):
            violations.append("SIEMENS_NO_CYCLE: 有固定循环但缺 CYCLE81/83/84")
        traori = "TRAORI" in text
        if prog.five_axis and not traori:
            violations.append("SIEMENS_NO_TRAORI: 五轴程序缺 TRAORI")
        if not prog.five_axis and traori:
            violations.append("SIEMENS_TRAORI_MISUSE: 三轴/非联动程序误用 TRAORI（仅五轴联动允许）")
        if has_rtcp:
            mo, mc = _ordered_pair_missing(text, r"\bTRAORI\b", r"\bTRAFOOF\b")
            if mo:
                violations.append("SIEMENS_NO_TRAORI: 五轴联动程序缺 TRAORI")
            elif mc:
                violations.append("SIEMENS_RTCP_NO_CANCEL: TRAORI 缺少 TRAFOOF 取消")
        if has_tilt:
            mo, mc = _ordered_pair_missing(text, r"CYCLE800\([^)]+\)", r"CYCLE800\(\s*\)")
            if mo or mc:
                violations.append("SIEMENS_CYCLE800_UNPAIRED: 3+2 CYCLE800 激活与取消不完整")
        if has_turn and not re.search(r"CYCLE95\(", text):
            violations.append("SIEMENS_NO_CYCLE95: 缺 CYCLE95 轮廓车削循环")
        if has_polar:
            mo, mc = _ordered_pair_missing(text, r"\bTRANSMIT\b", r"\bTRAFOOF\b")
            if mo or mc:
                violations.append("SIEMENS_TRANSMIT_UNPAIRED: 极坐标 TRANSMIT/TRAFOOF 未配对")
        if has_cyl:
            mo, mc = _ordered_pair_missing(text, r"TRACYL\(", r"\bTRAFOOF\b")
            if mo or mc:
                violations.append("SIEMENS_TRACYL_UNPAIRED: 圆柱插补 TRACYL/TRAFOOF 未配对")
        if has_subspindle:
            mo, mc = _ordered_pair_missing(text, r"\bM268\b", r"\bM69\b")
            if mo or mc:
                violations.append("SIEMENS_SUBSPINDLE_CLAMP_ORDER: 副主轴接料必须先 M268 再 M69")
    elif dialect == "heidenhain":
        if not re.search(r"^BEGIN PGM", text, re.M):
            violations.append("HEID_NO_BEGIN: 缺少 BEGIN PGM")
        if not re.search(r"^END PGM", text, re.M):
            violations.append("HEID_NO_END: 缺少 END PGM")
        if "TOOL CALL" not in text:
            violations.append("HEID_NO_TOOLCALL: 缺少 TOOL CALL")
        if has_cycle and not re.search(r"CYCL DEF (200|203|207)", text):
            violations.append("HEID_NO_CYCLE: 有固定循环但缺 CYCL DEF 200/203/207")
        if has_rtcp:
            mo, mc = _ordered_pair_missing(text, r"(?:FUNCTION\s+TCPM|\bM128\b)", r"(?:FUNCTION\s+RESET\s+TCPM|\bM129\b)")
            if mo:
                violations.append("HEID_NO_TCPM: 五轴联动缺少 FUNCTION TCPM / M128")
            elif mc:
                violations.append("HEID_TCPM_NO_CANCEL: 五轴 TCPM 缺少 FUNCTION RESET TCPM / M129")
        if not prog.five_axis and prog.machine_type == "milling_3axis":
            if re.search(r"FUNCTION\s+TCPM|\bM128\b|PLANE\s+SPATIAL", text):
                violations.append("HEID_3AXIS_MULTIAXIS_MISUSE: 三轴程序误用 TCPM/PLANE SPATIAL")
        if has_tilt:
            mo, mc = _ordered_pair_missing(text, r"PLANE\s+SPATIAL", r"PLANE\s+RESET")
            if mo or mc:
                violations.append("HEID_PLANE_UNPAIRED: 3+2 PLANE SPATIAL / PLANE RESET 未配对")
    return {"passed": not violations, "violations": violations, "basis": "measured"}


# ===========================================================================
# 5. 坐标与 6-DOF 位姿回读（同一 CL 在三种方言下逐点一致）
# ===========================================================================
def round_trip_pose(dialect: str, nc_text: str) -> List[Dict[str, float]]:
    """从发射出的 NC 解析每个 CLMove 的全轴位姿 (X, Y, Z, A, B, C, W)。"""
    poses: List[Dict[str, float]] = []
    cur: Dict[str, float] = {ax: 0.0 for ax in _ALL_POSE_AXES}
    lines = nc_text.splitlines()
    in_ignored_block = False
    in_fanuc_polar = False
    pending_rotary_index = False

    if dialect in ("fanuc", "siemens"):
        pat = re.compile(r"(?<![A-Z])([XYZABCW])=?(-?\d+(?:\.\d+)?)")
        motion = re.compile(r"^G0?[0123]\b")
        for idx, line in enumerate(lines):
            s = line.strip()
            up = s.upper()
            if "TURNING_CYCLE_BEGIN" in up or "SUBSPINDLE_TRANSFER_BEGIN" in up:
                in_ignored_block = True
                continue
            if "TURNING_CYCLE_END" in up or "SUBSPINDLE_TRANSFER_END" in up:
                in_ignored_block = False
                continue
            if in_ignored_block:
                continue
            if dialect == "fanuc":
                if re.search(r"\bG12\.1\b", up):
                    in_fanuc_polar = True
                elif re.search(r"\bG13\.1\b", up):
                    in_fanuc_polar = False
            if re.search(r"\bM11\b", up):
                pending_rotary_index = True
                continue
            if re.search(r"\bM10\b", up):
                pending_rotary_index = False
                continue
            if not motion.match(up):
                continue
            nxt = lines[idx + 1].strip() if idx + 1 < len(lines) else ""
            if dialect == "siemens" and re.match(r"^CYCLE8[134]\b", nxt):
                continue  # 循环预定位，不是 CLMove
            vals = {a: float(v) for a, v in pat.findall(up)}
            if not vals:
                continue
            if pending_rotary_index and not (set(vals) & {"X", "Y", "Z", "W"}):
                for ax in ("A", "B", "C"):
                    if ax in vals:
                        cur[ax] = vals[ax]
                pending_rotary_index = False
                continue
            pending_rotary_index = False
            if dialect == "fanuc" and in_fanuc_polar and "C" in vals and "Y" not in vals:
                vals["Y"] = vals.pop("C")
            for ax in _ALL_POSE_AXES:
                if ax in vals:
                    cur[ax] = vals[ax]
            poses.append(dict(cur))
    elif dialect == "heidenhain":
        pat = re.compile(r"(?<![A-Z])([XYZABCW])([+-]?\d+(?:\.\d+)?)")
        for idx, line in enumerate(lines):
            s = line.strip()
            up = s.upper()
            if "TURNING_CYCLE_BEGIN" in up or "SUBSPINDLE_TRANSFER_BEGIN" in up:
                in_ignored_block = True
                continue
            if "TURNING_CYCLE_END" in up or "SUBSPINDLE_TRANSFER_END" in up:
                in_ignored_block = False
                continue
            if in_ignored_block:
                continue
            if "ROTARY_INDEX_UNCLAMP" in up or "B-HEAD_INDEX" in up:
                pending_rotary_index = True
                continue
            if "ROTARY_INDEX_CLAMP" in up:
                pending_rotary_index = False
                continue
            if not up.startswith("L ") or "M5" in up:
                continue
            nxt = lines[idx + 1].strip().upper() if idx + 1 < len(lines) else ""
            if nxt.startswith("CYCL DEF"):
                continue  # 循环预定位，不是 CLMove
            vals = {a: float(v) for a, v in pat.findall(up)}
            if not vals:
                continue
            if pending_rotary_index and not (set(vals) & {"X", "Y", "Z", "W"}):
                for ax in ("A", "B", "C"):
                    if ax in vals:
                        cur[ax] = vals[ax]
                pending_rotary_index = False
                continue
            pending_rotary_index = False
            for ax in _ALL_POSE_AXES:
                if ax in vals:
                    cur[ax] = vals[ax]
            poses.append(dict(cur))
    return poses


def round_trip_coords(dialect: str, nc_text: str) -> List[Tuple[float, float, float]]:
    """从发射出的 NC 解析直线/圆弧刀位块的 X/Y/Z，返回坐标序列。"""
    return [(p["X"], p["Y"], p["Z"]) for p in round_trip_pose(dialect, nc_text)]


def _cl_motion_coords(prog: CLProgram) -> List[Tuple[float, float, float]]:
    return [(x, y, z) for _, x, y, z in _resolve_moves(prog)]


def verify_coordinate_consistency(prog: CLProgram, tol_mm: float = _COORD_TOL_MM) -> Dict[str, Any]:
    """三方言语义门：同一 CL 发射后回读坐标必须逐点一致（±tol）。空刀路判红。"""
    expected = _cl_motion_coords(prog)
    if not expected:
        return {"passed": False, "violations": ["NO_MOTION: 无刀位运动，坐标一致性不可证"],
                "basis": "measured", "per_dialect": {}}
    per: Dict[str, Any] = {}
    violations: List[str] = []
    for dialect in SUPPORTED_DIALECTS:
        nc = _EMITTERS[dialect](prog)
        got = round_trip_coords(dialect, nc)
        if len(got) != len(expected):
            violations.append(f"{dialect}: 回读 {len(got)} 点 != CL {len(expected)} 点")
            per[dialect] = {"matched": False, "points": len(got)}
            continue
        max_err = 0.0
        for (ex, ey, ez), (gx, gy, gz) in zip(expected, got):
            err = max(abs(ex - gx), abs(ey - gy), abs(ez - gz))
            max_err = max(max_err, err)
        ok = max_err <= tol_mm
        per[dialect] = {"matched": ok, "points": len(got), "max_err_mm": round(max_err, 6)}
        if not ok:
            violations.append(f"{dialect}: 坐标最大偏差 {max_err:.4f}mm > {tol_mm}mm")
    return {"passed": not violations, "violations": violations,
            "basis": "measured", "per_dialect": per}


def verify_pose_consistency(
    prog: CLProgram,
    dialects: Sequence[str] = SUPPORTED_DIALECTS,
    tol_mm: float = _COORD_TOL_MM,
    tol_deg: float = _COORD_TOL_MM,
) -> Dict[str, Any]:
    """三方言 6-DOF 位姿语义门：同一多轴/车铣 CL 发射后 X/Y/Z/W(mm) 与 A/B/C(deg) 逐点一致。"""
    expected = [pose for _, pose in _resolve_poses(prog)]
    if not expected:
        return {"passed": False, "violations": ["NO_MOTION: 无刀位运动，位姿一致性不可证"],
                "basis": "measured", "per_dialect": {}}
    per: Dict[str, Any] = {}
    violations: List[str] = []
    for dialect in dialects:
        if dialect not in _EMITTERS:
            violations.append(f"UNKNOWN_DIALECT: {dialect}")
            continue
        nc = _EMITTERS[dialect](prog)
        got = round_trip_pose(dialect, nc)
        if len(got) != len(expected):
            violations.append(f"{dialect}: 位姿回读 {len(got)} 点 != CL {len(expected)} 点")
            per[dialect] = {"matched": False, "points": len(got)}
            continue
        max_lin_err = 0.0
        max_rot_err = 0.0
        for exp_p, got_p in zip(expected, got):
            for ax in ("X", "Y", "Z", "W"):
                max_lin_err = max(max_lin_err, abs(exp_p[ax] - got_p[ax]))
            for ax in ("A", "B", "C"):
                max_rot_err = max(max_rot_err, abs(exp_p[ax] - got_p[ax]))
        ok = max_lin_err <= tol_mm and max_rot_err <= tol_deg
        per[dialect] = {
            "matched": ok,
            "points": len(got),
            "max_linear_err_mm": round(max_lin_err, 6),
            "max_rotary_err_deg": round(max_rot_err, 6),
        }
        if not ok:
            violations.append(
                f"{dialect}: 位姿偏差 lin={max_lin_err:.4f}mm rot={max_rot_err:.4f}deg"
            )
    return {"passed": not violations, "violations": violations,
            "basis": "measured", "per_dialect": per}


# ===========================================================================
# 6. 顶层编排：CL -> 方言 NC + 结构门 + 坐标门
# ===========================================================================
def post_process(prog: CLProgram, dialect: str = "fanuc") -> Dict[str, Any]:
    """把 CL 程序编译为指定方言 NC，并跑 CL 安全门 + 方言结构门 + 坐标/位姿一致性门。"""
    if dialect not in _EMITTERS:
        return {"status": "blocked", "dialect": dialect,
                "error": f"UNKNOWN_DIALECT: 支持 {SUPPORTED_DIALECTS}", "basis": "measured"}
    cl_gate = validate_program(prog)
    if not cl_gate["passed"]:
        return {"status": "blocked", "dialect": dialect, "nc": None,
                "cl_gate": cl_gate, "basis": "measured",
                "error": "CL 安全门未通过: " + "; ".join(cl_gate["violations"])}
    nc = _EMITTERS[dialect](prog)
    dialect_gate = validate_dialect(dialect, nc, prog)
    coord_gate = verify_coordinate_consistency(prog)
    pose_gate = verify_pose_consistency(prog)
    passed = dialect_gate["passed"] and coord_gate["passed"] and pose_gate["passed"]
    return {
        "status": "passed" if passed else "failed",
        "dialect": dialect,
        "nc": nc,
        "cl_gate": cl_gate,
        "dialect_gate": dialect_gate,
        "coord_gate": coord_gate,
        "pose_gate": pose_gate,
        "basis": "measured",
    }


# ===========================================================================
# 7. 标准全机床能力 CL/NC 生成器（三轴/四轴/五轴/车削/车铣复合/副主轴）
# ===========================================================================
def build_cl_from_spec(spec: Dict[str, Any], name: str = "VIRTU") -> CLProgram:
    """从回转件规格派生一条代表性包络铣削 + 中心钻 CL 刀路。"""
    d_outer = float(spec.get("d_outer", 53.0))
    d_inner = float(spec.get("d_inner", 0.0) or 0.0)
    overall_len = float(spec.get("overall_len", 45.0))
    r = max(1.0, d_outer / 2.0)
    depth = -min(2.0, overall_len / 4.0)
    tool_d = max(2.0, min(10.0, d_outer / 4.0))
    ops: List[Any] = [
        CLToolChange(tool_id=1, diameter_mm=tool_d, length_mm=50.0),
        CLSpindle(rpm=1200, direction="cw"),
        CLCoolant(on=True),
        CLMove(mode="rapid", x=0.0, y=0.0, z=5.0),
        CLMove(mode="feed", x=r, y=0.0, z=depth, f=100.0),
        CLMove(mode="arc_cw", x=-r, y=0.0, z=depth, i=-r, j=0.0, f=100.0),
        CLMove(mode="arc_cw", x=r, y=0.0, z=depth, i=r, j=0.0, f=100.0),
        CLMove(mode="rapid", z=5.0),
    ]
    if d_inner > 0:
        ops.append(CLCycle(kind="drill", x=0.0, y=0.0,
                           z_depth=-overall_len / 2.0, r_plane=2.0, feed=80.0))
    ops += [CLSpindle(rpm=0, direction="stop"), CLCoolant(on=False)]
    return CLProgram(name=name, units="mm", five_axis=False, wcs="G54", ops=ops)


def build_canonical_cl_program(
    capability: str,
    spec: Optional[Dict[str, Any]] = None,
    *,
    rotary_axes: Optional[Sequence[str]] = None,
    variant: str = "default",
    name: Optional[str] = None,
) -> CLProgram:
    """构建覆盖三轴/四轴/五轴/车削/车铣复合/副主轴接料的标准 CL 程序。"""
    cfg = dict(spec or {})
    cap = str(capability).strip()
    prog_name = name or f"VIRTU_{cap.upper()}"
    dx = float(cfg.get("dx", 100.0))
    dy = float(cfg.get("dy", 80.0))
    dz = float(cfg.get("dz", 40.0))
    stock_d = float(cfg.get("stock_d", cfg.get("d_outer", 60.0)))
    step_d = float(cfg.get("step_d", min(stock_d * 0.65, stock_d - 8.0)))
    total_len = float(cfg.get("total_len", cfg.get("overall_len", 50.0)))
    rpm = int(cfg.get("rpm", 2400))
    feed = float(cfg.get("feed", 240.0))

    if cap == "milling_3axis":
        ops: List[Any] = [
            CLToolChange(1, 10.0, 60.0),
            CLSpindle(rpm, "cw"),
            CLCoolant(True),
            CLMove("rapid", x=0.0, y=0.0, z=10.0),
            CLMove("feed", x=dx * 0.4, y=dy * 0.3, z=-3.0, f=feed),
            CLMove("feed", x=-dx * 0.4, y=dy * 0.3, z=-3.0, f=feed),
            CLMove("arc_cw", x=dx * 0.4, y=-dy * 0.3, z=-3.0, i=0.0, j=-dy * 0.3, f=feed),
            CLMove("rapid", x=0.0, y=0.0, z=10.0),
            CLCycle("peck", x=15.0, y=15.0, z_depth=-min(12.0, dz * 0.5), r_plane=2.0, peck_q=3.0, feed=100.0),
            CLSpindle(0, "stop"),
            CLCoolant(False),
        ]
        return CLProgram(name=prog_name, five_axis=False, machine_type="milling_3axis", ops=ops)

    if cap == "milling_4axis_indexed":
        ax = (str(rotary_axes[0]).upper() if rotary_axes else "A")
        idx_0 = {"a": 0.0} if ax == "A" else ({"b": 0.0} if ax == "B" else {"c": 0.0})
        idx_90 = {"a": 90.0} if ax == "A" else ({"b": 90.0} if ax == "B" else {"c": 90.0})
        ops = [
            CLToolChange(1, 10.0, 75.0),
            CLSpindle(rpm, "cw"),
            CLCoolant(True),
            CLRotaryIndex(**idx_0, clamp=True),
            CLMove("rapid", x=0.0, y=0.0, z=10.0),
            CLMove("feed", x=30.0, y=0.0, z=-4.0, f=feed),
            CLMove("rapid", z=25.0),
            CLRotaryIndex(**idx_90, clamp=True),
            CLMove("rapid", x=0.0, y=10.0, z=10.0),
            CLMove("feed", x=30.0, y=10.0, z=-4.0, f=feed),
            CLMove("rapid", z=25.0),
            CLRotaryIndex(**idx_0, clamp=True),
            CLSpindle(0, "stop"),
            CLCoolant(False),
        ]
        return CLProgram(name=prog_name, five_axis=False, machine_type="milling_4axis_indexed",
                         rotary_axes=(ax,), ops=ops)

    if cap == "milling_4axis_simultaneous":
        ax = (str(rotary_axes[0]).upper() if rotary_axes else "A")
        k = ax.lower()
        ops = [
            CLToolChange(2, 8.0, 80.0),
            CLSpindle(rpm, "cw"),
            CLCoolant(True),
            CLRotaryIndex(**{k: 0.0}, clamp=False),
            CLMove("rapid", x=0.0, y=0.0, z=10.0, **{k: 0.0}),
            CLMove("feed", x=12.0, y=4.0, z=-2.5, f=feed, **{k: 30.0}),
            CLMove("feed", x=24.0, y=8.0, z=-2.5, f=feed, **{k: 60.0}),
            CLMove("feed", x=36.0, y=12.0, z=-2.5, f=feed, **{k: 90.0}),
            CLMove("rapid", x=0.0, y=0.0, z=20.0, **{k: 0.0}),
            CLSpindle(0, "stop"),
            CLCoolant(False),
        ]
        return CLProgram(name=prog_name, five_axis=False, machine_type="milling_4axis_simultaneous",
                         rotary_axes=(ax,), ops=ops)

    if cap == "milling_5axis_3plus2":
        pair = tuple(str(x).upper() for x in (rotary_axes or ("A", "C")))[:2]
        pair_label = "".join(pair)
        ops = [
            CLToolChange(3, 8.0, 90.0),
            CLSpindle(rpm, "cw"),
            CLCoolant(True),
            CLWorkplaneTilt(euler_a=30.0, euler_b=0.0, euler_c=45.0, origin=(0.0, 0.0, 0.0),
                            active=True, rotary_pair=pair_label),
            CLMove("rapid", x=10.0, y=10.0, z=10.0),
            CLMove("feed", x=10.0, y=10.0, z=-5.0, f=feed),
            CLMove("feed", x=25.0, y=10.0, z=-5.0, f=feed),
            CLCycle("drill", x=25.0, y=20.0, z_depth=-12.0, r_plane=2.0, feed=100.0),
            CLMove("rapid", x=10.0, y=10.0, z=25.0),
            CLWorkplaneTilt(active=False, rotary_pair=pair_label),
            CLSpindle(0, "stop"),
            CLCoolant(False),
        ]
        return CLProgram(name=prog_name, five_axis=False, machine_type="milling_5axis_3plus2",
                         rotary_axes=pair, ops=ops)

    if cap == "milling_5axis_simultaneous":
        pair = tuple(str(x).upper() for x in (rotary_axes or ("B", "C")))[:2]
        r1, r2 = pair[0].lower(), pair[1].lower()
        ops = [
            CLToolChange(4, 6.0, 100.0),
            CLSpindle(max(rpm, 4000), "cw"),
            CLCoolant(True),
            CLMove("rapid", x=0.0, y=0.0, z=50.0, **{r1: 0.0, r2: 0.0}),
            CLRTCP(active=True, tool_offset_h=4),
            CLMove("rapid", x=18.0, y=0.0, z=10.0, **{r1: 10.0, r2: 0.0}),
            CLMove("feed", x=18.0, y=6.0, z=-3.0, f=feed, **{r1: 15.0, r2: 45.0}),
            CLMove("feed", x=12.0, y=15.0, z=-5.0, f=feed, **{r1: 22.5, r2: 90.0}),
            CLMove("feed", x=0.0, y=18.0, z=-6.0, f=feed, **{r1: 28.0, r2: 135.0}),
            CLRTCP(active=False, tool_offset_h=4),
            CLMove("rapid", x=0.0, y=0.0, z=50.0, **{r1: 0.0, r2: 0.0}),
            CLSpindle(0, "stop"),
            CLCoolant(False),
        ]
        return CLProgram(name=prog_name, five_axis=True, machine_type="milling_5axis_simultaneous",
                         rotary_axes=pair, ops=ops)

    if cap == "turning":
        steps = list(cfg.get("steps") or [(step_d, round(total_len * 0.45, 2))])
        ops = [
            CLToolChange(1, 0.8, 0.0),
            CLSpindle(1500, "cw"),
            CLCoolant(True),
            CLMove("rapid", x=stock_d + 2.0, z=2.0),
            CLTurningCycle(stock_d=stock_d, steps=steps, total_len=total_len),
            CLMove("rapid", x=max(100.0, stock_d + 20.0), z=80.0),
            CLSpindle(0, "stop"),
            CLCoolant(False),
        ]
        return CLProgram(name=prog_name, five_axis=False, machine_type="turning",
                         has_y_axis=False, ops=ops)

    if cap == "mill_turn_off_axis_milling":
        interp = "cylindrical" if variant == "cylindrical" else ("cartesian" if variant == "c_indexed" else "polar")
        steps = list(cfg.get("steps") or [(step_d, round(total_len * 0.4, 2))])
        radius = round(step_d / 2.0, 3)
        ops = [
            CLToolChange(1, 0.8, 0.0),
            CLSpindle(1500, "cw"),
            CLCoolant(True),
            CLMove("rapid", x=stock_d + 2.0, z=2.0),
            CLTurningCycle(stock_d=stock_d, steps=steps, total_len=total_len),
            CLMove("rapid", x=max(100.0, stock_d + 20.0), z=50.0),
            CLToolChange(2, 8.0, 60.0),
            CLMillTurnMode(
                mode="milling", live_rpm=3000, c_axis_engage=True,
                interpolation=interp, cylinder_radius_mm=(radius if interp == "cylindrical" else 0.0),
                active=True,
            ),
        ]
        if interp == "polar":
            ops += [
                CLMove("rapid", x=step_d * 0.6, y=0.0, z=5.0),
                CLMove("feed", x=step_d * 0.6, y=0.0, z=-3.0, f=160.0),
                CLMove("feed", x=step_d * 0.6, y=10.0, z=-3.0, f=160.0),
                CLMove("feed", x=-step_d * 0.6, y=10.0, z=-3.0, f=160.0),
                CLMove("rapid", x=step_d + 4.0, y=0.0, z=20.0),
            ]
        elif interp == "cylindrical":
            ops += [
                CLMove("rapid", x=step_d + 4.0, z=5.0, c=0.0),
                CLMove("feed", x=step_d - 4.0, z=-8.0, c=0.0, f=150.0),
                CLMove("feed", x=step_d - 4.0, z=-18.0, c=90.0, f=150.0),
                CLMove("feed", x=step_d - 4.0, z=-18.0, c=180.0, f=150.0),
                CLMove("rapid", x=step_d + 6.0, z=20.0, c=0.0),
            ]
        else:
            ops += [
                CLMove("rapid", x=step_d * 0.7, z=5.0, c=0.0),
                CLMove("feed", x=step_d * 0.5, z=-4.0, c=90.0, f=150.0),
                CLMove("feed", x=step_d * 0.5, z=-4.0, c=180.0, f=150.0),
                CLMove("rapid", x=step_d + 6.0, z=20.0, c=0.0),
            ]
        ops += [
            CLMillTurnMode(mode="milling", active=False, c_axis_engage=True, interpolation=interp),
            CLCoolant(False),
        ]
        return CLProgram(name=prog_name, five_axis=False, machine_type="mill_turn_off_axis_milling",
                         rotary_axes=("C",), has_y_axis=False, ops=ops)

    if cap == "mill_turn_y_axis_milling":
        steps = list(cfg.get("steps") or [(step_d, round(total_len * 0.4, 2))])
        b_angle = 45.0 if variant == "b_head" else None
        rot = ("B", "C") if b_angle is not None else ("C",)
        ops = [
            CLToolChange(1, 0.8, 0.0),
            CLSpindle(1500, "cw"),
            CLCoolant(True),
            CLMove("rapid", x=stock_d + 2.0, z=2.0),
            CLTurningCycle(stock_d=stock_d, steps=steps, total_len=total_len),
            CLMove("rapid", x=max(100.0, stock_d + 20.0), y=0.0, z=50.0),
            CLToolChange(3, 10.0, 70.0),
            CLMillTurnMode(mode="milling", live_rpm=3500, c_axis_engage=True,
                           interpolation="cartesian", b_head_angle_deg=b_angle, active=True),
            CLMove("rapid", x=step_d + 6.0, y=12.0, z=5.0, c=0.0),
            CLMove("feed", x=step_d * 0.7, y=12.0, z=-6.0, c=0.0, f=180.0),
            CLMove("feed", x=step_d * 0.7, y=-12.0, z=-6.0, c=45.0, f=180.0),
            CLMove("rapid", x=max(100.0, stock_d + 20.0), y=0.0, z=50.0, c=0.0),
            CLMillTurnMode(mode="milling", active=False, c_axis_engage=True),
            CLCoolant(False),
        ]
        return CLProgram(name=prog_name, five_axis=False, machine_type="mill_turn_y_axis_milling",
                         rotary_axes=rot, has_y_axis=True, ops=ops)

    if cap == "subspindle_transfer":
        steps = list(cfg.get("steps") or [(step_d, round(total_len * 0.4, 2))])
        ops = [
            CLToolChange(1, 0.8, 0.0),
            CLSpindle(1400, "cw"),
            CLCoolant(True),
            CLMove("rapid", x=stock_d + 2.0, y=0.0, z=2.0),
            CLTurningCycle(stock_d=stock_d, steps=steps, total_len=total_len),
            CLMove("rapid", x=max(100.0, stock_d + 20.0), y=0.0, z=50.0),
            CLToolChange(2, 10.0, 65.0),
            CLMillTurnMode(mode="milling", live_rpm=3200, c_axis_engage=True, active=True),
            CLMove("rapid", x=step_d + 4.0, y=8.0, z=5.0, c=0.0),
            CLMove("feed", x=step_d * 0.65, y=8.0, z=-5.0, c=90.0, f=180.0),
            CLMove("rapid", x=max(100.0, stock_d + 20.0), y=0.0, z=60.0, c=0.0),
            CLMillTurnMode(mode="milling", active=False, c_axis_engage=True),
            CLSubspindleTransfer(z_pickup_mm=-total_len * 0.6, w_home_mm=0.0,
                                 w_pickup_mm=-140.0, sync_rpm=600, cutoff=True, back_wcs="G55"),
            CLToolChange(4, 0.8, 0.0),
            CLSpindle(1600, "cw"),
            CLMove("rapid", x=step_d + 4.0, y=0.0, z=2.0),
            CLMove("feed", x=0.0, y=0.0, z=-0.5, f=0.15),
            CLMove("rapid", x=max(100.0, stock_d + 20.0), y=0.0, z=60.0),
            CLSpindle(0, "stop"),
            CLCoolant(False),
        ]
        return CLProgram(name=prog_name, five_axis=False, machine_type="subspindle_transfer",
                         rotary_axes=("C",), has_y_axis=True, ops=ops)

    raise ValueError(f"unsupported capability for canonical CL generation: {capability!r}")


def generate_capability_nc(
    capability: str,
    dialect: str = "fanuc",
    spec: Optional[Dict[str, Any]] = None,
    *,
    rotary_axes: Optional[Sequence[str]] = None,
    variant: str = "default",
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """为指定机床加工能力与控制器方言生成通过 CL/方言/位姿门禁的 NC 草案。"""
    prog = build_canonical_cl_program(
        capability, spec=spec, rotary_axes=rotary_axes, variant=variant, name=name,
    )
    res = post_process(prog, dialect=dialect)
    res["capability"] = capability
    res["machine_type"] = prog.machine_type
    res["rotary_axes"] = list(prog.rotary_axes)
    res["variant"] = variant
    res["program_release_allowed"] = False
    res["limitation"] = (
        "Static CL postprocessor and coordinate/dialect gates only; "
        "exact machine kinematics, post hash, and VERICUT simulation remain required before release."
    )
    return res
