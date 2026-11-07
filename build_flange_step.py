# -*- coding: utf-8 -*-
"""
兜底方案（已落地）：用 OCP (pythonocc 的 pip 包 / OpenCASCADE) 离线生成法兰盘实体，
导出 STEP (ISO 10303)。SOLIDWORKS 原生可打开 (File > Open)。
完全不依赖 SW GUI / COM，运行稳定。
参数（米）:
  D_Outer 外径 = 0.120  PCD 分布圆 = 0.095
  D_Bore  轴孔 = 0.040  Thk 厚    = 0.020
  N=6  D_Bolt=0.012
用法: python build_flange_step.py
"""
import math

P = dict(D_Outer=0.120, D_Bore=0.040, Thk=0.020, N=6, D_Bolt=0.012, PCD=0.095)
OUT = r"D:\Virtu模型\Flange_Parametric.step"


def build():
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCP.gp import gp_Ax2, gp_Pnt, gp_Dir
    from OCP.STEPControl import STEPControl_Writer, STEPControl_asIs
    from OCP.IFSelect import IFSelect_RetDone

    ax = gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1))  # 沿 +Z 轴
    R_out = P["D_Outer"] / 2.0
    R_bore = P["D_Bore"] / 2.0
    T = P["Thk"]
    N = int(P["N"])
    r_bolt = P["D_Bolt"] / 2.0
    r_pcd = P["PCD"] / 2.0

    # 主体圆柱
    body = BRepPrimAPI_MakeCylinder(ax, R_out, T).Shape()
    # 中心轴孔（略长于主体以确保切穿）
    bore = BRepPrimAPI_MakeCylinder(ax, R_bore, T + 1e-6).Shape()
    part = BRepAlgoAPI_Cut(body, bore).Shape()

    # 螺栓孔（贯穿，沿 Z）
    for i in range(N):
        a = 2.0 * math.pi * i / N
        cx = r_pcd * math.cos(a)
        cy = r_pcd * math.sin(a)
        hole_ax = gp_Ax2(gp_Pnt(cx, cy, 0), gp_Dir(0, 0, 1))
        hole = BRepPrimAPI_MakeCylinder(hole_ax, r_bolt, T + 1e-6).Shape()
        part = BRepAlgoAPI_Cut(part, hole).Shape()

    writer = STEPControl_Writer()
    writer.Transfer(part, STEPControl_asIs)
    st = writer.Write(OUT)
    ok = (st == IFSelect_RetDone)
    print("STEP 写出:", "OK" if ok else ("状态=%s" % st))
    print("已生成:", OUT)


if __name__ == "__main__":
    build()
