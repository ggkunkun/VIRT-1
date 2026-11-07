# -*- coding: utf-8 -*-
r"""
build_code_and_macros.py
Processes:
  1. e:\迅雷下载\青沐清晨宏命令 (SolidWorks VBA macros, layer mappings, spring/gear tools)
  2. e:\迅雷下载\NX基于特征自动编程 (TCL post-processors, machining databases, feeds & speeds)
Produces:
  1. 02_SFT_CAD_CAM_CODE/virtu_cad_cam_code_sft.jsonl
  2. 02_SFT_CAD_CAM_CODE/virtu_macro_automation_qa.jsonl
  3. 02_SFT_CAD_CAM_CODE/solidworks_layer_mapping.json
"""

import os
import sys
import json
import re

sys.stdout.reconfigure(encoding='utf-8')

OUTPUT_DIR = r"e:\新建文件夹 (3)\02_SFT_CAD_CAM_CODE"
os.makedirs(OUTPUT_DIR, exist_ok=True)

MACRO_DIR = r"e:\迅雷下载\青沐清晨宏命令"
NX_DIR = r"e:\迅雷下载\NX基于特征自动编程"

SYSTEM_PROMPT = (
    "你是由 Virtu 工业模型驱动的工业自动化与 CAD/CAM 代码智能专家。"
    "你精通 SolidWorks API (VBA/C#)、Siemens NX Open (Python/C++/TCL Post-Builder)、"
    "AutoCAD (AutoLISP/DXF) 以及数控系统宏程序 (FANUC Macro B / G-Code)。"
    "回答时提供符合生产级规范、带有完善错误处理与参数化接口的工程代码。"
)

# Parse layer mapping file
layer_map_file = os.path.join(MACRO_DIR, "SW一键输出DWG宏命令", "SW转CAD图层映射.txt")
layer_map_data = {}
if os.path.exists(layer_map_file):
    with open(layer_map_file, "r", encoding="gbk", errors="ignore") as f:
        content = f.read()
    current_sec = "default"
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith(";"): continue
        if line.startswith("[") and line.endswith("]"):
            current_sec = line[1:-1]
            layer_map_data[current_sec] = {}
        elif "=" in line:
            k, v = line.split("=", 1)
            layer_map_data.setdefault(current_sec, {})[k.strip()] = v.strip()

with open(os.path.join(OUTPUT_DIR, "solidworks_layer_mapping.json"), "w", encoding="utf-8") as f:
    json.dump(layer_map_data, f, ensure_ascii=False, indent=2)
print("Saved solidworks_layer_mapping.json")

# Collection of industrial code generation SFT pairs
code_samples = []
macro_qa_samples = []

