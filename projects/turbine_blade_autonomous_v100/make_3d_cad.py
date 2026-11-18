import math
from build123d import *
with BuildPart() as p:
    # (1) 圣诞树三齿榫头 (Fir-tree Root, 高 30mm)
    with Locations((0, 0, 0)):
        Box(20, 24, 30, align=(Align.CENTER, Align.CENTER, Align.MIN))
        # 叠加三对精密外凸榫齿
        for z_tooth in [7.5, 15.0, 22.5]:
            with Locations((0, 0, z_tooth)):
                Box(24, 20, 4.5, align=(Align.CENTER, Align.CENTER, Align.CENTER))
    # (2) 阻尼缘板 (Platform, 位于 Z=30 处，厚度 6mm)
    with Locations((0, 0, 30)):
        Box(28, 42, 6, align=(Align.CENTER, Align.CENTER, Align.MIN))
    # (3) 变截面空间扭曲叶身 (Airfoil Blade, 高度 59mm，从 Z=36 到 Z=95)
    # 在三个高度建立带旋转角的草图截面，并调用无参 loft() 完成放样
    with BuildSketch(Plane.XY.offset(36)) as s_root:
        Ellipse(x_radius=19, y_radius=3.6)
    with BuildSketch(Plane.XY.offset(65)) as s_mid:
        with Locations(Rotation(0, 0, 14.25)):
            Ellipse(x_radius=16, y_radius=2.7)
    with BuildSketch(Plane.XY.offset(95)) as s_tip:
        with Locations(Rotation(0, 0, 28.5)):
            Ellipse(x_radius=13, y_radius=1.8)
    loft()
part = p.part
vol = part.volume
assert vol > 12000.0, f"Volume {vol} is too small!"
mass_g = vol * 8.19e-3  # Inconel 718 镍基高温合金密度 8.19 g/cm³
export_step(part, "turbine_blade_3d_cad.step")
export_stl(part, "turbine_blade_3d_cad.stl")
print(f"[3D_CAD_COMPLETE] Turbine blade volume: {vol:.2f} mm3, Mass: {mass_g:.2f} g")