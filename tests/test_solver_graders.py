"""Mutation probe for the solver-backed graders.

The point of ``world_state_verified`` / ``physics_invariant`` is that a verdict tracks the
recomputed number, not the string. Each test here plants one physically wrong world_state that
the old text graders still accept, and asserts the new graders reject it. A test that only
checks "correct input -> pass" would prove nothing: a grader that always passes also passes.
"""
import json

import pytest

from virtu_eval.graders import GRADERS, _wm_verifier, score_case

SCENARIO = {
    "task": "removal",
    "inputs": {"doc": 2.0, "woc": 5.0, "vf": 400.0, "L": 100.0,
               "rho": 7.85e-3, "stock_vol": 200000.0},
}

# solver truth: removed=1000 mm3, mrr=4000 mm3/min, mass=7.85 g, remaining=1562.15 g, dV=-1000
SOLVER_TRUTH = {
    "material_removed_mm3": 1000.0,
    "mrr_mm3_per_min": 4000.0,
    "removed_mass_g": 7.85,
    "resulting_mass_g": 1562.15,
    "delta_volume_mm3": -1000.0,
}

DESIGN_SCENARIO = {
    "task": "design",
    "inputs": {"r_out": 50.0, "r_bore": 20.0, "t": 10.0,
               "n_holes": 6, "r_hole": 5.0, "rho": 7.85e-3},
}


def _ws(**over):
    state = dict(SOLVER_TRUTH)
    state.update(over)
    return json.dumps(state, ensure_ascii=False)


def _crit(kind="world_state_verified", **over):
    c = {"type": kind, "key": kind, "scenario": SCENARIO}
    c.update(over)
    return c


def _ev(scored, i=0):
    return scored["criteria"][i]["evidence"]


def test_solver_truth_fixture_is_self_consistent():
    """Guard the fixture itself: these must be the numbers the solver actually produces."""
    assert _wm_verifier().recompute(SCENARIO) == pytest.approx(SOLVER_TRUTH, rel=1e-9)


def test_correct_world_state_passes_both_new_graders():
    for kind in ("world_state_verified", "physics_invariant"):
        scored = score_case(_ws(), [_crit(kind)])
        assert scored["score"] == 100.0, f"{kind}: {_ev(scored)}"


# ---------------------------------------------------------------------------
# planted defects: text graders green, solver graders red
# ---------------------------------------------------------------------------

def test_unit_scale_defect_is_rejected():
    """Density taken as g/mm^3 instead of g/cm^3 -> mass 1000x too large."""
    resp = _ws(removed_mass_g=7850.0)
    # The volume half of the answer is still right, so text graders that look at shape and at
    # one correct magnitude hand out credit; the mass is 1000x off and they never see it.
    old = score_case(resp, [{"type": "numeric_near", "key": "vol", "value": 1000.0},
                            {"type": "json_object", "key": "shape",
                             "required_keys": ["removed_mass_g", "resulting_mass_g"]}])
    assert old["score"] == 100.0, f"old graders should be fooled: {old['criteria']}"

    new = score_case(resp, [_crit()])
    assert new["score"] == 0.0, f"1000x unit error slipped through: {_ev(new)}"
    assert _ev(new).startswith("L1")


def test_echoed_input_is_scored_as_the_answer():
    """The substring hole: the prompt's own density appears in a prose field, so
    ``numeric_near`` credits it as the computed mass. Reciting an input measured as physics."""
    resp = json.dumps({"material_removed_mm3": 1000.0, "mrr_mm3_per_min": 4000.0,
                       "delta_volume_mm3": -1000.0, "resulting_mass_g": 1562.15,
                       "note": "rho 7.85 g/cm3"}, ensure_ascii=False)
    old = score_case(resp, [{"type": "numeric_near", "key": "mass", "value": 7.85},
                            {"type": "json_object", "key": "shape",
                             "required_keys": ["material_removed_mm3"]}])
    assert old["score"] == 100.0, f"old graders should be fooled: {old['criteria']}"

    new = score_case(resp, [_crit()])
    assert new["score"] == 0.0, f"echoed density scored as the answer: {_ev(new)}"
    assert "removed_mass_g" in _ev(new)


def test_sign_defect_is_rejected():
    resp = _ws(delta_volume_mm3=1000.0)
    new = score_case(resp, [_crit()])
    assert new["score"] == 0.0
    assert _ev(new).startswith("L1")

    old = score_case(resp, [{"type": "numeric_near", "key": "dv", "value": 1000.0}])
    assert old["score"] == 100.0, "old grader accepts the wrong sign"


