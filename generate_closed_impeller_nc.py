# -*- coding: utf-8 -*-
"""
Generate 5-Axis CNC Toolpath (FANUC 30iM G-code) for Aero-Engine Closed Impeller
(Shrouded Impeller / 闭式叶轮五轴特种流道铣削加工程序)
Machine: DMG Mori NMV1500 (Fanuc 30iM)
"""

import math
import numpy as np

nc_path = r"D:\Virtu模型\closed_impeller_5axis.nc"

lines = []
lines.append("%")
lines.append("O2002 (AERO-ENGINE SHROUDED CLOSED IMPELLER 5-AXIS MACHINING)")
lines.append("(MATERIAL: TC11 TITANIUM ALLOY / INCONEL 718)")
lines.append("(MACHINE: DMG MORI NMV1500 - FANUC 30iM)")
lines.append("(PART NUMBER: AE-SHR-IMP-002)")
lines.append("G21 G90 G40 G80 G49 G17")
lines.append("G54")

# ==============================================================
# OP1: Shroud Outer Profile & Inlet Eye Roughing
# Tool 1: 16mm Roughing Endmill (T1 M06)
# ==============================================================
lines.append("(=== OPERATION 1: SHROUD EXTERIOR & INLET EYE TURNING/MILLING ===)")
lines.append("M01")
lines.append("T1 M06 (16MM ROUGHING ENDMILL)")
lines.append("S4000 M03")
lines.append("M08")
lines.append("G00 G90 B0. C0.")
lines.append("G00 X0. Y0. Z60.")
lines.append("G43 H1 Z50.")

# Inlet eye spiral entry (D=70mm, R=35mm)
for z_cut in [45.0, 40.0, 35.0, 30.0]:
    lines.append(f"G01 Z{z_cut:.2f} F600.")
    lines.append(f"G02 I35.0 J0. F1200.")
    lines.append("G01 X0. Y0. F800.")

# Shroud conical profile turning (R from 35 at Z=45 to R=80 at Z=16)
for z_lvl in np.linspace(45.0, 16.0, 8):
    t = (45.0 - z_lvl) / 29.0
    r_curr = 38.5 + (80.0 - 38.5) * t
    lines.append(f"G00 X{r_curr + 5.0:.2f} Y0. Z{z_lvl + 2.0:.2f}")
    lines.append(f"G01 X{r_curr:.2f} Y0. Z{z_lvl:.2f} F800.")
    lines.append(f"G02 I-{r_curr:.2f} J0. F1500.")
    lines.append(f"G00 X{r_curr + 5.0:.2f}")

lines.append("G00 Z80.")
lines.append("M09")
lines.append("G49 G90")

# ==============================================================
# OP2: 5-Axis Internal Closed Flow Passage Undercutting (10 Passages)
# Tool 2: 10mm Spherical Lollipop / Undercut Ball Mill (T2 M06)
# G43.4 RTCP Active
# ==============================================================
lines.append("(=== OPERATION 2: 5-AXIS INTERNAL CLOSED PASSAGE UNDERCUTTING ===)")
lines.append("M01")
lines.append("T2 M06 (10MM LOLLIPOP UNDERCUT BALL NOSE)")
lines.append("S9500 M03")
lines.append("M08")
lines.append("G05.1 Q1")
lines.append("G43.4 H2 (RTCP / TCPM MODE)")

num_passages = 10
for ch in range(num_passages):
    ch_angle = ch * (360.0 / num_passages)
    lines.append(f"(--- Channel {ch + 1}/{num_passages}: Angle {ch_angle:.1f} deg ---)")
    
    # Approach entry at inlet
    entry_r = 36.0
    entry_rad = math.radians(ch_angle)
    ex = entry_r * math.cos(entry_rad)
    ey = entry_r * math.sin(entry_rad)
    lines.append(f"G00 X{ex:.3f} Y{ey:.3f} Z55. B0. C{ch_angle:.2f}")
    lines.append(f"G01 Z42. F1000.")
    
    # 5-axis curve through internal passage from inlet to outlet
    # B tilts into channel (up to 28 deg), C rotates along spiral
    for step in range(16):
        t = step / 15.0
        # radius from 36 to 78
        r = 36.0 + (78.0 - 36.0) * t
        # z from 38 down to 10
        z = 38.0 - 28.0 * (t**0.8)
        # spiral angle delta
        delta_phi = -math.radians(35.0 * (t**1.4))
        phi = entry_rad + delta_phi
        
        px = r * math.cos(phi)
        py = r * math.sin(phi)
        
        # 5-axis tilt angles
        b_angle = 18.0 * math.sin(t * math.pi)
        c_angle = ch_angle + math.degrees(delta_phi) * 0.7
        
        lines.append(f"G01 X{px:.3f} Y{py:.3f} Z{z:.3f} B{b_angle:.2f} C{c_angle:.2f} F900.")
        
    # Retract along passage exit
    exit_rad = entry_rad - math.radians(35.0)
    lines.append(f"G01 X{88.0 * math.cos(exit_rad):.3f} Y{88.0 * math.sin(exit_rad):.3f} Z12. F1200.")
    lines.append(f"G00 Z65. B0.")

lines.append("G49")
lines.append("G05.1 Q0")
lines.append("G00 Z100.")
lines.append("M09")
lines.append("M05")
lines.append("G91 G28 Z0.")
lines.append("G28 X0. Y0. B0. C0.")
lines.append("M30 (PROGRAM END)")
lines.append("%")

with open(nc_path, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"Generated closed impeller NC: {nc_path} (Lines: {len(lines)})")

# ==============================================================
# Update / Create VERICUT Project: closed_impeller_vericut.vcproject
# ==============================================================
with open(r'E:\samples\All\force_impeller_dmg_mori_nmv1500_fan30im_mm.vcproject', 'r', encoding='utf-8', errors='ignore') as f:
    vc_content = f.read()

# Replace references
vc_content = vc_content.replace('force-impeller.nc', nc_path)
vc_content = vc_content.replace('force-impeller_stock.ply', r'D:\Virtu模型\closed_impeller_stock.stl')
vc_content = vc_content.replace('force-impeller_design.ply', r'D:\Virtu模型\closed_impeller_design.stl')
vc_content = vc_content.replace('DMG Mori, NMV1500, Mapps IV, 5 axis vertical mill, AC table, Metric, Force, Aerospace, Impeller, Autodiff',
                                'DMG Mori NMV1500, Aero-Engine Shrouded Closed Impeller 5-Axis Machining Simulation')

out_vc = r'D:\Virtu模型\closed_impeller_vericut.vcproject'
with open(out_vc, 'w', encoding='utf-8') as f:
    f.write(vc_content)

print(f"Created VERICUT project: {out_vc}")
