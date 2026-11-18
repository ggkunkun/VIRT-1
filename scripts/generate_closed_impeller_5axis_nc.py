# -*- coding: utf-8 -*-
"""为 AE_CLOSED_IMPELLER_NASA1975 生成五轴 NC（FANUC 30iM / DMG NMV1500）并做安全校验。

- 复用 scripts/build_nasa_closed_impeller.py 的几何函数（轮毂/轮盖型线、叶片包角）
- OP1：D16 立铣刀，轮盖外轮廓与进气口粗加工
- OP2：D10 棒棒糖刀，G43.4 RTCP，16 条封闭流道五轴联动
- 输出：NC 程序 + 校验报告 JSON
"""

from __future__ import annotations

import importlib.util
import json
import math
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "artifacts" / "aero_closed_impeller"
OUT_DIR.mkdir(parents=True, exist_ok=True)

_spec = importlib.util.spec_from_file_location(
    "impeller_build", ROOT / "scripts" / "build_nasa_closed_impeller.py")
geo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(geo)

NC_PATH = OUT_DIR / "AE_CLOSED_IMPELLER_NASA1975_5AXIS.nc"
REPORT_PATH = OUT_DIR / "nc_validation.json"

SAFE_Z = 90.0
STOCK_TOP = 82.0
STOCK_R = 135.0


def fmt(v: float) -> str:
    return f"{v:.3f}".rstrip("0").rstrip(".")


def build_nc() -> list[str]:
    t_grid, theta = geo.camber_theta()
    lines: list[str] = []
    a = lines.append

    a("%")
    a("O2003 (AERO-ENGINE CLOSED IMPELLER NASA1975 - 5AXIS)")
    a("(MODEL: AE_CLOSED_IMPELLER_NASA1975 D2=258.06 H=74.85 Z=16 BLADES)")
    a("(MACHINE: DMG MORI NMV1500 / FANUC 30iM / AC TABLE)")
    a("(STOCK: D270 X 82  MATERIAL: TC11/INCONEL718)")
    a("G21 G90 G40 G80 G49 G17")
    a("G54")

    # ---------------- OP1: 轮盖外轮廓 / 进气口粗加工 ----------------
    a("(=== OP1: COVER OUTER PROFILE ROUGHING D16 ===)")
    a("M01")
    a("T1 M06 (D16 ROUGHING ENDMILL)")
    a("S4000 M03")
    a("M08")
    a("G00 G90 B0. C0.")
    a("G00 X132. Y0. Z100.")
    a("G43 H1 Z95.")
    for z_cut, radius in ((80.0, 132.0), (77.0, 126.0), (74.85, 120.0)):
        a(f"G01 Z{fmt(z_cut)} F300.")
        a(f"G02 I-{fmt(radius)} J0. F900.")
        a(f"G01 X{fmt(radius - 8.0)} F500.")
    a("G01 X0. Y0. F500.")
    a("G00 Z95.")
    a("M09")
    a("G49 G90")

    # ---------------- OP2: 16 条封闭流道五轴精加工 ----------------
    a("(=== OP2: 16 CLOSED PASSAGES 5-AXIS RTCP D10 LOLLIPOP ===)")
    a("M01")
    a("T2 M06 (D10 LOLLIPOP UNDERCUT BALL NOSE)")
    a("S9500 M03")
    a("M08")
    a("G05.1 Q1")
    a("G43.4 H2 (RTCP/TCPM)")

    pitch = 360.0 / geo.Z_BLADES
    steps = 20
    for ch in range(geo.Z_BLADES):
        base = ch * pitch + pitch / 2.0
        r_entry = (geo.R1H + geo.R1S) / 2.0
        a(f"(--- CHANNEL {ch + 1}/{geo.Z_BLADES} C={base:.2f} ---)")
        a(f"G00 X{fmt(r_entry * math.cos(math.radians(base)))} "
          f"Y{fmt(r_entry * math.sin(math.radians(base)))} Z95. B0. C{fmt(base)}")
        a(f"G01 Z{fmt(geo.Z_INLET)} F300.")
        for s in range(steps + 1):
            t = s / steps
            r_h = geo.R1H + (geo.R2 - geo.R1H) * t
            r_s = geo.R1S + (geo.R2 - geo.R1S) * t
            r = (r_h + r_s) / 2.0
            z = (geo.z_hub(r_h) + geo.z_shroud(r_s)) / 2.0
            th = float(np.interp(t, t_grid, theta)) + math.radians(base)
            b_ang = 12.0 + 10.0 * math.sin(math.pi * t)
            a(f"G01 X{fmt(r * math.cos(th))} Y{fmt(r * math.sin(th))} Z{fmt(z)} "
              f"B{fmt(b_ang)} C{fmt(math.degrees(th))} F700.")
        th_end = float(theta[-1]) + math.radians(base)
        a(f"G01 X{fmt((STOCK_R + 5.0) * math.cos(th_end))} "
          f"Y{fmt((STOCK_R + 5.0) * math.sin(th_end))} Z{fmt(geo.Z_SHROUD_EXIT)} "
          f"B0. C{fmt(math.degrees(th_end))} F800.")
        a("G00 Z95. B0.")

    a("G49")
    a("G05.1 Q0")
    a("G00 Z120.")
    a("M09")
    a("M05")
    a("G91 G28 Z0.")
    a("G28 X0. Y0. B0. C0.")
    a("M30 (PROGRAM END)")
    a("%")
    return lines


