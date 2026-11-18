"""后处理器：IR (List[Move]) → ISO 标准数控代码（FANUC / SIEMENS / HUAZHONG）。

严格遵守三家控制器语法差异：
  - FANUC:    % / O0001 / (comment) / G21 / G50(车床限速) / G98-G99(车床进给) / G94-G95(铣床) / G32 F / G28
  - SIEMENS:  ; %_N_O0001_MPF / ; comment / G71(公制) / LIMS=(限速) / G94-G95 / G33 K / SUPA G0
  - HUAZHONG: %0001 / (comment) / G21 / G46(或G50) / G94-G95 / G32 F / G28
"""
from __future__ import annotations

from typing import List

from cam_autogen.contracts import Move, PostProfile


def _fmt(val: float, dec: int) -> str:
    if abs(val) < 0.5 * (10 ** -dec):
        val = 0.0
    s = f"{val:.{dec}f}".rstrip("0")
    return s if not s.endswith(".") else s  # 保留小数点（如 X10. 符合 ISO 习惯）


def _comment(text: str, dialect: str) -> str:
    clean = text.replace("(", "[").replace(")", "]").replace(";", " ")
    if dialect == "SIEMENS":
        return f"; {clean}"
    return f"({clean})"


def render(moves: List[Move], profile: PostProfile) -> str:
    d = profile.dialect
    is_lathe = profile.machine_kind in ("lathe", "turn_mill")
    dec = profile.decimals
    lines: List[str] = []
    n_seq = profile.line_step

    def emit(body: str) -> None:
        nonlocal n_seq
        if profile.line_numbers and not body.startswith(("%", "; %_N_")):
            lines.append(f"N{n_seq:04d} {body}")
            n_seq += profile.line_step
        else:
            lines.append(body)

    pnum = f"{profile.program_number:04d}"
    if d == "FANUC":
        lines.append("%")
        lines.append(f"O{pnum} ({profile.machine_kind.upper()} AUTO PROGRAM)")
        emit("G18 G21 G40 G80 G97 G99" if is_lathe else "G17 G21 G40 G49 G80 G90 G94")
        if is_lathe:
            emit(f"G50 S{int(profile.spindle_max_rpm)}")
    elif d == "SIEMENS":
        lines.append(f"; %_N_O{pnum}_MPF")
        lines.append(f"; {profile.machine_kind.upper()} AUTO PROGRAM")
        emit("G18 G71 G40 G90 G95 G97" if is_lathe else "G17 G71 G40 G90 G94")
    else:  # HUAZHONG
        lines.append(f"%{pnum}")
        lines.append(f"({profile.machine_kind.upper()} AUTO PROGRAM)")
        emit("G18 G21 G40 G80 G95 G97" if is_lathe else "G17 G21 G40 G49 G80 G90 G94")

    active_tool: int = 1
    motion_modal: str = ""
    pending_tap_pitch: float = 1.0

    for m in moves:
        k = m.kind
        if k == "comment":
            emit(_comment(m.text or "", d))
        elif k == "work_offset":
            emit(m.text or profile.work_offset)
        elif k == "feed_mode":
            if m.text == "mm_rev":
                emit("G99" if (d == "FANUC" and is_lathe) else "G95")
            else:
                emit("G98" if (d == "FANUC" and is_lathe) else "G94")
        elif k == "tool_change":
            active_tool = m.tool or 1
            if is_lathe:
                if d == "SIEMENS":
                    emit(f"T{active_tool} D1 {_comment(m.text or '', d)}")
                else:
                    emit(f"T{active_tool:02d}{active_tool:02d} {_comment(m.text or '', d)}")
            else:
                if d == "SIEMENS":
                    emit(f'T="T{active_tool:02d}" D1 M06 {_comment(m.text or "", d)}')
                else:
                    emit(f"T{active_tool:02d} M06 {_comment(m.text or '', d)}")
                    emit(f"G00 G43 H{active_tool:02d} Z50.")
            motion_modal = ""
        elif k == "spindle":
            code = "M04" if (m.text or "CW") == "CCW" else "M03"
            emit(f"G97 S{int(m.s or 1000)} {code}" if is_lathe else f"S{int(m.s or 1000)} {code}")
        elif k == "css":
            s_clamp = int(min(m.extra.get("max_rpm", profile.spindle_max_rpm), profile.spindle_max_rpm))
            if d == "SIEMENS":
                emit(f"G96 S{int(m.s or 150)} LIMS={s_clamp} M03")
            elif d == "HUAZHONG":
                clamp = profile.max_rpm_clamp_code or "G46"
                if clamp == "G50":
                    emit(f"G50 S{s_clamp}")
                    emit(f"G96 S{int(m.s or 150)} M03")
                else:
                    emit(f"G96 S{int(m.s or 150)} {clamp} M03")
            else:
                emit(f"G50 S{s_clamp}")
                emit(f"G96 S{int(m.s or 150)} M03")
        elif k == "spindle_stop":
            emit("M05")
        elif k == "live_spindle":
            emit(f"{profile.live_spindle_cw} S{int(m.s or 1500)}")
        elif k == "live_spindle_stop":
            emit(profile.live_spindle_stop)
        elif k == "c_axis":
            if m.text == "on":
                emit(profile.c_axis_on)
            elif m.text == "off":
                emit(profile.c_axis_off)
            if m.c is not None:
                emit(f"G00 C{_fmt(m.c, dec)}")
                motion_modal = "G00"
        elif k == "coolant":
            emit(profile.coolant_on)
        elif k == "coolant_off":
            emit(profile.coolant_off)
        elif k == "dwell":
            emit(f"G04 F{_fmt(m.f or 0.2, 2)}" if d == "SIEMENS" else f"G04 P{int((m.f or 0.2) * 1000)}")
        elif k == "safe_retract":
            if d == "SIEMENS":
                if is_lathe and m.x is not None and m.z is not None:
                    emit(f"G00 X{_fmt(m.x, dec)}")
                    emit(f"G00 Z{_fmt(m.z, dec)}")
                else:
                    emit("SUPA G0 Z0 D0")
            elif profile.home_return == "G53":
                emit("G53 G00 Z0" if not is_lathe else f"G00 X{_fmt(m.x or 150, dec)} Z{_fmt(m.z or 60, dec)}")
            else:
                if is_lathe:
                    if m.x is not None:
                        emit(f"G00 X{_fmt(m.x, dec)}")
                    if m.z is not None:
                        emit(f"G00 Z{_fmt(m.z, dec)}")
                else:
                    emit("G91 G28 Z0.")
                    emit("G90")
            motion_modal = "G00"
        elif k in ("rapid", "linear", "arc_cw", "arc_ccw", "thread"):
            # 刚性攻丝周期渲染（保留标准循环可读性）
            if m.extra.get("tap_cycle"):
                r_val = m.extra.get("r", 3.0)
                pending_tap_pitch = float(m.extra.get("pitch", 1.0))
                if d == "SIEMENS":
                    emit(f"G331 Z{_fmt(m.z or 0, dec)} K{_fmt(pending_tap_pitch, 3)} S{int(m.extra.get('rpm', 500))}")
                else:
                    if d == "FANUC":
                        emit(f"M29 S{int(m.extra.get('rpm', 500))}")
                    emit(f"G84 X{_fmt(m.x or 0, dec)} Y{_fmt(m.y or 0, dec)} Z{_fmt(m.z or 0, dec)} R{_fmt(r_val, dec)} F{_fmt(m.f or 100, 1)}")
                continue
            if m.extra.get("tap_retract"):
                if d == "SIEMENS":
                    emit(f"G332 Z{_fmt(m.z or 3, dec)} K{_fmt(pending_tap_pitch, 3)}")
                else:
                    emit("G80")
                continue

            if k == "rapid":
                gcode = "G00"
            elif k == "linear":
                gcode = "G01"
            elif k == "arc_cw":
                gcode = "G02"
            elif k == "arc_ccw":
                gcode = "G03"
            else:
                gcode = "G33" if d == "SIEMENS" else "G32"

            parts = []
            if gcode != motion_modal or k == "thread":
                parts.append(gcode)
                motion_modal = gcode
            if m.x is not None:
                parts.append(f"X{_fmt(m.x, dec)}")
            if m.y is not None:
                parts.append(f"Y{_fmt(m.y, dec)}")
            if m.z is not None:
                parts.append(f"Z{_fmt(m.z, dec)}")
            if m.c is not None:
                parts.append(f"C{_fmt(m.c, dec)}")
            if m.i is not None:
                parts.append(f"I{_fmt(m.i, dec)}")
            if m.j is not None:
                parts.append(f"J{_fmt(m.j, dec)}")
            if m.f is not None:
                if k == "thread" and d == "SIEMENS":
                    parts.append(f"K{_fmt(m.f, 4)}")
                elif k != "rapid":
                    parts.append(f"F{_fmt(m.f, 3 if (is_lathe and m.f < 10) else 1)}")
            if parts:
                emit(" ".join(parts))
        elif k == "program_end":
            emit("M30")

    if d == "FANUC":
        lines.append("%")
    return "\n".join(lines) + "\n"
