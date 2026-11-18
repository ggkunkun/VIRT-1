# -*- coding: utf-8 -*-
"""A′ 端到端确定性产出器：CAD 实体 / 性能强度分析 / 二维工程图。

红线：
1. 本模块只按冻结参数**执行**建模、复算、制图，不做任何“合格/不合格”判定；
   判定权仍然只属于 closed_impeller_proctor.ruler() 与各 stage 的独立审计。
2. 分析阶段的所有数值一律由 ruler() 复算派生，不引入任何独立假设或美化系数。
3. 每次产出都在 stdout 打印阶段完成标记，格式与原模型脚本契约一致，
   以便监考环审计代码原样复用，不必为“谁写的脚本”开特例。

用法（由 closed_impeller_proctor --engine solver 调用，也可单独运行）：
    python impeller_stage_solver.py --proj <项目目录> --params params_frozen.json
"""
import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent.parent
MODEL = "virtu-ties-v1:latest"
DEFAULT_PROJ = ROOT / "projects" / "impeller_closed_v1"


# ---------------------------------------------------------------- CAD 实体
def blade_centerline(ri, R, beta_deg, n=11):
    """后弯叶片中心线：r 从 ri 到 R，周向角随半径按出口后弯角累积。"""
    import math as m
    tb = m.tan(m.radians(beta_deg))
    pts = []
    for i in range(n):
        r = ri + (R - ri) * i / (n - 1)
        th = (R - r) * tb / max(r, 1e-6)
        pts.append((r * m.cos(th), r * m.sin(th)))
    return pts


def offset_polyline(pts, d):
    """把开口折线法向偏移 d 后返回新的点列（用于生成有厚度的叶片轮廓）。"""
    out = []
    n = len(pts)
    for i, (x, y) in enumerate(pts):
        if i == 0:
            tx, ty = pts[1][0] - x, pts[1][1] - y
        elif i == n - 1:
            tx, ty = x - pts[-2][0], y - pts[-2][1]
        else:
            tx, ty = pts[i + 1][0] - pts[i - 1][0], pts[i + 1][1] - pts[i - 1][1]
        norm = math.hypot(tx, ty) or 1e-9
        nx, ny = -ty / norm, tx / norm
        out.append((x + nx * d, y + ny * d))
    return out


def build_cad(p, outdir):
    """按冻结参数建立封闭式离心叶轮实体，导出 STEP + STL。"""
    from build123d import (Align, Axis, Cylinder, Polygon, Pos, export_step,
                           export_stl, extrude)

    R = p["D2_mm"] / 2.0
    th = p["hub_disk_thickness_mm"]
    ts = p["shroud_thickness_mm"]
    L = p["axial_length_mm"]
    bore = p["bore_diameter_mm"] / 2.0
    Z = int(p["Z_blades"])
    tb = p["blade_thickness_mm"]
    h = L - th - ts
    if h <= 1.0:
        raise SystemExit(f"[FATAL] 叶片高度 {h:.2f} mm 非正，参数自相矛盾")

    ri = max(p["D1t_mm"] / 2.0, bore * 1.6)
    center = blade_centerline(ri, R, p["beta2b_deg"])
    poly = offset_polyline(center, tb / 2.0) + offset_polyline(center, -tb / 2.0)[::-1]

    from build123d import Sketch
    sk = Sketch() + Polygon(*poly, align=None)
    # 显式给出拉伸方向：build123d 的 extrude 在部分版本上默认沿 -Z 拉伸，
    # 不显式指定会让叶片长到轮毂盘下方，导致拓扑判据整体判红。
    blade = extrude(sk, amount=h, dir=(0, 0, 1))

    hub = Pos(0, 0, 0) * Cylinder(R, th, align=(Align.CENTER, Align.CENTER, Align.MIN))
    shroud = Pos(0, 0, L - ts) * Cylinder(R, ts, align=(Align.CENTER, Align.CENTER, Align.MIN))
    solid = hub + shroud
    for i in range(Z):
        solid = solid + (Pos(0, 0, th) * blade).rotate(Axis.Z, i * 360.0 / Z)

    tool = Pos(0, 0, -1.0) * Cylinder(bore, L + 2.0,
                                     align=(Align.CENTER, Align.CENTER, Align.MIN))
    solid = solid - tool

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    step_path = outdir / "impeller_closed.step"
    stl_path = outdir / "impeller_closed.stl"
    export_step(solid, str(step_path))
    # STL 导出：OCC 的 StlAPI_Writer 在含非 ASCII 字符的目标目录（本项目根目录含中文）
    # 上会返回 False 且不落盘，因此先在纯 ASCII 临时目录写出，再用 Python 搬回项目目录。
    import shutil
    import tempfile
    tmp_dir = Path(tempfile.mkdtemp(prefix="impeller_stl_"))
    tmp_stl = tmp_dir / "impeller_closed.stl"
    ok_stl = export_stl(solid, str(tmp_stl), tolerance=0.05, angular_tolerance=0.2)
    if not ok_stl or not tmp_stl.exists() or tmp_stl.stat().st_size < 10000:
        raise RuntimeError(f"STL 网格导出失败（export_stl 返回 {ok_stl}）")
    shutil.move(str(tmp_stl), str(stl_path))
    if not stl_path.exists():
        raise RuntimeError("STL 产物未落盘")

    vol = float(solid.volume)
    mass = vol * 4.43e-3
    print(f"[CAD_COMPLETE] Volume: {vol:.2f} mm3 Mass: {mass:.2f} g")
    return {"step": str(step_path), "stl": str(stl_path), "volume_mm3": vol, "mass_g": mass}


