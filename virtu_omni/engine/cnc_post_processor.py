# -*- coding: utf-8 -*-
"""cnc_post_processor.py — 真实多控制器 CNC 后处理器（CL 中间表示 -> 方言 NC）。

此前全仓只有 FANUC Macro B 模板（wish_cad_cam_engine.generate_cimco_macro），
README/AGENTS 宣称的 "Siemens 840D / Heidenhain TNC 多控制器后处理" 没有任何
真实发射器。本模块把刀位（Cutter Location, CL）中间表示编译成三种真实方言：

  * FANUC 0i/31i  —— G 代码 + Macro B 变量 + G81/G83/G84 固定循环
  * Siemens 840D  —— CYCLE81/83/84 循环 + TRAORI（仅五轴）+ G71/G90
  * Heidenhain TNC—— Klartext L 块 + CYCL DEF 200/203/207 + BEGIN/END PGM

设计公理（测量宪法 §8）：
  1. 每个方言发射器都配 ``validate_dialect`` 结构门——空程序 / 缺主轴 / 缺循环 /
     五轴误用 TRAORI 一律判红，植入坏样本必须可证伪。
  2. ``round_trip_coords`` 把发射出的 NC 重新解析回坐标，与 CL 逐点核对（±tol），
     证明"同一刀路在三种方言下坐标一致"，而不是三套互不一致的模板。
  3. 诚实边界：这是 CL->方言的**语法/坐标**后处理器，不含具体机床的运动学标定、
     RTCP 摆长补偿或螺距误差表；TRAORI/CYCL DEF 是真实关键字，不是标定过的变换。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

SUPPORTED_DIALECTS = ("fanuc", "siemens", "heidenhain")
_COORD_TOL_MM = 1e-3


# ===========================================================================
# 1. CL 中间表示（与控制器无关的刀位数据）
# ===========================================================================
@dataclass
class CLMove:
    """直线/圆弧刀位。mode: rapid|feed|arc_cw|arc_ccw。坐标绝对 mm，缺省为模态继承。"""
    mode: str
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    i: Optional[float] = None   # 圆弧圆心增量（FANUC I/J 风格）
    j: Optional[float] = None
    f: Optional[float] = None   # 进给 mm/min


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
class CLProgram:
    name: str = "VIRTU"
    units: str = "mm"           # mm|inch
    five_axis: bool = False
    wcs: str = "G54"
    ops: List[Any] = field(default_factory=list)


# ===========================================================================
# 2. CL 级安全门（先于方言发射；可证伪）
# ===========================================================================
def validate_program(prog: CLProgram) -> Dict[str, Any]:
    """CL 级模态/碰撞安全门。空程序、无主轴切削、快速扎刀一律判红。"""
    violations: List[str] = []
    if not prog.ops:
        violations.append("EMPTY_PROGRAM: 刀位程序为空，禁止发射")

    has_spindle = False
    has_feed = False
    cur_z: Optional[float] = None
    r_plane: Optional[float] = None
    for op in prog.ops:
        if isinstance(op, CLSpindle):
            if op.direction in ("cw", "ccw") and op.rpm > 0:
                has_spindle = True
        elif isinstance(op, CLCycle):
            r_plane = op.r_plane
        elif isinstance(op, CLMove):
            if op.z is not None:
                cur_z = op.z
            if op.mode == "feed":
                has_feed = True
            if op.mode == "rapid" and op.z is not None and r_plane is not None:
                if op.z < r_plane - _COORD_TOL_MM:
                    violations.append(
                        f"RAPID_PLUNGE: G00 快速下刀 Z={op.z} 低于参考平面 {r_plane}，撞刀风险")
    if has_feed and not has_spindle:
        violations.append("NO_SPINDLE: 存在切削进给但未启动主轴 (M03/M04)")
    return {"passed": not violations, "violations": violations, "basis": "measured"}


# ===========================================================================
# 3. 方言发射器
# ===========================================================================
def _fmt(v: float) -> str:
    return f"{v:.3f}".rstrip("0").rstrip(".")


def _resolve_moves(prog: CLProgram) -> List[Tuple[CLMove, float, float, float]]:
    """把模态坐标前向填充，返回 (move, x, y, z) 显式序列（供发射与回读核对）。"""
    cx = cy = cz = 0.0
    out = []
    for op in prog.ops:
        if not isinstance(op, CLMove):
            continue
        if op.x is not None:
            cx = op.x
        if op.y is not None:
            cy = op.y
        if op.z is not None:
            cz = op.z
        out.append((op, cx, cy, cz))
    return out


def _resolved_lookup(prog: CLProgram) -> Dict[int, Tuple[float, float, float]]:
    return {id(op): (x, y, z) for op, x, y, z in _resolve_moves(prog)}


def emit_fanuc(prog: CLProgram) -> str:
    resolved = _resolved_lookup(prog)
    lines = ["%", f"O0001 ({prog.name})",
             ("G21" if prog.units == "mm" else "G20") + " G90 G54 G17 G40 G80"]
    for op in prog.ops:
        if isinstance(op, CLToolChange):
            lines.append(f"T{op.tool_id:02d} M06 (D{_fmt(op.diameter_mm)})")
        elif isinstance(op, CLSpindle):
            if op.direction == "stop":
                lines.append("M05")
            else:
                m = "M03" if op.direction == "cw" else "M04"
                lines.append(f"S{op.rpm} {m}")
        elif isinstance(op, CLCoolant):
            lines.append("M08" if op.on else "M09")
        elif isinstance(op, CLMove):
            x, y, z = resolved[id(op)]
            g = {"rapid": "G00", "feed": "G01", "arc_cw": "G02", "arc_ccw": "G03"}[op.mode]
            words = [g, f"X{_fmt(x)}", f"Y{_fmt(y)}", f"Z{_fmt(z)}"]
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
    lines = [f";{prog.name}", f";UNITS {'MM' if prog.units == 'mm' else 'INCH'}",
             ("G71" if prog.units == "mm" else "G70") + " G90 G54 G17 G40"]
    if prog.five_axis:
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
        elif isinstance(op, CLMove):
            x, y, z = resolved[id(op)]
            g = {"rapid": "G0", "feed": "G1", "arc_cw": "G2", "arc_ccw": "G3"}[op.mode]
            words = [g, f"X={_fmt(x)}", f"Y={_fmt(y)}", f"Z={_fmt(z)}"]
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
    lines += ["M09", "M05", "M30"]
    return "\n".join(lines) + "\n"


def emit_heidenhain(prog: CLProgram) -> str:
    resolved = _resolved_lookup(prog)
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
        elif isinstance(op, CLMove):
            x, y, z = resolved[id(op)]
            words = ["L", f"X{x:+.3f}", f"Y{y:+.3f}", f"Z{z:+.3f}"]
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
            lines.append(f"  Q200=2 ;SET-UP CLEARANCE")
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
def validate_dialect(dialect: str, nc_text: str, prog: CLProgram) -> Dict[str, Any]:
    if dialect not in _EMITTERS:
        return {"passed": False, "violations": [f"UNKNOWN_DIALECT: {dialect}"], "basis": "measured"}
    text = nc_text.strip()
    violations: List[str] = []
    if not text:
        violations.append("EMPTY_NC: 发射结果为空")

    has_cycle = any(isinstance(o, CLCycle) for o in prog.ops)
    has_feed = any(isinstance(o, CLMove) and o.mode == "feed" for o in prog.ops)

    if dialect == "fanuc":
        if not text.startswith("%"):
            violations.append("FANUC_NO_TAPE: 缺少 % 带符号")
        if "M30" not in text:
            violations.append("FANUC_NO_END: 缺少 M30 程序结束")
        if has_feed and not re.search(r"\bM0?3\b|\bM0?4\b", text):
            violations.append("FANUC_NO_SPINDLE: 有切削进给但缺 M03/M04")
        if has_cycle and not re.search(r"\bG8[134]\b", text):
            violations.append("FANUC_NO_CYCLE: 有固定循环但缺 G81/G83/G84")
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
            violations.append("SIEMENS_TRAORI_MISUSE: 三轴程序误用 TRAORI（仅五轴允许）")
    elif dialect == "heidenhain":
        if not re.search(r"^BEGIN PGM", text, re.M):
            violations.append("HEID_NO_BEGIN: 缺少 BEGIN PGM")
        if not re.search(r"^END PGM", text, re.M):
            violations.append("HEID_NO_END: 缺少 END PGM")
        if "TOOL CALL" not in text:
            violations.append("HEID_NO_TOOLCALL: 缺少 TOOL CALL")
        if has_cycle and not re.search(r"CYCL DEF (200|203|207)", text):
            violations.append("HEID_NO_CYCLE: 有固定循环但缺 CYCL DEF 200/203/207")
    return {"passed": not violations, "violations": violations, "basis": "measured"}


# ===========================================================================
# 5. 坐标回读（同一 CL 在三种方言下逐点一致）
# ===========================================================================
def round_trip_coords(dialect: str, nc_text: str) -> List[Tuple[float, float, float]]:
    """从发射出的 NC 解析直线/圆弧刀位块的 X/Y/Z，返回坐标序列。

    跳过两类非 CLMove 块：固定循环的预定位（其后紧跟 CYCLE/CYCL DEF）与
    Heidenhain 的主轴停/退刀块（含 M5），保证回读点数与 CL 刀位一一对应。
    """
    coords: List[Tuple[float, float, float]] = []
    lines = nc_text.splitlines()
    if dialect in ("fanuc", "siemens"):
        pat = re.compile(r"([XYZ])=?(-?\d+(?:\.\d+)?)")
        motion = re.compile(r"^G0?[0123]\b")
        for idx, line in enumerate(lines):
            s = line.strip()
            if not motion.match(s):
                continue
            nxt = lines[idx + 1].strip() if idx + 1 < len(lines) else ""
            if dialect == "siemens" and nxt.startswith("CYCLE8"):
                continue  # 循环预定位，不是 CLMove
            vals = {a: float(v) for a, v in pat.findall(s)}
            if not vals:
                continue
            coords.append((vals.get("X", 0.0), vals.get("Y", 0.0), vals.get("Z", 0.0)))
    elif dialect == "heidenhain":
        pat = re.compile(r"([XYZ])([+-]?\d+(?:\.\d+)?)")
        for idx, line in enumerate(lines):
            s = line.strip()
            if not s.startswith("L ") or "M5" in s:
                continue
            nxt = lines[idx + 1].strip() if idx + 1 < len(lines) else ""
            if nxt.startswith("CYCL DEF"):
                continue  # 循环预定位，不是 CLMove
            vals = {a: float(v) for a, v in pat.findall(s)}
            if not vals:
                continue
            coords.append((vals.get("X", 0.0), vals.get("Y", 0.0), vals.get("Z", 0.0)))
    return coords


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


# ===========================================================================
# 6. 顶层编排：CL -> 方言 NC + 结构门 + 坐标门
# ===========================================================================
def post_process(prog: CLProgram, dialect: str = "fanuc") -> Dict[str, Any]:
    """把 CL 程序编译为指定方言 NC，并跑 CL 安全门 + 方言结构门 + 坐标一致性门。"""
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
    passed = dialect_gate["passed"] and coord_gate["passed"]
    return {
        "status": "passed" if passed else "failed",
        "dialect": dialect,
        "nc": nc,
        "cl_gate": cl_gate,
        "dialect_gate": dialect_gate,
        "coord_gate": coord_gate,
        "basis": "measured",
    }


# ===========================================================================
# 7. 由零件规格派生代表性 CL 刀路（供极限链接入多控制器后处理）
# ===========================================================================
def build_cl_from_spec(spec: Dict[str, Any], name: str = "VIRTU") -> CLProgram:
    """从回转件规格派生一条代表性包络铣削 + 中心钻 CL 刀路。

    诚实边界：这是按规格包络生成的**代表性**刀路（用于多控制器方言发射与坐标
    一致性取证），不是对真实曲面做 CAM 求交的结果；坐标一致性门是实测的。
    """
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