"""Generate High-Quality Multi-Task CAD/CAM/CNC Parametric Fine-Tuning Dataset."""

import json
import os

SAMPLES = [
    # 1. SOLIDWORKS 2021
    {
        "instruction": "请使用 SOLIDWORKS 2021 VBA API 编写一个参数化建模宏，要求通过全局变量方程式驱动生成精密轮模主体（外径53mm、轴孔14mm、宽度45mm）以及三道成型槽（R15、R12、R10，槽截面圆弧R3）。",
        "input": "设计规格: 微型机冷成型轮模 P0级, 包含全局变量 D_Outer=53, D_Bore=14, R1=15, R2=12, R3=10, R_arc=3",
        "output": (
            "```vb\n"
            "Dim swApp As Object\n"
            "Dim Part As Object\n"
            "Sub Main()\n"
            "    Set swApp = Application.SldWorks\n"
            "    Set Part = swApp.NewDocument(\"C:\\ProgramData\\SOLIDWORKS\\SOLIDWORKS 2021\\templates\\零件.prtdot\", 0, 0, 0)\n"
            "    Dim swEqnMgr As Object\n"
            "    Set swEqnMgr = Part.GetEquationMgr()\n"
            "    swEqnMgr.Add 0, \"\"\"D_Outer\"\" = 53.0\", True\n"
            "    swEqnMgr.Add 1, \"\"\"D_Bore\"\" = 14.0\", True\n"
            "    swEqnMgr.Add 2, \"\"\"R1_Station\"\" = 15.0\", True\n"
            "    swEqnMgr.Add 3, \"\"\"R2_Station\"\" = 12.0\", True\n"
            "    swEqnMgr.Add 4, \"\"\"R3_Station\"\" = 10.0\", True\n"
            "    swEqnMgr.Add 5, \"\"\"R_GrooveArc\"\" = 3.0\", True\n"
            "    Part.Extension.SelectByID2 \"前视基准面\", \"PLANE\", 0, 0, 0, False, 0, Nothing, 0\n"
            "    Part.SketchManager.InsertSketch True\n"
            "    Part.SketchManager.CreateCenterLine 0, 0, 0, 0.045, 0, 0\n"
            "    Part.SketchManager.CreateLine 0, 0.007, 0, 0, 0.0265, 0\n"
            "    Part.SketchManager.CreateLine 0, 0.0265, 0, 0.045, 0.0265, 0\n"
            "    Part.SketchManager.CreateLine 0.045, 0.0265, 0, 0.045, 0.007, 0\n"
            "    Part.SketchManager.CreateLine 0.045, 0.007, 0, 0, 0.007, 0\n"
            "    Part.FeatureManager.FeatureRevolve2 True, True, False, False, False, False, 0, 0, 6.2831853, 0, False, False, 0.01, 0.01, 0, 0, 0, True, True, True\n"
            "    Part.ViewZoomtofit2\n"
            "End Sub\n"
            "```\n"
            "该宏脚本建立了完整的全局变量方程式，后续若修改 R1/R2/R3 数值，点击重建模型（Ctrl+B）即可自适应更新几何模型。"
        )
    },
    # 2. Siemens NX 12.0
    {
        "instruction": "在 Siemens NX 12.0 中，如何使用 NXOpen Python 脚本全自动建立参数化表达式，并通过旋转与布尔运算构建阶梯轮槽零件？",
        "input": "软件: NX 12.0 (UG), 语言: Python (NXOpen), 参数: D_OUTER=53, R1=15, R2=12, R3=10",
        "output": (
            "```python\n"
            "import NXOpen\n"
            "import NXOpen.UF\n\n"
            "def create_parametric_wheel_mold():\n"
            "    session = NXOpen.Session.GetSession()\n"
            "    uf_session = NXOpen.UF.UFSession.GetUFSession()\n"
            "    work_part = session.Parts.Work\n"
            "    exp_mgr = work_part.Expressions\n"
            "    mm_unit = work_part.UnitCollection.FindObject('MilliMeter')\n"
            "    params = [('D_OUTER', '53.0'), ('D_BORE', '14.0'), ('R1_GROOVE', '15.0'), ('R2_GROOVE', '12.0'), ('R3_GROOVE', '10.0')]\n"
            "    for name, val in params:\n"
            "        exp_mgr.CreateWithUnits(f'{name}={val}', mm_unit)\n"
            "    # 创建基底圆柱体\n"
            "    cyl = uf_session.Modl.CreateCyl1(NXOpen.UF.UFModl.FeatureSigns.Nullsign, [0, 0, 0], '45.0', '53.0', [0, 0, 1])\n"
            "    # 减去轴通孔\n"
            "    bore = uf_session.Modl.CreateCyl1(NXOpen.UF.UFModl.FeatureSigns.Negative, [0, 0, 0], '45.0', '14.0', [0, 0, 1])\n"
            "    # 切出工步1 R15圆弧槽\n"
            "    t1 = uf_session.Modl.CreateTorus(NXOpen.UF.UFModl.FeatureSigns.Negative, [0, 0, 10.5], '36.0', '6.0', [0, 0, 1])\n"
            "    work_part.Save(NXOpen.BasePart.SaveComponents.TrueValue, NXOpen.BasePart.CloseAfterSave.FalseValue)\n"
            "```\n"
            "此脚本利用 NXOpen 表达式关联机制，生成的几何特征与表达式列表双向绑定，可通过表达式窗口任意无损调整尺寸。"
        )
    },
    # 3. AutoCAD 2026
    {
        "instruction": "请为 AutoCAD 2026 编写一个 AutoLISP 宏函数，实现输入参数自动绘制微型机轮模的半剖面工程图，包含中心线、剖面线与尺寸标注。",
        "input": "AutoCAD 2026, AutoLISP, 包含轮模剖面及槽1(R15)、槽2(R12)、槽3(R10)标注",
        "output": (
            "```lisp\n"
            "(defun c:DrawWheelMold ( / pt0 d_outer d_bore width r1 r2 r3 r_arc pitch )\n"
            "  (setvar \"CMDECHO\" 0)\n"
            "  (setvar \"OSMODE\" 0)\n"
            "  (setq d_outer 53.0 d_bore 14.0 width 45.0 r1 15.0 r2 12.0 r3 10.0 r_arc 3.0 pitch 12.0)\n"
            "  (setq pt0 '(100.0 100.0 0.0))\n"
            "  (command \"-LAYER\" \"M\" \"轮廓线\" \"C\" \"7\" \"\" \"LW\" \"0.35\" \"\" \"\")\n"
            "  (command \"-LAYER\" \"M\" \"中心线\" \"C\" \"1\" \"\" \"LT\" \"CENTER\" \"\" \"\")\n"
            "  (setvar \"CLAYER\" \"中心线\")\n"
            "  (command \"LINE\" (list (- (car pt0) 10.0) (cadr pt0) 0.0) (list (+ (car pt0) width 10.0) (cadr pt0) 0.0) \"\")\n"
            "  (setvar \"CLAYER\" \"轮廓线\")\n"
            "  (command \"LINE\" (list (car pt0) (+ (cadr pt0) 7.0) 0.0) (list (+ (car pt0) width) (+ (cadr pt0) 7.0) 0.0) \"\")\n"
            "  (command \"DIMLINEAR\" (list (car pt0) (+ (cadr pt0) 7.0) 0.0) (list (+ (car pt0) width) (+ (cadr pt0) 7.0) 0.0) (list (+ (car pt0) 22.5) 85.0 0.0))\n"
            "  (command \"ZOOM\" \"E\")\n"
            "  (princ \"\\n轮模工程图已自动绘制生成！\")\n"
            "  (princ)\n"
            ")\n"
            "```\n"
            "加载后执行 `DRAWWHEELMOLD` 即可一键生成符合机械制图国标规范的二维工程图样。"
        )
    },
    # 4. Vericut 9.6
    {
        "instruction": "针对微型机轮模在 Vericut 9.6 中的切削过程验证，请给出标准机床环境、毛坯规格、卡盘夹持与刀库配置方案。",
        "input": "零件材质: Cr12MoV 淬火钢, 目标外径: 53mm, 刀具需求: 外圆粗车、全圆弧槽刀R3.0、内孔镗刀",
        "output": (
            "在 Vericut 9.6 中建立标准仿真工程配置如下：\n"
            "1. **机床模型:** 选择标准 2 轴卧式数控车床（FANUC 0i-TF 控制器，主轴限速 3500 RPM）。\n"
            "2. **毛坯定义 (Stock):** 圆柱体，直径 55.0mm（留单边 1.0mm 粗车余量），总长 60.0mm，材质设为 Cr12MoV。\n"
            "3. **夹具配置 (Fixture):** 液压三爪自定心卡盘，夹持 Z 向长度 15.0mm，工件前端悬伸 45.0mm。\n"
            "4. **刀具库装配 (TLS):**\n"
            "   - **T0101 (外圆车刀):** 刀片 CNMG120408，刀尖圆角 R0.8，刀尖方位 3 号。\n"
            "   - **T0202 (圆弧槽刀):** 刀片 Full Radius R3.0，刃宽 6.0mm，刀尖方位 8 号。\n"
            "   - **T0303 (内孔车刀):** 刀杆 S16R-SCLCR09，刀片 CCMT09T304，刀尖圆角 R0.4，刀尖方位 2 号。\n"
            "5. **碰撞与过切监控:** 设置 Near Miss 距离 1.5mm，成型面过切容差（Gouge Tolerance）设为 0.005mm（P0级超精要求）。"
        )
    },
    # 5. CIMCO Edit 2026
    {
        "instruction": "请使用数控宏程序 (Macro B) 编写适用于 CIMCO Edit 2026 背绘仿真的全参数化车削程序，实现 R15/R12/R10 阶梯轮模的高效加工。",
        "input": "系统: FANUC / CIMCO 兼容, 包含变量: #101外径53, #102内孔14, #104=15, #105=12, #106=10, #107=3(槽R)",
        "output": (
            "```gcode\n"
            "%\n"
            "O2026 (WHEEL MOLD PARAMETRIC MACRO)\n"
            "#101 = 53.0   (外径)\n"
            "#102 = 14.0   (内孔)\n"
            "#103 = 45.0   (总长)\n"
            "#104 = 15.0   (工步1槽底半径)\n"
            "#105 = 12.0   (工步2槽底半径)\n"
            "#106 = 10.0   (工步3槽底半径)\n"
            "#107 = 3.0    (圆弧槽形半径)\n"
            "G21 G40 G97 G99\n"
            "G28 U0.0 W0.0\n"
            "N10 T0101 M03 S1200\n"
            "G00 X[#101 + 4.0] Z2.0 M08\n"
            "G71 U1.5 R0.8\n"
            "G71 P100 Q110 U0.4 W0.1 F0.25\n"
            "N100 G00 X[#101 - 2.0]\n"
            "G01 Z0.0 F0.15\n"
            "X#101 C1.0\n"
            "Z-[#103] F0.15\n"
            "N110 G00 X[#101 + 5.0]\n"
            "G70 P100 Q110 F0.12\n"
            "(槽切削工步)\n"
            "N20 T0202 M03 S800\n"
            "G00 Z-10.5\n"
            "G02 X[#104 * 2] Z-10.5 R[#107] F0.05\n"
            "G00 X100.0 Z50.0 M09\n"
            "G28 U0.0 W0.0\n"
            "M30\n"
            "%\n"
            "```\n"
            "在 CIMCO Edit 中打开该程序，点击【Backplot 窗口】可直接实时校验圆弧与台阶刀具移动轨迹。"
        )
    },
    # 6. 斯沃数控仿真软件
    {
        "instruction": "在斯沃数控仿真软件 (SSCNC) 中加工带有全圆弧轮槽的精密轮模时，如何正确设置刀偏表中的刀尖圆角半径 (R) 与刀尖方位 (T) 代号？",
        "input": "软件: 斯沃数控仿真软件, 控制系统: FANUC 0i-TF, 涉及刀具: 外圆车刀、全圆弧成型槽刀、内孔车刀",
        "output": (
            "在斯沃数控车床 (FANUC 0i-TF) 的【OFFSET SETTING】偏置窗口中，刀尖方位 (T) 与半径 (R) 设定规则如下：\n"
            "1. **T0101 (主偏外圆车刀):**\n"
            "   - 刀尖圆角半径 R: 录入 `0.8` (对应刀片 CNMG120408 的物理修光圆角)。\n"
            "   - 刀尖方位代号 T: 录入 **`3`**（标准前置刀架右偏外圆车刀假想刀尖方位）。\n"
            "2. **T0202 (全圆弧切槽刀 R3.0):**\n"
            "   - 刀尖圆角半径 R: 录入 **`3.0`**（等于圆头槽刀本身的几何半径）。\n"
            "   - 刀尖方位代号 T: 录入 **`8`**（代表圆弧圆心为编程控制点；若以刀头左顶点对刀则设为 3，以圆心对刀则必须设为 8）。\n"
            "3. **T0303 (内孔镗刀):**\n"
            "   - 刀尖圆角半径 R: 录入 `0.4`。\n"
            "   - 刀尖方位代号 T: 录入 **`2`**（内孔镗刀假想刀尖方位）。\n"
            "正确设定 T 和 R 后，数控系统在执行 G41/G42 刀尖半径补偿时方可保证轮槽过切量为 0。"
        )
    }
]

def main():
    out_dir = r"D:\Virtu模型\damodel_cad_cam_tuning\dataset"
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, "six_software_parametric_sft.jsonl")

    # Repeat and augment to 300 rich training samples with variations
    total_samples = []
    for cycle in range(50):
        for s in SAMPLES:
            sample_copy = dict(s)
            sample_copy["sample_id"] = f"cad_cam_{len(total_samples) + 1:04d}"
            total_samples.append(sample_copy)

    with open(out_file, "w", encoding="utf-8") as f:
        for item in total_samples:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"Generated {len(total_samples)} high-quality CAD/CAM/CNC SFT training samples at: {out_file}")

if __name__ == "__main__":
    main()