def test_missing_field_is_rejected():
    resp = json.dumps({"material_removed_mm3": 1000.0, "delta_volume_mm3": -1000.0})
    new = score_case(resp, [_crit()])
    assert new["score"] == 0.0
    assert "mrr_mm3_per_min" in _ev(new)


def test_near_miss_is_accepted_by_default_and_rejected_when_tightened():
    """tol_rel is the effort knob: the runtime ladder's 8% must not silently become the
    evaluation's ruler."""
    resp = _ws(mrr_mm3_per_min=4300.0)  # 7.5% high
    loose = score_case(resp, [_crit()])
    assert loose["score"] == 100.0, f"default solver tolerance should accept 7.5%: {_ev(loose)}"

    strict = score_case(resp, [_crit(tol_rel=0.01)])
    assert strict["score"] == 0.0
    assert "mrr_mm3_per_min" in _ev(strict)


def test_physics_invariant_checks_conservation_not_truth():
    """L1 must pass a self-consistent but wrong set, so the two graders stay distinct
    instead of one silently doing both jobs."""
    resp = _ws(material_removed_mm3=2000.0, delta_volume_mm3=-2000.0,
               mrr_mm3_per_min=8000.0, removed_mass_g=15.7, resulting_mass_g=1554.3)
    invariant = score_case(resp, [_crit("physics_invariant")])
    assert invariant["score"] == 100.0, f"L1 should not be an oracle: {_ev(invariant)}"

    verified = score_case(resp, [_crit()])
    assert verified["score"] == 0.0, "L2 should reject the doubled numbers"


# ---------------------------------------------------------------------------
# anti-vacuity: a grader that cannot compute must fail, never pass
# ---------------------------------------------------------------------------

def test_unsupported_task_fails_loudly_not_vacuously():
    crit = _crit(scenario={"task": "not_a_real_task", "inputs": {"a": 1}})
    new = score_case(_ws(), [crit])
    assert new["score"] == 0.0
    assert "no_reference" in _ev(new)


def test_missing_scenario_fails_loudly():
    crit = {"type": "world_state_verified", "key": "k"}
    new = score_case(_ws(), [crit])
    assert new["score"] == 0.0
    assert "scenario_missing" in _ev(new)


def test_min_compared_blocks_partial_assertion():
    """Asserting only the easy fields while staying silent on the rest earns no credit."""
    ref = _wm_verifier().recompute(DESIGN_SCENARIO)
    assert len(ref) >= 2, f"fixture needs a multi-field design reference, got {sorted(ref)}"

    graded_fully = score_case(json.dumps(ref), [_crit(scenario=DESIGN_SCENARIO)])
    assert graded_fully["score"] == 100.0, _ev(graded_fully)

    partial = score_case(json.dumps(list(ref)[:1]),
                         [_crit(scenario=DESIGN_SCENARIO, min_compared=len(ref))])
    assert partial["score"] == 0.0, "silent fields must not count as agreement"

    short = score_case(json.dumps(ref),
                       [_crit(scenario=DESIGN_SCENARIO, min_compared=len(ref) + 1)])
    assert short["score"] == 0.0
    assert "vacuous" in _ev(short)


def test_weighted_blend_keeps_physics_as_a_real_share():
    """A case mixing one text criterion and one solver criterion must lose half its score
    when the physics is wrong -- no free pass from fluent prose."""
    resp = _ws(removed_mass_g=7850.0)
    criteria = [{"type": "literal_all", "key": "units", "values": ["mm3", "g"], "weight": 1},
                _crit(weight=1)]
    scored = score_case(resp, criteria)
    assert scored["score"] == 50.0
    by_key = {d["key"]: d["passed"] for d in scored["criteria"]}
    assert by_key == {"units": True, "world_state_verified": False}


def test_composite_reference_field_is_named_not_silently_graded():
    """``_cmp_numeric`` skips list values, so a centroid the solver returns as a triple cannot
    be graded by equality. It must show up in the evidence instead of counting as agreement."""
    scen = {"task": "mass_props",
            "inputs": {"shape": "box", "params": {"l": 120.0, "w": 60.0, "h": 20.0},
                       "rho": 7.85e-3}}
    ref = _wm_verifier().recompute(scen)
    assert any(isinstance(v, list) for v in ref.values()), \
        f"fixture needs a composite solver field: {sorted(ref)}"

    scored = score_case(json.dumps({**ref, "centroid_mm": [1.0, 1.0, 1.0]}),
                        [_crit(scenario=scen)])
    assert scored["score"] == 100.0, _ev(scored)
    assert "ungraded_composite" in _ev(scored)


def test_graders_are_registered_for_the_validator():
    assert {"world_state_verified", "physics_invariant"} <= set(GRADERS)
