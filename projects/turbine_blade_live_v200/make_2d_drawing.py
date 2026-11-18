# -*- coding: utf-8 -*-
"""Stage-2 4-Tooth Fir-Tree Turbine Blade 2D Drawing (ezdxf).
Part: HIGH-PRESSURE TURBINE ROTOR BLADE STAGE-2
Material: CMSX-4 Single Crystal Superalloy
Units: Millimeter (mm)
"""
import ezdxf
import math

doc = ezdxf.new("R2010")
msp = doc.modelspace()

# Standard Layers
doc.layers.add("OUTLINE", color=7)
doc.layers.add("CENTER", color=1)
doc.layers.add("DIM", color=3)
doc.layers.add("TEXT", color=2)

# 1. 4-Tooth Fir-tree Root (Z: -24 -> 0)
root_pts = []
for k in range(4):
    y = -float(k) * 5.5 - 2.0
    xr = 13.0 - float(k) * 1.6
    root_pts.append((xr, y))
    root_pts.append((xr + 1.8, y - 2.0))
    root_pts.append((xr - 0.5, y - 3.8))
root_pts.append((5.0, -24.0))
root_pts.append((-5.0, -24.0))
for pt in reversed(root_pts[:-2]):
    root_pts.append((-pt[0], pt[1]))

msp.add_lwpolyline(root_pts, close=True, dxfattribs={"layer": "OUTLINE"})

# 2. Damping Platform (Z: 0 -> 5)
platform_pts = [(-22.0, 0.0), (22.0, 0.0), (22.0, 5.0), (-22.0, 5.0)]
msp.add_lwpolyline(platform_pts, close=True, dxfattribs={"layer": "OUTLINE"})

# 3. Twisted Airfoil (Z: 5 -> 75, Height = 70mm)
# Root section (chord 36mm)
airfoil_root = []
for i in range(21):
    x = float(i) * 36.0 / 20.0
    yc = 0.08 * x * (1.0 - x / 36.0)
    yt = 0.12 * 36.0 * 0.5 * (1.0 - x / 36.0)
    airfoil_root.append((x - 18.0, 5.0 + yc + yt))
for i in range(20, -1, -1):
    x = float(i) * 36.0 / 20.0
    yc = 0.08 * x * (1.0 - x / 36.0)
    yt = 0.12 * 36.0 * 0.5 * (1.0 - x / 36.0)
    airfoil_root.append((x - 18.0, 5.0 + yc - yt))
msp.add_lwpolyline(airfoil_root, close=True, dxfattribs={"layer": "OUTLINE"})

# Centerline
msp.add_line((0, -28), (0, 82), dxfattribs={"layer": "CENTER"})

# Title block & Annotations
msp.add_text("HIGH-PRESSURE TURBINE ROTOR BLADE STAGE-2", dxfattribs={"layer": "TEXT", "height": 3.0}).set_placement((35.0, 60.0))
msp.add_text("MATERIAL: CMSX-4 SINGLE CRYSTAL SUPERALLOY", dxfattribs={"layer": "TEXT", "height": 2.2}).set_placement((35.0, 54.0))
msp.add_text("ROTOR SPEED: 15,200 RPM | GAS TEMP: 750 C", dxfattribs={"layer": "TEXT", "height": 2.0}).set_placement((35.0, 48.0))
msp.add_text("FIR-TREE TEETH: 4-TIER PRECISION BROACHED", dxfattribs={"layer": "TEXT", "height": 2.0}).set_placement((35.0, 42.0))
msp.add_text("TWIST ANGLE: 31.5 DEG | TOTAL HEIGHT: 99.0 mm", dxfattribs={"layer": "TEXT", "height": 2.0}).set_placement((35.0, 36.0))

doc.saveas("turbine_blade_stage2.dxf")
print("[2D_BLUEPRINT_COMPLETE] Generated turbine_blade_stage2.dxf successfully!")
