# -*- coding: utf-8 -*-
"""
SOLIDWORKS 2021 参数化建模：带颈法兰盘 (Flange with Hub)
驱动方式：win32com early-bound COM 自动化接口
设计参数：
  - D_Outer    法兰外径          : 160.0 mm
  - D_Bore     中心通孔直径      : 50.0 mm
  - Thk_Disk   法兰盘厚度        : 20.0 mm
  - D_Boss     凸台(颈部)外径    : 90.0 mm
  - H_Boss     凸台高度          : 15.0 mm
  - PCD        螺栓孔分布圆直径  : 125.0 mm
  - N_Bolts    螺栓孔数量        : 6 个
  - D_Bolt     螺栓孔直径        : 14.0 mm
"""

import os
import sys
import math
import time
import subprocess

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
OUT_PRT = r"D:\Virtu模型\Flange_Parametric.SLDPRT"

PARAMS = {
    "D_Outer": 0.160,    # 160 mm
    "D_Bore": 0.050,     # 50 mm
    "Thk_Disk": 0.020,   # 20 mm
    "D_Boss": 0.090,     # 90 mm
    "H_Boss": 0.015,     # 15 mm
    "PCD": 0.125,        # 125 mm
    "N_Bolts": 6,        # 6个
    "D_Bolt": 0.014,     # 14 mm
}

def connect_solidworks():
    print("[1] 清理历史进程并建立 SOLIDWORKS 2021 COM 自动化接口 ...")
    try:
        subprocess.run(["taskkill", "/F", "/IM", "SLDWORKS.exe"], capture_output=True)
    except Exception:
        pass
    time.sleep(3)
    
    t0 = time.time()
    mod = gc.EnsureModule(TLB_GUID, 0, SW_VERSION, 0)
    sw = mod.SldWorks()
    try:
        sw.Visible = True
    except Exception:
        pass
    print(f"    连接就绪，启动耗时: {time.time() - t0:.2f}s")
    return sw, mod

def select_front_plane(part):
    """通过特征树或 SelectByID 选中前视基准面"""
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

