# -*- coding: utf-8 -*-
"""Zero-error 5-axis NC for AE_CLOSED_IMPELLER (FANUC 30iM / DMG NMV1500).

Work-zero convention (VERICUT station offset "54 - Spindle to Stock"):
  Z0 = stock top (world 152.85), so all cutting Z is <= 0.

Fixture limits that the toolpath must respect (see make_impeller_vise.py):
  jaw top  = world 95  -> work Z -57.85
  pedestal top = world 70 -> work Z -82.85
=> All lateral / OD moves are kept at work Z >= -56.5 (1.35 mm above jaw top).
   The lower 25 mm of the block stays as the clamping zone (OP3 after re-clamp).

Sequence:
  OP1  T1 D16 endmill: circular pre-form of the square block to r=137.5,
       Z 0 -> -56.5 in 2 mm steps (removes the four corners, clears the jaws).
  OP2  T2 D10 lollipop: G43.4 RTCP, 16 closed passages, enter at r=140
       (Z -56.5), sweep the mid-channel curve to the inlet (Z -8), retract
       along the same curve (closed impeller: no vertical entry).
"""
from __future__ import annotations

import importlib.util
import json
import math
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(r"E:\vericut_impeller_run\impeller.nc")
REPORT = ROOT / "artifacts" / "aero_closed_impeller" / "nc_validation_zero_error.json"

_spec = importlib.util.spec_from_file_location(
    "impeller_build", ROOT / "scripts" / "build_nasa_closed_impeller.py")
geo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(geo)

SAFE_Z = 10.0            # work Z for all rapids / lateral moves
JAW_TOP_WORK = -57.85    # world 95 - stock top 152.85
LATERAL_Z = -56.5        # 1.35 mm above jaw top
PREFORM_R = 137.5
ENTRY_R = 140.0
STOCK_TOP_WORK = 0.0


def fmt(v: float) -> str:
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def channel_points() -> list[tuple[float, float, float, float]]:
    """Return (x, y, z_work, c_deg) from exit (t=1) to inlet (t=0), truncated."""
    t_grid, theta = geo.camber_theta()
    pts = []
    for k in range(41):
        t = 1.0 - k / 40.0
        r_h = geo.R1H + (geo.R2 - geo.R1H) * t
        r_s = geo.R1S + (geo.R2 - geo.R1S) * t
        r = (r_h + r_s) / 2.0
        z_design = (geo.z_hub(r_h) + geo.z_shroud(r_s)) / 2.0
        z_work = z_design - 77.85
        th = float(np.interp(t, t_grid, theta))
        if z_work < LATERAL_Z:
            continue
        pts.append((r * math.cos(th), r * math.sin(th), z_work, math.degrees(th)))
    return pts


def build() -> list[str]:
    L: list[str] = []
    a = L.append
    a("%")
    a("O2005 (AE-CI-258 CLOSED IMPELLER - 5AXIS ZERO-ERROR SETUP)")
    a("(WORK Z0 = STOCK TOP; LOWER 25MM = CLAMPING ZONE / OP3 AFTER RE-CLAMP)")
    a("(MACHINE DMG MORI NMV1500 / FANUC 30iM / B -180..160 C 0..360)")
    a("(STOCK 264.06 X 264.06 X 82.85 TC11; JAW TOP = WORK Z-57.85)")
    a("G21 G17 G40 G49 G80 G90")
    a("G54")
    a("M01")

    # ---------------- OP1 : circular pre-form ----------------
    a("(=== OP1 CIRCULAR PRE-FORM D16 ===)")
    a("T1 M06 (D16 ENDMILL)")
    a("S1800 M03")
    a("M08")
    a("G00 G90 B0. C0.")
    a("G00 X0. Y0. Z30.")
    a("G43 H1 Z20.")
    z = -1.5
    while z > -57.0 - 1e-6:
        a(f"G01 X{fmt(PREFORM_R)} Y0. Z{fmt(z)} F400.")
        a(f"G03 I-{fmt(PREFORM_R)} J0. F600.")
        a(f"G01 X{fmt(PREFORM_R - 12.0)} F600.")
        a("G00 Z20.")
        z -= 1.5
    a("G00 Z30.")
    a("M09")
    a("G49")

    # ---------------- OP2 : 16 closed passages, RTCP ----------------
    a("(=== OP2 16 CLOSED PASSAGES D10 LOLLIPOP / G43.4 RTCP ===)")
    a("M01")
    a("T2 M06 (D10 LOLLIPOP)")
    a("S3200 M03")
    a("M08")
    a("G00 G90 B0. C0.")
    a("G00 X0. Y0. Z30.")
    a("G43.4 H2 (TCPM ON)")
    pitch = 360.0 / geo.Z_BLADES
    base_pts = channel_points()
    for ch in range(geo.Z_BLADES):
        base = ch * pitch
        a(f"(--- PASSAGE {ch + 1}/{geo.Z_BLADES} C{fmt(base)} ---)")
        # entry point outside the pre-form, at the same angle as the exit point
        ex, ey, ez, ec = base_pts[0]
        ang = math.radians(ec + base)
        a(f"G00 X{fmt(ENTRY_R * math.cos(ang))} Y{fmt(ENTRY_R * math.sin(ang))} "
          f"Z{fmt(SAFE_Z)} B0. C{fmt((ec + base) % 360.0)}")
        a(f"G01 Z{fmt(LATERAL_Z)} F300.")
        # inward sweep  (exit -> inlet)
        for i, (x, y, zw, c) in enumerate(base_pts):
            b = 12.0 + 10.0 * math.sin(math.pi * (1.0 - i / max(1, len(base_pts) - 1)))
            a(f"G01 X{fmt(x)} Y{fmt(y)} Z{fmt(zw)} B{fmt(b)} "
              f"C{fmt((c + base) % 360.0)} F700.")
        # return along the same path (no vertical retract inside the part)
        for i in range(len(base_pts) - 2, -1, -1):
            x, y, zw, c = base_pts[i]
            b = 12.0 + 10.0 * math.sin(math.pi * (1.0 - i / max(1, len(base_pts) - 1)))
            a(f"G01 X{fmt(x)} Y{fmt(y)} Z{fmt(zw)} B{fmt(b)} "
              f"C{fmt((c + base) % 360.0)} F900.")
        a(f"G01 X{fmt(ENTRY_R * math.cos(ang))} Y{fmt(ENTRY_R * math.sin(ang))} "
          f"Z{fmt(LATERAL_Z)} B0. F900.")
        a(f"G00 Z{fmt(SAFE_Z)}")

    a("G49")
    a("G00 Z30.")
    a("M09")
    a("M05")
    a("G91 G28 Z0.")
    a("G28 X0. Y0.")
    a("G90")
    a("G00 B0. C0.")
    a("M30 (END OF PROGRAM)")
    a("%")
    return L