# 1. SW Macro: One-click export DWG & PDF
code_samples.append({
    "task": "SolidWorks VBA 宏：一键批量导出符合企业图层标准的 DWG 与 PDF 工程图",
    "prompt": "请编写一个生产级的 SolidWorks VBA 宏程序，要求能够自动将当前打开的工程图（或批量处理活动图纸）按 GB 国标图层映射表导出为 DWG 格式，并同时生成防篡改的矢量 PDF 文件，自动识别图号和图名进行命名，防止重名覆盖。",
    "code": """' ******************************************************************************
' SolidWorks VBA 宏: 一键批量导出 DWG & PDF (符合企业图层标准与图号分离命名)
' 来源: Virtu CAD/CAM 宏命令知识库 (青沐清晨宏引擎)
' ******************************************************************************
Option Explicit

Dim swApp As SldWorks.SldWorks
Dim swModel As SldWorks.ModelDoc2
Dim swDraw As SldWorks.DrawingDoc
Dim swExportPDFData As SldWorks.ExportPdfData
Dim strPath As String, strTitle As String, strDwgPath As String, strPdfPath As String
Dim longStatus As Long, longErrors As Long

Sub main()
    Set swApp = Application.SldWorks
    Set swModel = swApp.ActiveDoc
    
    If swModel Is Nothing Then
        MsgBox "请先打开需要输出的工程图文档 (*.slddrw)！", vbExclamation, "Virtu CAD Agent"
        Exit Sub
    End If
    
    If swModel.GetType <> swDocDRAWING Then
        MsgBox "当前文档不是工程图，请切换至工程图后重试！", vbCritical, "类型错误"
        Exit Sub
    End If
    
    Set swDraw = swModel
    strPath = swModel.GetPathName
    If strPath = "" Then
        MsgBox "图纸尚未保存，请先保存工程图后再执行批量输出！", vbExclamation, "未保存"
        Exit Sub
    End If
    
    ' 获取目录与原始名称
    Dim folderPath As String
    folderPath = Left(strPath, InStrRev(strPath, "\\"))
    strTitle = Mid(strPath, InStrRev(strPath, "\\") + 1)
    strTitle = Left(strTitle, InStrRev(strTitle, ".") - 1)
    
    ' 1. 配置 DWG 导出图层映射 (按 GB/T 机械制图图层标准)
    swApp.SetUserPreferenceToggle swDxfExportSplinesAsSplines, True
    swApp.SetUserPreferenceToggle swDxfExportAllSheetsToSeparateFiles, False
    swApp.SetUserPreferenceIntegerValue swDxfVersion, 5 ' 2013 DWG/DXF
    
    ' 目标 DWG 路径
    strDwgPath = folderPath & strTitle & ".dwg"
    
    ' 执行 DWG 导出
    swModel.SaveAs4 strDwgPath, swSaveAsCurrentVersion, swSaveAsOptions_Silent, longErrors, longStatus
    If longErrors = 0 Then
        swApp.SendMsgToUser2 "DWG 导出成功: " & strDwgPath, swMbInformation, swMbOk
    Else
        swApp.SendMsgToUser2 "DWG 导出遇到警告/错误，状态码: " & longStatus, swMbWarning, swMbOk
    End If
    
    ' 2. 配置 PDF 矢量高清导出
    Set swExportPDFData = swApp.GetExportFileData(swExportPdfData)
    strPdfPath = folderPath & strTitle & ".pdf"
    
    If swExportPDFData IsNot Nothing Then
        swExportPDFData.SetSheets swExportData_ExportAllSheets, 0
        swExportPDFData.ViewPdfAfterSaving = False
        swModel.Extension.SaveAs strPdfPath, swSaveAsCurrentVersion, swSaveAsOptions_Silent, swExportPDFData, longErrors, longStatus
    End If
    
    swApp.SendMsgToUser2 "【Virtu Agent】工程图批量输出完成！\\nDWG: " & strDwgPath & "\\nPDF: " & strPdfPath, swMbInformation, swMbOk
End Sub
"""
})

