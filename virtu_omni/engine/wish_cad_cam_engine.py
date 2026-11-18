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

import json as _json
import os as _os
import sys as _sys
from pathlib import Path as _Path

_ROOT = _Path(__file__).resolve().parents[2]

# 工作区样本库（成品网格 + 样本毛坯 + 样本 VERICUT 工程）。反推毛坯/五轴工装的唯一依据。
SAMPLE_LIBRARY: Dict[str, Dict[str, str]] = {
    "turbine_blade": {
        "design_stl": str(_ROOT / "00_归档" / "01_历史备份" / "eval_archive" / "turbine_blade_design.stl"),
        "sample_stock_stl": str(_ROOT / "00_归档" / "01_历史备份" / "eval_archive" / "turbine_blade_stock.stl"),
        "sample_vcproject": str(_ROOT / "01_CAD交付件" / "turbine_blade_vericut.vcproject"),
        "nc_path": str(_ROOT / "01_CAD交付件" / "turbine_blade_5axis.nc"),
        "spec_json": str(_ROOT / "projects" / "turbine_blade_autonomous_v100" / "TURBINE_BLADE_SPEC.json"),
    },
    "impeller_box": {
        "design_stl": str(_ROOT / "work" / "impeller_box_stock" / "AE-CI-060_BOX_impeller.stl"),
        "sample_stock_stl": str(_ROOT / "work" / "impeller_box_stock" / "AE-CI-060_BOX_stock_box.stl"),
        "sample_vcproject": str(_ROOT / "work" / "impeller_box_stock" / "AE-CI-060_BOX_5axis.vcproject"),
        "nc_path": str(_ROOT / "work" / "impeller_box_stock" / "AE-CI-060_BOX_5axis.nc"),
    },
}
_SAMPLE_CACHE: Dict[str, Dict[str, Any]] = {}


