# -*- coding: utf-8 -*-
"""按 NASA NTRS 19750003125 样例参数生成闭式叶轮（闭式离心叶轮）参数化模型。

参数来源：artifacts/nasa_1975_impeller_sample_params.csv
  - 叶轮出口半径 r2 = 129.03 mm，进口轮毂半径 r1h = 38.10 mm
  - 进口轮盖半径 r1s = 84.58 mm，出口宽度 b2 = 13.69 mm
  - 叶片数 Z = 16，出口后弯角 β2 ≈ -25°
  - 叶片厚度：轮盖侧 1.27 mm，轮毂侧 3.81 mm（线性锥度）
  - 叶片为直纹面：前缘径向线元、尾缘轴向线元、零 lean

明确标注的工程假设（非 NASA 原文）：
  - 轴孔半径 12.5 mm（Φ25 H7）
  - 轮盘背部基体厚 6.0 mm
  - 前轮盖壁厚 5.0 mm（闭式化）
  - 进口叶片角 β1 = -55°（相对径向），用于生成后弯型线
  - 圆角/倒角未建模（复杂布尔相交处，后续 CAE/CAM 阶段补）
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np
from build123d import (
    Axis,
    Face,
    Vector,
    Wire,
    export_step,
    export_stl,
    loft,
    revolve,
)

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "artifacts" / "aero_closed_impeller"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ----------------------------- 设计参数（NASA 1975 样例） -----------------------------
R1H = 38.10        # mm 进口轮毂半径
R1S = 84.58        # mm 进口轮盖半径
R2 = 129.03        # mm 出口半径
B2 = 13.69         # mm 出口宽度
L_AX = 69.85       # mm 叶轮轴向长度（不含轮盖附加厚度）
Z_BLADES = 16      # 叶片数
T_HUB = 3.81       # mm 轮毂侧叶片厚度
T_SHROUD = 1.27    # mm 轮盖侧叶片厚度
BETA2 = -25.0      # deg 出口后弯角（相对径向）

# ----------------------------- 工程假设（非原文） -----------------------------
R_BORE = 12.5      # mm 轴孔半径
HUB_BASE = 6.0     # mm 轮盘背部基体厚度
COVER_T = 5.0      # mm 前轮盖壁厚
# 16 片叶片节距 22.5°，进口角必须足够小以免相邻叶片包角重叠；
# -12° 对应总包角约 -14.5°，留出约 8° 流道。
BETA_IN = -12.0    # deg 进口叶片角（相对径向）
STATIONS = 9       # 叶片放样截面数

Z_SHROUD_EXIT = HUB_BASE + B2          # 19.69
Z_COVER_OUT_EXIT = Z_SHROUD_EXIT + COVER_T   # 24.69
Z_INLET = L_AX                          # 69.85
Z_COVER_OUT_INLET = Z_INLET + COVER_T   # 74.85
R_COVER_OUT_INLET = R1S + COVER_T       # 89.58

# 子午型线控制点 (r, z)
HUB_CTRL = [(R1H, Z_INLET), (60.0, 55.0), (85.0, 40.0), (110.0, 22.0), (R2, HUB_BASE)]
SHROUD_CTRL = [(R1S, Z_INLET), (100.0, 55.0), (115.0, 38.0), (R2, Z_SHROUD_EXIT)]
HUB_CTRL_S = sorted(HUB_CTRL)
SHROUD_CTRL_S = sorted(SHROUD_CTRL)


def z_hub(r: float) -> float:
    return float(np.interp(r, [p[0] for p in HUB_CTRL_S], [p[1] for p in HUB_CTRL_S]))


def z_shroud(r: float) -> float:
    return float(np.interp(r, [p[0] for p in SHROUD_CTRL_S], [p[1] for p in SHROUD_CTRL_S]))


def build_hub():
    pts = [(R_BORE, 0.0), (R2, 0.0), (R2, HUB_BASE)]
    pts += [(r, z) for r, z in reversed(HUB_CTRL_S)]
    pts += [(R_BORE, Z_INLET)]
    face = Face(Wire.make_polygon([Vector(r, 0, z) for r, z in pts], close=True))
    return revolve(face, Axis.Z)


def build_cover():
    inner = list(SHROUD_CTRL_S)  # (R1S..R2) 内侧流道面
    outer = [
        (R2, Z_COVER_OUT_EXIT),
        (115.0, 38.0 + COVER_T),
        (100.0, 55.0 + COVER_T),
        (R_COVER_OUT_INLET, Z_COVER_OUT_INLET),
    ]
    # 顺序：进口内缘 -> 内侧型线 -> 出口外缘 -> 外侧型线 -> 进口外缘 -> 闭合
    pts = [(R1S, Z_INLET)] + inner[1:] + outer
    face = Face(Wire.make_polygon([Vector(r, 0, z) for r, z in pts], close=True))
    return revolve(face, Axis.Z)


def camber_theta() -> tuple[np.ndarray, np.ndarray]:
    """沿中径流线积分 dθ = tan(β)·dr/r，得到后弯包角分布。"""
    n = 80
    r_mid = np.linspace((R1H + R1S) / 2.0, R2, n)
    betas = np.linspace(BETA_IN, BETA2, n)
    theta = np.zeros(n)
    for i in range(1, n):
        dr = r_mid[i] - r_mid[i - 1]
        theta[i] = theta[i - 1] + math.tan(math.radians(betas[i])) * dr / r_mid[i]
    return np.linspace(0.0, 1.0, n), theta


def build_blade():
    t_grid, theta = camber_theta()
    sections = []
    for k in range(STATIONS):
        t = k / (STATIONS - 1)
        rh = R1H + (R2 - R1H) * t
        rs = R1S + (R2 - R1S) * t
        zh, zs = z_hub(rh), z_shroud(rs)
        th = float(np.interp(t, t_grid, theta))
        c, s = math.cos(th), math.sin(th)
        tangent = Vector(-s, c, 0.0)  # 切向单位向量
        hub_pt = Vector(rh * c, rh * s, zh)
        shroud_pt = Vector(rs * c, rs * s, zs)
        hh, hs = T_HUB / 2.0, T_SHROUD / 2.0
        pts = [hub_pt + tangent * hh, shroud_pt + tangent * hs,
               shroud_pt - tangent * hs, hub_pt - tangent * hh]
        sections.append(Face(Wire.make_polygon(pts, close=True)))
    blade = loft(sections, ruled=True)
    return blade, math.degrees(float(theta[-1]))


def render_preview(stl_path: Path, png_path: Path) -> None:
    """用 trimesh + matplotlib 输出一张等轴测预览图。"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import trimesh
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    mesh = trimesh.load(str(stl_path), force="mesh")
    tri = mesh.vertices[mesh.faces]
    step = max(1, len(tri) // 8000)
    tri = tri[::step]
    fig = plt.figure(figsize=(9, 7), dpi=150)
    ax = fig.add_subplot(111, projection="3d")
    pc = Poly3DCollection(tri, facecolor=(0.62, 0.72, 0.82),
                          edgecolor=(0.25, 0.3, 0.35), linewidths=0.1)
    ax.add_collection3d(pc)
    b = mesh.bounds
    ax.set_xlim(b[0][0], b[1][0])
    ax.set_ylim(b[0][1], b[1][1])
    ax.set_zlim(b[0][2], b[1][2])
    ax.set_box_aspect((b[1][0] - b[0][0], b[1][1] - b[0][1], b[1][2] - b[0][2]))
    ax.view_init(elev=28, azim=-55)
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(png_path, dpi=150)
    plt.close(fig)


def export_assembly_stl(hub, cover, blade, stl_path: Path) -> None:
    """单实体的 OCC 网格化在本机不稳定；改为分件网格 + 旋转阵列拼装成多体 STL。"""
    import shutil

    import trimesh
    from build123d import Mesher

    tmp = OUT_DIR / "_tmp_mesh"
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        meshes = []
        for name, shape, deflection in (("hub", hub, 0.5), ("cover", cover, 0.5),
                                        ("blade", blade, 0.3)):
            part_stl = tmp / f"{name}.stl"
            mesher = Mesher()
            mesher.add_shape(shape, linear_deflection=deflection, angular_deflection=0.4)
            mesher.write(str(part_stl))
            meshes.append(trimesh.load(str(part_stl), force="mesh"))
        base_blade = meshes.pop()
        for i in range(Z_BLADES):
            copy = base_blade.copy()
            copy.apply_transform(trimesh.transformations.rotation_matrix(
                math.radians(i * 360.0 / Z_BLADES), [0, 0, 1]))
            meshes.append(copy)
        trimesh.util.concatenate(meshes).export(str(stl_path))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> dict:
    t0 = time.perf_counter()
    print(">>> 构建轮盘（hub）...")
    hub = build_hub()
    print(">>> 构建前轮盖（shroud cover）...")
    cover = build_cover()
    print(">>> 构建叶片（ruled blade）...")
    blade, wrap_deg = build_blade()
    pitch_deg = 360.0 / Z_BLADES
    if abs(wrap_deg) > pitch_deg - 4.0:
        raise RuntimeError(
            f"blade wrap {wrap_deg:.1f}° overlaps pitch {pitch_deg:.1f}°; reduce BETA_IN")

    print(f">>> 阵列 {Z_BLADES} 片叶片并布尔合并（单次 fuse，约十几秒）...")
    blades = [blade.rotate(Axis.Z, i * 360.0 / Z_BLADES) for i in range(Z_BLADES)]
    impeller = hub.fuse(cover, *blades).clean()

    bb = impeller.bounding_box()
    try:
        valid = bool(impeller.is_valid)
    except Exception:
        valid = None
    solids = len(impeller.solids())

    step_path = OUT_DIR / "AE_CLOSED_IMPELLER_NASA1975.step"
    stl_path = OUT_DIR / "AE_CLOSED_IMPELLER_NASA1975.stl"
    export_step(impeller, str(step_path))
    # STEP 往返回读，完成体积一致性校验。
    from build123d import import_step
    roundtrip = import_step(str(step_path))
    rt_volume = roundtrip.volume
    export_assembly_stl(hub, cover, blade, stl_path)
    stl_ok = stl_path.exists()
    png_path = OUT_DIR / "AE_CLOSED_IMPELLER_NASA1975_preview.png"
    if stl_ok:
        render_preview(stl_path, png_path)

    report = {
        "model": "AE_CLOSED_IMPELLER_NASA1975",
        "source": "NASA NTRS 19750003125 sample impeller (converted to mm)",
        "parameters_from_source": {
            "r1h_mm": R1H, "r1s_mm": R1S, "r2_mm": R2, "D2_mm": round(2 * R2, 2),
            "b2_mm": B2, "axial_length_mm": L_AX, "blade_count": Z_BLADES,
            "blade_thickness_hub_mm": T_HUB, "blade_thickness_shroud_mm": T_SHROUD,
            "beta2_deg": BETA2,
        },
        "assumptions": {
            "bore_radius_mm": R_BORE, "hub_base_thickness_mm": HUB_BASE,
            "cover_wall_mm": COVER_T, "beta1_deg": BETA_IN,
            "fillets": "not modeled",
        },
        "derived": {
            "typical_wrap_deg": round(wrap_deg, 1),
            "blade_pitch_deg": round(pitch_deg, 2),
            "channel_height_inlet_radial_mm": round(R1S - R1H, 2),
            "channel_height_exit_mm": B2,
            "overall_height_mm": round(Z_COVER_OUT_INLET, 2),
        },
        "measured": {
            "volume_mm3": round(impeller.volume, 1),
            "step_roundtrip_volume_mm3": round(rt_volume, 1),
            "volume_delta_pct": round(abs(rt_volume - impeller.volume) / impeller.volume * 100, 4),
            "bbox_min_mm": [round(v, 2) for v in (bb.min.X, bb.min.Y, bb.min.Z)],
            "bbox_max_mm": [round(v, 2) for v in (bb.max.X, bb.max.Y, bb.max.Z)],
            "solid_count": solids,
            "is_valid": valid,
            "stl_export_ok": bool(stl_ok),
            "step_bytes": step_path.stat().st_size,
            "stl_bytes": stl_path.stat().st_size if stl_path.exists() else 0,
            "preview_png": str(png_path) if png_path.exists() else None,
            "elapsed_s": round(time.perf_counter() - t0, 1),
        },
        "outputs": {"step": str(step_path), "stl": str(stl_path), "preview": str(png_path)},
        "stl_note": "STL 为分件网格拼装的多体网格（hub+cover+16 blades）；STEP 为单一融合实体",
        "basis": "measured (geometry) / asserted (NASA source parameters)",
    }
    report_path = OUT_DIR / "build_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["measured"], ensure_ascii=False, indent=2))
    print("report:", report_path)
    return report


if __name__ == "__main__":
    main()