# ------------------------------------------------------------ 性能/强度分析
def build_analysis(p, ruler_fn=None):
    """全部数值由独立尺子复算派生（不允许任何独立假设）。

    ruler_fn 由调用方注入（监考环传入其自身 ruler 函数对象），
    避免在本模块内二次 import proctor 触发 stdout 重配置、也避免尺子出现第二份副本。
    """
    if ruler_fn is None:
        import closed_impeller_proctor as cp
        ruler_fn = cp.ruler
    vals, viol, adv = ruler_fn(p)
    res = {
        "u2_m_s": vals["u2_m_s"],
        "pressure_ratio": vals["pressure_ratio_recomputed"],
        "M_rel_tip": vals["M_rel_tip"],
        "FOS": vals["FOS_recomputed"],
        "sigma_eq_MPa": vals["sigma_eq_MPa"],
        "T02_K": vals["T02_K"],
        "dh0_kJ_kg": vals["dh0_kJ_kg"],
        "cm2_m_s": vals["cm2_m_s"],
        "slip_sigma": vals["slip_sigma"],
        "Ns": vals["Ns"],
        "method": "analytic_recomputed(由冻结参数解析复算，判别式见 closed_impeller_proctor.ruler)",
        "ruler_violations": viol,
    }
    print("[ANALYSIS_COMPLETE] " + json.dumps(res, ensure_ascii=False))
    return res