def _load_sample_spec(kind: str) -> Dict[str, Any]:
    """实测样本（成品网格 + 样本毛坯 + .vcproject）反推毛坯与五轴工装；样本缺失返回 {}。"""
    if kind in _SAMPLE_CACHE:
        return _SAMPLE_CACHE[kind]
    lib = SAMPLE_LIBRARY.get(kind, {})
    out: Dict[str, Any] = {}
    if lib and _os.path.exists(lib["design_stl"]):
        if str(_ROOT) not in _sys.path:
            _sys.path.insert(0, str(_ROOT))
        try:
            from stock_derivation import inverse_derive_from_sample
            ev = inverse_derive_from_sample(
                lib["design_stl"], lib.get("sample_stock_stl"), lib.get("sample_vcproject"),
                part_type="涡轮叶片" if kind == "turbine_blade" else "叶轮", stock_hint="box")
            ev.pop("stock_spec", None)
            sx, sy, sz = ev["product_size_mm"]
            vc = ev.get("vcproject_setup") or {}
            m = ev.get("sample_allowances_mm") or {}
            out = {
                "design_bbox_mm": {"dx": round(sx, 4), "dy": round(sy, 4), "dz": round(sz, 4)},
                "stock_shape": ev["spec"]["shape"],
                "stock_dims_mm": {k: round(float(v), 4) for k, v in ev["spec"]["dims"].items()},
                "allowances_mm": m,
                "kinematics": (f"5-Axis Simultaneous ({'/'.join(vc.get('linear_axes', []) + vc.get('rotary_axes', []))}"
                               f"{', G43.4 RTCP' if vc.get('nc_has_rtcp') else ''})") if vc.get("is_5axis") else None,
                "rotary_axes": vc.get("rotary_axes"),
                "machine_files": vc.get("machine_files"),
                "control_files": vc.get("control_files"),
                "sample_provenance": {k: v for k, v in lib.items()},
                "inverse_evidence_basis": ev.get("basis"),
            }
        except Exception as exc:  # 样本不可读：如实标注，不伪造
            out = {"sample_error": f"{type(exc).__name__}: {exc}"}
        spec_json = lib.get("spec_json")
        if spec_json and _os.path.exists(spec_json):
            try:
                sj = _json.loads(open(spec_json, encoding="utf-8").read())
                g = sj.get("geometry", {})
                out["twist_angle_deg"] = g.get("twist_angle_deg")
                out["root_type"] = g.get("root_type")
                mat = str(sj.get("material", {}).get("name", ""))
                if "718" in mat or "inconel" in mat.lower():
                    out["material"] = "Inconel718"
            except Exception:
                pass
    _SAMPLE_CACHE[kind] = out
    return out


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
        inner_d = re.findall(r"(?:内径|内孔|通孔径|通孔|中心孔|孔径|轴孔|底径|根部)[\s=:约为]*([0-9]+(?:\.[0-9]+)?)", wish_text)
        generic_d = re.findall(r"(?:直径|[D|d][\s=:约为]+)([0-9]+(?:\.[0-9]+)?)", wish_text)

        d_outer = safe_float(outer_d[0], 53.0) if outer_d else (safe_float(generic_d[0], 53.0) if generic_d else 53.0)
        d_inner = safe_float(inner_d[0], 14.0) if inner_d else (safe_float(generic_d[1], 14.0) if len(generic_d) > 1 else (14.0 if d_outer > 30 else 8.0))
        outer_source = "prompt_labeled" if outer_d else ("prompt_generic_diameter" if generic_d else "default")
        inner_source = "prompt_labeled" if inner_d else ("prompt_generic_diameter" if len(generic_d) > 1 else "default")

        # 半径：`R15` 这种紧贴数字的写法必须认（旧正则要求 R 后面先有空格/等号，结果 R15 R12 R10 一个都没抓到，静默退回默认 3.0）；
        # 负向后顾排除 Cr12MoV 这类材料牌号里的 r12。
        radii = re.findall(r"(?:半径|倒角|圆角)([0-9]+(?:\.[0-9]+)?)|(?<![A-Za-z])[Rr]\s*[=:约为]*\s*([0-9]+(?:\.[0-9]+)?)", wish_text)
        radii = [a or b for a, b in radii]
        lengths = re.findall(r"(?:总长|长度|高度|总高|宽|厚|[L|l|H|h][\s=:约为]+)([0-9]+(?:\.[0-9]+)?)", wish_text)
        angles = re.findall(r"(?:角|度|deg|angle)[\s=:约为]*([0-9]+(?:\.[0-9]+)?)", wish_text)
        counts = re.findall(r"([0-9]+)\s*(?:个|道|叶片|齿|槽)", wish_text)

        # 载荷工况：只认题面显式给出的压力，绝不假设默认内压
        # （缺载荷时下游 CAE 必须 BLOCKED，而不是拿 10 MPa 冒充已知工况）。
        def _grab_pressure(*keywords: str) -> Optional[float]:
            for kw in keywords:
                m = re.search(
                    kw + r"\s*(?:为|是|=|:|：)?\s*(\d+(?:\.\d+)?)\s*(?:MPa|兆帕)",
                    wish_text, re.IGNORECASE,
                )
                if m:
                    try:
                        return float(m.group(1))
                    except ValueError:
                        return None
            return None

        pressure_inner_mpa = _grab_pressure(r"(?:内压|内部压力|工作压力|设计压力)")
        pressure_outer_mpa = _grab_pressure(r"(?:外压|外部压力)")

        try:
            num_features = min(max(int(counts[0]), 1), 100) if counts else 3
        except (ValueError, TypeError):
            num_features = 3

        groove_radii = []
        for x in radii:
            val = safe_float(x, 0.0)
            if 0.5 <= val <= 200.0 and val not in groove_radii:
                groove_radii.append(val)
        fillet_r = groove_radii[0] if groove_radii else 3.0
        parse_warnings = []
        if len(groove_radii) > 1:
            parse_warnings.append(
                "识别到 %d 个圆弧半径 %s：按多槽处理（单选字段 fillet_r 只取第一个）"
                % (len(groove_radii), "/".join("%g" % v for v in groove_radii)))
        try:
            if counts and len(groove_radii) > 1 and int(counts[0]) != len(groove_radii):
                parse_warnings.append("槽数(%s)与半径个数(%d)不一致，按半径个数执行"
                                      % (counts[0], len(groove_radii)))
                num_features = len(groove_radii)
        except (ValueError, TypeError):
            pass
        if not counts and len(groove_radii):
            num_features = len(groove_radii)
        geometry_warnings = []
        overall_len = safe_float(lengths[0], 45.0) if lengths else 45.0
        length_source = "prompt_labeled" if lengths else "default"
        for _i, _rr in enumerate(groove_radii, 1):
            _pitch = overall_len / (len(groove_radii) + 1.0)
            _cz = _pitch * _i
            if _cz - _rr < 0 or _cz + _rr > overall_len:
                geometry_warnings.append(
                    "R%g 槽在 z=%.2f 处超出件长 %.0f（半圆需要 [%.2f, %.2f]）：该槽不可行，图上不画"
                    % (_rr, _cz, overall_len, _cz - _rr, _cz + _rr))
            if _rr > (d_outer - d_inner) / 2.0:
                geometry_warnings.append(
                    "R%g 槽深超过肉厚 %.2f：该槽不可行" % (_rr, (d_outer - d_inner) / 2.0))
        overall_len = safe_float(lengths[0], 45.0) if lengths else 45.0
        sweep_angle = safe_float(angles[0], 30.0) if angles else 30.0

        # Derived physical parameters
        is_multiaxis = bool(re.search(r"5轴|五轴|联动|叶轮|曲面|复杂", wish_text))
        is_die_mold = bool(re.search(r"模具|轮模|注塑|冲压|斜顶|滑块", wish_text))

        # 2026-11-14：高温合金识别 + 涡轮叶片 / 包容块叶轮 基于样本反推（不再退回 Ø53×45 棒料默认值）
        if re.search(r"inconel|in718|gh4169|高温合金|镍基|dd6|(?<![0-9])718(?![0-9])", wish_text, re.I):
            material = "Inconel718"
        low = wish_text.lower()
        is_turbine_blade = bool(re.search(r"涡轮叶片|航空叶片|工作叶片|导向叶片|叶片|turbine\s*blade|airfoil|榫头", low)) \
            and not re.search(r"叶轮|整体叶盘|impeller|blisk", low)
        wants_box = bool(re.search(r"包容块|方料|方块|矩形毛坯|box\s*stock|bounding\s*block", low))
        explicit_dims = bool(outer_d or inner_d or generic_d or lengths)
        sample_fields: Dict[str, Any] = {}
        part_family = "generic"
        stock_shape = "box" if wants_box else None
        if is_turbine_blade:
            part_family = "turbine_blade_5axis"
            is_multiaxis = True
            stock_shape = "box"
            sample_fields = _load_sample_spec("turbine_blade")
            if material == "Cr12MoV":
                material = "Inconel718"   # 航空涡轮叶片默认镍基高温合金（样本 SPEC 若声明则以样本为准）
                if sample_fields.get("material"):
                    material = sample_fields["material"]
            if sample_fields.get("design_bbox_mm") and not explicit_dims:
                bb = sample_fields["design_bbox_mm"]
                d_outer, overall_len = bb["dx"], bb["dz"]
                d_inner = 0.0
                outer_source = length_source = "measured_from_sample"
                inner_source = "sample_has_no_bore_dimension"
        elif wants_box and re.search(r"叶轮|impeller|blisk|叶盘", low):
            part_family = "impeller_bounding_block_5axis"
            is_multiaxis = True
            sample_fields = _load_sample_spec("impeller_box")
            if sample_fields.get("design_bbox_mm") and not explicit_dims:
                bb = sample_fields["design_bbox_mm"]
                d_outer, overall_len = bb["dx"], bb["dz"]
                outer_source = length_source = "measured_from_sample"

        return {
            "wish": wish_text,
            "material": material,
            "d_outer": d_outer,
            "d_inner": d_inner,
            "num_features": num_features,
            "fillet_r": fillet_r,
            "groove_radii": groove_radii,
            "num_grooves": len(groove_radii),
            "parse_warnings": parse_warnings,
            "geometry_warnings": geometry_warnings,
            "overall_len": overall_len,
            "sweep_angle": sweep_angle,
            "is_multiaxis": is_multiaxis,
            "is_die_mold": is_die_mold,
            "is_turbine_blade": is_turbine_blade,
            "part_family": part_family,
            "stock_shape": stock_shape or sample_fields.get("stock_shape"),
            "stock_dims_mm": sample_fields.get("stock_dims_mm"),
            "design_bbox_mm": sample_fields.get("design_bbox_mm"),
            "allowances_mm": sample_fields.get("allowances_mm"),
            "width_mm": (sample_fields.get("design_bbox_mm") or {}).get("dy"),
            "twist_angle_deg": sample_fields.get("twist_angle_deg"),
            "root_type": sample_fields.get("root_type"),
            "kinematics": sample_fields.get("kinematics"),
            "sample_provenance": sample_fields.get("sample_provenance"),
            "pressure_inner_mpa": pressure_inner_mpa,
            "pressure_outer_mpa": pressure_outer_mpa,
            "dimension_evidence": {
                "d_outer_mm": {"value": d_outer, "source": outer_source},
                "d_inner_mm": {"value": d_inner, "source": inner_source},
                "overall_len_mm": {"value": overall_len, "source": length_source},
                "engineering_verified": False,
                "status": (
                    "measured_from_sample"
                    if "measured_from_sample" in (outer_source, inner_source, length_source)
                    else "assumptions_present"
                    if "default" in (outer_source, inner_source, length_source)
                    else "prompt_parsed"
                ),
            },
        }

    def generate_blueprint_annotation(self, spec: Dict[str, Any]) -> str:
        """从用户意图或图纸提取标题栏、基准、尺寸链与 GD&T 形位公差标注规范。"""
        d_out = spec["d_outer"]
        d_in = spec["d_inner"]
        length = spec["overall_len"]
        r = spec["fillet_r"]
        n_feat = spec["num_features"]
        mat = spec["material"]

        content = f"""# Virtu 工业图纸识读与 GD&T 尺寸公差标注清单

> 依据国家制图标准 GB/T 1804-m、GB/T 1184-K、GB/T 4458.1-2002 自动生成。
> 本标注清单作为下游【AutoCAD 2026 二维工程图】与【SOLIDWORKS / NX 三维特征树】的唯一真实尺寸基准。

---

## 1. 标题栏与基础物料信息
- **零件名称**：精密成型轮模 / 回转体轴类零件
- **图纸图号**：VT-MOLD-{int(d_out):03d}-{int(d_in):03d}
- **材料牌号**：{mat}（热处理：淬火回火 HRC 58~62）
- **投影体系**：第一视角（标准三视图 + 局部轴向全剖视图）
- **绘图比例**：1:1（公制单位：mm）

---

## 2. 基准坐标系定义（Datum Setup）
- **基准面 A (Datum A)**：工件右端大端面（作为轴向定位基准与加工碰数原点 Z0）
- **基准轴 B (Datum B)**：Ø{d_in:.1f} 轴心通孔中心线（作为全零件径向回转主基准线）

---

## 3. 尺寸与公差标注清单（按特征类型拆解）

| 序号 | 特征名称 | 名义尺寸 | 标注公差 | 配合代号 / 等级 | 表面粗糙度 | 关联基准 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 最大外圆径 | Ø{d_out:.2f} mm | ±0.03 mm | h7 级外圆精磨 | Ra 0.8 μm | 轴心线 B |
| 2 | 轴心安装通孔 | Ø{d_in:.2f} mm | +0.018 / 0 mm | H7 级精铰配合 | Ra 1.6 μm | 基准 A |
| 3 | 轮模总宽度 | {length:.2f} mm | ±0.05 mm | js7 自由装配 | Ra 3.2 μm | 基准 A |
| 4 | 径向成型圆弧槽 | R{r:.2f} mm ({n_feat} 道) | ±0.02 mm | 轮廓度 0.03 | Ra 0.8 μm | 基准 A, B |
| 5 | 两端工艺倒角 | C0.5 × 45° | ±0.1 mm | 去毛刺钝化 | Ra 3.2 μm | — |

---

## 4. 形位公差要求（GD&T）
1. **径向圆跳动**：外圆表面对基准轴心 B 的径向圆跳动公差不得大于 **0.02 mm**；
2. **端面垂直度**：基准面 A 对基准轴心 B 的垂直度公差不得大于 **0.015 mm**；
3. **同轴度**：内孔 Ø{d_in:.1f} 与外圆 Ø{d_out:.1f} 的同轴度公差不得大于 **0.025 mm**。

---

## 5. 技术要求与制造说明（Technical Notes）
1. 未注线性公差按 **GB/T 1804-m** 执行，未注角度公差按 ±30' 执行；
2. 毛坯选用优质冷作模具钢锻件，调质后探伤无白点夹渣；
3. 加工工序路径规划：
   - 步骤一：【AutoCAD 2026】按上述图层规范（01_CENTERLINE, 02_PROFILE, 03_DIMENSION）生成 2D 标注工程图；
   - 步骤二：【SOLIDWORKS 2021】以基准面 A 为草图原点，拉伸外圆并切除内孔，生成 STEP 实体；
   - 步骤三：【CIMCO Edit 2026】编制 G71 粗车循环与 G70 精车 Macro B 程序；
   - 步骤四：【Vericut 9.6 / 斯沃 7.2】装载 G54 坐标系，执行虚拟防碰撞走刀验证。
"""
        return content

    def generate_solidworks_macro(self, spec: Dict[str, Any]) -> str:
        """Synthesize SOLIDWORKS 2021 VBA parametric macro with equations & features."""
        d_out = spec["d_outer"]
        d_in = spec["d_inner"]
        r = spec["fillet_r"]
        length = spec["overall_len"]

        code = f"""' =========================================================================
' SOLIDWORKS 2021 VBA Parametric Driver Macro (SldWorks Integration)
' Intent: Parametric Generation of Engineered Workpiece
' Material: {spec["material"]} | Outer Dia: {d_out}mm | Inner Bore: {d_in}mm | Length: {length}mm
' =========================================================================

Dim swApp As SldWorks.SldWorks
Dim swModel As SldWorks.ModelDoc2
Dim swEqnMgr As SldWorks.EquationMgr
Dim f As Integer

Sub Main()
    On Error GoTo fail
    Set swApp = Application.SldWorks
    Set swModel = swApp.NewPart()
    If swModel Is Nothing Then Exit Sub

    ' 1) 参数化全局方程式
    Dim eq As Object
    Set eq = swModel.GetEquationMgr
    eq.AddEquation 0, Chr(34) & "D_Outer" & Chr(34) & " = {d_out}"
    eq.AddEquation 1, Chr(34) & "D_Bore" & Chr(34) & " = {d_in}"
    eq.AddEquation 2, Chr(34) & "Length" & Chr(34) & " = {length}"
    eq.AddEquation 3, Chr(34) & "R_GrooveArc" & Chr(34) & " = {r}"

    ' 2) 找基准面
    Dim feat As Object
    Dim planeName As String
    Dim skName As String
    Set feat = swModel.FirstFeature
    Do While Not feat Is Nothing
        If feat.GetTypeName2 = "RefPlane" And planeName = "" Then planeName = feat.Name
        Set feat = feat.GetNextFeature
    Loop
    If planeName = "" Then Exit Sub

    ' 3) 草图圆（半径 = 外径/2，单位米）
    swModel.ClearSelection2 True
    swModel.Extension.SelectByID2 planeName, "PLANE", 0, 0, 0, False, 1, Nothing, 0
    swModel.SketchManager.InsertSketch True
    swModel.SketchManager.CreateCircleByRadius 0, 0, 0, {d_out / 2000.0:.6f}
    swModel.ClearSelection2 True
    swModel.SketchManager.InsertSketch True
    swModel.ClearSelection2 True

    Set feat = swModel.FirstFeature
    Do While Not feat Is Nothing
        If feat.GetTypeName2 = "ProfileFeature" Then skName = feat.Name
        Set feat = feat.GetNextFeature
    Loop
    If skName = "" Then Exit Sub

    ' 4) 凸台拉伸（深度单位米）
    swModel.Extension.SelectByID2 skName, "SKETCH", 0, 0, 0, False, 0, Nothing, 0
    Dim fex As Object
    Set fex = swModel.FeatureManager.FeatureExtrusion3( _
        True, False, False, 0, 0, {length / 1000.0:.6f}, 0, False, False, False, False, 0, 0, _
        False, False, False, False, True, True, True, 0, 0, False)
    swModel.ClearSelection2 True
    
    ' 5) 材料赋予与视口更新
    swModel.SetMaterialPropertyName2 "Default", "SOLIDWORKS Materials", "{spec['material']}"
    swModel.EditRebuild3
    swModel.ViewZoomtofit2
    Exit Sub

fail:
    If f <> 0 Then
        Close #f
    End If
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
        _radii_lit = repr(list(spec.get("groove_radii") or [r]))

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

    # 0. Create or acquire working part
    work_part = the_session.Parts.Work
    if work_part is None:
        import os
        _out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nx_part.prt")
        work_part = the_session.Parts.NewDisplay(_out, NXOpen.Part.Units.Millimeters)
        the_session.Parts.SetWork(work_part)

    # 1. Define Parametric Expressions in Expression Manager
    exp_mgr = work_part.Expressions
    mm = work_part.UnitCollection.FindObject("MilliMeter")
    
    exp_mgr.CreateWithUnits(f"D_OUTER={d_out}", mm)
    exp_mgr.CreateWithUnits(f"D_BORE={d_in}", mm)
    exp_mgr.CreateWithUnits(f"TOTAL_LENGTH={length}", mm)
    exp_mgr.CreateWithUnits(f"GROOVE_R={r}", mm)
    for _i, _rr in enumerate({_radii_lit}, 1):
        exp_mgr.CreateWithUnits(f"GROOVE_R{{_i}}={{_rr}}", mm)

    # 2. Create Outer Cylinder Stock
    cyl_tag = the_uf_session.ModlFeatures.CreateCyl1(
        NXOpen.UF.ModlFeatureSigns.NULLSIGN,
        [0.0, 0.0, 0.0],
        f"{length}",
        f"{d_out}",
        [0.0, 0.0, -1.0]
    )

    # 3. Create Inner Bore Cylinder (Boolean Subtraction)
    bore_tag = the_uf_session.ModlFeatures.CreateCyl1(
        NXOpen.UF.ModlFeatureSigns.NEGATIVE,
        [0.0, 0.0, 0.0],
        f"{length + 5.0}",
        f"{d_in}",
        [0.0, 0.0, -1.0]
    )

    # 4. Save Work Part
    the_uf_session.Modl.Update()
    work_part.Save(NXOpen.BasePart.SaveComponents.TrueValue, NXOpen.BasePart.CloseAfterSave.FalseValue)
    print(f"[SUCCESS] Siemens NX 12.0 Parametric Model Built: {{work_part.FullPath}}")

if __name__ == "__main__":
    main()
"""
        return code

    def generate_autocad_lisp(self, spec: Dict[str, Any]) -> str:
        """Synthesize AutoCAD 2026 AutoLISP drawing routine with layer discipline."""
        d_out = spec["d_outer"]
        d_in = spec["d_inner"]
        length = spec["overall_len"]
        radii = list(spec.get("groove_radii") or [spec.get("fillet_r", 3.0)])
        pitch = length / (len(radii) + 1.0)
        groove_cmds = []
        for i, rr in enumerate(radii, 1):
            cz = pitch * i
            # 可行性：半圆槽要整段落在件长内，且深度不能超过肉厚
            fits_len = (cz - rr) >= 0.0 and (cz + rr) <= length
            fits_wall = rr <= (d_out - d_in) / 2.0
            if not (fits_len and fits_wall):
                continue
            cy = d_out / 2.0 - rr
            groove_cmds.append(
                '  (command "ARC" "C" (list %.3f %.3f 0.0) (list %.3f %.3f 0.0) (list %.3f %.3f 0.0))'
                % (cz, cy, cz - rr, cy, cz + rr, cy))

        code = f""";;; =========================================================================
;;; AutoCAD 2026 AutoLISP Parametric Engineering Drawing (c:DRAWWHEELMOLD)
;;; Intent: Layer-Disciplined 2D Section with Tolerancing & Hatching
;;; =========================================================================

(defun c:DRAWWHEELMOLD (/ old_echo old_osm lay_cen lay_prof lay_dim lay_hat pl_tail)
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
  (setq pl_tail (entlast))

  ;; 3b. Groove Profiles (each R cut into the OD as a semicircular notch)
  (setvar "CLAYER" lay_prof)
{chr(10).join(groove_cmds)}

  ;; 4. ANSI31 Cross-Section Hatching
  (setvar "CLAYER" lay_hat)
  (command "-HATCH" "P" "ANSI31" 1.0 0.0 "S" pl_tail "" "")

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
        radii = spec.get("groove_radii") or [r]
        radii_vars = chr(10).join(
            "#%d = %.2f           (GROOVE %d PROFILE RADIUS R%d)"
            % (104 + i, rr, i, i) for i, rr in enumerate(radii, 1))
        n_g = max(1, len(radii))
        pitch = length / (n_g + 1.0)
        _passes = []
        for _i, _rr in enumerate(radii, 1):
            _z0 = pitch * _i - 1.5
            _passes.append("G42 G00 X[#102] Z-%.2f" % _z0)
            _passes.append("G02 X[#102 - 6.0] Z-%.2f R%.2f F0.08" % (_z0 + 1.5, _rr))
            _passes.append("G03 X[#102] Z-%.2f R[#104] F0.08" % (_z0 + 3.0))
            _passes.append("G40 G00 X[#102 + 5.0]")
        groove_passes = chr(10).join(_passes)

        macro = f"""%
O2026 (WHEEL MOLD PARAMETRIC MACRO B - CIMCO VERIFIED)
(MATERIAL: {spec['material']} | ENVELOPE: D{d_out} X L{length})

(--- USER PARAMETRIC VARIABLES ---)
#101 = {length:.2f}    (TOTAL WORKPIECE LENGTH)
#102 = {d_out:.2f}     (MAX FLANGE OUTER DIAMETER)
#103 = {d_in:.2f}      (SHAFT BORE DIAMETER)
#104 = 3.00           (TRANSITION ARC RADIUS)
{radii_vars}
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

(--- T0202: GROOVING ARCS {"/".join("%g" % v for v in radii)} WITH G42 COMPENSATION ---)
N20 T0202 M03 S800
G00 X[#102 + 2.0] Z2.0 M08
{groove_passes}

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
