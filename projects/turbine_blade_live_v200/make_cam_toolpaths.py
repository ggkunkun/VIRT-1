# -*- coding: utf-8 -*-
"""Stage-4 Multi-Axis CAM Post-Processing & G-Code Generation.
Part: HIGH-PRESSURE TURBINE ROTOR BLADE STAGE-2
Operations:
  1. turbine_firtree_root.nc (O4001): 4-Tooth Fir-tree Root Wire-EDM / Broaching Toolpath
  2. turbine_5axis_airfoil.nc (O4002): 5-Axis Simultaneous High-Speed Spiral Blade Milling
"""
import math

# 1. Generate 4-Tooth Fir-Tree Root NC Code
firtree_lines = [
    "% (O4001 - HPT STAGE-2 FIR-TREE ROOT 4-TOOTH FINISHING)",
    "O4001",
    "G21 G90 G40 G49",
    "G54 G00 X0.000 Y0.000 Z10.000",
    "M08 (DIELECTRIC FLUID ON)",
    "F100.0",
]

for k in range(4):
    y_base = -k * 5.5 - 2.0
    xr_base = 13.0 - k * 1.6
    firtree_lines.extend([
        f"(--- TOOTH TIER {k+1} PROFILING ---)",
        f"G01 X{xr_base:.3f} Y{y_base:.3f}",
        f"G02 X{xr_base + 1.8:.3f} Y{y_base - 2.0:.3f} R2.100",
        f"G03 X{xr_base - 0.5:.3f} Y{y_base - 3.8:.3f} R1.450",
        f"G01 X{-xr_base + 0.5:.3f} Y{y_base - 3.8:.3f}",
        f"G03 X{-xr_base - 1.8:.3f} Y{y_base - 2.0:.3f} R1.450",
        f"G02 X{-xr_base:.3f} Y{y_base:.3f} R2.100",
    ])

firtree_lines.extend([
    "G00 Z25.000",
    "M09",
    "M30",
    "%",
])

with open("turbine_firtree_root.nc", "w", encoding="utf-8") as f:
    f.write("\n".join(firtree_lines) + "\n")

# 2. Generate 5-Axis Airfoil Finishing NC Code (O4002)
airfoil_lines = [
    "% (O4002 - HPT STAGE-2 5-AXIS AIRFOIL SPIRAL MILLING)",
    "O4002",
    "G21 G90 G94 G40 G49 G17",
    "G54 G00 X0.000 Y0.000 Z120.000 A0.000 C0.000",
    "T0404 M06 (R3.0 SOLID CARBIDE BALL MILL)",
    "S16000 M03",
    "M08 (HIGH PRESSURE SPINDLE COOLANT)",
    "G43 H04 Z105.000",
    "G00 X-20.000 Y0.000 Z102.000 A0.000 C0.000",
    "G01 Z99.000 F1200.0",
]

# Generate multi-level helical 5-axis spiral toolpath from Tip (Z=99) to Root (Z=29)
n_layers = 28
for layer in range(n_layers):
    t_layer = layer / float(n_layers - 1)
    z_curr = 99.0 - t_layer * 70.0
    twist_deg = 31.5 * (1.0 - t_layer)
    a_tilt = 12.0 * math.sin(t_layer * math.pi)
    c_rot = twist_deg
    
    airfoil_lines.append(f"(--- PASS {layer+1}/{n_layers}: Z={z_curr:.2f} mm, TWIST={twist_deg:.1f} DEG ---)")
    n_pts = 16
    for i in range(n_pts + 1):
        theta = i * 2.0 * math.pi / n_pts
        x_pt = (12.0 + 6.0 * (1.0 - t_layer)) * math.cos(theta)
        y_pt = (1.8 + 2.0 * (1.0 - t_layer)) * math.sin(theta)
        f_feed = 1800.0 if layer > 0 else 800.0
        airfoil_lines.append(
            f"G01 X{x_pt:.3f} Y{y_pt:.3f} Z{z_curr:.3f} A{a_tilt:.3f} C{c_rot:.3f} F{f_feed:.1f}"
        )

airfoil_lines.extend([
    "G00 Z130.000 A0.000 C0.000",
    "M09",
    "M05",
    "G91 G28 Z0.000",
    "G28 X0.000 Y0.000",
    "M30",
    "%",
])

with open("turbine_5axis_airfoil.nc", "w", encoding="utf-8") as f:
    f.write("\n".join(airfoil_lines) + "\n")

print(f"[CAM_POST_COMPLETE] Generated turbine_firtree_root.nc ({len(firtree_lines)} lines) and turbine_5axis_airfoil.nc ({len(airfoil_lines)} lines)!")
