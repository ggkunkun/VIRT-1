from build123d import *

with BuildPart() as p:
    # 1. 轮盘底座
    Cylinder(radius=60, height=10)
    # 2. 轮毂本体 (放在底盘上方)
    with Locations((0, 0, 10)):
        Cone(bottom_radius=30, top_radius=20, height=35)
    # 3. 6片后弯叶片阵列
    for i in range(6):
        with Locations(Rotation(0, 0, i * 60)):
            with Locations((35, 0, 10)):
                Box(40, 2.5, 15, align=(Align.CENTER, Align.CENTER, Align.MIN))
    # 4. 减去中心孔与键槽
    Hole(radius=8, depth=50)
    with Locations((8 + 1.15, 0, 22.5)):
        Box(2.3, 5.0, 50, mode=Mode.SUBTRACT)

export_step(p.part, "impeller_3d_cad.step")
export_stl(p.part, "impeller_3d_cad.stl")

vol = p.part.volume
mass = vol * 2.81e-3
print(f"[3D_CAD_COMPLETE] Volume: {vol:.2f} mm3, Mass: {mass:.2f} g")