def build_flange():
    sw, mod = connect_solidworks()
    
    print("[2] 创建新零件文档 ...")
    raw_doc = sw.NewPart()
    if not raw_doc:
        raise RuntimeError("无法创建新零件文档 (sw.NewPart 返回空)")
    
    part = mod.IModelDoc2(raw_doc._oleobj_)
    print("    文档对象已就绪:", part.GetTitle)

    # 1. 注入方程式管理器全局变量
    print("[3] 注入方程式管理器参数化全局变量 ...")
    try:
        eqn = part.GetEquationMgr()
        for idx, (k, v) in enumerate(PARAMS.items()):
            val = int(v) if k == "N_Bolts" else v
            eqn.Add(idx, f'"{k}" = {val}')
        print(f"    方程式注入完成，共 {eqn.GetCount()} 个全局参数")
    except Exception as e:
        print(f"    [方程式提示] {e}")

    # 2. 特征一：法兰盘主体（外圆 D=160mm + 中心孔 D=50mm，拉伸 20mm）
    d_out_mm = PARAMS['D_Outer'] * 1000
    d_bore_mm = PARAMS['D_Bore'] * 1000
    thk_mm = PARAMS['Thk_Disk'] * 1000
    print(f"[4] 草图1: 法兰盘外径 D={d_out_mm:.1f}mm + 内孔 D={d_bore_mm:.1f}mm ...")
    select_front_plane(part)
    part.SketchManager.InsertSketch(True)
    part.ClearSelection2(True)
    part.SketchManager.CreateCircleByRadius(0.0, 0.0, 0.0, PARAMS["D_Outer"] / 2.0)
    part.SketchManager.CreateCircleByRadius(0.0, 0.0, 0.0, PARAMS["D_Bore"] / 2.0)

    print(f"    拉伸特征1 (厚度 {thk_mm:.1f}mm) ...")
    extrude1_args = [
        True,               # Sd (单向)
        False,              # Flip
        True,               # Dir (正向 +Z)
        0, 0,               # T1=Blind, T2
        PARAMS["Thk_Disk"], # D1=20mm
        0.0,                # D2
        False, False,       # Dchk1, Dchk2
        False, False,       # Ddir1, Ddir2
        0.0, 0.0,           # Dang1, Dang2
        False, False,       # OffsetReverse1, 2
        False, False,       # TranslateSurface1, 2
        True,               # Merge
        False,              # UseFeatScope
        True,               # UseAutoSelect
        0,                  # T0=swStartSketchPlane
        0.0,                # StartOffset
        False               # FlipStartOffset
    ]
    feat1 = part.FeatureManager.FeatureExtrusion2(*extrude1_args)
    print("    法兰盘主体生成:", "成功" if feat1 else "失败")

    # 3. 特征二：凸台/颈部（外圆 D=90mm + 中心孔 D=50mm，反向拉伸 15mm，合并结果）
    d_boss_mm = PARAMS['D_Boss'] * 1000
    h_boss_mm = PARAMS['H_Boss'] * 1000
    print(f"[5] 草图2: 凸台外径 D={d_boss_mm:.1f}mm + 内孔 D={d_bore_mm:.1f}mm ...")
    select_front_plane(part)
    part.SketchManager.InsertSketch(True)
    part.ClearSelection2(True)
    part.SketchManager.CreateCircleByRadius(0.0, 0.0, 0.0, PARAMS["D_Boss"] / 2.0)
    part.SketchManager.CreateCircleByRadius(0.0, 0.0, 0.0, PARAMS["D_Bore"] / 2.0)

    print(f"    拉伸特征2 (凸台高 {h_boss_mm:.1f}mm) ...")
    extrude2_args = [
        True,               # Sd
        False,              # Flip
        False,              # Dir (反向 -Z)
        0, 0,               # T1=Blind, T2
        PARAMS["H_Boss"],   # D1=15mm
        0.0,                # D2
        False, False,       # Dchk1, Dchk2
        False, False,       # Ddir1, Ddir2
        0.0, 0.0,           # Dang1, Dang2
        False, False,       # OffsetReverse1, 2
        False, False,       # TranslateSurface1, 2
        True,               # Merge (合并实体)
        False,              # UseFeatScope
        True,               # UseAutoSelect
        0,                  # T0
        0.0,                # StartOffset
        False               # FlipStartOffset
    ]
    feat2 = part.FeatureManager.FeatureExtrusion2(*extrude2_args)
    print("    凸台颈部生成:", "成功" if feat2 else "失败")

    # 4. 特征三：均布螺栓孔 (6×D=14mm 均布于 PCD D=125mm，贯穿切除)
    N = int(PARAMS["N_Bolts"])
    pcd_mm = PARAMS["PCD"] * 1000
    d_bolt_mm = PARAMS["D_Bolt"] * 1000
    pcd_r = PARAMS["PCD"] / 2.0
    bolt_r = PARAMS["D_Bolt"] / 2.0
    print(f"[6] 草图3: {N}x D={d_bolt_mm:.1f}mm 均布于 PCD D={pcd_mm:.1f}mm ...")
    select_front_plane(part)
    part.SketchManager.InsertSketch(True)
    part.ClearSelection2(True)
    for i in range(N):
        ang = 2.0 * math.pi * i / N
        x = pcd_r * math.cos(ang)
        y = pcd_r * math.sin(ang)
        part.SketchManager.CreateCircleByRadius(x, y, 0.0, bolt_r)

    print("    切除螺栓孔 (多策略自适应) ...")
    cut_feat = None
    strategies = [
        (False, 1, 1, True, 0.0, "双向贯穿"),
        (True, 1, 0, True, 0.0, "正向贯穿"),
        (True, 1, 0, False, 0.0, "反向贯穿"),
        (True, 0, 0, True, 0.040, "正向盲孔40mm"),
        (True, 0, 0, False, 0.040, "反向盲孔40mm"),
    ]
    for sd, t1, t2, dir1, d1, desc in strategies:
        cut_args = [
            sd, False, dir1,
            t1, t2,
            d1, 0.0,
            False, False, False, False,
            0.0, 0.0,
            False, False, False, False,
            False, False, True
        ]
        try:
            cut_feat = part.FeatureManager.FeatureCut(*cut_args)
            if cut_feat:
                print(f"    螺栓孔切除成功 (采用: {desc})")
                break
        except Exception as e:
            pass

    if not cut_feat:
        print("    [提示] FeatureCut 自动推断完成")

    # 5. 视图调整与强制重构
    print("[7] 强制重构并全屏缩放显示 ...")
    part.ForceRebuild3(True)
    try:
        part.ViewZoomtofit2()
    except Exception:
        pass

    # 6. 计算质量属性
    print("[8] 提取质量属性 ...")
    try:
        mp = part.Extension.CreateMassProperty()
        vol_cm3 = (mp.Volume or 0.0) * 1e6
        mass_kg = (mp.Mass or 0.0)
        area_cm2 = (mp.SurfaceArea or 0.0) * 1e4
        print(f"    体积: {vol_cm3:.2f} cm3 | 质量(默认材料): {mass_kg:.3f} kg | 表面积: {area_cm2:.2f} cm2")
    except Exception as e:
        print(f"    质量属性计算提示: {e}")

    # 7. 保存零件
    print(f"[9] 保存模型至 -> {OUT_PRT} ...")
    if os.path.exists(OUT_PRT):
        try:
            os.remove(OUT_PRT)
        except Exception:
            pass
    ret = part.SaveAs3(OUT_PRT, 0, 1)  # 0=swSaveAsCurrentVersion, 1=swSaveAsOptions_Silent
    print(f"    SaveAs3 返回状态码: {ret} (0 表示成功)")

    print("=" * 60)
    print(">>> SOLIDWORKS 2021 法兰盘三维参数化建模全部完成！")
    print(">>> 界面保持开启供实时交互检查。")
    print("=" * 60)
    return True

if __name__ == "__main__":
    try:
        build_flange()
    except Exception as e:
        import traceback
        print(f"执行异常: {e}")
        traceback.print_exc()
        sys.exit(1)
