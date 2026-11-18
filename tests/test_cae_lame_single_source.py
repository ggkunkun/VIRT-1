# -*- coding: utf-8 -*-
"""Lamé CAE results must share the registered formula and fail closed."""

import pytest

from scripts.wm_verifier import recompute
from virtu_eval.audit_case_arithmetic import eval_expr
from virtu_eval.derivation import LAWS, resolve
from virtu_omni.agent.grounded_inference import lame_thick_cylinder
from virtu_omni.agent.super_agent import VirtuSuperAgent
from virtu_omni.agent.facet_contracts import validate_facet_result


CASES = [
    {"pressure_inner_mpa": 10.0, "pressure_outer_mpa": 0.0,
     "r_outer_mm": 30.0, "r_inner_mm": 10.0, "yield_strength_mpa": 503.0},
    {"pressure_inner_mpa": 0.0, "pressure_outer_mpa": 25.0,
     "r_outer_mm": 50.0, "r_inner_mm": 35.0, "yield_strength_mpa": 850.0},
    {"pressure_inner_mpa": 24.0, "pressure_outer_mpa": 3.0,
     "r_outer_mm": 50.0, "r_inner_mm": 25.0, "yield_strength_mpa": 276.0},
]


def _assert_laws_match_recompute(inputs):
    stress_inputs = {key: value for key, value in inputs.items() if key != "yield_strength_mpa"}
    actual = recompute({"task": "lame_cylinder_stress", "inputs": stress_inputs})
    assert actual
    for field, expression in resolve("lame_cylinder_stress", stress_inputs).items():
        expected = eval_expr(expression)[0]
        assert abs(expected - actual[field]) <= 1e-10 * max(1.0, abs(actual[field])), field
    fos_inputs = {"Sy": inputs["yield_strength_mpa"], "sigma": actual["peak_von_mises_mpa"]}
    fos = recompute({"task": "fea_fos", "inputs": fos_inputs})
    for field, expression in resolve("fea_fos", fos_inputs).items():
        expected = eval_expr(expression)[0]
        assert abs(expected - fos[field]) <= 1e-10 * max(1.0, abs(fos[field])), field
    actual.update({"safety_factor": fos["safety_factor"], "fos_gate": fos["fos_gate"]})
    return actual


@pytest.mark.parametrize("inputs", CASES)
def test_lame_registered_laws_match_runtime_recompute(inputs):
    _assert_laws_match_recompute(inputs)


def test_von_mises_combines_principal_stresses_instead_of_relabeling_hoop_stress():
    result = _assert_laws_match_recompute(CASES[0])
    assert result["lame_hoop_inner_mpa"] == pytest.approx(12.5)
    assert result["peak_von_mises_mpa"] == pytest.approx(19.4855715851)
    assert result["peak_von_mises_mpa"] != pytest.approx(result["lame_hoop_inner_mpa"])


def test_grounded_lame_solver_uses_the_shared_reference():
    shared = _assert_laws_match_recompute(CASES[0])
    result = lame_thick_cylinder(20.0, 60.0, 10.0)
    assert result["basis"] == "virtu_eval.derivation.LAWS"
    assert result["sigma_theta_inner_mpa"] == pytest.approx(shared["lame_hoop_inner_mpa"])
    assert result["von_mises_inner_mpa"] == pytest.approx(shared["von_mises_inner_mpa"])


def test_torsion_laws_match_registered_reference_and_physical_units():
    torsion_inputs = {"torque_nm": 100.0, "r_outer_mm": 10.0, "r_inner_mm": 0.0}
    torsion = recompute({"task": "shaft_torsion", "inputs": torsion_inputs})
    torsion_law = resolve("shaft_torsion", torsion_inputs)
    assert torsion["torsional_shear_mpa"] == pytest.approx(63.6619772368)
    assert eval_expr(torsion_law["torsional_shear_mpa"])[0] == pytest.approx(
        torsion["torsional_shear_mpa"])

    combined_inputs = {"base_von_mises_mpa": 12.0,
                       "torsional_shear_mpa": torsion["torsional_shear_mpa"]}
    combined = recompute({"task": "combined_vm_torsion", "inputs": combined_inputs})
    expression = resolve("combined_vm_torsion", combined_inputs)["combined_von_mises_mpa"]
    assert eval_expr(expression)[0] == pytest.approx(combined["combined_von_mises_mpa"])


