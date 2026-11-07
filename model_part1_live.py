# -*- coding: utf-8 -*-
r"""
完整执行 SOLIDWORKS 2021 法兰盘三维参数化建模全过程，并将模型保存写入：
c:\Users\Administrator\Desktop\零件1.SLDPRT
"""

import os
import sys
import math
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import win32com.client
import win32com.client.gencache as gc

TLB_GUID = "{83A33D31-27C5-11CE-BFD4-00400513BB57}"
SW_VERSION = 29
TARGET_FILE = r"C:\Users\Administrator\Desktop\零件1.SLDPRT"

PARAMS = {
    "D_Outer": 0.160,    # 法兰外径 160 mm
    "D_Bore": 0.050,     # 中心通孔 50 mm
    "Thk_Disk": 0.020,   # 法兰盘厚度 20 mm
    "D_Boss": 0.090,     # 凸台外径 90 mm
    "H_Boss": 0.015,     # 凸台高度 15 mm
    "PCD": 0.125,        # 螺栓孔分度圆直径 125 mm
    "N_Bolts": 6,        # 螺栓孔数量 6 个
    "D_Bolt": 0.014,     # 螺栓孔直径 14 mm
}

def select_front_plane(part):
    names = ["前视基准面", "Front Plane", "Front"]
    for nm in names:
        try:
            if part.SelectByID(nm, "PLANE", 0.0, 0.0, 0.0):
                return True
        except Exception:
            pass
    f = part.FirstFeature()
    while f is not None:
        try:
            if f.Name in names:
                f.Select2(False, 0)
                return True
        except Exception:
            pass
        try:
            f = f.GetNextFeature()
        except Exception:
            break
    return False

