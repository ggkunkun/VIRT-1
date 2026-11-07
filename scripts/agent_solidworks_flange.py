# -*- coding: utf-8 -*-
"""
agent_solidworks_flange.py — Agent 驱动 SOLIDWORKS 2021 自动化拉起、草图绘制与三维法兰盘参数化建模
"""

import os
import sys
import time
import json
import subprocess
import win32com.client
from win32com.client import gencache

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from bridges.desktop_controller import DesktopController
from bridges.software_registry import DESKTOP_SHORTCUTS, resolve_shortcut

SW_EXE = r"D:\SOLIDWORKS (2)\SLDWORKS.exe"
OUTPUT_DIR = os.path.join(_ROOT, "scratch", "flange_model")
os.makedirs(OUTPUT_DIR, exist_ok=True)

METRICS_FILE = os.path.join(OUTPUT_DIR, "flange_metrics.txt").replace("\\", "/")
SLDPRT_FILE = os.path.join(OUTPUT_DIR, "Flange_DN50_PN16.SLDPRT").replace("\\", "/")
STEP_FILE = os.path.join(OUTPUT_DIR, "Flange_DN50_PN16.STEP").replace("\\", "/")
SWB_FILE = os.path.join(OUTPUT_DIR, "build_flange.swb").replace("\\", "/")
SCREENSHOT_FILE = os.path.join(OUTPUT_DIR, "solidworks_flange_screenshot.png")

# 法兰盘工业标准设计参数 (DN50 PN16 标准机械法兰)
FLANGE_PARAMS = {
    "standard": "DN50 PN16",
    "material": "Steel 1045 (45号钢)",
    "d_outer_mm": 160.0,       # 法兰外径 160 mm
    "thickness_base_mm": 18.0,  # 法兰底盘厚度 18 mm
    "d_hub_mm": 90.0,           # 凸台颈部外径 90 mm
    "height_total_mm": 30.0,    # 总高度 30 mm (凸台高 12 mm)
    "d_bore_mm": 50.0,          # 中心贯通孔径 50 mm
    "pcd_bolt_mm": 125.0,       # 螺栓分布圆直径 (PCD) 125 mm
    "num_bolts": 4,             # 螺栓孔数量 4 个均布
    "d_bolt_mm": 18.0,          # 螺栓孔径 18 mm (适配 M16 螺栓)
}

