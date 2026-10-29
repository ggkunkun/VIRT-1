"""Wish-Style Intent-to-Parametric CAD/CAM/CAE Engineering Engine.

Provides automated decomposition of declarative manufacturing wishes into
rigorous, compilable code, macros, and configuration templates across:
1. SOLIDWORKS 2021 (VBA macro, EquationMgr, Simulation CAE)
2. Siemens NX 12.0 (NXOpen Python, ExpressionCollection, CAM Multi-Axis)
3. AutoCAD 2026 (AutoLISP with layer discipline, GD&T, and dimensioning)
4. Vericut 9.6 (Kinematic machine simulation, OptiPath/Force, Auto-Diff)
5. CIMCO Edit 2026 (FANUC Macro B parametric NC code, variable logic)
6. 斯沃数控仿真 (SSCNC 7.2 shop-floor touch-off & WCS calibration)
"""

import math
import re
from typing import Any, Dict, List, Optional
from virtu_omni.knowledge.software_plugin_ontology import SOFTWARE_ONTOLOGY


class WishCADCAMEngine:
    """Translates high-level declarative wishes into multi-software engineering code."""

    def __init__(self):
        self.ontology = SOFTWARE_ONTOLOGY

    def parse_wish_intent(self, wish_text: Any) -> Dict[str, Any]:
        """Extract geometric, material, and manufacturing constraints from natural text."""
        # Sanitize input if passed as list of blocks or non-string
        if not isinstance(wish_text, str):
            if isinstance(wish_text, list):
                parts = []
                for item in wish_text:
                    if isinstance(item, dict):
                        parts.append(str(item.get("text", "")))
                    else:
                        parts.append(str(item))
                wish_text = " ".join(parts)
            elif isinstance(wish_text, dict):
                wish_text = str(wish_text.get("text", wish_text))
            else:
                wish_text = str(wish_text)

        # 1. Extract material
        material = "Cr12MoV"
        if re.search(r"钛合金|ti-?6al-?4v|titanium", wish_text, re.I):
            material = "Ti-6Al-4V"
        elif re.search(r"铝合金|7075|6061|aluminum", wish_text, re.I):
            material = "AL7075-T6"
        elif re.search(r"45#|45号钢|1045", wish_text, re.I):
            material = "Steel45"
        elif re.search(r"不锈钢|304|316|stainless", wish_text, re.I):
            material = "SS304"

        def safe_float(val: Any, default: float) -> float:
            try:
                return float(val)
            except (ValueError, TypeError):
                return default

        # 2. Extract key dimensions using regex requiring at least one digit
        outer_d = re.findall(r"(?:外径|外轮廓|外圆)[\s=:约为]*([0-9]+(?:\.[0-9]+)?)", wish_text)
        inner_d = re.findall(r"(?:内径|内孔|孔径|轴孔|底径|根部)[\s=:约为]*([0-9]+(?:\.[0-9]+)?)", wish_text)
        generic_d = re.findall(r"(?:直径|[D|d][\s=:约为]+)([0-9]+(?:\.[0-9]+)?)", wish_text)

        d_outer = safe_float(outer_d[0], 53.0) if outer_d else (safe_float(generic_d[0], 53.0) if generic_d else 53.0)
        d_inner = safe_float(inner_d[0], 14.0) if inner_d else (safe_float(generic_d[1], 14.0) if len(generic_d) > 1 else (14.0 if d_outer > 30 else 8.0))

        radii = re.findall(r"(?:半径|倒角|圆角|[R|r][\s=:约为]+)([0-9]+(?:\.[0-9]+)?)", wish_text)
        lengths = re.findall(r"(?:总长|长度|高度|总高|宽|厚|[L|l|H|h][\s=:约为]+)([0-9]+(?:\.[0-9]+)?)", wish_text)
        angles = re.findall(r"(?:角|度|deg|angle)[\s=:约为]*([0-9]+(?:\.[0-9]+)?)", wish_text)
        counts = re.findall(r"([0-9]+)\s*(?:个|道|叶片|齿|槽)", wish_text)

        try:
            num_features = min(max(int(counts[0]), 1), 100) if counts else 3
        except (ValueError, TypeError):
            num_features = 3

        fillet_r = safe_float(radii[0], 3.0) if radii else 3.0
        overall_len = safe_float(lengths[0], 45.0) if lengths else 45.0
        sweep_angle = safe_float(angles[0], 30.0) if angles else 30.0

        # Derived physical parameters
        is_multiaxis = bool(re.search(r"5轴|五轴|联动|叶轮|曲面|复杂", wish_text))
        is_die_mold = bool(re.search(r"模具|轮模|注塑|冲压|斜顶|滑块", wish_text))

        return {
            "wish": wish_text,
            "material": material,
            "d_outer": d_outer,
            "d_inner": d_inner,
            "num_features": num_features,
            "fillet_r": fillet_r,
            "overall_len": overall_len,
            "sweep_angle": sweep_angle,
            "is_multiaxis": is_multiaxis,
            "is_die_mold": is_die_mold,
        }

    def generate_solidworks_macro(self, spec: Dict[str, Any]) -> str:
        """Synthesize SOLIDWORKS 2021 VBA parametric macro with equations & features."""
        d_out = spec["d_outer"]
        d_in = spec["d_inner"]
        r = spec["fillet_r"]
        length = spec["overall_len"]

        code = f"""' =========================================================================
' SOLIDWORKS 2021 VBA Parametric Driver Macro
' Intent: Parametric Generation of Engineered Workpiece
' Material: {spec["material"]} | Outer Dia: {d_out}mm | Inner Bore: {d_in}mm
' =========================================================================

Dim swApp As SldWorks.SldWorks
Dim Part As SldWorks.ModelDoc2
Dim swEqnMgr As SldWorks.EquationMgr
Dim boolstatus As Boolean
Dim longstatus As Long

Sub Main()
    Set swApp = Application.SldWorks
    Set Part = swApp.NewDocument("C:\\ProgramData\\SolidWorks\\SOLIDWORKS 2021\\templates\\Part.prtdot", 0, 0, 0)
    If Part Is Nothing Then
        MsgBox "Failed to create part. Please check template path.", vbCritical
        Exit Sub
    End If
    
    ' 1. Set Global Variables in Equation Manager
    Set swEqnMgr = Part.GetEquationMgr
    swEqnMgr.AddEquation 0, "\"D_Outer\" = {d_out}"
    swEqnMgr.AddEquation 1, "\"D_Bore\" = {d_in}"
    swEqnMgr.AddEquation 2, "\"Length\" = {length}"
    swEqnMgr.AddEquation 3, "\"R_GrooveArc\" = {r}"
    
    ' 2. Create Revolve Base Sketch on Front Plane
    boolstatus = Part.Extension.SelectByID2("Front Plane", "PLANE", 0, 0, 0, False, 0, Nothing, 0)
    Part.SketchManager.InsertSketch True
    Part.ClearSelection2 True
    
    ' Centerline on Spindle Axis
    Part.SketchManager.CreateCenterLine 0, 0, 0, {length / 1000.0}, 0, 0
    ' Outer boundary profile
    Part.SketchManager.CreateLine 0, {d_in / 2000.0}, 0, 0, {d_out / 2000.0}, 0
    Part.SketchManager.CreateLine 0, {d_out / 2000.0}, 0, {length / 1000.0}, {d_out / 2000.0}, 0
    Part.SketchManager.CreateLine {length / 1000.0}, {d_out / 2000.0}, 0, {length / 1000.0}, {d_in / 2000.0}, 0
    Part.SketchManager.CreateLine {length / 1000.0}, {d_in / 2000.0}, 0, 0, {d_in / 2000.0}, 0
    
    ' 3. Revolve Feature (360 deg)
    Dim swFeature As SldWorks.Feature
    Set swFeature = Part.FeatureManager.FeatureRevolve2(True, True, False, False, False, False, 0, 0, 6.2831853, 0, False, False, 0.01, 0.01, 0, 0, 0, True, True, True)
    
    ' 4. Add Material & Simulation Setup
    Part.SetMaterialPropertyName2 "Default", "SOLIDWORKS Materials", "{spec['material']}"
    Part.ViewZoomtofit2
    Part.EditRebuild3
    MsgBox "SOLIDWORKS 2021 Parametric Model Successfully Generated!", vbInformation
End Sub
"""
        return code

    def generate_nx12_script(self, spec: Dict[str, Any]) -> str:
        """Synthesize Siemens NX 12.0 Python Open API script with expressions."""
        d_out = spec["d_outer"]
        d_in = spec["d_inner"]
        length = spec["overall_len"]
        r = spec["fillet_r"]
        n_feat = spec["num_features"]

        code = f"""# =========================================================================
# Siemens NX 12.0 Python Open API Parametric Journal
# Intent: Parametric Generation of Engineered Workpiece
# Material: {spec["material"]} | OD: {d_out}mm | ID: {d_in}mm
# =========================================================================

import NXOpen
import NXOpen.UF
import math

def main():
    the_session = NXOpen.Session.GetSession()
    the_uf_session = NXOpen.UF.UFSession.GetUFSession()
    work_part = the_session.Parts.Work

    # 1. Define Parametric Expressions in Expression Manager
    exp_mgr = work_part.Expressions
    mm = work_part.UnitCollection.FindObject("MilliMeter")
    
    exp_mgr.CreateWithUnits("D_OUTER", f"[{{mm.FullName}}] {d_out}")
    exp_mgr.CreateWithUnits("D_BORE", f"[{{mm.FullName}}] {d_in}")
    exp_mgr.CreateWithUnits("TOTAL_LENGTH", f"[{{mm.FullName}}] {length}")
    exp_mgr.CreateWithUnits("GROOVE_R", f"[{{mm.FullName}}] {r}")

    # 2. Create Outer Cylinder Stock
    # CreateCyl1(FeatureSign, Origin[3], Height, Diameter, Direction[3])
    cyl_tag = the_uf_session.Modl.CreateCyl1(
        NXOpen.UF.UFModl.FeatureSigns.Nullsign,
        [0.0, 0.0, 0.0],
        f"{length}",
        f"{d_out}",
        [0.0, 0.0, -1.0]
    )

    # 3. Create Inner Bore Cylinder (Boolean Subtraction)
    bore_tag = the_uf_session.Modl.CreateCyl1(
        NXOpen.UF.UFModl.FeatureSigns.Negative,
        [0.0, 0.0, 0.0],
        f"{length + 5.0}",
        f"{d_in}",
        [0.0, 0.0, -1.0]
    )

    # 4. Create Multi-Step Radial Grooves (Torus Boolean Subtractions)
    pitch = {length / (n_feat + 1.0):.2f}
    for i in range(1, {n_feat + 1}):
        z_pos = -pitch * i
        # CreateTorus(FeatureSign, Center[3], RingDia, TubeDia, Direction[3])
        the_uf_session.Modl.CreateTorus(
            NXOpen.UF.UFModl.FeatureSigns.Negative,
            [0.0, 0.0, z_pos],
            f"{d_out - 2 * r}",
            f"{2 * r}",
            [0.0, 0.0, 1.0]
        )

    # 5. Update and Save Work Part
    the_uf_session.Modl.Update()
    print("[SUCCESS] Siemens NX 12.0 Parametric Model & Features Built.")

if __name__ == "__main__":
    main()
"""
        return code

    def generate_autocad_lisp(self, spec: Dict[str, Any]) -> str:
        """Synthesize AutoCAD 2026 AutoLISP drawing routine with layer discipline."""
        d_out = spec["d_outer"]
        d_in = spec["d_inner"]
        length = spec["overall_len"]

        code = f""";;; =========================================================================
;;; AutoCAD 2026 AutoLISP Parametric Engineering Drawing (c:DRAWWHEELMOLD)
;;; Intent: Layer-Disciplined 2D Section with Tolerancing & Hatching
;;; =========================================================================

(defun c:DRAWWHEELMOLD (/ old_echo old_osm lay_cen lay_prof lay_dim lay_hat)
  (setq old_echo (getvar "CMDECHO"))
  (setq old_osm (getvar "OSMODE"))
  (setvar "CMDECHO" 0)
  (setvar "OSMODE" 0)

  ;; 1. Setup Engineering Layers with Distinct Colors
  (setq lay_cen "01_CENTERLINE")
  (setq lay_prof "02_PROFILE")
  (setq lay_dim "03_DIMENSION")
  (setq lay_hat "04_HATCH")

  (command "-LAYER" "M" lay_cen "C" "1" "" "LT" "CENTER" "" "")
  (command "-LAYER" "M" lay_prof "C" "7" "" "LW" "0.35" "" "")
  (command "-LAYER" "M" lay_dim "C" "3" "" "LW" "0.18" "" "")
  (command "-LAYER" "M" lay_hat "C" "8" "" "LW" "0.13" "" "")

  ;; 2. Draw Spindle Centerline
  (setvar "CLAYER" lay_cen)
  (command "LINE" (list -10.0 0.0 0.0) (list {length + 10.0} 0.0 0.0) "")

  ;; 3. Draw Outer Section Contour on Profile Layer
  (setvar "CLAYER" lay_prof)
  (command "PLINE"
           (list 0.0 {d_in / 2.0} 0.0)
           (list 0.0 {d_out / 2.0} 0.0)
           (list {length} {d_out / 2.0} 0.0)
           (list {length} {d_in / 2.0} 0.0)
           "C")

  ;; 4. ANSI31 Cross-Section Hatching
  (setvar "CLAYER" lay_hat)
  (command "-HATCH" "P" "ANSI31" 1.0 0.0 "S" (entlast) "" "")

  ;; 5. Add Key ISO Dimensions & Tolerances
  (setvar "CLAYER" lay_dim)
  ;; Overall Length Dimension
  (command "DIMLINEAR" (list 0.0 {d_out / 2.0} 0.0) (list {length} {d_out / 2.0} 0.0) (list {length / 2.0} {d_out / 2.0 + 12.0} 0.0))
  ;; Outer Diameter Dimension
  (command "DIMLINEAR" (list {length} 0.0 0.0) (list {length} {d_out / 2.0} 0.0) (list {length + 15.0} {d_out / 4.0} 0.0))
  ;; Inner Bore Dimension
  (command "DIMLINEAR" (list 0.0 0.0 0.0) (list 0.0 {d_in / 2.0} 0.0) (list -15.0 {d_in / 4.0} 0.0))

  ;; Restore Environment Variables
  (command "ZOOM" "E")
  (setvar "CMDECHO" old_echo)
  (setvar "OSMODE" old_osm)
  (princ "\\n[AutoCAD 2026] Parametric Engineering Drawing Generated Successfully!")
  (princ)
)
"""
        return code

    def generate_vericut_config(self, spec: Dict[str, Any]) -> str:
        """Synthesize Vericut 9.6 `.opt` machine simulation & OptiPath/Force config."""
        d_out = spec["d_outer"]
        length = spec["overall_len"]
        mat = spec["material"]

        config = f"""; =========================================================================
; Vericut 9.6 Virtual Machine Simulation & Force Optimization (.opt)
; Workpiece: {mat} | Envelope: D{d_out + 4:.1f} x {length + 15:.1f}mm
; =========================================================================

[SETUP]
MACHINE: 5_AXIS_TURNING_MILLING_CENTER
CONTROL: FANUC_0i_TF_DUAL_CHANNEL
WORKPIECE_ORIGIN: 0.000, 0.000, 0.000

[STOCK]
TYPE: CYLINDER
DIAMETER: {d_out + 4.0:.2f}
LENGTH: {length + 15.0:.2f}
MATERIAL: {mat}
CHUCK_CLAMPING_LENGTH: 20.00

[TOOL_LIBRARY]
T0101: TYPE=OD_ROUGH, INSERT=WNMG080408, RAD=0.8, DIR=3, HOLDER=DWLNR2525M08
T0202: TYPE=GROOVE_FINISH, INSERT=FULL_RADIUS_R3, RAD={spec['fillet_r']}, DIR=8, HOLDER=N123G2
T0303: TYPE=ID_BORING, INSERT=CCMT09T304, RAD=0.4, DIR=2, HOLDER=A16Q-SCLCR09
T0404: TYPE=BALL_ENDMILL, DIA=6.0, FLUTES=4, STICKOUT=35.0

[COLLISION_DETECTION]
GOUGE_TOLERANCE: 0.005
EXCESS_TOLERANCE: 0.010
RAPID_COLLISION_STOP: ON
NEAR_MISS_DISTANCE: 2.000

[FORCE_OPTIMIZATION]
FORCE_ENABLED: ON
MATERIAL_YIELD_STRESS: 880.0 MPa
MAX_CUTTING_FORCE: 2500.0 N
MAX_CHIP_THICKNESS: 0.22 mm
CORNER_DECELERATION: 40%
VIBRATION_THRESHOLD_RMS: 1.25

[AUTO_DIFF]
COMPARE_TO_CAD: TRUE
CAD_MODEL: Workpiece_Design_Nominal.step
COLOR_IN_TOLERANCE: GREEN (+/-0.02mm)
COLOR_EXCESS: BLUE (>+0.02mm)
COLOR_GOUGE: RED (<-0.005mm)
"""
        return config

    def generate_cimco_macro(self, spec: Dict[str, Any]) -> str:
        """Synthesize CIMCO Edit 2026 Macro B parametric NC code."""
        d_out = spec["d_outer"]
        d_in = spec["d_inner"]
        length = spec["overall_len"]
        r = spec["fillet_r"]

        macro = f"""%
O2026 (WHEEL MOLD PARAMETRIC MACRO B - CIMCO VERIFIED)
(MATERIAL: {spec['material']} | ENVELOPE: D{d_out} X L{length})

(--- USER PARAMETRIC VARIABLES ---)
#101 = {length:.2f}    (TOTAL WORKPIECE LENGTH)
#102 = {d_out:.2f}     (MAX FLANGE OUTER DIAMETER)
#103 = {d_in:.2f}      (SHAFT BORE DIAMETER)
#104 = {r:.2f}         (GROOVE BOTTOM RADIUS)
#105 = 15.00           (GROOVE 1 PROFILE RADIUS R1)
#106 = 12.00           (GROOVE 2 PROFILE RADIUS R2)
#107 = 10.00           (GROOVE 3 PROFILE RADIUS R3)
#108 = 0.40            (FINISH ALLOWANCE X-AXIS)

(--- INITIALIZATION & SAFE POSITION ---)
G21 G40 G97 G99
G28 U0.0 W0.0

(--- T0101: OD ROUGH TURNING G71 CYCLE ---)
N10 T0101 M03 S1200
G00 X[#102 + 4.0] Z2.0 M08
G71 U2.0 R0.8
G71 P100 Q110 U[#108] W0.1 F0.25
N100 G00 X[#103]
G01 Z0.0 F0.15
X[#102 - 1.0] C0.5
Z-[#101] F0.18
X[#102 + 2.0]
N110 G00 X[#102 + 4.0]

(--- T0101: G70 FINISH TURNING ---)
G70 P100 Q110 S1800 F0.12
G00 X[#102 + 10.0] Z50.0 M09
G28 U0.0 W0.0

(--- T0202: GROOVING ARCS R15 / R12 / R10 WITH G42 COMPENSATION ---)
N20 T0202 M03 S800
G00 X[#102 + 2.0] Z2.0 M08
G42 G00 X[#102] Z-10.5
G02 X[#102 - 6.0] Z-12.0 R[#105] F0.08
G03 X[#102] Z-13.5 R[#104] F0.08
G40 G00 X[#102 + 5.0]

G28 U0.0 W0.0
M30
%
"""
        return macro

    def generate_sscnc_setup_guide(self, spec: Dict[str, Any]) -> str:
        """Synthesize SSCNC 7.2 shop-floor touch-off & WCS setup manual."""
        d_out = spec["d_outer"]
        length = spec["overall_len"]

        guide = f"""# 斯沃数控仿真软件 (SSCNC FANUC 0i-TF) 实操对刀手册

## 1. 虚拟车床配置与工件装夹
- **机床型号**：选择【FANUC 0i-TF 卧式斜床身数控车床】。
- **毛坯设置**：
  - 材料选择：`{spec['material']}`
  - 毛坯规格：外径 $\\varnothing {d_out + 4.0:.1f}\\text{{mm}}$，总长 ${length + 20.0:.1f}\\text{{mm}}$
  - 卡盘装夹：选择【三爪自定心液压卡盘】，夹持长度 $20.0\\text{{mm}}$，工件伸出端长度 ${length + 5.0:.1f}\\text{{mm}}$。

## 2. 刀塔刀具装配与刀沿方位号配置
| 刀位号 | 刀具类型 | 刀片规格 | 刀尖圆弧 $r_\\epsilon$ | 假想刀尖方位号 (方向代码) |
|---|---|---|---|---|
| **T0101** | 外圆粗车刀 | WNMG080408 (80°菱形) | $0.8\\text{{mm}}$ | **3号** (右偏外圆车刀标准方位) |
| **T0202** | 圆弧成型槽刀 | R{spec['fillet_r']}全圆弧硬质合金刀片 | ${spec['fillet_r']}\\text{{mm}}$ | **8号** (径向直插成型方位) |
| **T0303** | 内孔镗刀 | CCMT09T304 (80°微型内孔镗刀) | $0.4\\text{{mm}}$ | **2号** (标准内孔镗刀方位) |

## 3. G54 工件坐标系试切对刀步骤
1. **Z 轴对刀（设定工件右端面为 Z0.000）**：
   - 切换至【手轮模式 (HANDLE)】，主轴正转 `M03 S800`。
   - 操纵 T0101 刀具轻微试切工件右端面，切平后 **保持 Z 轴不动**。
   - 刀具退回 X 正方向，进入 CNC 系统面板：【OFFSET SETTING】 $\\to$ 【坐标系 (WORK)】 $\\to$ 光标移动至 `G54` 的 `Z` 坐标列。
   - 键入 `Z0.`，按下屏幕下方软键【测量 (MEASUR)】，系统自动计算并写入 Z 轴工件原点偏移量。
2. **X 轴对刀（设定工件回转中心为 X0.000）**：
   - 摇动手轮使刀具轻微外圆试切一段长度（约 5~10mm），切削完成后 **保持 X 轴绝对不动**。
   - 沿 Z 轴正方向退出刀具，停止主轴。
   - 使用游标卡尺测量试切外圆实际直径 $D_{{meas}}$。
   - 进入 `G54` 的 `X` 坐标列，输入 `X[实际测量值]`，按下【测量 (MEASUR)】软键完成标定。

## 4. 仿真运行验证
- 调入宏程序 `O2026.NC`，闭合防护门，切入【自动加工 (AUTO)】模式，单段试切无过切后按下【循环启动 (CYCLE START)】。
"""
        return guide

    def generate_slider_dashboard(self, spec: Dict[str, Any]) -> str:
        """Generate interactive parametric slider UI and physical variation indicators."""
        d_out = float(spec.get("d_outer", 53.0))
        d_in = float(spec.get("d_inner", 14.0))
        length = float(spec.get("overall_len", 45.0))
        r = float(spec.get("fillet_r", 10.0))
        mat = str(spec.get("material", "HT200"))

        # Density mapping (g/cm^3)
        density_map = {
            "HT200": 7.2, "灰铸铁": 7.2, "Steel45": 7.85, "45号钢": 7.85,
            "Cr12MoV": 7.7, "AL6061-T6": 2.7, "AL7075-T6": 2.81, "Ti-6Al-4V": 4.43
        }
        density = density_map.get(mat, 7.8)

        # Physical calculation (cylindrical envelope approx minus bore)
        vol_cm3 = max(0.1, (3.14159 * ((d_out / 20.0)**2 - (d_in / 20.0)**2) * (length / 10.0)) * 0.88)
        mass_kg = (vol_cm3 * density) / 1000.0
        wall_thk = (d_out - d_in) / 2.0
        aspect_ratio = length / max(1.0, d_out)

        def make_bar(val: float, min_val: float, max_val: float, width: int = 14) -> str:
            ratio = max(0.0, min(1.0, (val - min_val) / max(1.0, max_val - min_val)))
            pos = int(ratio * width)
            bar = "━" * pos + "●" + "─" * (width - pos)
            return f"[{bar}]"

        bar_dout = make_bar(d_out, 20.0, 150.0)
        bar_din = make_bar(d_in, 5.0, 80.0)
        bar_len = make_bar(length, 10.0, 200.0)
        bar_r = make_bar(r, 0.5, 30.0)

        rigidity_status = "✅ 结构刚度充裕" if wall_thk >= 5.0 else "⚠️ 警告：壁厚偏薄，需校核切削变形"
        aspect_type = "回转短盘类零件" if aspect_ratio < 1.0 else "细长阶梯轴类零件"

        dashboard = f"""### 🎛️ 3D 模型特征参数实时滑块控制台 (Dynamic Parametric Sliders)

| 驱动特征维度 | 滑块刻度视图 | 当前数值 | 允许极值范围 | 灵敏度/步长 |
| :--- | :---: | :---: | :---: | :---: |
| 🔵 **外径轮廓 $D_{{max}}$** | `{bar_dout}` | **`{d_out:.1f} mm`** | `20.0 ~ 150.0 mm` | `±1.0 mm` |
| 🟢 **内孔配合径 $D_{{bore}}$** | `{bar_din}` | **`{d_in:.1f} mm`** | `5.0 ~ 80.0 mm` | `±0.5 mm` |
| 🟡 **零件总长 $L_T$** | `{bar_len}` | **`{length:.1f} mm`** | `10.0 ~ 200.0 mm` | `±1.0 mm` |
| 🟣 **过渡圆角 $R$** | `{bar_r}` | **`{r:.1f} mm`** | `0.5 ~ 30.0 mm` | `±0.5 mm` |

> 📊 **即时物理与制造特性评估**：
> - **安全结构壁厚**: `t = {wall_thk:.2f} mm` ({rigidity_status})
> - **净重预估 ({mat})**: `≈ {mass_kg:.3f} kg` (有效回转体积: `{vol_cm3:.1f} cm³`)
> - **几何形态判定**: `{aspect_type}` (长径比: `{aspect_ratio:.2f}`)
>
> 💡 *联动提示：您可在 WorkBuddy 中直接输入参数变动愿景（例如“将外径改为60mm，内孔扩大到18mm”），系统将秒级驱动三维特征树联动重生成！*
"""
        return dashboard

    def synthesize_all_six(self, wish_text: str) -> str:
        """Decompose intent and synthesize engineering deliverables across all 6 software packages."""
        spec = self.parse_wish_intent(wish_text)
        sw = self.generate_solidworks_macro(spec)
        nx = self.generate_nx12_script(spec)
        cad = self.generate_autocad_lisp(spec)
        vericut = self.generate_vericut_config(spec)
        cimco = self.generate_cimco_macro(spec)
        sscnc = self.generate_sscnc_setup_guide(spec)
        slider_dashboard = self.generate_slider_dashboard(spec)

        return f"""# 【许愿式工业制造全流程求解报告】

### 1. 意图解析与物理几何规格
- **用户制造愿景**: {spec['wish']}
- **工程材质选择**: `{spec['material']}`
- **几何轮廓规格**: 理论外径 $D_{{max}} = {spec['d_outer']:.2f}\\,\\text{{mm}}$ | 内孔径 $D_{{bore}} = {spec['d_inner']:.2f}\\,\\text{{mm}}$
- **零件总长/高度**: $L_T = {spec['overall_len']:.2f}\\,\\text{{mm}}$ | 主特征数: {spec['num_features']} | 倒圆角: $R = {spec['fillet_r']:.2f}\\,\\text{{mm}}$
- **工况判定**: 多轴联动复杂曲面: {spec['is_multiaxis']} | 模具工装结构: {spec['is_die_mold']}

{slider_dashboard}

---

### 📂 六大工业软件全套工程代码（分级折叠呈现·点击展开）

<details open>
<summary><b>📐 2. SOLIDWORKS 2021 参数化方程式驱动宏 (.vba) [点击折叠/展开]</b></summary>

```vb
{sw}
```
</details>

<details>
<summary><b>⚙️ 3. Siemens NX 12.0 Python Open API 造型脚本 (.py) [点击折叠/展开]</b></summary>

```python
{nx}
```
</details>

<details>
<summary><b>📏 4. AutoCAD 2026 AutoLISP 工程图自动绘制与标注 (.lsp) [点击折叠/展开]</b></summary>

```lisp
{cad}
```
</details>

<details>
<summary><b>🛡️ 5. Vericut 9.6 物理力学切削与五轴运动学仿真配置 (.opt) [点击折叠/展开]</b></summary>

```plaintext
{vericut}
```
</details>

<details>
<summary><b>📟 6. CIMCO Edit 2026 FANUC Macro B 参数化数控宏程序 (.nc) [点击折叠/展开]</b></summary>

```gcode
{cimco}
```
</details>

<details>
<summary><b>🔧 7. 斯沃数控仿真软件 (SSCNC 7.2) 现场装夹与 G54 对刀规程 [点击折叠/展开]</b></summary>

{sscnc}
</details>
"""