def run_flange_process_on_part1():
    print("=" * 75)
    print(">>> [步骤 1/8] 连接 SOLIDWORKS 2021 核心接口与视窗置顶 ...")
    print("=" * 75)
    t0 = time.time()
    mod = gc.EnsureModule(TLB_GUID, 0, SW_VERSION, 0)
    sw = mod.SldWorks()
    try:
        sw.Visible = True
    except Exception:
        pass
    print(f"    -> 连接就绪，耗时: {time.time() - t0:.2f}s")

    print("\n" + "=" * 75)
    print(f">>> [步骤 2/8] 准备目标零件文档: {TARGET_FILE} ...")
    print("=" * 75)
    # 如果目标文件存在，先打开它；若打开失败则新建零件
    part = None
    if os.path.exists(TARGET_FILE):
        ret = sw.OpenDoc6(TARGET_FILE, 1, 1, "", 0, 0)
        raw = ret[0] if isinstance(ret, tuple) else ret
        if raw:
            part = mod.IModelDoc2(raw._oleobj_)
            print(f"    -> 成功打开已有零件文档: {TARGET_FILE}")
    
    if part is None:
        raw = sw.NewPart()
        part = mod.IModelDoc2(raw._oleobj_)
        print("    -> 新建零件模板文档")

    title = part.GetTitle() if callable(part.GetTitle) else part.GetTitle
    print(f"    -> 当前活动文档标题: {title}")

    # 步骤 3：注入参数化全局变量
    print("\n" + "=" * 75)
    print(">>> [步骤 3/8] 注入方程式管理器参数化设计变量 ...")
    print("=" * 75)
    try:
        eqn = part.GetEquationMgr()
        for idx, (k, v) in enumerate(PARAMS.items()):
            val = int(v) if k == "N_Bolts" else v
            eqn.Add(idx, f'"{k}" = {val}')
            unit = "个" if k == "N_Bolts" else "mm"
            disp_v = v if k == "N_Bolts" else v * 1000
            print(f"    -> 全局变量 #{idx+1}: {k:<10s} = {disp_v:>6g} {unit}")
        print(f"    -> 方程式注入完成，共 {eqn.GetCount()} 个全局参数")
    except Exception as e:
        print(f"    [方程式提示] {e}")

    # 步骤 4：草图1与法兰盘主体拉伸
    print("\n" + "=" * 75)
    print(">>> [步骤 4/8] 绘制草图1并拉伸生成法兰盘基体 (Boss-Extrude1) ...")
    print("=" * 75)
    select_front_plane(part)
    part.SketchManager.InsertSketch(True)
    part.ClearSelection2(True)
    r_out = PARAMS["D_Outer"] / 2.0
    r_bore = PARAMS["D_Bore"] / 2.0
    part.SketchManager.CreateCircleByRadius(0.0, 0.0, 0.0, r_out)
    part.SketchManager.CreateCircleByRadius(0.0, 0.0, 0.0, r_bore)
    print(f"    -> 草图1图元: 外轮廓圆 R={r_out*1000:.1f}mm + 中心通孔 R={r_bore*1000:.1f}mm")

    extrude1_args = [
        True, False, True, 0, 0, PARAMS["Thk_Disk"], 0.0,
        False, False, False, False, 0.0, 0.0,
        False, False, False, False, True, False, True,
        0, 0.0, False
    ]
    feat1 = part.FeatureManager.FeatureExtrusion2(*extrude1_args)
    print(f"    -> 拉伸特征1生成: {'成功' if feat1 else '失败'} (厚度 {PARAMS['Thk_Disk']*1000:.1f}mm)")

    # 步骤 5：草图2与颈部凸台反向拉伸合并
    print("\n" + "=" * 75)
    print(">>> [步骤 5/8] 绘制草图2并拉伸生成颈部凸台 (Boss-Extrude2) ...")
    print("=" * 75)
    select_front_plane(part)
    part.SketchManager.InsertSketch(True)
    part.ClearSelection2(True)
    r_boss = PARAMS["D_Boss"] / 2.0
    part.SketchManager.CreateCircleByRadius(0.0, 0.0, 0.0, r_boss)
    part.SketchManager.CreateCircleByRadius(0.0, 0.0, 0.0, r_bore)
    print(f"    -> 草图2图元: 凸台外圆 R={r_boss*1000:.1f}mm + 同心中孔 R={r_bore*1000:.1f}mm")

    extrude2_args = [
        True, False, False, 0, 0, PARAMS["H_Boss"], 0.0,
        False, False, False, False, 0.0, 0.0,
        False, False, False, False, True, False, True,
        0, 0.0, False
    ]
    feat2 = part.FeatureManager.FeatureExtrusion2(*extrude2_args)
    print(f"    -> 凸台特征2生成: {'成功' if feat2 else '失败'} (高度 {PARAMS['H_Boss']*1000:.1f}mm, 合并实体)")

    # 步骤 6：草图3与圆周均布螺栓孔贯穿切除
    print("\n" + "=" * 75)
    print(">>> [步骤 6/8] 绘制草图3并贯穿切除螺栓孔 (Cut-Extrude1) ...")
    print("=" * 75)
    N = int(PARAMS["N_Bolts"])
    pcd_r = PARAMS["PCD"] / 2.0
    bolt_r = PARAMS["D_Bolt"] / 2.0
    select_front_plane(part)
    part.SketchManager.InsertSketch(True)
    part.ClearSelection2(True)
    for i in range(N):
        ang = 2.0 * math.pi * i / N
        x = pcd_r * math.cos(ang)
        y = pcd_r * math.sin(ang)
        part.SketchManager.CreateCircleByRadius(x, y, 0.0, bolt_r)
        print(f"    -> 螺栓孔 #{i+1}: 角度={math.degrees(ang):>5.1f}°, 坐标 X={x*1000:>6.2f}mm, Y={y*1000:>6.2f}mm, 半径={bolt_r*1000:.1f}mm")

    cut_args = [
        False, False, True,
        1, 1,
        0.0, 0.0,
        False, False, False, False,
        0.0, 0.0,
        False, False, False, False,
        False, False, True
    ]
    cut_feat = part.FeatureManager.FeatureCut(*cut_args)
    print(f"    -> 螺栓孔贯穿切除生成: {'成功' if cut_feat else '失败'} (双向贯穿 Through All)")

    # 步骤 7：强制拓扑重构、视图切换与存盘
    print("\n" + "=" * 75)
    print(">>> [步骤 7/8] 强制重构并保存零件至桌面零件1.SLDPRT ...")
    print("=" * 75)
    part.ForceRebuild3(True)
    try:
        part.ShowNamedView2("*Isometric", 7)
        part.ViewZoomtofit2()
    except Exception:
        pass

    # 保存
    ret = part.SaveAs3(TARGET_FILE, 0, 1)
    print(f"    -> 模型保存至: {TARGET_FILE} (SaveAs3 状态码: {ret})")

    # 步骤 8：物理属性校验与特征树总结
    print("\n" + "=" * 75)
    print(">>> [步骤 8/8] 提取最终实体物理属性与特征设计树节点 ...")
    print("=" * 75)
    try:
        mp = part.Extension.CreateMassProperty()
        vol_cm3 = (mp.Volume or 0.0) * 1e6
        mass_kg = (mp.Mass or 0.0)
        area_cm2 = (mp.SurfaceArea or 0.0) * 1e4
        com = mp.CenterOfMass
        print(f"    -> 实体体积:   {vol_cm3:.2f} cm³")
        print(f"    -> 实体表面积: {area_cm2:.2f} cm²")
        if com:
            print(f"    -> 质心坐标:   X={com[0]*1000:.2f}mm, Y={com[1]*1000:.2f}mm, Z={com[2]*1000:.2f}mm")
    except Exception as e:
        print(f"    [属性提示] {e}")

    # 特征树提取
    print("    -> 最新特征设计树 (FeatureManager Tree):")
    feat = part.FirstFeature()
    f_idx = 1
    while feat is not None:
        try:
            fn = feat.Name
            ft = feat.GetTypeName2() if callable(feat.GetTypeName2) else feat.GetTypeName2
            if any(k in ft.lower() for k in ["extrude", "cut", "sketch", "plane"]):
                print(f"       [{f_idx:02d}] {fn:<25s} (类型: {ft})")
                f_idx += 1
        except Exception:
            pass
        try:
            feat = feat.GetNextFeature()
        except Exception:
            break

    # 截取最终屏幕
    out_cap = r"D:\Virtu模型\scratch\flange_part1_modeled.png"
    try:
        from bridges.desktop_controller import DesktopController
        ctl = DesktopController()
        ctl.capture(output_path=out_cap)
        print(f"    -> 屏幕截图保存: {out_cap}")
    except Exception as e:
        pass

    print("\n" + "=" * 75)
    print(">>> 【全部完成】零件1.SLDPRT 法兰盘三维建模全过程已成功执行！")
    print(">>> SOLIDWORKS 界面保持当前活动状态供您在屏幕上实时交互查看。")
    print("=" * 75)

if __name__ == "__main__":
    try:
        run_flange_process_on_part1()
    except Exception as e:
        import traceback
        print(f"执行异常: {e}")
        traceback.print_exc()
        sys.exit(1)