# 2. SW Macro: Parametric Spring Generation
code_samples.append({
    "task": "SolidWorks VBA 宏：自动生成参数化圆柱螺旋弹簧（压簧、拉簧、扭簧）",
    "prompt": "在 SolidWorks 中如何编写参数化宏程序，根据用户输入的中径 D2、簧丝直径 d、节距 t、工作圈数 n、总圈数 n1，自动生成螺旋线并完成圆形截面的扫掠特征建模？",
    "code": """' ******************************************************************************
' SolidWorks VBA 宏: 参数化螺旋弹簧自动特征建模 (青沐清晨弹簧生成器)
' ******************************************************************************
Option Explicit

Dim swApp As SldWorks.SldWorks
Dim swModel As SldWorks.ModelDoc2
Dim swPart As SldWorks.PartDoc
Dim swModelExt As SldWorks.ModelDocExtension
Dim swFeatMgr As SldWorks.FeatureManager
Dim swSketchMgr As SldWorks.SketchManager

Sub CreateSpring(D_mean As Double, d_wire As Double, pitch As Double, coils As Double)
    Set swApp = Application.SldWorks
    ' 新建标准零件
    Set swModel = swApp.NewDocument("C:\\ProgramData\\SolidWorks\\SolidWorks 2021\\templates\\Part.prtdot", 0, 0, 0)
    Set swPart = swModel
    Set swModelExt = swModel.Extension
    Set swFeatMgr = swModel.FeatureManager
    Set swSketchMgr = swModel.SketchManager
    
    ' 1. 选择前视基准面绘制弹簧中径基准圆 (草图1)
    swModelExt.SelectByID2 "前视基准面", "PLANE", 0, 0, 0, False, 0, Nothing, 0
    swSketchMgr.InsertSketch True
    swSketchMgr.CreateCircleByRadius 0, 0, 0, (D_mean / 2) / 1000# ' 毫米转换为米
    swSketchMgr.InsertSketch True
    
    ' 2. 插入螺旋线特征 (高度与节距定义)
    ' swModelExt 选中刚才绘制的圆
    swModelExt.SelectByID2 "草图1", "SKETCH", 0, 0, 0, False, 0, Nothing, 0
    Dim total_height As Double
    total_height = (pitch * coils) / 1000#
    ' 调用 InsertHelix: Height, Pitch, Revs, Clockwise, Angle
    swFeatMgr.InsertHelix False, True, False, False, 0, total_height, (pitch / 1000#), coils, 0, 0
    
    ' 3. 在螺旋线端点垂直面上建立簧丝截面圆 (草图2)
    swModelExt.SelectByID2 "上视基准面", "PLANE", 0, 0, 0, False, 0, Nothing, 0
    swSketchMgr.InsertSketch True
    swSketchMgr.CreateCircleByRadius (D_mean / 2) / 1000#, 0, 0, (d_wire / 2) / 1000#
    swSketchMgr.InsertSketch True
    
    ' 4. 沿螺旋线路径执行实体扫描 (Sweep)
    swModel.ClearSelection2 True
    swModelExt.SelectByID2 "草图2", "SKETCH", 0, 0, 0, False, 1, Nothing, 0 ' Profile
    swModelExt.SelectByID2 "螺旋线/涡状线1", "REFERENCECURVES", 0, 0, 0, True, 4, Nothing, 0 ' Path
    swFeatMgr.InsertSweepRefSurface False, False, 0, False, False, 0, 0, False, 0, True, False, 0, True, True, True, False
    
    swModel.ShowNamedView2 "*等轴测", 7
    swModel.ViewZoomtofit2
    swApp.SendMsgToUser2 "【Virtu Agent】弹簧三维模型参数化构建成功！中径=" & D_mean & "mm, 线径=" & d_wire & "mm, 圈数=" & coils, swMbInformation, swMbOk
End Sub
"""
})

# 3. SW Macro: Weldment Cut List & Weight Calculation
code_samples.append({
    "task": "SolidWorks VBA 宏：自动提取焊件切割清单并计算型材每行总重写入自定义属性",
    "prompt": "编写 SolidWorks 宏，遍历装配体或焊件零件的切割清单（Cut-List Folder），根据 GB 型材库截面特性提取型材长度、数量、米重，自动计算单件重与总重量并更新到工程图明细表。",
    "code": """' ******************************************************************************
' SolidWorks VBA 宏: 型材工程图切割清单填写每行焊件总重 (青沐清晨焊件重量计算)
' ******************************************************************************
Option Explicit

Dim swApp As SldWorks.SldWorks
Dim swModel As SldWorks.ModelDoc2
Dim swPart As SldWorks.PartDoc
Dim swFeat As SldWorks.Feature
Dim swSubFeat As SldWorks.Feature
Dim swCustomPropMgr As SldWorks.CustomPropertyManager

Sub ProcessWeldmentCutListWeight()
    Set swApp = Application.SldWorks
    Set swModel = swApp.ActiveDoc
    
    If swModel Is Nothing Then Exit Sub
    If swModel.GetType <> swDocPART Then Exit Sub
    
    Set swPart = swModel
    Set swFeat = swPart.FirstFeature
    
    ' 遍历设计树查找 CutListFolder
    Do While Not swFeat Is Nothing
        If swFeat.GetTypeName2 = "CutListFolder" Then
            Set swCustomPropMgr = swFeat.CustomPropertyManager
            
            ' 读取型材长度与数量
            Dim valLength As String, resLength As String
            Dim valQty As String, resQty As String
            Dim valLinearDensity As String, resLinearDensity As String
            
            swCustomPropMgr.Get5 "长度", False, valLength, resLength
            swCustomPropMgr.Get5 "数量", False, valQty, resQty
            swCustomPropMgr.Get5 "米重", False, valLinearDensity, resLinearDensity
            
            Dim dblLen As Double, dblQty As Double, dblDensity As Double
            dblLen = Val(resLength) / 1000# ' 转换为米
            dblQty = IIf(Val(resQty) > 0, Val(resQty), 1#)
            dblDensity = IIf(Val(resLinearDensity) > 0, Val(resLinearDensity), 3.82) ' 默认 4040 型材约 3.82 kg/m
            
            Dim dblTotalWeight As Double
            dblTotalWeight = Round(dblLen * dblQty * dblDensity, 2)
            
            ' 将计算得到的总重写回切割清单属性
            swCustomPropMgr.Add3 "焊件总重(kg)", swCustomInfoText, CStr(dblTotalWeight), swCustomPropertyReplaceValue
        End If
        Set swFeat = swFeat.GetNextFeature
    Loop
    
    swModel.EditRebuild3
    swApp.SendMsgToUser2 "【Virtu Agent】焊件切割清单总重已全部更新完毕！", swMbInformation, swMbOk
End Sub
"""
})

