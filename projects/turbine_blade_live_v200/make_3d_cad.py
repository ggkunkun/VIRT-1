# -*- coding: utf-8 -*-
"""Stage-2 4-Tooth Fir-Tree Turbine Blade 3D CAD Modeling (build123d).
Part: HIGH-PRESSURE TURBINE ROTOR BLADE STAGE-2
Material: CMSX-4 Single Crystal Superalloy (rho = 8.70 g/cm³)
"""
from build123d import *

with BuildPart() as p:
    # 1. 4-Tooth Fir-tree Root (Height: 24mm, Z: 0 -> 24)
    with Locations((0, 0, 0)):
        Box(22, 26, 24, align=(Align.CENTER, Align.CENTER, Align.MIN))
        # 4 pairs of precision fir-tree teeth
        for z_tooth in [3.0, 9.0, 15.0, 21.0]:
            with Locations((0, 0, z_tooth)):
                Box(26, 22, 4.0, align=(Align.CENTER, Align.CENTER, Align.CENTER))

    # 2. Damping Platform (Z: 24 -> 29, Thickness: 5mm)
    with Locations((0, 0, 24)):
        Box(32, 44, 5, align=(Align.CENTER, Align.CENTER, Align.MIN))

    # 3. Twisted Airfoil Blade (Z: 29 -> 99, Height: 70mm, Stagger Twist: 31.5 deg)
    with BuildSketch(Plane.XY.offset(29)) as s_root:
        Ellipse(x_radius=18, y_radius=3.8)
    with BuildSketch(Plane.XY.offset(64)) as s_mid:
        with Locations(Rotation(0, 0, 15.75)):
            Ellipse(x_radius=15, y_radius=2.8)
    with BuildSketch(Plane.XY.offset(99)) as s_tip:
        with Locations(Rotation(0, 0, 31.5)):
            Ellipse(x_radius=12, y_radius=1.8)
    loft()

part = p.part
vol = part.volume
assert vol > 18000.0, f"Volume {vol} is too small! Failed volume conservation assertion."

density_g_cm3 = 8.70
mass_g = vol * density_g_cm3 * 1e-3

export_step(part, "turbine_blade_stage2.step")
export_stl(part, "turbine_blade_stage2.stl")

print(f"[3D_CAD_COMPLETE] Stage-2 Turbine Blade Volume: {vol:.2f} mm3, Mass: {mass_g:.2f} g")
