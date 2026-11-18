"""The law registry must not grow a second physics.

``resolve()`` substitutes the given values into the registered law; ``wm_verifier.recompute()`` is
the runtime truth. If these ever disagree, the graded "did you pick the right law" score is
measuring the registry, not the machine. So equality is asserted for every family, every shipped
case, and perturbed inputs -- and any numeric reference field with no registered law fails the
test rather than going ungraded.
"""
import json
import os
import random

import pytest

from virtu_eval.audit_case_arithmetic import eval_expr
from virtu_eval.derivation import LAWS, check, numeric_laws, resolve
from virtu_eval.graders import _wm_verifier

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASE_PATH = os.path.join(ROOT, "data", "benchmark", "virtu_eval_phys_v1", "physics.jsonl")
wm = _wm_verifier()


def _cases():
    with open(CASE_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _crit(case):
    return [c for c in case["criteria"] if c["type"] == "world_state_verified"][0]


SCENARIOS = [_crit(c)["scenario"] for c in _cases()]

# Domain-specific law families need a deterministic registry contract probe, but are
# intentionally kept out of the sealed benchmark case pool.
REGISTRY_ONLY_SCENARIOS = {
    "lame_cylinder_stress": {
        "task": "lame_cylinder_stress",
        "inputs": {
            "pressure_inner_mpa": 10.0,
            "pressure_outer_mpa": 0.0,
            "r_outer_mm": 30.0,
            "r_inner_mm": 10.0,
        },
    },
    "shaft_torsion": {
        "task": "shaft_torsion",
        "inputs": {"torque_nm": 100.0, "r_outer_mm": 10.0, "r_inner_mm": 4.0},
    },
    "combined_vm_torsion": {
        "task": "combined_vm_torsion",
        "inputs": {"base_von_mises_mpa": 12.0, "torsional_shear_mpa": 5.0},
    },
}


def _perturbed(scenario, rng):
    inputs = {}
    for key, value in scenario["inputs"].items():
        if isinstance(value, list):
            inputs[key] = [round(v * rng.uniform(0.7, 1.4), 6) for v in value]
        elif isinstance(value, (int, float)):
            inputs[key] = round(value * rng.uniform(0.7, 1.4), 6)
        else:
            inputs[key] = value
    return {"task": scenario["task"], "inputs": inputs}


def test_registry_covers_every_numeric_reference_field():
    """A field the solver produces but the registry cannot express would be silently ungraded."""
    for task in LAWS:
        scenario = next((s for s in SCENARIOS if s["task"] == task),
                        REGISTRY_ONLY_SCENARIOS.get(task))
        assert scenario, f"no shipped case exercises task {task}"
        ref = wm.recompute(scenario)
        assert ref, f"solver returns no reference for {task}"
        numeric = {k for k, v in ref.items()
                   if isinstance(v, (int, float)) and not isinstance(v, bool)}
        registered = {f for f, _ in numeric_laws(task)}
        assert registered == numeric, f"{task}: registry {sorted(registered)} vs solver {sorted(numeric)}"


@pytest.mark.parametrize("scenario", SCENARIOS,
                         ids=[s["task"] + str(i) for i, s in enumerate(SCENARIOS)])
def test_registry_equals_solver_on_shipped_cases(scenario):
    ref = wm.recompute(scenario)
    gold = resolve(scenario["task"], scenario["inputs"])
    assert set(gold) == {k for k, v in ref.items()
                         if isinstance(v, (int, float)) and not isinstance(v, bool)}
    for field, expr in gold.items():
        assert eval_expr(expr)[0] == pytest.approx(ref[field], rel=1e-6), \
            f"{scenario['task']}.{field}: registry {expr} -> {eval_expr(expr)[0]} != solver {ref[field]}"


def test_registry_equals_solver_on_perturbed_inputs():
    """Same claim on inputs nobody authored, so a lucky constant cannot carry the test."""
    rng = random.Random(20261104)
    checked = 0
    for scenario in SCENARIOS:
        for _ in range(6):
            pert = _perturbed(scenario, rng)
            ref = wm.recompute(pert)
            if not ref:
                continue
            for field, expr in resolve(pert["task"], pert["inputs"]).items():
                assert eval_expr(expr)[0] == pytest.approx(ref[field], rel=1e-6), \
                    f"{pert['task']}.{field} on {pert['inputs']}"
                checked += 1
    assert checked > 150, f"only {checked} comparisons ran - perturbation is not reaching the solver"


# ---------------------------------------------------------------------------
# the decomposition the numeric ruler cannot express: law vs arithmetic
# ---------------------------------------------------------------------------

ROUGH = {"task": "roughness", "inputs": {"f": 0.12, "r_eps": 0.8}}


def test_correct_law_with_wrong_multiplication_scores_as_physics_pass():
    """The thesis under test: a model may know Ra=1000f^2/(8r_eps) and still fat-finger 1.8."""
    verdict = check("roughness", "surface_roughness_ra_um", "(0.12)*(0.12)*1000/(8*(0.8))",
                    ROUGH["inputs"])
    assert verdict["ok"] is True
    assert verdict["evaluated"] == pytest.approx(2.25, rel=1e-6)
    assert verdict["fabricated_literals"] == []


def test_remembered_default_instead_of_given_value_is_flagged():
    """r_eps=1.0 is the box's known default nose radius, and the prompt said 0.8."""
    verdict = check("roughness", "surface_roughness_ra_um", "1000*(0.12)^2/(8*1.0)",
                    ROUGH["inputs"])
    assert verdict["ok"] is False
    assert 1.0 in verdict["fabricated_literals"]


def test_wrong_law_is_caught_by_value_not_by_string_match():
    """Omitting the /8 is a real law error; it must not pass just because the numbers are all given."""
    verdict = check("roughness", "surface_roughness_ra_um", "1000*(0.12)^2/(0.8)", ROUGH["inputs"])
    assert verdict["ok"] is False
    assert verdict["fabricated_literals"] == []
    assert verdict["rel_err_vs_law"] > 0.5


def test_dropping_a_factor_is_caught():
    """The observed failure on this box: n=1000*Vc/(pi*D) answered as 1000*Vc."""
    inputs = {"D": 16.0, "vc": 120.0, "n_max": 3000.0}
    assert check("adapt_machine", "required_spindle_rpm", "1000*(120)", inputs)["ok"] is False
    assert check("adapt_machine", "required_spindle_rpm", "1000*(120)/(pi*(16))", inputs)["ok"] is True


def test_radius_diameter_confusion_is_caught():
    inputs = {"D": 16.0, "vc": 120.0, "n_max": 3000.0}
    half = check("adapt_machine", "required_spindle_rpm", "1000*(120)/(pi*(8))", inputs)
    assert half["ok"] is False
    assert 8.0 in half["fabricated_literals"], "a bound value that is not the given D is invented"


def test_chained_field_uses_the_previous_result_as_a_legitimate_literal():
    """removed_mass_g = material_removed_mm3*rho: the intermediate is not a fabricated number."""
    inputs = {"doc": 2.0, "woc": 5.0, "vf": 400.0, "L": 100.0,
              "rho": 0.00785, "stock_vol": 200000.0}
    verdict = check("removal", "removed_mass_g", "(1000.0)*(0.00785)", inputs)
    assert verdict["ok"] is True, verdict
    assert verdict["evaluated"] == pytest.approx(7.85, rel=1e-6)


def test_unregistered_field_and_unresolvable_inputs_are_refused_not_flopped():
    verdict = check("removal", "collision_risk", "(2.0)*(5.0)*(100.0)",
                    {"doc": 2.0, "woc": 5.0, "vf": 400.0, "L": 100.0,
                     "rho": 0.00785, "stock_vol": 200000.0})
    assert verdict["ok"] is False and "no registered law" in verdict["reason"]

    thin = check("removal", "removed_mass_g", "(2.0)*(5.0)", {"doc": 2.0})
    assert thin["ok"] is False and "registry_cannot_resolve" in thin["reason"]