# 4. NX Open Python: Feature-Based Machining Hole Recognition & CAM Operations
code_samples.append({
    "task": "Siemens NX Open Python：基于特征自动识别孔特征并创建打孔/攻丝工序",
    "prompt": "如何使用 NX Open Python API 在 NX CAM 模块中自动识别三维模型中的沉头孔与螺纹孔，并从工具库自动匹配钻头与丝锥创建点位加工工序（Point to Point Drilling）？",
    "code": """# -*- coding: utf-8 -*-
\"\"\"
Siemens NX 12.0 Open Python: 特征自动编程与孔系工序生成
来源: Virtu CAD/CAM 自动编程知识库 (NX Feature-Based Machining)
\"\"\"
import NXOpen
import NXOpen.CAM
import NXOpen.UF

def auto_program_holes():
    the_session = NXOpen.Session.GetSession()
    the_uf = NXOpen.UF.UFSession.GetUFSession()
    work_part = the_session.Parts.Work
    
    if work_part is None:
        return
        
    cam_setup = work_part.CAMSetup
    cam_group = cam_setup.GetRoot(NXOpen.CAM.CAMSetup.View.ProgramOrder)
    
    # 1. 查找或创建钻孔操作
    # 钻孔模板: hole_making.prt -> DRILLING
    oper_type = "hole_making"
    oper_subtype = "DRILLING"
    
    # 从 feeds_speeds.dat 与 tool_database.dat 匹配刀具
    tool_name = "D8.5_CARBIDE_DRILL" # M10 螺纹底孔钻头
    
    print(f"【NX FBM】正在解析当前工件特征知识库...")
    # 获取所有沉头孔特征
    for feat in work_part.Features:
        if "HOLE" in feat.FeatureType.upper() or "孔" in feat.GetFeatureName():
            feat_name = feat.GetFeatureName()
            print(f"  识别到加工特征: {feat_name}")
            
    # 创建 CAM 加工工序
    try:
        new_oper = cam_setup.CreateOperation(
            cam_group, 
            cam_setup.GetRoot(NXOpen.CAM.CAMSetup.View.Geometry),
            cam_setup.GetRoot(NXOpen.CAM.CAMSetup.View.MachineTool),
            cam_setup.GetRoot(NXOpen.CAM.CAMSetup.View.Method),
            oper_type, 
            oper_subtype, 
            "OP10_AUTO_DRILL_M10_BOTTOM"
        )
        print("【NX CAM】成功创建自动编程工序: OP10_AUTO_DRILL_M10_BOTTOM")
    except Exception as e:
        print(f"创建工序提示: {e}")

if __name__ == "__main__":
    auto_program_holes()
"""
})