def validate(lines: list[str]) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    pos = {"X": 0.0, "Y": 0.0, "Z": 0.0, "B": 0.0, "C": 0.0}
    feed = None
    motion = None
    spindle_on = False
    rapid_min_z = None
    min_z = None
    max_z = None
    g00_below_safe: list[int] = []
    channels = 0

    word = re.compile(r"([A-Z])([+-]?\d+(?:\.\d+)?)")
    for idx, raw in enumerate(lines, start=1):
        if "CHANNEL" in raw:
            channels += 1
        line = raw.split("(")[0].split(";")[0].strip()
        if not line or line.startswith("%"):
            continue
        words = {k.upper(): float(v) for k, v in word.findall(line)}
        if "G" in words:
            g = int(words["G"])
            if g in (0, 1, 2, 3):
                motion = g
        for axis in ("X", "Y", "Z", "B", "C"):
            if axis in words:
                pos[axis] = words[axis]
        if "F" in words:
            feed = words["F"]
        if "M03" in line or "M04" in line:
            spindle_on = True
        if motion == 1 and "F" not in words and feed is None:
            errors.append(f"L{idx}: G01 without active feedrate")
        if motion == 1 and (("X" in words) or ("Y" in words) or ("Z" in words)) and not spindle_on:
            errors.append(f"L{idx}: cutting move before spindle start")
        if motion in (1, 2, 3):
            min_z = pos["Z"] if min_z is None else min(min_z, pos["Z"])
            max_z = pos["Z"] if max_z is None else max(max_z, pos["Z"])
        if "G00" in line or ("G" in words and int(words["G"]) == 0):
            if "Z" in words:  # 只在程序块真的给出 Z 时判定
                rapid_min_z = words["Z"] if rapid_min_z is None else min(rapid_min_z, words["Z"])
                if words["Z"] < SAFE_Z - 0.01:
                    g00_below_safe.append(idx)
    if g00_below_safe:
        errors.append(f"G00 below safe plane Z={SAFE_Z}: lines {g00_below_safe}")
    if "M30" not in lines[-2] and "M30" not in lines[-1]:
        errors.append("missing M30 program end")
    if channels != geo.Z_BLADES:
        errors.append(f"channel count {channels} != blade count {geo.Z_BLADES}")

    # 复用工程自带 FANUC 语法/安全校验器
    try:
        from virtu_omni.serving.gbnf_grammar import validate_gcode_syntax
        code = "\n".join(lines)
        ok, gbnf_errors = validate_gcode_syntax(code)
        warnings.extend([f"gbnf: {e}" for e in gbnf_errors])
        gbnf_ok = ok
    except Exception as exc:  # noqa: BLE001 - 校验器不可用时不影响主校验
        gbnf_ok = None
        warnings.append(f"gbnf validator unavailable: {type(exc).__name__}: {exc}")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "gbnf_ok": gbnf_ok,
        "channels": channels,
        "expected_channels": geo.Z_BLADES,
        "feedrate_seen": feed is not None,
        "spindle_started": spindle_on,
        "min_z_mm": None if min_z is None else round(min_z, 2),
        "max_z_mm": None if max_z is None else round(max_z, 2),
        "rapid_min_z_mm": None if rapid_min_z is None else round(rapid_min_z, 2),
        "safe_plane_z_mm": SAFE_Z,
        "stock_top_z_mm": STOCK_TOP,
        "g00_below_safe_lines": g00_below_safe,
        "basis": "measured (static parse of generated NC)",
    }


def main() -> dict:
    lines = build_nc()
    NC_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report = {
        "nc_file": str(NC_PATH),
        "nc_lines": len(lines),
        "validation": validate(lines),
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["validation"], ensure_ascii=False, indent=2))
    print("nc:", NC_PATH)
    return report


if __name__ == "__main__":
    main()
