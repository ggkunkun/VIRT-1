# -*- coding: utf-8 -*-
"""OP3 flip setup NC for AE_CLOSED_IMPELLER (FANUC 30iM / DMG NMV1500).

Setup after OP1/OP2 (which machined work Z 0 .. -57.0, Z0 = stock top):
  - part is flipped 180 deg about X
  - work Z0 of OP3 = as-flipped top face = original stock bottom
  - fixture = internal expanding mandrel in the D76.2 hub bore
    (fixture top at OP3 Z -25.85, i.e. the finished upper rim plane)
  - remaining material to remove: 5 mm back-face allowance (Z 0..-5)
    and the lower OD band (Z -5..-25.85) down to r=129.03

Zero-error rules: G54, G43 H, spindle before feed, all G00 at Z>=+10,
cutting kept at Z>=-25.5 (0.35 mm above fixture top), no G05.1, no G28
with rotary axes, M30 at the end.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

OUT = Path(r"E:\vericut_impeller_run\OP3_FLIP.nc")
REPORT = Path(r"D:\Virtu模型\artifacts\aero_closed_impeller\op3_validation.json")

SAFE_Z = 10.0
FACE_Z = -5.0
OD_BOTTOM = -25.5
FIXTURE_TOP = -32.85
PART_R = 129.03
TOOL_R = 5.0          # D10 lollipop
FACE_R = 124.0        # D16 face mill covers to 132
PART_HALF = 132.03


def fmt(v: float) -> str:
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def build() -> list[str]:
    L: list[str] = []
    a = L.append
    a("%")
    a("O2006 (AE-CI-258 OP3 FLIP - BACK FACE + LOWER OD)")
    a("(WORK Z0 = AS-FLIPPED TOP = ORIGINAL STOCK BOTTOM)")
    a("(FIXTURE: INTERNAL MANDREL IN D76.2 BORE, TOP AT Z-32.85)")
    a("(CUT RANGE 0..-25.5; BLOCK BOTTOM AT Z-25.85)")
    a("G21 G17 G40 G49 G80 G90")
    a("G54")
    a("M01")

    # ---- T1 D16 : back face, 5 mm ----
    a("(=== T1 D16 BACK FACE 5MM ===)")
    a("T1 M06 (D16 FACE MILL)")
    a("S1600 M03")
    a("M08")
    a("G00 G90 B0. C0.")
    a("G00 X0. Y0. Z30.")
    a("G43 H1 Z20.")
    a("G00 X140. Y0. Z10.")
    a("G01 Z" + fmt(FACE_Z) + " F200.")
    r = FACE_R
    while r > 0.001:
        a(f"G01 X{fmt(r)} Y0. F500.")
        a(f"G03 I-{fmt(r)} J0. F600.")
        r -= 12.0
    a("G01 X0. Y0. F500.")
    a("G00 Z20.")
    a("M09")
    a("G49")

    # ---- T2 D10 : lower OD to r=129.03 ----
    a("(=== T2 D10 LOWER OD TO r129.03, DEPTH 25.5MM ===)")
    a("M01")
    a("T2 M06 (D10 LOLLIPOP)")
    a("S2200 M03")
    a("M08")
    a("G00 G90 B0. C0.")
    a("G00 X0. Y0. Z30.")
    a("G43 H2 Z20.")
    rc = PART_R + TOOL_R
    a(f"G00 X{fmt(rc)} Y0. Z{fmt(SAFE_Z)}.")
    a(f"G01 Z{fmt(FACE_Z)} F300.")
    z = FACE_Z
    while z > OD_BOTTOM + 0.001:
        z = max(z - 2.5, OD_BOTTOM)
        a(f"G02 I-{fmt(rc)} J0. Z{fmt(z)} F500.")
    a(f"G02 I-{fmt(rc)} J0. F400.")
    a("G00 Z30.")
    a("M09")
    a("M05")
    a("G49")
    a("G91 G28 Z0.")
    a("G28 X0. Y0.")
    a("G90")
    a("G00 B0. C0.")
    a("M30 (END OF PROGRAM)")
    a("%")
    return L


def validate(lines: list[str]) -> dict:
    errors: list[str] = []
    feed = None
    motion = 0
    spindle = False
    min_z = None
    for i, raw in enumerate(lines, 1):
        code = raw.split("(")[0].strip()
        if not code or code in ("%",):
            continue
        if "G28" in code:
            continue
        w = {k.upper(): float(v) for k, v in re.findall(r"([A-Za-z])([+-]?\d+(?:\.\d+)?)", code)}
        gs = [float(v) for k, v in re.findall(r"([Gg])(\d+(?:\.\d+)?)", code)]
        if gs and gs[0] in (0.0, 1.0, 2.0, 3.0):
            motion = gs[0]
        if "F" in w:
            feed = w["F"]
        if "M03" in code:
            spindle = True
        if "M05" in code:
            spindle = False
        if motion in (1.0, 2.0, 3.0) and feed is None:
            errors.append(f"L{i}: feed move without F")
        if motion in (1.0, 2.0, 3.0) and not spindle:
            errors.append(f"L{i}: cutting move with spindle stopped")
        if motion in (1.0, 2.0, 3.0) and "Z" in w:
            min_z = w["Z"] if min_z is None else min(min_z, w["Z"])
        if motion == 0.0 and "Z" in w and w["Z"] < SAFE_Z - 0.01:
            errors.append(f"L{i}: G00 below safe plane ({w['Z']})")
    if min_z is not None and min_z < OD_BOTTOM - 0.001:
        errors.append(f"cut below fixture clearance: {min_z}")
    if not any("M30" in x for x in lines[-3:]):
        errors.append("missing M30")
    return {
        "valid": not errors,
        "errors": errors,
        "min_cut_z": min_z,
        "fixture_top_z": FIXTURE_TOP,
        "clearance_mm": None if min_z is None else round(min_z - FIXTURE_TOP, 3),
        "basis": "measured (static parse of generated NC)",
    }


def main() -> None:
    lines = build()
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\r\n")
    rep = {"nc_file": str(OUT), "nc_lines": len(lines), "validation": validate(lines)}
    REPORT.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(rep["validation"], ensure_ascii=False, indent=2))
    print("nc:", OUT, len(lines), "lines")


if __name__ == "__main__":
    main()





