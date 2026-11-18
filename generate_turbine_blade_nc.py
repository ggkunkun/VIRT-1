# -*- coding: utf-8 -*-
"""
Generate 5-Axis Simultaneous CNC Toolpath (FANUC 30iM G-code)
for Aero-Engine High-Pressure Turbine Rotor Blade Machining.
Operations:
1. 3-Tier Fir-Tree Root Rough & Finish Grinding/Milling (枞树型榫头成形加工)
2. Platform Profile & Sealing Slot Finishing (缘板与阻尼密封槽精加工)
3. 5-Axis Simultaneous Aerodynamic Airfoil Spiral Finishing (三维扭转气动叶身五轴联动螺旋精铣)
"""

import math

nc_path = r"D:\Virtu模型\turbine_blade_5axis.nc"

lines = []
lines.append("%")
lines.append("O1001 (AERO-ENGINE HPT TURBINE ROTOR BLADE 5-AXIS MACHINING)")
lines.append("(MATERIAL: DD6 SINGLE CRYSTAL SUPERALLOY)")
lines.append("(MACHINE: DMG MORI NMV1500 - FANUC 30iM)")
lines.append("(PART NUMBER: AE-HPT-BLD-001)")
lines.append("G21 G90 G40 G80 G49 G17")
lines.append("G54")

# ==============================================================
# OP1: Fir-Tree Root 3-Tier Serration Creep-Feed / Milling
# Tool 1: 10mm Ball/Form Endmill (T1 M06)
# ==============================================================
lines.append("(=== OPERATION 1: FIR-TREE ROOT 3-TIER SERRATION FORMING ===)")
lines.append("M01")
lines.append("T1 M06 (10MM FIR-TREE FORM ENDMILL)")
lines.append("S3500 M03")
lines.append("M08 (COOLANT ON)")
lines.append("G00 G90 B0. C0.")
lines.append("G00 X-25. Y-15. Z10.")
lines.append("G43 H1 Z5.")

# Tooth 1 (Top tooth)
lines.append("(--- Tooth 1: Top Serration Pass ---)")
for depth in [-4.0, -8.0]:
    lines.append(f"G00 X-22. Y-14. Z{depth:.2f}")
    lines.append(f"G01 X-15. Y-12. Z{depth:.2f} F600.")
    lines.append(f"G01 X-9. Y-8. Z{depth:.2f} F450.")
    lines.append(f"G02 X-9. Y8. R12.5 F450.")
    lines.append(f"G01 X-15. Y12. Z{depth:.2f} F600.")
    lines.append(f"G00 X-22. Y14.")

# Tooth 2 (Middle tooth)
lines.append("(--- Tooth 2: Middle Serration Pass ---)")
for depth in [-12.0, -16.0]:
    lines.append(f"G00 X-20. Y-12. Z{depth:.2f}")
    lines.append(f"G01 X-13.5 Y-10. Z{depth:.2f} F550.")
    lines.append(f"G01 X-8. Y-6. Z{depth:.2f} F400.")
    lines.append(f"G02 X-8. Y6. R11.0 F400.")
    lines.append(f"G01 X-13.5 Y10. Z{depth:.2f} F550.")
    lines.append(f"G00 X-20. Y12.")

# Tooth 3 (Bottom tooth)
lines.append("(--- Tooth 3: Bottom Serration Pass ---)")
for depth in [-22.0, -26.0, -29.0]:
    lines.append(f"G00 X-18. Y-10. Z{depth:.2f}")
    lines.append(f"G01 X-12. Y-8. Z{depth:.2f} F500.")
    lines.append(f"G01 X-7. Y-4. Z{depth:.2f} F350.")
    lines.append(f"G02 X-7. Y4. R9.5 F350.")
    lines.append(f"G01 X-12. Y8. Z{depth:.2f} F500.")
    lines.append(f"G00 X-18. Y10.")

lines.append("G00 Z30.")
lines.append("M09")
lines.append("G49 G90")

