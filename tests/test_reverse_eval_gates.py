# -*- coding: utf-8 -*-
"""tests/test_reverse_eval_gates.py — 逆向工程客观闸门反证与可证伪性测试.

严格落实《测量宪法》第四条：
“闸必须能被证伪。新增任何判据或门禁，同时提交‘植入坏样本 ⇒ 必须红’的反证测试。
空匹配集、解析失败、if not exists: continue 一律判红，不得当作通过。”
"""

import pytest
import sys
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from virtu_omni.reverse_engineering.graders import (
    grade_dimension_fidelity,
    grade_family_classification,
    grade_volume_conservation,
    grade_hole_pattern_fidelity,
    grade_parametric_feature_tree,
    grade_vba_code_integrity,
    grade_reconstruction_case
)


def test_gate_dimension_corrupted_mutation():
    """反证：植入严重超差的坏尺寸，保真度必须判红 (分数 <= 10)."""
    gt_dims = {"outer_diameter": 160.0, "inner_bore": 50.0, "total_length": 24.0}
    corrupted_dims = {"outer_diameter": 999.0, "inner_bore": 1.0, "total_length": 500.0}
    score, trace = grade_dimension_fidelity(corrupted_dims, gt_dims)
    assert score == 0.0, f"坏样本未被判零分: score={score}, trace={trace}"
    assert "超差" in trace


def test_gate_volume_non_positive_veto():
    """反证：植入零体积或负体积，体积守恒闸门必须否决判 0 分."""
    score_zero, trace_zero = grade_volume_conservation(0.0, 100.0)
    assert score_zero == 0.0
    assert "物理体积非正" in trace_zero

    score_neg, trace_neg = grade_volume_conservation(-50.0, 100.0)
    assert score_neg == 0.0
    assert "物理体积非正" in trace_neg


def test_gate_volume_gross_deviation_veto():
    """反证：植入偏差达 300% 的伪造体积，体积守恒闸门必须给 0 分."""
    score, trace = grade_volume_conservation(400.0, 100.0)
    assert score == 0.0, f"伪造体积未被拦截: score={score}"
    assert "体积守恒严重违背" in trace


def test_gate_family_mismatch_veto():
    """反证：分类错误必须得 0 分."""
    score, trace = grade_family_classification("PRISMATIC_BLOCK", "ROTATIONAL_MOLD")
    assert score == 0.0
    assert "分类错误" in trace


def test_gate_malicious_vba_injection_veto():
    """反证：植入 Shell 命令注入攻击载荷，必须触发安全一票否决 (0 分)."""
    malicious_vba = """
    Option Explicit
    Sub main()
        Dim wsh As Object
        Set wsh = CreateObject("WScript.Shell")
        wsh.Run "cmd.exe /c calc"
    End Sub
    """
    score, trace = grade_vba_code_integrity(malicious_vba)
    assert score == 0.0, f"注入攻击未被安全否决: score={score}"
    assert "安全否决" in trace


def test_gate_empty_vba_veto():
    """反证：空代码必须得 0 分."""
    score, trace = grade_vba_code_integrity("")
    assert score == 0.0


def test_gate_perfect_sample_passes():
    """正证：真实合格样本综合评分必须 >= 95 分."""
    perfect_record = {
        "key_dimensions": {
            "outer_diameter": 160.0,
            "inner_bore": 50.0,
            "total_length": 24.0,
            "hole_patterns": [{"pcd_diameter": 130.0, "hole_diameter": 12.0, "hole_count": 6}]
        },
        "hole_patterns": [{"pcd_diameter": 130.0, "hole_diameter": 12.0, "hole_count": 6}],
        "part_family": "FLANGE_PLATE",
        "theoretical_volume_mm3": 442100.0,
        "reconstruction_vba": """
Option Explicit
Dim swApp As Object, Part As Object, boolstatus As Boolean
Dim swFeat As Object, swEqnMgr As Object

Sub main()
    Set swApp = Application.SldWorks
    Set Part = swApp.NewPart()
    Set swEqnMgr = Part.GetEquationMgr
    swEqnMgr.Add -1, "\"D_Outer\" = 160.0"
    
    Part.ClearSelection2 True
    Part.SelectByID "前视基准面", "PLANE", 0, 0, 0
    Part.SketchManager.InsertSketch True
    Part.SketchManager.CreateCircleByRadius 0, 0, 0, 0.08
    Part.ClearSelection2 True
    Set swFeat = Part.FeatureManager.FeatureExtrusion3(True, False, False, 0, 0, 0.024, 0, False, False, False, False, 0, 0, False, False, False, False, True, True, True, 0, 0, False)

    Part.ClearSelection2 True
    Part.SelectByID "前视基准面", "PLANE", 0, 0, 0
    Part.SketchManager.InsertSketch True
    Part.SketchManager.CreateCircleByRadius 0, 0, 0, 0.025
    Part.ClearSelection2 True
    Set swFeat = Part.FeatureManager.FeatureCut3(True, False, False, 0, 0, 0.03, 0, False, False, False, False, 0, 0, False, False, False, False, False, True, True, True, True, False, 0, 0, False)
End Sub
        """,
        "rebuild_success": True
    }
    case_def = {
        "id": "REV-TEST",
        "name": "测试法兰",
        "family": "FLANGE_PLATE",
        "passing_threshold": 75.0,
        "ground_truth": {
            "outer_diameter": 160.0,
            "inner_bore": 50.0,
            "total_length": 24.0,
            "pcd_diameter": 130.0,
            "bolt_hole_dia": 12.0,
            "bolt_hole_count": 6,
            "theoretical_volume_cm3": 442.10,
            "feature_sequence": ["FeatureExtrusion3", "FeatureCut3", "EquationMgr"]
        },
        "evaluation_criteria": {
            "required_dims": ["outer_diameter", "inner_bore", "total_length"]
        }
    }

    res = grade_reconstruction_case(perfect_record, case_def)
    assert res["passed"] is True
    assert res["total_score"] >= 95.0, f"真实优秀样本得分低于95: {res['total_score']}"
