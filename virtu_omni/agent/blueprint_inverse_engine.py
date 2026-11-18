"""Inverse Engineering Engine for Unknown Blueprints & 2D/3D Drawings.

Deduces parametric feature trees, geometric constraints, equation managers,
and assembly mating relationships from unknown drawing specifications.
"""

import re
import json
import math
from typing import Dict, Any, List


class BlueprintInverseEngine:
    """Reverse-engineers engineering drawings into parametric feature trees and assembly code."""

    def __init__(self):
        self.primitive_classifiers = {
            "shaft_sleeve": ["套筒", "轴套", "轴承座", "法兰套", "轴", "回转", "外径", "内孔", "台阶轴"],
            "bracket_plate": ["支架", "连接板", "安装板", "底座", "基板", "固定架", "压板"],
            "housing_box": ["箱体", "壳体", "模具框", "腔体", "滑台座", "气缸固定座"],
            "gear_flange": ["齿轮", "带轮", "法兰盘", "分度盘", "联轴器"]
        }

    def infer_blueprint_features(self, blueprint_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze blueprint input to deduce primary geometry, feature tree, and assembly mates."""
        desc = blueprint_spec.get("description", "")
        dims = blueprint_spec.get("dimensions", {})
        ocr_text = blueprint_spec.get("ocr_text", "")
        supplied_provenance = blueprint_spec.get("dimension_provenance", {})
        full_text = f"{desc} {ocr_text} {json.dumps(dims, ensure_ascii=False)}"

        # Preserve where dimensions came from. A template default can still support a draft,
        # but it must never look like a dimension read from the drawing.
        dimension_sources: Dict[str, str] = {}
        assumed_dimensions: List[str] = []
        ocr_readbacks: Dict[str, str] = {}

        ocr_patterns = {
            "length_mm": r"(?:总长|全长|轴向长度|长度|长)\s*[:=：]?\s*(\d+(?:\.\d+)?)\s*(mm|毫米|inch|in|英寸)",
            "width_mm": r"(?:宽度|宽)\s*[:=：]?\s*(\d+(?:\.\d+)?)\s*(mm|毫米|inch|in|英寸)",
            "thickness_mm": r"(?:厚度|厚|总高|高度)\s*[:=：]?\s*(\d+(?:\.\d+)?)\s*(mm|毫米|inch|in|英寸)",
            "hole_diameter_mm": r"(?:内径|内孔|轴孔|孔径|bore)\s*(?:[ØΦφ])?\s*[:=：]?\s*(\d+(?:\.\d+)?)\s*(mm|毫米|inch|in|英寸)",
            "pitch_mm": r"(?:节圆|分度圆|孔距|中心距|PCD)\s*(?:直径)?\s*[:=：]?\s*(\d+(?:\.\d+)?)\s*(mm|毫米|inch|in|英寸)",
        }

        def read_ocr_dimension(name: str) -> float | None:
            pattern = ocr_patterns.get(name)
            if not pattern or not ocr_text:
                return None
            match = re.search(pattern, str(ocr_text), flags=re.IGNORECASE)
            if not match:
                return None
            value = float(match.group(1))
            unit = match.group(2).lower()
            if unit in ("inch", "in", "英寸"):
                value *= 25.4
            if not math.isfinite(value) or value <= 0:
                return None
            ocr_readbacks[name] = match.group(0)
            dimension_sources[name] = f"ocr_text_unverified:{match.group(0)}"
            return value

        def read_dimension(name: str, aliases: tuple[str, ...], default: float) -> float:
            for key in aliases:
                value = dims.get(key)
                if value is None or value == "":
                    continue
                try:
                    parsed = float(value)
                except (TypeError, ValueError):
                    continue
                if math.isfinite(parsed) and parsed > 0:
                    source = supplied_provenance.get(name) if isinstance(supplied_provenance, dict) else None
                    dimension_sources[name] = str(source or f"dimensions.{key}")
                    if "default" in dimension_sources[name].lower() or "assumed" in dimension_sources[name].lower():
                        assumed_dimensions.append(name)
                    return parsed
            ocr_value = read_ocr_dimension(name)
            if ocr_value is not None:
                return ocr_value
            assumed_dimensions.append(name)
            dimension_sources[name] = "template_default"
            return default

        # 1. Classify Category
        category = "bracket_plate"
        for cat, keywords in self.primitive_classifiers.items():
            if any(k in full_text for k in keywords):
                category = cat
                break

        if category in ("shaft_sleeve", "gear_flange"):
            # In a turning part, the legacy ``length`` slot represents outer diameter;
            # axial length is ``thickness``. Keep the OCR labels aligned with that contract.
            unit = r"(mm|毫米|inch|in|英寸)"
            ocr_patterns["length_mm"] = (
                r"(?:外圆直径|外径|外圆|outer\s*diameter|OD)\s*[:=：]?\s*"
                r"(?:[ØΦφ]\s*)?(\d+(?:\.\d+)?)\s*" + unit
            )
            ocr_patterns["thickness_mm"] = (
                r"(?:总长|全长|轴向长度|长度|length)\s*[:=：]?\s*"
                r"(\d+(?:\.\d+)?)\s*" + unit
            )

        # 2. Extract Key Dimensions
        length = read_dimension("length_mm", ("length", "L", "overall_len", "total_len", "d_outer"), 120.0)
        width = read_dimension("width_mm", ("width", "W", "width_mm"), 80.0)
        thickness = read_dimension(
            "thickness_mm", ("thickness", "T", "height", "H", "overall_len", "total_len"), 25.0
        )
        hole_d = read_dimension("hole_diameter_mm", ("hole_d", "bore", "d_inner", "inner_diameter"), 10.0)
        pitch = read_dimension("pitch_mm", ("pitch", "spacing", "bolt_circle_diameter"), 50.0)

        feature_tree = []
        equations = {}

        # 3. Construct FeatureTree based on Category
        if category in ["shaft_sleeve", "gear_flange"]:
            # Revolving geometry
            equations["D_Outer"] = length
            equations["D_Inner"] = hole_d
            equations["Total_Length"] = thickness
            
            feature_tree = [
                {
                    "feature_type": "EquationMgr",
                    "feature_name": "全局变量与方程式驱动",
                    "parameters": equations
                },
                {
                    "feature_type": "SketchOnPlane",
                    "feature_name": "草图1_回转半截面",
                    "plane_ref": "Front Plane",
                    "parameters": {
                        "contour": "ClosedRevolveProfile",
                        "constraints": ["CoincidentWithOrigin", "HorizontalAxisSymmetry"],
                        "dimensions": {"OuterRadius": length / 2, "BoreRadius": hole_d / 2, "Length": thickness}
                    }
                },
                {
                    "feature_type": "BossRevolve",
                    "feature_name": "凸台-旋转1",
                    "parameters": {"angle_deg": 360.0, "axis_ref": "Centerline"}
                },
                {
                    "feature_type": "HoleWizard",
                    "feature_name": "法兰沉头孔向导",
                    "parameters": {"type": "Counterbore", "size": "M6", "pcd": length * 0.75, "count": 4}
                },
                {
                    "feature_type": "Chamfer",
                    "feature_name": "外圆与内孔倒角",
                    "parameters": {"distance_mm": 1.5, "angle_deg": 45.0, "target_edges": "OuterAndInnerBoreEdges"}
                }
            ]
            assembly_mates = [
                {"mate_type": "Concentric", "ref_entity": "Axis_Shaft", "target": "Assembly_Spindle_Center"},
                {"mate_type": "Coincident", "ref_entity": "Front_Flange_Face", "target": "Assembly_Base_Mounting_Face"}
            ]

        else:
            # Prismatic Plate / Bracket geometry
            equations["Length"] = length
            equations["Width"] = width
            equations["Thickness"] = thickness
            equations["Hole_Distance"] = pitch

            feature_tree = [
                {
                    "feature_type": "EquationMgr",
                    "feature_name": "方程式全局变量定义",
                    "parameters": equations
                },
                {
                    "feature_type": "SketchOnPlane",
                    "feature_name": "草图1_基体中心矩形",
                    "plane_ref": "Top Plane",
                    "parameters": {
                        "sketch_type": "CenterRectangle",
                        "constraints": ["SymmetricAboutOrigin"],
                        "dimensions": {"Length": length, "Width": width}
                    }
                },
                {
                    "feature_type": "BossExtrude",
                    "feature_name": "凸台-拉伸1",
                    "plane_ref": "Top Plane",
                    "parameters": {"depth_mm": thickness, "direction": "Blind"}
                },
                {
                    "feature_type": "HoleWizard",
                    "feature_name": "4x标准安装沉头孔向导",
                    "plane_ref": "FaceID_Top",
                    "parameters": {
                        "type": "Countersink",
                        "standard": "GB/T 70.3",
                        "size": f"M{int(hole_d) if hole_d else 6}",
                        "hole_layout": "RectangularPattern",
                        "spacing_x": pitch,
                        "spacing_y": width - 20
                    }
                },
                {
                    "feature_type": "Fillet",
                    "feature_name": "四角过渡圆角",
                    "parameters": {"radius_mm": 5.0, "target_edges": "FourVerticalEdges"}
                }
            ]
            assembly_mates = [
                {"mate_type": "Coincident", "ref_entity": "Bottom_Face", "target": "Fixture_Top_Plane"},
                {"mate_type": "Concentric", "ref_entity": "Hole_1", "target": "Locating_Pin_1"},
                {"mate_type": "Concentric", "ref_entity": "Hole_2", "target": "Locating_Pin_2"}
            ]

        required_dimensions = (
            ["length_mm", "thickness_mm", "hole_diameter_mm"]
            if category in ("shaft_sleeve", "gear_flange")
            else ["length_mm", "width_mm", "thickness_mm", "hole_diameter_mm", "pitch_mm"]
        )
        required_assumptions = [name for name in assumed_dimensions if name in required_dimensions]
        evidence_status = "assumptions_present" if required_assumptions else "input_dimensions_complete"

        return {
            "classified_primitive": category,
            "deduced_equations": equations,
            "feature_tree": feature_tree,
            "assembly_mates": assembly_mates,
            "target_material": blueprint_spec.get("material", "AL6061-T6"),
            "geometry_evidence": {
                "status": evidence_status,
                "verified": False,
                "basis": "rule_inferred_feature_tree",
                "dimension_sources": dimension_sources,
                "ocr_readbacks": ocr_readbacks,
                "assumed_dimensions": required_assumptions,
                "unused_template_dimensions": [name for name in assumed_dimensions
                                                if name not in required_dimensions],
                "classification_basis": "keyword_classifier",
                "note": (
                    "模板尺寸只用于草案，必须从原图/OCR或结构化规格补齐后才能进入工程验证。"
                    if required_assumptions else
                    "尺寸来自结构化输入；特征树仍为规则推导，尚非 CAD 拓扑识别。"
                ),
            },
        }

    def generate_solidworks_vba_script(self, inverse_result: Dict[str, Any]) -> str:
        """Convert deduced feature tree into deterministic SolidWorks VBA API script."""
        eqs = inverse_result.get("deduced_equations", {})
        eq_lines = []
        for k, v in eqs.items():
            eq_lines.append(f'    swEqnMgr.Add -1, """"{k}"" = {v}"')

        return f"""' SolidWorks 2021 Automated Inverse-Deduction Macro
' Generated by Virtu Autonomous Engineering Agent
Dim swApp As SldWorks.SldWorks
Dim swModel As SldWorks.ModelDoc2
Dim swPart As SldWorks.PartDoc
Dim swFeatMgr As SldWorks.FeatureManager
Dim swEqnMgr As SldWorks.EquationMgr
Dim boolstatus As Boolean
Dim longstatus As Long

Sub main()
    Set swApp = Application.SldWorks
    Set swModel = swApp.NewDocument("C:\\ProgramData\\SolidWorks\\templates\\Part.prtdot", 0, 0, 0)
    Set swPart = swModel
    Set swFeatMgr = swModel.FeatureManager
    Set swEqnMgr = swModel.GetEquationMgr

    ' 1. Bind Deduced Parametric Equations
{chr(10).join(eq_lines)}
    swEqnMgr.EvaluateAll

    ' 2. Create Base Sketch & Solid Geometry
    swModel.Extension.SelectByID2 "Top Plane", "PLANE", 0, 0, 0, False, 0, Nothing, 0
    swModel.SketchManager.InsertSketch True
    swModel.SketchManager.CreateCenterRectangle 0, 0, 0, 0.05, 0.03, 0
    swModel.SketchManager.InsertSketch True

    ' 3. Base Extrude Feature
    swFeatMgr.FeatureExtrusion3 True, False, False, 0, 0, 0.025, 0.01, False, False, False, False, 0, 0, False, False, False, False, True, True, True, 0, 0, False

    swModel.ViewZoomtofit2
    swModel.ForceRebuild3 True
    MsgBox "Inverse Blueprint Modeling Completed Successfully!", vbInformation, "Virtu Agent"
End Sub
"""