# ---------------------------------------------------------------- 二维图纸
def build_drawing(p, outdir):
    """生成 impeller_closed_2d.dxf：主视图 + 轴向剖视 + 标准图层 + 尺寸 + 标题栏。"""
    import ezdxf
    from ezdxf.enums import TextEntityAlignment

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    dxf_path = outdir / "impeller_closed_2d.dxf"

    doc = ezdxf.new("R2010", setup=True)
    for name, color in [("OUTLINE", 7), ("CENTER", 1), ("HIDDEN", 8),
                        ("DIM", 3), ("TITLE_BLOCK", 5)]:
        if name not in doc.layers:
            doc.layers.add(name, color=color)
    doc.header["$LTSCALE"] = 1.0
    msp = doc.modelspace()

    D2 = p["D2_mm"]
    D1t = p["D1t_mm"]
    D1h = p["D1h_mm"]
    bore = p["bore_diameter_mm"]
    L = p["axial_length_mm"]
    Z = int(p["Z_blades"])
    ts = p["shroud_thickness_mm"]
    th = p["hub_disk_thickness_mm"]
    b2 = p["b2_mm"]
    tb = p["blade_thickness_mm"]

    # ---- 主视图：置于上方，中心 (0, L + D2/2 + 30)
    cx, cy = 0.0, L + D2 / 2.0 + 40.0
    for d in (D2, D1t, D1h, bore):
        msp.add_circle((cx, cy), d / 2.0, dxfattribs={"layer": "OUTLINE"})
    msp.add_line((cx - D2 / 2 - 10, cy), (cx + D2 / 2 + 10, cy), dxfattribs={"layer": "CENTER"})
    msp.add_line((cx, cy - D2 / 2 - 10), (cx, cy + D2 / 2 + 10), dxfattribs={"layer": "CENTER"})

    # 叶片投影：Z 条后弯样条
    ri = D1t / 2.0
    tb_half = tb / 2.0
    for k in range(Z):
        ang0 = k * 2 * math.pi / Z
        for sgn in (1, -1):
            pts = []
            for q in range(9):
                r = ri + (D2 / 2.0 - ri) * q / 8.0
                thk = (D2 / 2.0 - r) * math.tan(math.radians(p["beta2b_deg"])) / max(r, 1e-6)
                a = ang0 + thk + sgn * tb_half / max(r, 1e-6)
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
            msp.add_spline(fit_points=pts, dxfattribs={"layer": "OUTLINE"})

    # ---- 轴向剖视图：置于下方，左侧对称轴 x=0，z 向上换算为 y
    base_y = 0.0
    R = D2 / 2.0
    # 轮毂盘
    msp.add_lwpolyline([(-bore / 2, base_y), (-R, base_y), (-R, base_y + th),
                        (-bore / 2, base_y + th)], close=True, dxfattribs={"layer": "OUTLINE"})
    msp.add_lwpolyline([(bore / 2, base_y), (R, base_y), (R, base_y + th),
                        (bore / 2, base_y + th)], close=True, dxfattribs={"layer": "OUTLINE"})
    # 盖盘（封闭上盘，覆盖全宽）
    msp.add_lwpolyline([(-R, base_y + L - ts), (-bore / 2, base_y + L - ts),
                        (-bore / 2, base_y + L), (-R, base_y + L)], close=True,
                       dxfattribs={"layer": "OUTLINE"})
    msp.add_lwpolyline([(R, base_y + L - ts), (bore / 2, base_y + L - ts),
                        (bore / 2, base_y + L), (R, base_y + L)], close=True,
                       dxfattribs={"layer": "OUTLINE"})
    # 叶片（剖视中为倾斜薄断面，出口宽度 b2）
    for sgn in (-1, 1):
        msp.add_lwpolyline([(sgn * (D1t / 2), base_y + th), (sgn * (D1t / 2), base_y + L - ts),
                            (sgn * (R - 0.0), base_y + L - ts), (sgn * R, base_y + th)],
                           close=True, dxfattribs={"layer": "OUTLINE"})
    # 中心孔 + 中心线
    msp.add_line((0, base_y - 8), (0, base_y + L + 8), dxfattribs={"layer": "CENTER"})
    msp.add_line((-R - 12, base_y), (R + 12, base_y), dxfattribs={"layer": "CENTER"})
    msp.add_line((-bore / 2, base_y - 6), (-bore / 2, base_y + L),
                 dxfattribs={"layer": "HIDDEN"})
    msp.add_line((bore / 2, base_y - 6), (bore / 2, base_y + L),
                 dxfattribs={"layer": "HIDDEN"})
    # 出口宽度 b2 与叶尖
    msp.add_line((R, base_y + th), (R + b2, base_y + th), dxfattribs={"layer": "OUTLINE"})
    msp.add_line((R + b2, base_y + th), (R + b2, base_y + L - ts), dxfattribs={"layer": "OUTLINE"})
    msp.add_line((R + b2, base_y + L - ts), (R, base_y + L - ts), dxfattribs={"layer": "OUTLINE"})

    # ---- 尺寸标注（4 项以上）
    dim = msp.add_linear_dim(base=(cx, cy - D2 / 2 - 22), p1=(cx - D2 / 2, cy - D2 / 2 - 5),
                             p2=(cx + D2 / 2, cy - D2 / 2 - 5), dimstyle="EZDXF", dxfattribs={"layer": "DIM"})
    dim.set_text(f"D2={D2:g}")
    dim.render()
    dim = msp.add_linear_dim(base=(cx, cy + D2 / 2 + 14), p1=(cx - D1t / 2, cy + D1t / 2 + 3),
                             p2=(cx + D1t / 2, cy + D1t / 2 + 3), dimstyle="EZDXF", dxfattribs={"layer": "DIM"})
    dim.set_text(f"D1t={D1t:g}")
    dim.render()
    dim = msp.add_diameter_dim(center=(cx, cy), radius=bore / 2.0, angle=45,
                              dimstyle="EZDXF", dxfattribs={"layer": "DIM"})
    dim.set_text(f"BORE={bore:g}")
    dim.render()
    dim = msp.add_linear_dim(base=(-R - 26, base_y + L / 2), p1=(-R - 8, base_y),
                             p2=(-R - 8, base_y + L), angle=90, dimstyle="EZDXF", dxfattribs={"layer": "DIM"})
    dim.set_text(f"L={L:g}")
    dim.render()
    dim = msp.add_linear_dim(base=(R + b2 + 18, base_y + L / 2), p1=(R + b2 + 6, base_y + th),
                             p2=(R + b2 + 6, base_y + L - ts), angle=90, dimstyle="EZDXF", dxfattribs={"layer": "DIM"})
    dim.set_text(f"SHROUD={ts:g}/HUB={th:g}")
    dim.render()

    # ---- 标题栏
    x0, y0 = R + 40.0, base_y - 10.0
    msp.add_lwpolyline([(x0, y0), (x0 + 120, y0), (x0 + 120, y0 + 34), (x0, y0 + 34)],
                       close=True, dxfattribs={"layer": "TITLE_BLOCK"})
    for i in range(1, 4):
        msp.add_line((x0, y0 + i * 8.5), (x0 + 120, y0 + i * 8.5),
                     dxfattribs={"layer": "TITLE_BLOCK"})
    msp.add_text("CLOSED IMPELLER / 封闭式离心叶轮",
                 dxfattribs={"layer": "TITLE_BLOCK", "height": 3.4}).set_placement(
        (x0 + 4, y0 + 25.5), align=TextEntityAlignment.LEFT)
    msp.add_text("MATERIAL: Ti-6Al-4V", dxfattribs={"layer": "TITLE_BLOCK", "height": 2.6}).set_placement(
        (x0 + 4, y0 + 17), align=TextEntityAlignment.LEFT)
    msp.add_text(f"Z={Z}  beta2b={p['beta2b_deg']:g}deg  eta={p['eta_total']:g}",
                 dxfattribs={"layer": "TITLE_BLOCK", "height": 2.6}).set_placement(
        (x0 + 4, y0 + 8.5), align=TextEntityAlignment.LEFT)
    msp.add_text(f"D2={D2:g}  L={L:g}  UNIT: mm",
                 dxfattribs={"layer": "TITLE_BLOCK", "height": 2.6}).set_placement(
        (x0 + 4, y0 + 1), align=TextEntityAlignment.LEFT)

    doc.saveas(str(dxf_path))
    n = len(list(msp))
    print(f"[DRAWING_COMPLETE] entities: {n}")
    return {"dxf": str(dxf_path), "entities": n}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--proj", default=str(DEFAULT_PROJ))
    ap.add_argument("--params", default=None, help="params_frozen.json 路径（缺省 <proj>/params_frozen.json）")
    ap.add_argument("stage", choices=["cad", "analysis", "drawing", "all"])
    args = ap.parse_args()
    proj = Path(args.proj)
    pf = Path(args.params) if args.params else proj / "params_frozen.json"
    p = json.loads(pf.read_text(encoding="utf-8"))
    if args.stage in ("cad", "all"):
        build_cad(p, proj)
    if args.stage in ("analysis", "all"):
        build_analysis(p)
    if args.stage in ("drawing", "all"):
        build_drawing(p, proj)


if __name__ == "__main__":
    main()