# ==============================================================
# OP2: Platform Perimeter & Sealing Slot Finishing
# Tool 2: 6mm Flat Endmill (T2 M06)
# ==============================================================
lines.append("(=== OPERATION 2: PLATFORM PROFILE & DAMPER SLOT FINISHING ===)")
lines.append("M01")
lines.append("T2 M06 (6MM FLAT ENDMILL)")
lines.append("S4800 M03")
lines.append("M08")
lines.append("G00 X-25. Y-20. Z15.")
lines.append("G43 H2 Z8.")

# Rectangular contour milling of platform (36 x 28 x 6)
for z_lvl in [4.0, 1.0]:
    lines.append(f"G01 Z{z_lvl:.2f} F800.")
    lines.append(f"G01 X-20. Y-16. F1000.")
    lines.append(f"G01 X20. Y-16.")
    lines.append(f"G01 X20. Y16.")
    lines.append(f"G01 X-20. Y16.")
    lines.append(f"G01 X-20. Y-16.")

lines.append("G00 Z30.")
lines.append("M09")
lines.append("G49 G90")

# ==============================================================
# OP3: 5-Axis Simultaneous Aerodynamic Airfoil Spiral Finishing
# Tool 3: 3.5mm Tapered Ball Endmill (T3 M06)
# Using G43.4 (RTCP / Tool Center Point Control)
# ==============================================================
lines.append("(=== OPERATION 3: 5-AXIS SIMULTANEOUS SPIRAL AIRFOIL FINISHING ===)")
lines.append("M01")
lines.append("T3 M06 (3.5MM TAPERED BALL NOSE)")
lines.append("S12000 M03")
lines.append("M08")
lines.append("G05.1 Q1 (HIGH SPEED LOOKAHEAD)")
lines.append("G43.4 H3 (RTCP / TCPM ACTIVE)")

# Spiral down from blade tip (Z=91) to blade root (Z=6)
# Chord scales from 24mm at tip to 32mm at root
# Stagger angle rotates from 25 deg at tip to 48 deg at root (Total twist = 23 deg)
z_start = 91.0
z_end = 6.0
num_loops = 55
pts_per_loop = 24

lines.append("G00 X0. Y0. Z105. B0. C0.")
lines.append("G01 Z93. F1500.")

for loop in range(num_loops):
    frac = loop / float(num_loops)
    z_curr = z_start - frac * (z_start - z_end)
    chord_curr = 24.0 + frac * (32.0 - 24.0)
    stagger_deg = 25.0 + frac * 23.0
    stagger_rad = math.radians(stagger_deg)
    
    # 5-axis tilt angle B tracks twist angle, C tracks rotary orientation
    b_tilt = (stagger_deg - 25.0) * 0.45
    
    for pt in range(pts_per_loop):
        theta = 2.0 * math.pi * pt / pts_per_loop
        # Elliptical cross section approximating cambered airfoil
        u = math.cos(theta)
        v = math.sin(theta) * 0.28
        
        # Scale by chord and rotate by stagger
        xr = (u * (chord_curr * 0.5)) * math.cos(stagger_rad) - (v * (chord_curr * 0.5)) * math.sin(stagger_rad)
        yr = (u * (chord_curr * 0.5)) * math.sin(stagger_rad) + (v * (chord_curr * 0.5)) * math.cos(stagger_rad)
        
        # Tool normal orientation
        c_rot = math.degrees(math.atan2(yr, xr)) * 0.35
        
        # Slight spiral Z progression
        z_pt = z_curr - (pt / float(pts_per_loop)) * ((z_start - z_end) / num_loops)
        
        lines.append(f"G01 X{xr:.3f} Y{yr:.3f} Z{z_pt:.3f} B{b_tilt:.2f} C{c_rot:.2f} F1200.")

lines.append("G49 (CANCEL RTCP)")
lines.append("G05.1 Q0")
lines.append("G00 Z120.")
lines.append("G00 X0. Y0. B0. C0.")
lines.append("M09")
lines.append("M05")
lines.append("G91 G28 Z0.")
lines.append("G28 X0. Y0. B0. C0.")
lines.append("M30 (PROGRAM END)")
lines.append("%")

with open(nc_path, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"Generated 5-axis turbine blade NC program: {nc_path}")
print(f"Total lines: {len(lines)}")