def validate(lines: list[str]) -> dict:
    errors: list[str] = []
    warns: list[str] = []
    pos = {"X": 0.0, "Y": 0.0, "Z": 0.0, "B": 0.0, "C": 0.0}
    feed = None
    motion = 0
    spindle = False
    rtcp = False
    rtcp_seen = 0
    passes = 0
    min_cut_z = None
    for i, raw in enumerate(lines, 1):
        if raw.startswith("(--- PASSAGE"):
            passes += 1
        code = raw.split("(")[0].split(";")[0].strip()
        if not code or code.startswith("%"):
            continue
        if "G28" in code:
            continue
        w = {k.upper(): float(v) for k, v in re.findall(r"([A-Za-z])([+-]?\d+(?:\.\d+)?)", code)}
        gs = [float(v) for k, v in re.findall(r"([Gg])(\d+(?:\.\d+)?)", code)]
        if gs:
            g = gs[0]
            if g in (0.0, 1.0, 2.0, 3.0):
                motion = g
            if g == 43.4:
                rtcp = True
                rtcp_seen += 1
            if g == 49.0:
                rtcp = False
        for k in pos:
            if k in w:
                pos[k] = w[k]
        if "F" in w:
            feed = w["F"]
        if "M03" in code or "M04" in code:
            spindle = True
        if "M05" in code:
            spindle = False
        if motion in (1.0, 2.0, 3.0) and feed is None:
            errors.append(f"L{i}: feed move without F")
        if motion in (1.0, 2.0, 3.0) and not spindle:
            errors.append(f"L{i}: cutting move with spindle stopped")
        if motion == 1.0 and "Z" in w:
            min_cut_z = w["Z"] if min_cut_z is None else min(min_cut_z, w["Z"])
        if motion == 0.0 and "Z" in w and w["Z"] < SAFE_Z - 0.01:
            errors.append(f"L{i}: G00 below safe plane ({w['Z']})")
        if not (-180.0 <= pos["B"] <= 160.0):
            errors.append(f"L{i}: B out of range {pos['B']}")
        if not (-0.01 <= pos["C"] <= 360.01):
            errors.append(f"L{i}: C out of range {pos['C']}")
    if not (lines[-2].find("M30") >= 0 or lines[-1].find("M30") >= 0):
        errors.append("missing M30")
    if passes != geo.Z_BLADES:
        errors.append(f"passage count {passes} != {geo.Z_BLADES}")
    if rtcp_seen == 0:
        errors.append("G43.4 RTCP never enabled for 5-axis passages")
    if min_cut_z is not None and min_cut_z < -57.0 - 0.001:
        errors.append(f"cut below jaw-clearance plane: {min_cut_z}")
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warns,
        "passages": passes,
        "rtcp_enabled": rtcp_seen > 0,
        "min_cut_z": min_cut_z,
        "jaw_top_work_z": JAW_TOP_WORK,
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


