# -*- coding: utf-8 -*-
"""
Generate 3D Parametric CAD Solid Model for Aero-Engine High-Pressure Turbine (HPT) Rotor Blade
Kernel: build123d / OpenCASCADE
Exports: STEP (turbine_blade_hpt.step)
"""

import os
import numpy as np
from build123d import *

output_dir = r"C:\Users\Administrator\.gemini\antigravity\brain\adc7374e-187c-4d80-8350-b1df2ce4409e"
step_path = os.path.join(output_dir, "turbine_blade_hpt.step")

def generate_airfoil_pts(chord, max_thick_ratio, camber, stagger_deg, z_pos, n=36):
    beta = np.linspace(0, np.pi, n)
    x = 0.5 * (1 - np.cos(beta))
    yc = camber * x * (1 - x)
    dyc_dx = camber * (1 - 2 * x)
    theta = np.arctan(dyc_dx)
    yt = 5 * max_thick_ratio * (0.2969 * np.sqrt(np.maximum(x, 1e-6)) - 0.1260 * x - 0.3516 * (x**2) + 0.2843 * (x**3) - 0.1015 * (x**4))
    
    xu = x - yt * np.sin(theta)
    yu = yc + yt * np.cos(theta)
    xl = x + yt * np.sin(theta)
    yl = yc - yt * np.cos(theta)
    
    # Airfoil loop points in 2D
    x_coords = np.concatenate([xu, xl[::-1]]) * chord
    y_coords = np.concatenate([yu, yl[::-1]]) * chord
    
    # Center approximately on centroid
    x_coords -= np.mean(x_coords)
    y_coords -= np.mean(y_coords)
    
    # Rotate by stagger angle
    rad = np.radians(stagger_deg)
    cos_r, sin_r = np.cos(rad), np.sin(rad)
    xr = cos_r * x_coords - sin_r * y_coords
    yr = sin_r * x_coords + cos_r * y_coords
    
    return [Vector(float(px), float(py), float(z_pos)) for px, py in zip(xr, yr)]

try:
    with BuildPart() as turbine_blade:
        # 1. 枞树型榫头 (Fir-tree Root: Z from -30 to 0)
        with BuildSketch(Plane.XY.offset(-30)):
            # Draw fir tree symmetrical polygon
            firtree_pts = [
                (0, -12), (7, -12), (8, -11),
                (9, -8), (12, -4), (10, -2),
                (7, -1), (11, 3), (13.5, 5), (11.5, 7),
                (8, 8), (12.5, 12), (15, 14), (13, 16),
                (9, 17), (9, 18),
                (-9, 18), (-9, 17),
                (-13, 16), (-15, 14), (-12.5, 12), (-8, 8),
                (-11.5, 7), (-13.5, 5), (-11, 3), (-7, -1),
                (-10, -2), (-12, -4), (-9, -8),
                (-8, -11), (-7, -12), (0, -12)
            ]
            Polygon([Vector(p[0], p[1]) for p in firtree_pts])
        extrude(amount=30) # extrude along +Z from -30 to 0
        
        # 2. 缘板 (Platform: Z from 0 to 6, width 36 x length 28)
        with BuildSketch(Plane.XY):
            Rectangle(36, 28)
        extrude(amount=6)
        
        # 3. 三维扭转气动叶身 (Lofted Airfoil: Z from 6 to 91 mm)
        # Root section (Z = 6)
        pts_root = generate_airfoil_pts(chord=32, max_thick_ratio=0.18, camber=0.28, stagger_deg=48, z_pos=6)
        # Mid section (Z = 48.5)
        pts_mid = generate_airfoil_pts(chord=28, max_thick_ratio=0.14, camber=0.22, stagger_deg=36, z_pos=48.5)
        # Tip section (Z = 91)
        pts_tip = generate_airfoil_pts(chord=24, max_thick_ratio=0.10, camber=0.18, stagger_deg=25, z_pos=91)
        
        # Create spline wires for the 3 sections
        wire_root = Wire.make_polygon(pts_root)
        wire_mid = Wire.make_polygon(pts_mid)
        wire_tip = Wire.make_polygon(pts_tip)
        
        face_root = Face(wire_root)
        face_mid = Face(wire_mid)
        face_tip = Face(wire_tip)
        
        airfoil_solid = Solid.make_loft([wire_root, wire_mid, wire_tip])
        add(airfoil_solid)
        
    blade_part = turbine_blade.part
    print(f"Turbine blade modeled successfully!")
    print(f"Volume: {blade_part.volume:.2f} mm^3")
    print(f"Bounding Box: {blade_part.bounding_box()}")
    
    # Export to STEP
    export_step(blade_part, step_path)
    print(f"Exported STEP to: {step_path}")

except Exception as e:
    import traceback
    traceback.print_exc()