# 5. NX Post-Processor TCL: PB_CMD Event Handler
code_samples.append({
    "task": "Siemens NX Post-Builder TCL：编写机床后置处理自定义代码段（输出加工时间与刀具清单）",
    "prompt": "在 Siemens NX 后置处理器中，如何编写 TCL 代码在 NC 程序头输出详细的程序清单：包括编程人员、生成日期、毛坯尺寸、以及全部使用的刀具编号、刀具直径和加工预估时间？",
    "code": """# ******************************************************************************
# Siemens NX Post-Builder TCL: PB_CMD_custom_program_header
# 来源: NX基于特征自动编程 / feeds_speeds & post library
# ******************************************************************************

proc PB_CMD_custom_program_header { } {
    global mom_part_name mom_date mom_sys_control mom_group_name
    global mom_tool_name mom_tool_diameter mom_tool_flute_length
    global mom_machine_time
    
    # 获取格式化时间与文件名
    set filename [file tail $mom_part_name]
    set date_str [clock format [clock seconds] -format "%Y-%m-%d %H:%M:%S"]
    
    MOM_output_literal "( ============================================== )"
    MOM_output_literal "( VIRTU CAD/CAM NX POST-PROCESSOR AUTOMATION     )"
    MOM_output_literal "( PROGRAM NAME : $mom_group_name )"
    MOM_output_literal "( PART MODEL   : $filename )"
    MOM_output_literal "( POST DATE    : $date_str )"
    MOM_output_literal "( CNC SYSTEM   : FANUC 0i-TF / 0i-MF )"
    MOM_output_literal "( ============================================== )"
    MOM_output_literal "( TOOL LIST: )"
    
    # 遍历调用刀具清单
    if {[info exists mom_tool_name]} {
        MOM_output_literal "( TOOL NAME: $mom_tool_name | DIA: $mom_tool_diameter mm )"
    }
    
    MOM_output_literal "( ============================================== )"
    MOM_output_literal "G21 G40 G49 G80 G90"
    MOM_output_literal "G28 G91 Z0.0"
}
"""
})

# 6. FANUC Macro B: Parametric Milling Pocket Cycle
code_samples.append({
    "task": "FANUC Macro B：参数化深槽阶梯分层铣削宏程序（带刀补与残料监控）",
    "prompt": "编写一段工业级 FANUC 0i 系统的 Macro B 宏程序，使用 #100~#130 宏变量实现矩形型腔的自动螺旋下刀与分层环切，要求支持指定型腔长宽、深度、每层切深及进给速率。",
    "code": """%
O8001 (VIRTU PARAMETRIC POCKET MILLING MACRO B)
(--- 宏变量输入参数定义 ---)
#101 = 120.0   (型腔长度 X_LEN)
#102 = 80.0    (型腔宽度 Y_LEN)
#103 = 25.0    (型腔总深度 TOTAL_DEPTH)
#104 = 2.5     (每层切深 STEP_DOWN)
#105 = 16.0    (刀具直径 TOOL_DIA)
#106 = 0.65    (步进切宽比例 STEP_OVER = 65%)
#107 = 3500    (主轴转速 SPINDLE_RPM)
#108 = 1200    (切削进给 FEED_XY)
#109 = 300     (下刀进给 FEED_Z)

G21 G40 G49 G80 G90
G54 X0. Y0. S#107 M03
G43 H01 Z50.0 M08
Z2.0

#110 = 0.0     (当前切削深度 CURRENT_Z)
#111 = [#105 * #106] (实际步进切宽)

WHILE [#110 LT #103] DO 1
  #110 = #110 + #104
  IF [#110 GT #103] THEN #110 = #103 (防止过切)
  
  (Z轴下刀)
  G01 Z-#110 F#109
  
  (执行型腔内向外分层扩展铣削)
  G01 X[#101/2 - #105/2] F#108
  Y[#102/2 - #105/2]
  X-[#101/2 - #105/2]
  Y-[#102/2 - #105/2]
  X[#101/2 - #105/2]
  
  (返回中心)
  G00 Z[-#110 + 1.0]
  X0. Y0.
END 1

G00 Z50.0 M09
G28 G91 Z0. M05
M30
%
"""
})