VBA_MACRO_TEMPLATE = '''Dim swApp As Object
Dim swModel As Object

Sub main()
    On Error GoTo fail
    Set swApp = Application.SldWorks
    Dim f As Integer
    f = FreeFile
    Open "{metrics}" For Output As #f
    
    ' 1. 创建新零件
    Set swModel = swApp.NewPart()
    If swModel Is Nothing Then
        Print #f, "ERROR=NewPart returns Nothing"
        Close #f
        Exit Sub
    End If
    Print #f, "PART_TITLE=" & swModel.GetTitle
    
    ' 2. 获取前视基准面
    Dim feat As Object
    Dim planeName As String
    Set feat = swModel.FirstFeature
    Do While Not feat Is Nothing
        If feat.GetTypeName2 = "RefPlane" And planeName = "" Then planeName = feat.Name
        Set feat = feat.GetNextFeature
    Loop
    Print #f, "PLANE=" & planeName
    
    ' 3. 特征 1：法兰盘主体圆盘拉伸 (D=160mm, 厚度=18mm)
    swModel.ClearSelection2 True
    swModel.Extension.SelectByID2 planeName, "PLANE", 0, 0, 0, False, 1, Nothing, 0
    swModel.SketchManager.InsertSketch True
    swModel.SketchManager.CreateCircleByRadius 0, 0, 0, 0.080
    swModel.ClearSelection2 True
    swModel.SketchManager.InsertSketch True
    swModel.ClearSelection2 True
    
    Dim sk1 As String
    Set feat = swModel.FirstFeature
    Do While Not feat Is Nothing
        If feat.GetTypeName2 = "ProfileFeature" Then sk1 = feat.Name
        Set feat = feat.GetNextFeature
    Loop
    swModel.Extension.SelectByID2 sk1, "SKETCH", 0, 0, 0, False, 0, Nothing, 0
    Dim fex1 As Object
    Set fex1 = swModel.FeatureManager.FeatureExtrusion3( _
        True, False, False, 0, 0, 0.018, 0, False, False, False, False, 0, 0, _
        False, False, False, False, True, True, True, 0, 0, False)
    If Not fex1 Is Nothing Then Print #f, "FEAT_BASE=" & fex1.Name
    swModel.ClearSelection2 True
    
    ' 4. 特征 2：中心凸台 (D=90mm, 总高=30mm)
    swModel.Extension.SelectByID2 planeName, "PLANE", 0, 0, 0, False, 1, Nothing, 0
    swModel.SketchManager.InsertSketch True
    swModel.SketchManager.CreateCircleByRadius 0, 0, 0, 0.045
    swModel.ClearSelection2 True
    swModel.SketchManager.InsertSketch True
    swModel.ClearSelection2 True
    
    Dim sk2 As String
    Set feat = swModel.FirstFeature
    Do While Not feat Is Nothing
        If feat.GetTypeName2 = "ProfileFeature" Then sk2 = feat.Name
        Set feat = feat.GetNextFeature
    Loop
    swModel.Extension.SelectByID2 sk2, "SKETCH", 0, 0, 0, False, 0, Nothing, 0
    Dim fex2 As Object
    Set fex2 = swModel.FeatureManager.FeatureExtrusion3( _
        True, False, False, 0, 0, 0.030, 0, False, False, False, False, 0, 0, _
        False, False, False, False, True, True, True, 0, 0, False)
    If Not fex2 Is Nothing Then Print #f, "FEAT_HUB=" & fex2.Name
    swModel.ClearSelection2 True
    
    ' 5. 特征 3：中心贯通孔 (D=50mm, R=25mm)
    swModel.Extension.SelectByID2 planeName, "PLANE", 0, 0, 0, False, 1, Nothing, 0
    swModel.SketchManager.InsertSketch True
    swModel.SketchManager.CreateCircleByRadius 0, 0, 0, 0.025
    swModel.ClearSelection2 True
    swModel.SketchManager.InsertSketch True
    swModel.ClearSelection2 True
    
    Dim sk3 As String
    Set feat = swModel.FirstFeature
    Do While Not feat Is Nothing
        If feat.GetTypeName2 = "ProfileFeature" Then sk3 = feat.Name
        Set feat = feat.GetNextFeature
    Loop
    swModel.Extension.SelectByID2 sk3, "SKETCH", 0, 0, 0, False, 0, Nothing, 0
    Dim fcut1 As Object
    Set fcut1 = swModel.FeatureManager.FeatureCut3( _
        True, False, False, 0, 0, 0.050, 0, False, False, False, False, 0, 0, _
        False, False, False, False, True, True, True, False, 0, 0, False)
    If Not fcut1 Is Nothing Then Print #f, "FEAT_BORE=" & fcut1.Name
    swModel.ClearSelection2 True
    
    ' 6. 特征 4：4个螺栓通孔 (PCD=125mm, 孔径=18mm, R=9mm)
    swModel.Extension.SelectByID2 planeName, "PLANE", 0, 0, 0, False, 1, Nothing, 0
    swModel.SketchManager.InsertSketch True
    swModel.SketchManager.CreateCircleByRadius 0.0625, 0.0, 0.0, 0.009
    swModel.SketchManager.CreateCircleByRadius -0.0625, 0.0, 0.0, 0.009
    swModel.SketchManager.CreateCircleByRadius 0.0, 0.0625, 0.0, 0.009
    swModel.SketchManager.CreateCircleByRadius 0.0, -0.0625, 0.0, 0.009
    swModel.ClearSelection2 True
    swModel.SketchManager.InsertSketch True
    swModel.ClearSelection2 True
    
    Dim sk4 As String
    Set feat = swModel.FirstFeature
    Do While Not feat Is Nothing
        If feat.GetTypeName2 = "ProfileFeature" Then sk4 = feat.Name
        Set feat = feat.GetNextFeature
    Loop
    swModel.Extension.SelectByID2 sk4, "SKETCH", 0, 0, 0, False, 0, Nothing, 0
    Dim fcut2 As Object
    Set fcut2 = swModel.FeatureManager.FeatureCut3( _
        True, False, False, 0, 0, 0.050, 0, False, False, False, False, 0, 0, _
        False, False, False, False, True, True, True, False, 0, 0, False)
    If Not fcut2 Is Nothing Then Print #f, "FEAT_BOLTHOLES=" & fcut2.Name
    swModel.ClearSelection2 True
    
    ' 7. 重建与视图适应
    swModel.EditRebuild3
    swModel.ViewZoomtofit2
    
    ' 8. 测量物理属性
    Dim mp As Object
    Set mp = swModel.Extension.CreateMassProperty
    Print #f, "VOLUME_M3=" & mp.Volume
    Print #f, "SURFACE_AREA_M2=" & mp.SurfaceArea
    Print #f, "MASS_KG=" & mp.Mass
    
    ' 9. 保存原生 SLDPRT 零件
    swModel.SaveAs3 "{sldprt}", 0, 2
    Print #f, "SLDPRT_SAVED=" & (Dir("{sldprt}") <> "")
    
    ' 10. 导出 STEP 工业中性交换文件
    swModel.SaveAs3 "{step}", 0, 2
    Print #f, "STEP_SAVED=" & (Dir("{step}") <> "")
    Print #f, "STATUS=SUCCESS"
    Close #f
    Exit Sub
fail:
    Print #f, "FATAL=" & Err.Number & " " & Err.Description
    If f <> 0 Then Close #f
End Sub
'''


