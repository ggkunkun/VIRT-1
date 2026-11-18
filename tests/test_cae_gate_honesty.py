# -*- coding: utf-8 -*-
"""CAE 安全系数闸的诚实性回归：材料别名、载荷接线、扭矩参与、自愈不达标的真实判定。"""
import sys

sys.path.insert(0, ".")

from virtu_omni.engine.universal_cae_engine import UniversalCAEEngine, resolve_material

MAT_45 = "45\u53f7\u94a2"
MAT_UNKNOWN = "\u672a\u77e5\u6750\u6599XYZ"


def _shaft(spec, loads):
    return UniversalCAEEngine().analyze_and_optimize(
        {"family": "ROTATIONAL_SHAFT", "spec": dict(spec, material=MAT_45)}, loads)


def test_alias_resolves_to_declared_yield():
    mat, _ = resolve_material(MAT_45)
    assert mat is not None and mat.yield_strength_mpa == 355.0


def test_unknown_material_is_blocked_not_guessed():
    r = UniversalCAEEngine().analyze_and_optimize(
        {"family": "ROTATIONAL_SHAFT",
         "spec": {"d_outer": 53.0, "d_inner": 14.0, "material": MAT_UNKNOWN}},
        {"internal_pressure_mpa": 45.0})
    assert r["status"] == "blocked"
    assert r["verdict_code"] == "MATERIAL_UNRESOLVED"
    assert "factor_of_safety" not in r


def test_missing_material_is_blocked_instead_of_using_default():
    r = UniversalCAEEngine().analyze_and_optimize(
        {"family": "ROTATIONAL_SHAFT", "spec": {"d_outer": 53.0, "d_inner": 14.0}},
        {"internal_pressure_mpa": 10.0})
    assert r["status"] == "blocked"
    assert r["verdict_code"] == "MATERIAL_REQUIRED"
    assert "factor_of_safety" not in r


def test_shaft_missing_geometry_or_load_is_blocked_without_defaults():
    engine = UniversalCAEEngine()
    missing_geometry = engine.analyze_and_optimize(
        {"family": "ROTATIONAL_SHAFT", "spec": {"material": MAT_45}},
        {"internal_pressure_mpa": 10.0})
    assert missing_geometry["verdict_code"] == "GEOMETRY_REQUIRED"
    missing_load = engine.analyze_and_optimize(
        {"family": "ROTATIONAL_SHAFT",
         "spec": {"material": MAT_45, "d_outer": 53.0, "d_inner": 14.0}}, {})
    assert missing_load["verdict_code"] == "LOAD_REQUIRED"


def test_shaft_reports_shared_law_and_zero_load_assumptions():
    result = _shaft({"d_outer": 53.0, "d_inner": 14.0},
                    {"internal_pressure_mpa": 10.0})
    assert result["status"] == "passed"
    assert result["formula_source"] == "virtu_eval.derivation.LAWS"
    assert result["evidence_basis"] == "inferred"
    assert "external_pressure_mpa=0" in result["load_assumptions"]
    assert "torque_nm=0" in result["load_assumptions"]


def test_shaft_rejects_loads_outside_the_selected_solver_model():
    result = _shaft({"d_outer": 53.0, "d_inner": 14.0},
                    {"torque_nm": 100.0, "radial_load_n": 500.0})
    assert result["status"] == "blocked"
    assert result["verdict_code"] == "LOAD_UNSUPPORTED"
    assert "radial_load_n" in result["unsupported_loads"]


def test_material_alias_changes_fos_instead_of_silently_defaulting():
    spec = {"d_outer": 53.0, "d_inner": 14.0}
    with45 = _shaft(spec, {"internal_pressure_mpa": 45.0})
    cr12 = UniversalCAEEngine().analyze_and_optimize(
        {"family": "ROTATIONAL_SHAFT", "spec": dict(spec, material="Cr12MoV")},
        {"internal_pressure_mpa": 45.0})
    assert with45["yield_strength_mpa"] == 355.0
    assert with45["factor_of_safety"] < cr12["factor_of_safety"]


def test_tool_level_force_reaches_bearing_bracket_formula():
    eng = UniversalCAEEngine()
    spec = {"center_height": 50.0, "base_thickness": 14.0, "base_width": 60.0,
            "rib_thickness": 8.0, "material": MAT_45}
    light = eng.analyze_and_optimize({"family": "BEARING_BRACKET", "spec": spec}, {"load_n": 2000.0})
    heavy = eng.analyze_and_optimize({"family": "BEARING_BRACKET", "spec": spec}, {"load_n": 40000.0})
    assert heavy["von_mises_stress_mpa"] > light["von_mises_stress_mpa"]


def test_torque_participates_in_shaft_mises_stress():
    spec = {"d_outer": 53.0, "d_inner": 14.0}
    free = _shaft(spec, {"internal_pressure_mpa": 10.0})
    turned = _shaft(spec, {"internal_pressure_mpa": 10.0, "torque_nm": 300.0})
    assert turned["von_mises_stress_mpa"] > free["von_mises_stress_mpa"]


def test_sheet_family_is_formability_advisory_not_strength_selfheal():
    eng = UniversalCAEEngine()
    spec = {"sheet_thickness": 2.0, "inner_bend_radius": 2.0, "material": MAT_45}
    r = eng.analyze_and_optimize({"family": "SHEET_METAL_BEND", "spec": spec}, {})
    assert r["status"] == "formability_advisory"
    assert r["needs_reinforcement"] is False
    assert "d_outer" not in r["optimized_spec"]
    assert r["optimized_spec"]["inner_bend_radius"] == 2.0
    assert r["factor_of_safety"] < eng.TARGET_FOS


def test_sheet_family_never_reports_optimized_without_reaching_target():
    eng = UniversalCAEEngine()
    for t in (1.0, 2.0, 3.0):
        r = eng.analyze_and_optimize(
            {"family": "SHEET_METAL_BEND",
             "spec": {"sheet_thickness": t, "inner_bend_radius": t, "material": MAT_45}}, {})
        assert r["status"] != "optimized"