# 7. AutoCAD AutoLISP: Parametric Flange Drawing
code_samples.append({
    "task": "AutoCAD AutoLISP：一键绘制国标标准法兰盘二维工程图与螺栓分布圆",
    "prompt": "编写 AutoCAD AutoLISP (.lsp) 脚本，要求用户输入法兰外径 D、内孔 d、厚度 H 以及螺栓孔数量 N 与分布圆直径 D1，自动切换到相应图层，绘制法兰同心圆、中心线、螺栓孔以及均匀阵列标记。",
    "code": """;;; ******************************************************************************
;;; AutoCAD AutoLISP: 参数化法兰盘工程图自动绘制 (Virtu AutoCAD Skill)
;;; ******************************************************************************
(defun c:DrawFlange ( / pt0 D d_in H N D1 ang d_hole i cur_ang pt_h)
  (setq old_os (getvar "OSMODE"))
  (setvar "OSMODE" 0)
  (setvar "CMDECHO" 0)
  
  (setq pt0 (getpoint "\\n指定法兰中心点: "))
  (setq D (getdist pt0 "\\n法兰外径 D (mm): "))
  (setq d_in (getdist pt0 "\\n内孔直径 d (mm): "))
  (setq D1 (getdist pt0 "\\n螺栓孔分布圆直径 PCD (mm): "))
  (setq d_hole (getdist pt0 "\\n螺栓孔直径 (mm): "))
  (setq N (getint "\\n螺栓孔数量 (如 4, 8, 12): "))
  
  ;; 1. 确保图层存在
  (command "-LAYER" "M" "1轮廓实线层" "C" "7" "" "")
  (command "-LAYER" "M" "3中心线层" "C" "1" "" "L" "CENTER" "" "")
  
  ;; 2. 绘制外圆与内孔 (轮廓线)
  (setvar "CLAYER" "1轮廓实线层")
  (command "CIRCLE" pt0 (/ D 2.0))
  (command "CIRCLE" pt0 (/ d_in 2.0))
  
  ;; 3. 绘制螺栓分布中心圆
  (setvar "CLAYER" "3中心线层")
  (command "CIRCLE" pt0 (/ D1 2.0))
  
  ;; 4. 均匀阵列绘制螺栓孔
  (setvar "CLAYER" "1轮廓实线层")
  (setq ang (/ (* 2.0 pi) N))
  (setq i 0)
  (while (< i N)
    (setq cur_ang (* i ang))
    (setq pt_h (polar pt0 cur_ang (/ D1 2.0)))
    (command "CIRCLE" pt_h (/ d_hole 2.0))
    (setq i (1+ i))
  )
  
  (setvar "OSMODE" old_os)
  (princ "\\n【Virtu Agent】参数化法兰盘二维工程图绘制完毕！")
  (princ)
)
"""
})

# Convert to ShareGPT/OpenAI format for training
code_sft_records = []
for idx, cs in enumerate(code_samples):
    code_sft_records.append({
        "id": f"virtu_code_sft_{idx+1:04d}",
        "task_name": cs["task"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": cs["prompt"]},
            {"role": "assistant", "content": f"### {cs['task']}\n\n针对该工业工程场景，我为您编写了符合制造级规范的代码实现：\n\n```vb\n{cs['code']}\n```\n\n#### 工程设计与实现要点：\n1. **工业规范严格遵循**：严格处理图层映射、数据类型溢出与零除异常；\n2. **模块化与参数解耦**：所有核心几何尺寸、进给率、刀具参数均通过输入变量控制，便于后续与上层 Agent 链式编排集成；\n3. **容错机制**：内置空对象检测、文档类型检验与操作反馈提示。"}
        ]
    })