@pytest.mark.parametrize("task,inputs", [
    ("shaft_torsion", {"torque_nm": 10.0, "r_outer_mm": 5.0, "r_inner_mm": 5.0}),
    ("shaft_torsion", {"torque_nm": 10.0, "r_outer_mm": float("nan"), "r_inner_mm": 0.0}),
    ("combined_vm_torsion", {"base_von_mises_mpa": 1.0,
                              "torsional_shear_mpa": float("inf")}),
])
def test_invalid_torsion_inputs_return_no_reference(task, inputs):
    assert recompute({"task": task, "inputs": inputs}) == {}


def test_cae_facet_blocks_missing_load_and_uses_von_mises_reference():
    agent = object.__new__(VirtuSuperAgent)
    spec = {"material": "AL7075-T6", "d_outer": 60.0, "d_inner": 20.0,
            "overall_len": 50.0, "internal_pressure_mpa": 10.0}
    result = agent.facet_verify_cae(spec)
    assert result["status"] == "COMPLETED"
    assert result["calculation_verified"] is True
    assert result["engineering_verified"] is False
    assert result["evidence_basis"] == "inferred"
    assert result["max_von_mises_stress_mpa"] == pytest.approx(19.4855715851)
    assert result["max_von_mises_stress_mpa"] != pytest.approx(result["sigma_theta_inner_mpa"])

    missing = agent.facet_verify_cae({key: value for key, value in spec.items()
                                      if key != "internal_pressure_mpa"})
    assert missing["status"] == "BLOCKED"
    assert missing["safety_factor_fos"] is None
    assert "pressure_inner_mpa" in missing["missing_inputs"]


def test_cae_facet_contract_keeps_blocked_result_and_rejects_unproven_success():
    blocked = {"status": "BLOCKED", "safety_factor_fos": None, "fos_passed": False,
               "calculation_verified": False, "evidence_basis": "insufficient"}
    unproven = {"status": "COMPLETED", "safety_factor_fos": 3.0, "fos_passed": True}
    assert validate_facet_result("verify_cae_stress", blocked)["passed"]
    assert not validate_facet_result("verify_cae_stress", unproven)["passed"]


@pytest.mark.parametrize("overrides", [
    {"r_inner_mm": 30.0},
    {"pressure_inner_mpa": -1.0},
])
def test_invalid_lame_inputs_return_no_reference(overrides):
    inputs = dict(CASES[0])
    inputs.update(overrides)
    inputs.pop("yield_strength_mpa")
    assert recompute({"task": "lame_cylinder_stress", "inputs": inputs}) == {}


def test_equal_inner_and_outer_pressure_is_hydrostatic_not_invalid():
    result = recompute({"task": "lame_cylinder_stress", "inputs": {
        "pressure_inner_mpa": 10.0, "pressure_outer_mpa": 10.0,
        "r_outer_mm": 30.0, "r_inner_mm": 10.0,
    }})
    assert result["peak_von_mises_mpa"] == pytest.approx(0.0)


def test_mutated_lame_law_is_detected_by_parity_probe(monkeypatch):
    laws = list(LAWS["lame_cylinder_stress"])
    monkeypatch.setitem(
        LAWS,
        "lame_cylinder_stress",
        [(field, "pressure_inner_mpa*r_outer_mm^2/"
                 "(r_outer_mm^2-r_inner_mm^2)" if field == "peak_von_mises_mpa" else law)
         for field, law in laws],
    )
    with pytest.raises(AssertionError):
        _assert_laws_match_recompute(CASES[0])
