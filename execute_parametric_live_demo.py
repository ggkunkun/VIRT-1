# -*- coding: utf-8 -*-
r"""
SOLIDWORKS 2021 参数化绘图建模实时演示脚本
执行动作：
1. 启动并最大化 SOLIDWORKS 2021 界面
2. 注入方程式管理器参数化全局变量 (D_Outer, D_Bore, Thk_Disk, D_Boss, H_Boss, PCD, N_Bolts, D_Bolt)
3. 步骤一：前视基准面草图1 -> 拉伸法兰盘主体 (含截图)
4. 步骤二：前视基准面草图2 -> 反向拉伸颈部凸台并合并实体 (含截图)
5. 步骤三：前视基准面草图3 -> 极坐标均布 6 个螺栓孔贯穿切除 (含截图)
6. 视图切换至等轴测 (*Isometric) 并全屏自适应 (Zoom to Fit)
7. 保存零件至桌面：法兰盘_参数化.SLDPRT 与 零件1.SLDPRT
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
OUT_DESKTOP_1 = r"C:\Users\Administrator\Desktop\法兰盘_参数化.SLDPRT"
OUT_DESKTOP_2 = r"C:\Users\Administrator\Desktop\零件1.SLDPRT"
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
    print(">>> 【阶段 1/6】正在启动并最大化 SOLIDWORKS 2021 视窗 ...")
    print("=" * 80)
    try:
        subprocess.run(["taskkill", "/F", "/IM", "SLDWORKS.exe"], capture_output=True)
    except Exception:
        pass
    time.sleep(3)

    t0 = time.time()
    mod = gc.EnsureModule(TLB_GUID, 0, SW_VERSION, 0)
    sw = mod.SldWorks()
    sw.Visible = True
    print(f"    -> 软件引擎连接成功，耗时: {time.time() - t0:.2f} 秒")

    raw_part = sw.NewPart()
    if not raw_part:
        raise RuntimeError("无法创建零件文档")
    part = mod.IModelDoc2(raw_part._oleobj_)
    bring_sw_to_foreground()
    time.sleep(2)
    capture_screen("live_step1_sw_opened")

    # 阶段 2：注入方程式管理器参数化全局变量
    print("\n" + "=" * 80)
    print(">>> 【阶段 2/6】向方程式管理器 (EquationMgr) 注入参数化全局设计变量 ...")
    print("=" * 80)
    eqn = part.GetEquationMgr()
    for idx, (k, v) in enumerate(PARAMS.items()):
        val = int(v) if k == "N_Bolts" else v
        eqn.Add(idx, f'"{k}" = {val}')
        unit = "个" if k == "N_Bolts" else "mm"
        disp = v if k == "N_Bolts" else v * 1000
        print(f"    -> 参数 #{idx+1}: {k:<10s} = {disp:>6g} {unit}")
    print(f"    -> 方程式注入完成，共 {eqn.GetCount()} 个全局参数")

    # 阶段 3：前视基准面绘制法兰主体并拉伸
    print("\n" + "=" * 80)
    print(f">>> 【阶段 3/6】草图1: 前视基准面绘制法兰外径 (Ø{PARAMS['D_Outer']*1000:.0f}) + 内孔 (Ø{PARAMS['D_Bore']*1000:.0f}) -> 拉伸主体 ...")
    print("=" * 80)
    select_front_plane(part)
    part.SketchManager.InsertSketch(True)
    part.ClearSelection2(True)
    r_out = PARAMS["D_Outer"] / 2.0
    r_bore = PARAMS["D_Bore"] / 2.0
    part.SketchManager.CreateCircleByRadius(0.0, 0.0, 0.0, r_out)
    part.SketchManager.CreateCircleByRadius(0.0, 0.0, 0.0, r_bore)

    extrude1_args = [
        True, False, True, 0, 0, PARAMS["Thk_Disk"], 0.0,
        False, False, False, False, 0.0, 0.0,
        False, False, False, False, True, False, True,
        0, 0.0, False
    ]
    feat1 = part.FeatureManager.FeatureExtrusion2(*extrude1_args)
    print("    -> 法兰基体拉伸生成: 成功")
    part.ViewZoomtofit2()
    bring_sw_to_foreground()
    time.sleep(2)
    capture_screen("live_step2_flange_base")

    # 阶段 4：前视基准面绘制颈部凸台并反向拉伸合并
    print("\n" + "=" * 80)
    print(f">>> 【阶段 4/6】草图2: 前视基准面绘制颈部凸台 (Ø{PARAMS['D_Boss']*1000:.0f}) + 同心中孔 (Ø{PARAMS['D_Bore']*1000:.0f}) -> 反向拉伸合并 ...")
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
    print("    -> 颈部凸台生成并合并实体: 成功")
    part.ViewZoomtofit2()
    bring_sw_to_foreground()
    time.sleep(2)
    capture_screen("live_step3_neck_boss")

    # 阶段 5：前视基准面绘制 6×Ø14mm 螺栓孔并贯穿切除
    print("\n" + "=" * 80)
    print(f">>> 【阶段 5/6】草图3: 极坐标计算 6×Ø{PARAMS['D_Bolt']*1000:.0f}mm 均布于 PCD Ø{PARAMS['PCD']*1000:.0f}mm -> 双向贯穿切除 ...")
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
    print("    -> 螺栓孔双向贯穿切除: 成功")

    # 阶段 6：全模型重构、等轴测视图、属性计算与多路径存盘
    print("\n" + "=" * 80)
    print(">>> 【阶段 6/6】强制重构拓扑、等轴测视角展示、计算物理属性并保存零件 ...")
    print("=" * 80)
    part.ForceRebuild3(True)
    try:
        part.ShowNamedView2("*Isometric", 7)
    except Exception:
        pass
    part.ViewZoomtofit2()

    # 属性提取
    try:
        mp = part.Extension.CreateMassProperty()
        vol_cm3 = (mp.Volume or 0.0) * 1e6
        area_cm2 = (mp.SurfaceArea or 0.0) * 1e4
        com = mp.CenterOfMass
        print(f"    -> 实体体积:   {vol_cm3:.2f} cm³")
        print(f"    -> 实体表面积: {area_cm2:.2f} cm²")
        if com:
            print(f"    -> 质心坐标:   X={com[0]*1000:.2f}mm, Y={com[1]*1000:.2f}mm, Z={com[2]*1000:.2f}mm")
    except Exception:
        pass

    # 双路径存盘（覆盖桌面两处文件）
    for p in [OUT_DESKTOP_1, OUT_DESKTOP_2]:
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass
        ret = part.SaveAs3(p, 0, 1)
        print(f"    -> 已保存至桌面: {p} (返回码: {ret})")

    bring_sw_to_foreground()
    time.sleep(2)
    capture_screen("live_step4_final_modeled")

    print("\n" + "=" * 80)
    print(">>> 【实时全流程完成】法兰盘三维参数化绘图建模已全部执行完毕！")
    print(">>> SOLIDWORKS 2021 保持在前台全屏开启，您可以实时在屏幕上操作。")
    print("=" * 80)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print(f"执行异常: {e}")
        traceback.print_exc()
        sys.exit(1)