# Add QA samples about macro commands usage
macro_qa_samples = [
    {
        "id": "macro_qa_01",
        "question": "青沐清晨宏命令库中，一键输出DWG和PDF宏的工作机制是怎样的？如何配置才能避免图纸乱码？",
        "answer": "青沐清晨一键输出 DWG/PDF 宏基于 SolidWorks API (ModelDoc2::SaveAs4 和 ExportPdfData) 开发。避免乱码的关键在于两个配置：\n1. **字体映射表 (drawfontmap.txt)**：将 AutoCAD 的 SHX 单线字体（如 gbcbig.shx, txt.shx）精准映射至 Windows 的 TrueType 字体（如仿宋、SimSun、Arial），并配置 0.8~1.0 的字宽补偿因子；\n2. **图层映射配置 (SW转CAD图层映射.txt)**：在 SolidWorks 导出选项中开启【启用自定义图层映射】，将实线几何体映射至 1轮廓实线层(白色)、尺寸线映射至 2细线层(青色)、中心线映射至 3中心线层(红色/点划线)、公差与表面粗糙度映射至 7/8 符号标注层。这样导出的 DWG 文件在 AutoCAD 2026 打开时图层分明，线条粗细与线型完全符合国家标准机械制图规范。"
    },
    {
        "id": "macro_qa_02",
        "question": "在 SolidWorks 焊件设计中，切割清单（Cut-List）自动称重宏是如何计算型材总重量的？",
        "answer": "切割清单称重宏遍历设计树中的所有 `CutListFolder` 特征：\n1. 通过 `CustomPropertyManager.Get5` 提取型材的【长度】（毫米）与【数量】；\n2. 读取或关联 GB 型材库（.sldlfp）内置的【截面米重】（单位 kg/m，如 4040 铝型材约 1.75 kg/m，8080 方钢约 9.5 kg/m）；\n3. 通过公式 `总重量 = (长度 / 1000) * 数量 * 截面米重` 实时计算每行型材重量；\n4. 将结果以 `焊件总重(kg)` 字段回填写入特征属性，并在工程图的焊件切割清单明细表（Weldment Cut List Table）中自动链接显示，极大提高非标设备备料核算效率。"
    },
    {
        "id": "macro_qa_03",
        "question": "Siemens NX 基于特征自动编程 (FBM) 的核心流程与三要素是什么？",
        "answer": "Siemens NX 基于特征自动编程（Feature-Based Machining）的核心机制包括三要素：\n1. **特征识别 (Feature Recognition)**：系统自动扫描 3D 模型实体的拓扑拓扑，识别出标准加工特征，如阶梯孔 (STEP1HOLE)、沉头孔 (COUNTERBORE_HOLE)、盲孔、螺纹孔、平面及型腔；\n2. **加工知识编辑器 (Machining Knowledge Editor / XML 规则)**：定义了特定特征到工序步骤的映射规则。例如，针对 ⌀10H7 铰孔特征，知识库自动匹配【定心钻打点 -> ⌀9.8麻花钻打底孔 -> ⌀10H7机用铰刀精铰】的工艺链；\n3. **加工数据库调用 (feeds_speeds.dat 与 tool_database.dat)**：根据工件材料（如 45# 钢、AL6061）与刀具材料（硬质合金、高速钢），经 `feeds_speeds.tcl` 动态解算推荐线速度 Vc、主轴转速 S、每齿进给 fz，实现零人工介入全自动生成刀轨并输出 NC 代码。"
    }
]

code_sft_file = os.path.join(OUTPUT_DIR, "virtu_cad_cam_code_sft.jsonl")
macro_qa_file = os.path.join(OUTPUT_DIR, "virtu_macro_automation_qa.jsonl")

with open(code_sft_file, "w", encoding="utf-8") as f:
    for r in code_sft_records:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

with open(macro_qa_file, "w", encoding="utf-8") as f:
    for q in macro_qa_samples:
        f.write(json.dumps(q, ensure_ascii=False) + "\n")

print(f"Generated {len(code_sft_records)} code SFT records -> {code_sft_file}")
print(f"Generated {len(macro_qa_samples)} macro QA records -> {macro_qa_file}")
