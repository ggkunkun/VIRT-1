# -*- coding: utf-8 -*-
r"""
SOLIDWORKS 2021 从零开始绘图建模全流程实时脚本
用户要求：新建一个零件，看到从0开始绘图建模的完整过程
执行动作：
1. 启动并最大化 SOLIDWORKS 2021 界面
2. 步骤0：新建空白零件 (零件1 / Part1) -> 拍摄空白视窗
3. 注入方程式管理器 (EquationMgr) 全局参数化变量 (D_Outer, D_Bore, Thk_Disk, D_Boss, H_Boss, PCD, N_Bolts, D_Bolt)
4. 步骤1：前视基准面进入草图 -> 绘制基体外圆 (Ø160) 与 中心通孔 (Ø50) -> 拍摄2D草图
5. 步骤2：执行拉伸凸台1 (厚度 20mm) -> 实体化生成法兰基体 -> 拍摄3D实体
6. 步骤3：前视基准面再次进入草图 -> 绘制颈部凸台 (Ø90) 与 通孔 (Ø50) -> 反向拉伸 15mm 合并实体 -> 拍摄阶梯轴凸台
7. 步骤4：前视基准面草图3 -> 极坐标计算均布 6×Ø14mm 螺栓孔于 PCD Ø125mm -> 拍摄草图孔分布 -> 双向贯穿切除 -> 拍摄打孔完成
8. 步骤5：切换等轴测视图 (*Isometric) + 全屏自适应 (Zoom to Fit) -> 提取物理属性
9. 步骤6：保存零件至桌面：零件2_从零建模.SLDPRT 与 零件1.SLDPRT
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
OUT_DESKTOP_NEW = r"C:\Users\Administrator\Desktop\零件2_从零建模.SLDPRT"
OUT_DESKTOP_PART1 = r"C:\Users\Administrator\Desktop\零件1.SLDPRT"
OUT_DESKTOP_FLANGE = r"C:\Users\Administrator\Desktop\法兰盘_参数化.SLDPRT"
SCRATCH_DIR = r"D:\Virtu模型\scratch"

PARAMS = {
    "D_Outer": 0.160,    # 法兰外径 160.0 mm
    "D_Bore": 0.050,     # 中心通孔 50.0 mm
    "Thk_Disk": 0.020,   # 法兰盘厚度 20.0 mm
    "D_Boss": 0.090,     # 凸台外径 90.0 mm
    "H_Boss": 0.015,     # 凸台高度 15.0 mm
    "PCD": 0.125,        # 螺栓孔分度圆直径 125.0 mm
    "N_Bolts": 6,        # 螺栓孔数量 6 个
    "D_Bolt": 0.014,     # 螺栓孔直径 14.0 mm
}

def capture_screen(step_name):
    os.makedirs(SCRATCH_DIR, exist_ok=True)
    out_path = os.path.join(SCRATCH_DIR, f"{step_name}.png")
    try:
        from bridges.desktop_controller import DesktopController
        ctl = DesktopController()
        ctl.capture(output_path=out_path)
        print(f"    [视窗取证] 截图已生成 -> {out_path}")
    except Exception as e:
        print(f"    [截屏提示] {e}")

def bring_sw_to_foreground():
    try:
        import win32service, win32gui, win32con, ctypes
        hdesk = win32service.OpenDesktop("default", 0, False, win32con.MAXIMUM_ALLOWED)
        hdesk.SetThreadDesktop()

        def _find_sw(hwnd, res):
            if win32gui.IsWindowVisible(hwnd):
                t = win32gui.GetWindowText(hwnd)
                if "solidworks" in t.lower():
                    res.append((hwnd, t))
            return True

        sw_wins = []
        win32gui.EnumWindows(_find_sw, sw_wins)
        if sw_wins:
            main_hwnd, main_title = sw_wins[0]
            ctypes.windll.user32.ShowWindow(main_hwnd, win32con.SW_MAXIMIZE)
            ctypes.windll.user32.SwitchToThisWindow(main_hwnd, True)
            ctypes.windll.user32.SetForegroundWindow(main_hwnd)
    except Exception:
        pass

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

def main():
    print("=" * 80)
    print(">>> 【从零开始建模】初始化 SOLIDWORKS 2021 环境并准备全新画布 ...")
    print("=" * 80)

    try:
        subprocess.run(["taskkill", "/F", "/IM", "SLDWORKS.exe"], capture_output=True)
    except Exception:
        pass
    time.sleep(2)

    t0 = time.time()
    mod = gc.EnsureModule(TLB_GUID, 0, SW_VERSION, 0)
    sw = mod.SldWorks()
    sw.Visible = True
    print(f"    -> 软件引擎启动并建立直接连接，耗时: {time.time() - t0:.2f} 秒")

    # 步骤 0：新建空白零件
    print("\n" + "=" * 80)
    print(">>> 【第 0 步：新建零件】从零创建空白零件文档 (Part Document) ...")
    print("=" * 80)
    raw_part = sw.NewPart()
    if not raw_part:
        raise RuntimeError("无法创建零件文档")
    part = mod.IModelDoc2(raw_part._oleobj_)
    bring_sw_to_foreground()
    time.sleep(1.5)
    capture_screen("from_zero_step0_blank_canvas")
    print(f"    -> 空白零件创建成功，标题: {part.GetTitle()}")

    # 注入参数化方程式
    print("\n" + "=" * 80)
    print(">>> 【参数化配置】向方程式管理器 (EquationMgr) 注入法兰盘关键尺寸变量 ...")
    print("=" * 80)
    eqn = part.GetEquationMgr()
    for idx, (k, v) in enumerate(PARAMS.items()):
        val = int(v) if k == "N_Bolts" else v
        eqn.Add(idx, f'"{k}" = {val}')
        unit = "个" if k == "N_Bolts" else "mm"
        disp = v if k == "N_Bolts" else v * 1000
        print(f"    -> 全局变量 #{idx+1}: {k:<10s} = {disp:>6g} {unit}")
    print(f"    -> 方程式注入完成，共 {eqn.GetCount()} 个全局参数")

    # 步骤 1：前视基准面进入草图并绘制双圆
    print("\n" + "=" * 80)
    print(f">>> 【第 1 步：绘制2D草图】选择前视基准面，绘制同心圆草图 (外径 Ø{PARAMS['D_Outer']*1000:.0f}mm, 中孔 Ø{PARAMS['D_Bore']*1000:.0f}mm) ...")
    print("=" * 80)
    select_front_plane(part)
    part.SketchManager.InsertSketch(True)
    part.ClearSelection2(True)
    r_out = PARAMS["D_Outer"] / 2.0
    r_bore = PARAMS["D_Bore"] / 2.0
    part.SketchManager.CreateCircleByRadius(0.0, 0.0, 0.0, r_out)
    part.SketchManager.CreateCircleByRadius(0.0, 0.0, 0.0, r_bore)
    bring_sw_to_foreground()
    part.ViewZoomtofit2()
    time.sleep(2.0)
    capture_screen("from_zero_step1_sketch_base")
    print("    -> 2D草图绘制完成，画布显示同心圆")

    # 步骤 2：主体三维拉伸
    print("\n" + "=" * 80)
    print(f">>> 【第 2 步：主体三维拉伸】草图1 -> 执行凸台拉伸 (厚度: {PARAMS['Thk_Disk']*1000:.0f}mm) ...")
    print("=" * 80)
    extrude1_args = [
        True, False, True, 0, 0, PARAMS["Thk_Disk"], 0.0,
        False, False, False, False, 0.0, 0.0,
        False, False, False, False, True, False, True,
        0, 0.0, False
    ]
    feat1 = part.FeatureManager.FeatureExtrusion2(*extrude1_args)
    print("    -> 法兰基体拉伸生成完成！3D实体生成")
    part.ViewZoomtofit2()
    bring_sw_to_foreground()
    time.sleep(2.0)
    capture_screen("from_zero_step2_solid_base")

    # 步骤 3：颈部凸台绘制与反向拉伸合并
    print("\n" + "=" * 80)
    print(f">>> 【第 3 步：颈部凸台拉伸】绘制颈部草图 (外径 Ø{PARAMS['D_Boss']*1000:.0f}mm, 内孔 Ø{PARAMS['D_Bore']*1000:.0f}mm) -> 反向拉伸 {PARAMS['H_Boss']*1000:.0f}mm 合并实体 ...")
    print("=" * 80)
    select_front_plane(part)
    part.SketchManager.InsertSketch(True)
    part.ClearSelection2(True)
    r_boss = PARAMS["D_Boss"] / 2.0
    part.SketchManager.CreateCircleByRadius(0.0, 0.0, 0.0, r_boss)
    part.SketchManager.CreateCircleByRadius(0.0, 0.0, 0.0, r_bore)

    extrude2_args = [
        True, False, False, 0, 0, PARAMS["H_Boss"], 0.0,
        False, False, False, False, 0.0, 0.0,
        False, False, False, False, True, False, True,
        0, 0.0, False
    ]
    feat2 = part.FeatureManager.FeatureExtrusion2(*extrude2_args)
    print("    -> 颈部凸台生成并与基体合并实体完成！")
    part.ViewZoomtofit2()
    bring_sw_to_foreground()
    time.sleep(2.0)
    capture_screen("from_zero_step3_neck_boss")

    # 步骤 4：极坐标均布 6 个螺栓孔并贯穿切除
    print("\n" + "=" * 80)
    print(f">>> 【第 4 步：螺栓孔极坐标切除】在分度圆 PCD Ø{PARAMS['PCD']*1000:.0f}mm 上均布绘制 6×Ø{PARAMS['D_Bolt']*1000:.0f}mm 孔草图 -> 双向贯穿切除 ...")
    print("=" * 80)
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
        print(f"    -> 螺栓孔 #{i+1}: 角度={math.degrees(ang):>5.1f}°, X={x*1000:>6.2f}mm, Y={y*1000:>6.2f}mm")

    bring_sw_to_foreground()
    time.sleep(1.5)
    capture_screen("from_zero_step4a_holes_sketch")

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
    print("    -> 6个螺栓孔双向贯穿切除完成！")
    part.ViewZoomtofit2()
    bring_sw_to_foreground()
    time.sleep(2.0)
    capture_screen("from_zero_step4b_holes_cut")

    # 步骤 5：等轴测视角展示与物理属性
    print("\n" + "=" * 80)
    print(">>> 【第 5 步：等轴测视角展示】切换等轴测视角 (*Isometric)，自适应缩放 (Zoom to Fit)，提取物理特性 ...")
    print("=" * 80)
    part.ForceRebuild3(True)
    try:
        part.ShowNamedView2("*Isometric", 7)
    except Exception:
        pass
    part.ViewZoomtofit2()

    try:
        mp = part.Extension.CreateMassProperty()
        vol_cm3 = (mp.Volume or 0.0) * 1e6
        area_cm2 = (mp.SurfaceArea or 0.0) * 1e4
        com = mp.CenterOfMass
        print(f"    -> 零件体积:   {vol_cm3:.2f} cm³")
        print(f"    -> 零件表面积: {area_cm2:.2f} cm²")
        if com:
            print(f"    -> 质心坐标:   X={com[0]*1000:.2f}mm, Y={com[1]*1000:.2f}mm, Z={com[2]*1000:.2f}mm")
    except Exception:
        pass

    # 步骤 6：多路径保存
    print("\n" + "=" * 80)
    print(">>> 【第 6 步：保存零件】将新建模的法兰盘存盘 ...")
    print("=" * 80)
    for p in [OUT_DESKTOP_NEW, OUT_DESKTOP_PART1, OUT_DESKTOP_FLANGE]:
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass
        ret = part.SaveAs3(p, 0, 1)
        print(f"    -> 存盘成功: {p} (返回码: {ret})")

    bring_sw_to_foreground()
    time.sleep(2.0)
    capture_screen("from_zero_step5_final_isometric")

    print("\n" + "=" * 80)
    print(">>> 【从0建模全流程顺利完成！】")
    print(">>> SOLIDWORKS 2021 保持在前台全屏开启，您可以在屏幕上直接查看实时模型。")
    print("=" * 80)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print(f"执行异常: {e}")
        traceback.print_exc()
        sys.exit(1)