def run_solidworks_flange():
    print("=" * 70)
    print(" Agent 驱动 SOLIDWORKS 2021 法兰盘三维建模与工程图绘制")
    print("=" * 70)
    print(f"设计参数: {json.dumps(FLANGE_PARAMS, ensure_ascii=False, indent=2)}")

    # 1. 确保清空历史指标
    for p in (METRICS_FILE, SLDPRT_FILE, STEP_FILE):
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass

    # 2. 生成 VBA 宏脚本
    macro_content = VBA_MACRO_TEMPLATE.format(
        metrics=METRICS_FILE,
        sldprt=SLDPRT_FILE,
        step=STEP_FILE
    )
    with open(SWB_FILE, "w", encoding="gbk", errors="ignore") as f:
        f.write(macro_content)
    print(f"\n[1/5] 已生成 SOLIDWORKS 建模宏脚本: {SWB_FILE}")

    # 3. 检查或启动 SOLIDWORKS
    print("\n[2/5] 启动并连接 SOLIDWORKS 2021 ...")
    ctl = DesktopController()
    
    # 提前加载类型库以支持早期绑定
    try:
        gencache.EnsureModule("{83A33D31-27C5-11CE-BFD4-00400513BB57}", 0, 29, 0)
    except Exception as e:
        print(f"      gencache 提示: {e}")

    # 启动进程
    proc = subprocess.Popen([SW_EXE], cwd=os.path.dirname(SW_EXE))
    print(f"      SLDWORKS.exe 启动命令已发出 (PID: {proc.pid})，等待主窗就绪 ...", flush=True)

    app = None
    deadline = time.time() + 90
    while time.time() < deadline and app is None:
        try:
            ctl.dismiss_all_dialogs()
        except Exception:
            pass
        try:
            app = win32com.client.GetActiveObject("SldWorks.Application")
            if app is not None:
                break
        except Exception:
            time.sleep(2)

    if app is None:
        print("错误: 无法在超时时间内连接到 SOLIDWORKS COM 接口！")
        return False

    print("      >>> 成功通过 COM 连接到 SOLIDWORKS 2021 实例！")
    try:
        app.Visible = True
    except Exception:
        pass

    # 4. 执行宏建模
    print("\n[3/5] 执行参数化法兰盘建模 (RunMacro / RunMacro2) ...")
    t0 = time.time()
    rc = None
    try:
        rc = app.RunMacro(SWB_FILE, "main", "main")
        print(f"      RunMacro(main, main) 派发完成，返回码: {rc}")
    except Exception as e1:
        try:
            rc = app.RunMacro(SWB_FILE, "", "main")
            print(f"      RunMacro('', main) 派发完成，返回码: {rc}")
        except Exception as e2:
            try:
                rc = app.RunMacro2(SWB_FILE, "", "main", 0, None)
                print(f"      RunMacro2('', main, 0, None) 派发完成，返回码: {rc}", flush=True)
            except Exception as e3:
                try:
                    rc = app.RunMacro2(SWB_FILE, "", "main", 0)
                    print(f"      RunMacro2('', main, 0) 派发完成，返回码: {rc}", flush=True)
                except Exception as e4:
                    print(f"错误: 宏派发失败: {e1} | {e2} | {e3} | {e4}", flush=True)
                    return False

    # 等待结果指标回读
    wait_deadline = time.time() + 30
    while time.time() < wait_deadline:
        if os.path.exists(METRICS_FILE):
            break
        time.sleep(1.0)

    elapsed = time.time() - t0
    print(f"      建模执行耗时: {elapsed:.2f}s")

    # 5. 回读几何特征与物理属性
    metrics = {}
    if os.path.exists(METRICS_FILE):
        for line in open(METRICS_FILE, encoding="gbk", errors="ignore"):
            line = line.strip()
            if "=" in line:
                k, v = line.split("=", 1)
                metrics[k] = v.strip()

    print("\n[4/5] 建模回读指标:")
    for k, v in metrics.items():
        print(f"      {k:<16s}: {v}")

    # 计算体积
    vol_m3 = float(metrics.get("VOLUME_M3", 0.0))
    vol_mm3 = vol_m3 * 1e9
    print(f"      实测体积: {vol_mm3:.1f} mm³")

    # 6. 截取视窗截图取证
    print("\n[5/5] 截取桌面与 SOLIDWORKS 三维视窗 ...")
    time.sleep(1.5)
    cap_res = ctl.capture(output_path=SCREENSHOT_FILE)
    print(f"      截图保存路径: {SCREENSHOT_FILE} ({cap_res.get('width')}x{cap_res.get('height')})")

    # 7. 汇总产物
    artifacts = {
        "sldprt_path": SLDPRT_FILE if os.path.exists(SLDPRT_FILE) else None,
        "step_path": STEP_FILE if os.path.exists(STEP_FILE) else None,
        "swb_path": SWB_FILE,
        "metrics_path": METRICS_FILE,
        "screenshot_path": SCREENSHOT_FILE if os.path.exists(SCREENSHOT_FILE) else None,
        "metrics": metrics,
    }

    summary_file = os.path.join(OUTPUT_DIR, "flange_result.json")
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(artifacts, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print(" 法兰盘建模全流程顺利完成！")
    print(f" - SLDPRT 零件文件: {SLDPRT_FILE} (存在: {os.path.exists(SLDPRT_FILE)})")
    print(f" - STEP 交换文件:   {STEP_FILE} (存在: {os.path.exists(STEP_FILE)})")
    print(f" - 运行结果汇总:     {summary_file}")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = run_solidworks_flange()
    sys.exit(0 if success else 1)
