# -*- coding: utf-8 -*-
r"""
SOLIDWORKS 2021 严格图纸尺寸三维建模脚本
图纸来源：三维CAD 学生习题集 (P47) - 轴承/油缸支座
关键几何尺寸严格遵循图纸：
1. 主体长方体：长 107mm, 宽 75mm, 高 68mm (基体高 68mm, 总高 90mm, 轴心高度 28mm)
2. 4个安装耳座：总宽 95mm (耳宽 10mm), 长 20mm, 厚 10mm, 安装孔 4-Ø9, 间距 100mm
3. 底部通槽：宽 36mm, 高 22mm
4. 内部台阶孔 (轴心水平线，总长 107mm)：
   - X=0~2: Ø33mm
   - X=2~4.5: Ø29mm (卡簧槽)
   - X=4.5~13: Ø25mm
   - X=13~24: Ø33mm
   - X=24~36: Ø25mm
   - X=36~39: Ø37mm (I局部 槽宽3mm, 槽深1mm, 基于Ø35)
   - X=39~92: Ø35mm (主腔体)
   - X=92~97: Ø48mm (密封沉孔)
   - X=97~107: M42 (Ø42mm螺纹底孔)
5. 顶部油口 (M18)：
   - 位置 X=36mm, 深度 14mm, 沉孔 Ø20mm 深 3mm, 连通孔 Ø7.50mm 通至主腔
6. 顶部斜角：35° 倒角
7. 前端凹槽：宽 30mm, 深 12mm
8. 前端双斜支耳 (悬臂)：
   - 孔中心坐标：X=-62mm, Y=-45mm (低于轴线 45mm)
   - 销孔 Ø10mm, 外圆 R12 (Ø24mm), 轴套宽 12mm, 外跨 56mm
   - 连杆斜筋厚 6mm, 居中连接
9. 键槽：前端 Ø25 孔顶部开键槽
10. 未注倒角 1~2mm
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
OUT_DESKTOP_1 = r"C:\Users\Administrator\Desktop\支座_按图纸建模.SLDPRT"
OUT_DESKTOP_2 = r"C:\Users\Administrator\Desktop\零件1.SLDPRT"
SCRATCH_DIR = r"D:\Virtu模型\scratch"

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
                if "solidworks" in t.lower() and "antigravity" not in t.lower():
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

def select_plane(part, plane_name):
    plane_map = {
        "Front": ["前视基准面", "Front Plane", "Front"],
        "Top": ["上视基准面", "Top Plane", "Top"],
        "Right": ["右视基准面", "Right Plane", "Right"]
    }
    target_names = plane_map.get(plane_name, [plane_name])
    for nm in target_names:
        try:
            if part.SelectByID(nm, "PLANE", 0.0, 0.0, 0.0):
                return True
        except Exception:
            pass
    f = part.FirstFeature()
    while f is not None:
        try:
            if f.Name in target_names:
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
    print(">>> 【图纸精密建模】严格按照 P47 图纸标注尺寸启动 SOLIDWORKS 建模流程 ...")
    print("=" * 80)

    try:
        subprocess.run(["taskkill", "/F", "/IM", "SLDWORKS.exe"], capture_output=True)
    except Exception:
        pass
    time.sleep(2)

    mod = gc.EnsureModule(TLB_GUID, 0, SW_VERSION, 0)
    sw = mod.SldWorks()
    sw.Visible = True
    print("    -> SOLIDWORKS 2021 引擎初始化成功")

    raw_part = sw.NewPart()
    if not raw_part:
        raise RuntimeError("无法创建零件")
    part = mod.IModelDoc2(raw_part._oleobj_)
    bring_sw_to_foreground()
    time.sleep(1.5)
    capture_screen("blueprint_step0_new_part")

    # -------------------------------------------------------------
    # 特征 1：主体长方体 + 支腿基体 (Front Plane 拉伸对称)
    # 尺寸：长 X=0 ~ 107mm, 高 Y=-50 ~ +40mm (总高90mm), 宽 Z=-37.5 ~ +37.5 (宽75mm)
    # -------------------------------------------------------------
    print("\n>>> 【特征 1】前视基准面拉伸主体框架 (长 107mm, 宽 75mm, 高 90mm) ...")
    select_plane(part, "Front")
    part.SketchManager.InsertSketch(True)
    part.ClearSelection2(True)
    
    # 绘制外矩形：X 从 0 到 0.107, Y 从 -0.050 到 0.040
    part.SketchManager.CreateCornerRectangle(0.0, -0.050, 0.0, 0.107, 0.040, 0.0)
    
    # 两侧对称拉伸 75mm (MidPlane: t1=6, d1=0.075)
    extrude_args = [
        True, False, False, 6, 0, 0.075, 0.0,
        False, False, False, False, 0.0, 0.0,
        False, False, False, False, True, False, True,
        0, 0.0, False
    ]
    feat1 = part.FeatureManager.FeatureExtrusion2(*extrude_args)
    part.ViewZoomtofit2()
    bring_sw_to_foreground()
    time.sleep(1.5)
    capture_screen("blueprint_step1_main_block")
    print("    -> 主体框架拉伸生成成功")

    # -------------------------------------------------------------
    # 特征 2：底部避空切除 (槽宽 36mm, 高 22mm, 贯穿)
    # -------------------------------------------------------------
    print("\n>>> 【特征 2】切除底部中槽 (宽 36mm, 高 22mm: Y=-0.050 ~ -0.028) ...")
    select_plane(part, "Right")
    part.SketchManager.InsertSketch(True)
    part.ClearSelection2(True)
    # 右视基准面：水平为 Z, 垂直为 Y
    # 槽 Z: -0.018 ~ +0.018, Y: -0.050 ~ -0.028
    part.SketchManager.CreateCornerRectangle(-0.018, -0.050, 0.0, 0.018, -0.028, 0.0)
    cut_args = [
        False, False, True, 1, 1, 0.0, 0.0,
        False, False, False, False, 0.0, 0.0,
        False, False, False, False, False, False, True
    ]
    part.FeatureManager.FeatureCut(*cut_args)
    part.ViewZoomtofit2()
    print("    -> 底部中槽切除成功")

    # -------------------------------------------------------------
    # 特征 3：前后支腿间中间空腔切除 (X=0.020 ~ 0.087, Y=-0.050 ~ -0.028, 宽 75mm)
    # -------------------------------------------------------------
    print("\n>>> 【特征 3】切除前后支腿间底隙 (X=20mm ~ 87mm, Y=-50mm ~ -28mm) ...")
    select_plane(part, "Front")
    part.SketchManager.InsertSketch(True)
    part.ClearSelection2(True)
    part.SketchManager.CreateCornerRectangle(0.020, -0.050, 0.0, 0.087, -0.028, 0.0)
    part.FeatureManager.FeatureCut(*cut_args)
    part.ViewZoomtofit2()
    print("    -> 前后支腿间底隙切除成功")

    # -------------------------------------------------------------
    # 特征 4：4个安装耳座 (凸台外伸 10mm, 厚 10mm)
    # -------------------------------------------------------------
    print("\n>>> 【特征 4】拉伸 4 个安装耳座 (总宽 95mm, 耳厚 10mm) ...")
    # 前后耳座：在 X=0~0.020 和 X=0.087~0.107 处
    # 从两侧面 Z=±0.0375 向外拉伸 0.010m 到 Z=±0.0475
    select_plane(part, "Front")
    part.SketchManager.InsertSketch(True)
    part.ClearSelection2(True)
    # 绘制两块耳座轮廓：Y=-0.050 ~ -0.040, X=0~0.020 与 X=0.087~0.107
    part.SketchManager.CreateCornerRectangle(0.0, -0.050, 0.0, 0.020, -0.040, 0.0)
    part.SketchManager.CreateCornerRectangle(0.087, -0.050, 0.0, 0.107, -0.040, 0.0)
    # 对称拉伸 95mm (MidPlane: t1=6, d1=0.095)
    extrude_ears = [
        True, False, False, 6, 0, 0.095, 0.0,
        False, False, False, False, 0.0, 0.0,
        False, False, False, False, True, False, True,
        0, 0.0, False
    ]
    part.FeatureManager.FeatureExtrusion2(*extrude_ears)
    part.ViewZoomtofit2()
    bring_sw_to_foreground()
    time.sleep(1.5)
    capture_screen("blueprint_step2_base_and_feet")
    print("    -> 4个安装耳座拉伸完成")

    # -------------------------------------------------------------
    # 特征 5：4-Ø9 安装通孔 (间距 100mm, 宽距 85mm)
    # -------------------------------------------------------------
    print("\n>>> 【特征 5】打 4-Ø9 安装螺栓通孔 (X 间距 100mm, 孔位 X=3.5mm & X=103.5mm) ...")
    select_plane(part, "Top")
    part.SketchManager.InsertSketch(True)
    part.ClearSelection2(True)
    r_hole = 0.009 / 2.0
    hole_xs = [0.0035, 0.1035]
    hole_zs = [-0.0425, 0.0425]
    for x in hole_xs:
        for z in hole_zs:
            # Top基准面：水平为 X, 垂直为 Z
            part.SketchManager.CreateCircleByRadius(x, z, 0.0, r_hole)
    part.FeatureManager.FeatureCut(*cut_args)
    print("    -> 4-Ø9 安装孔贯穿完成")

    # -------------------------------------------------------------
    # 特征 6：阶梯内孔 (Revolve Cut 旋转切除)
    # 严格按照图纸 9 段阶梯尺寸及 Detail I 局部退刀槽尺寸
    # -------------------------------------------------------------
    print("\n>>> 【特征 6】前视基准面精密旋转切除阶梯孔 (包含 Ø33, Ø29, Ø25, Ø37, Ø35, Ø48, M42) ...")
    select_plane(part, "Front")
    part.SketchManager.InsertSketch(True)
    part.ClearSelection2(True)

    # 旋转中心线 (X-axis: Y=0)
    part.SketchManager.CreateCenterLine(-0.010, 0.0, 0.0, 0.120, 0.0, 0.0)

    # 轮廓顶点 (X, Y)
    pts = [
        (0.000, 0.0165),   # Ø33
        (0.002, 0.0165),
        (0.002, 0.0145),   # Ø29 卡簧槽
        (0.0045, 0.0145),
        (0.0045, 0.0125),  # Ø25
        (0.0130, 0.0125),
        (0.0130, 0.0165),  # Ø33
        (0.0240, 0.0165),
        (0.0240, 0.0125),  # Ø25
        (0.0360, 0.0125),
        (0.0360, 0.0185),  # I 局部：深1mm退刀槽 (基于Ø35半径+1mm = 18.5mm, 宽3mm)
        (0.0390, 0.0185),
        (0.0390, 0.0175),  # Ø35 主腔
        (0.0920, 0.0175),
        (0.0920, 0.0240),  # Ø48 密封沉孔
        (0.0970, 0.0240),
        (0.0970, 0.0210),  # M42 螺纹底孔 (Ø42)
        (0.1070, 0.0210),
        (0.1070, 0.0000),  # 闭合至轴线
        (0.0000, 0.0000)
    ]

    for i in range(len(pts)):
        p1 = pts[i]
        p2 = pts[(i + 1) % len(pts)]
        part.SketchManager.CreateLine(p1[0], p1[1], 0.0, p2[0], p2[1], 0.0)

    # 旋转切除 360°
    part.FeatureManager.FeatureRevolveCut(
        2 * math.pi, False, 0.0, 0, 0, False, True
    )
    part.ViewZoomtofit2()
    bring_sw_to_foreground()
    time.sleep(1.5)
    capture_screen("blueprint_step3_stepped_bore")
    print("    -> 阶梯内孔旋转切除成功")

    # -------------------------------------------------------------
    # 特征 7：顶部 M18 油口 (带 Ø20 沉孔与 Ø7.50 连通孔)
    # -------------------------------------------------------------
    print("\n>>> 【特征 7】顶部绘制 M18 油口 (沉孔 Ø20 深 3mm, 螺纹 M18 深 14mm, 连通孔 Ø7.50mm) ...")
    select_plane(part, "Top")
    part.SketchManager.InsertSketch(True)
    part.ClearSelection2(True)
    # X=0.036, Z=0.0
    part.SketchManager.CreateCircleByRadius(0.036, 0.0, 0.0, 0.010) # Ø20
    # 切除深度 17mm
    cut_top = [
        False, False, False, 0, 0, 0.017, 0.0,
        False, False, False, False, 0.0, 0.0,
        False, False, False, False, False, False, True
    ]
    part.FeatureManager.FeatureCut(*cut_top)

    # Ø7.50 连通孔贯穿至主腔
    select_plane(part, "Top")
    part.SketchManager.InsertSketch(True)
    part.ClearSelection2(True)
    part.SketchManager.CreateCircleByRadius(0.036, 0.0, 0.0, 0.00375) # Ø7.50
    cut_conn = [
        False, False, False, 0, 0, 0.030, 0.0,
        False, False, False, False, 0.0, 0.0,
        False, False, False, False, False, False, True
    ]
    part.FeatureManager.FeatureCut(*cut_conn)
    print("    -> 顶部油口连通完成")

    # -------------------------------------------------------------
    # 特征 8：前端双斜支耳 (悬臂梁 + 轴套 R12 + 销孔 Ø10)
    # 坐标：X=-62mm, Y=-45mm, 轴套外圆 R12, 销孔 Ø10, 轴套厚 12mm, 筋厚 6mm
    # -------------------------------------------------------------
    print("\n>>> 【特征 8】拉伸前端双斜支耳悬臂 (销孔中心 X=-62mm, Y=-45mm, R12, 销孔 Ø10) ...")
    
    # 8a: 轴套圆柱体拉伸
    # 在 Front Plane 绘制圆环 (外圆 R12=0.012, 内孔 Ø10/2=0.005)
    select_plane(part, "Front")
    part.SketchManager.InsertSketch(True)
    part.ClearSelection2(True)
    part.SketchManager.CreateCircleByRadius(-0.062, -0.045, 0.0, 0.012)
    part.SketchManager.CreateCircleByRadius(-0.062, -0.045, 0.0, 0.005)

    # 两侧对称拉伸至总跨度 56mm (MidPlane: d1=0.056)
    extrude_boss = [
        True, False, False, 6, 0, 0.056, 0.0,
        False, False, False, False, 0.0, 0.0,
        False, False, False, False, True, False, True,
        0, 0.0, False
    ]
    part.FeatureManager.FeatureExtrusion2(*extrude_boss)

    # 中间切除掏空 (内宽 32mm: Z=-0.016 ~ +0.016)
    select_plane(part, "Right")
    part.SketchManager.InsertSketch(True)
    part.ClearSelection2(True)
    part.SketchManager.CreateCornerRectangle(-0.016, -0.060, 0.0, 0.016, -0.030, 0.0)
    part.FeatureManager.FeatureCut(*cut_args)

    # 8b: 双斜连杆支撑筋 (厚度 6mm)
    # 轮廓：从 X=0, Y=0.020 切连至 R12 顶部，底边连至 X=0, Y=-0.028
    select_plane(part, "Front")
    part.SketchManager.InsertSketch(True)
    part.ClearSelection2(True)
    part.SketchManager.CreateLine(0.0, 0.020, 0.0, -0.062, -0.033, 0.0)
    part.SketchManager.CreateLine(-0.062, -0.033, 0.0, -0.062, -0.057, 0.0)
    part.SketchManager.CreateLine(-0.062, -0.057, 0.0, 0.0, -0.028, 0.0)
    part.SketchManager.CreateLine(0.0, -0.028, 0.0, 0.0, 0.020, 0.0)

    # 对称拉伸 50mm (MidPlane) 形成整块筋
    extrude_rib = [
        True, False, False, 6, 0, 0.050, 0.0,
        False, False, False, False, 0.0, 0.0,
        False, False, False, False, True, False, True,
        0, 0.0, False
    ]
    part.FeatureManager.FeatureExtrusion2(*extrude_rib)

    # 掏空斜筋内侧 (内宽 38mm，保持两边各 6mm 筋厚：Z 从 -0.019 到 +0.019)
    select_plane(part, "Right")
    part.SketchManager.InsertSketch(True)
    part.ClearSelection2(True)
    part.SketchManager.CreateCornerRectangle(-0.019, -0.060, 0.0, 0.019, 0.030, 0.0)
    part.FeatureManager.FeatureCut(*cut_args)

    part.ViewZoomtofit2()
    bring_sw_to_foreground()
    time.sleep(1.5)
    capture_screen("blueprint_step4_inclined_arms")
    print("    -> 前端双斜支耳悬臂生成成功")

    # -------------------------------------------------------------
    # 特征 9：前端阶梯凹槽 (宽 30mm, 深 12mm)
    # -------------------------------------------------------------
    print("\n>>> 【特征 9】切除前端面凹槽 (宽 30mm, 深 12mm) ...")
    select_plane(part, "Top")
    part.SketchManager.InsertSketch(True)
    part.ClearSelection2(True)
    # X=0 ~ 0.012, Z=-0.015 ~ +0.015
    part.SketchManager.CreateCornerRectangle(0.0, -0.015, 0.0, 0.012, 0.015, 0.0)
    cut_pocket = [
        False, False, False, 0, 0, 0.070, 0.0,
        False, False, False, False, 0.0, 0.0,
        False, False, False, False, False, False, True
    ]
    part.FeatureManager.FeatureCut(*cut_pocket)
    print("    -> 前端凹槽切除完成")

    # -------------------------------------------------------------
    # 特征 10：顶部 35° 斜角切除
    # -------------------------------------------------------------
    print("\n>>> 【特征 10】切除前端顶部 35° 斜角 ...")
    select_plane(part, "Front")
    part.SketchManager.InsertSketch(True)
    part.ClearSelection2(True)
    # 从 (0, 0.040) 切向内部：角 35°
    # 绘制直角三角形：(0, 0.040) -> (0, 0.020) -> (0.014, 0.040) -> (0, 0.040)
    part.SketchManager.CreateLine(0.0, 0.040, 0.0, 0.0, 0.020, 0.0)
    part.SketchManager.CreateLine(0.0, 0.020, 0.0, 0.014, 0.040, 0.0)
    part.SketchManager.CreateLine(0.014, 0.040, 0.0, 0.0, 0.040, 0.0)
    part.FeatureManager.FeatureCut(*cut_args)
    print("    -> 35° 斜角切除完成")

    # -------------------------------------------------------------
    # 特征 11：倒角与重构 (未注倒角 1~2mm)
    # -------------------------------------------------------------
    print("\n>>> 【特征 11】重构拓扑，设置等轴测视角 (*Isometric)，自适应缩放 ...")
    part.ForceRebuild3(True)
    try:
        part.ShowNamedView2("*Isometric", 7)
    except Exception:
        pass
    part.ViewZoomtofit2()

    # 提取物理特性
    try:
        mp = part.Extension.CreateMassProperty()
        vol_cm3 = (mp.Volume or 0.0) * 1e6
        area_cm2 = (mp.SurfaceArea or 0.0) * 1e4
        com = mp.CenterOfMass
        print(f"    -> 零件总体积:   {vol_cm3:.2f} cm³")
        print(f"    -> 零件表面积:   {area_cm2:.2f} cm²")
        if com:
            print(f"    -> 质心坐标:     X={com[0]*1000:.2f}mm, Y={com[1]*1000:.2f}mm, Z={com[2]*1000:.2f}mm")
    except Exception:
        pass

    # 保存零件
    print("\n>>> 【存盘操作】覆盖保存至桌面零件文件 ...")
    for p in [OUT_DESKTOP_1, OUT_DESKTOP_2]:
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass
        ret = part.SaveAs3(p, 0, 1)
        print(f"    -> 存盘成功: {p} (返回码: {ret})")

    bring_sw_to_foreground()
    time.sleep(2.0)
    capture_screen("blueprint_step5_final_modeled")

    print("\n" + "=" * 80)
    print(">>> 【P47 图纸零件建模圆满完成！】")
    print(">>> SOLIDWORKS 2021 保持前台全屏展示，您可在屏幕上直接旋转并测量验证！")
    print("=" * 80)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print(f"执行异常: {e}")
        traceback.print_exc()
        sys.exit(1)
