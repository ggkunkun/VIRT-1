"""The derivation grader must score law+binding apart from arithmetic -- and prove it.

Case 1 below is the whole point: a substituted expression that is right while the printed number is
wrong passes here and fails ``world_state_verified``. If instead both graders agreed, this criterion
would measure nothing the numeric ruler did not already measure, and it should be deleted.
"""
import json

import pytest

from virtu_eval.graders import score_case
from virtu_eval.derivation import resolve

ROUGH = {"task": "roughness", "inputs": {"f": 0.12, "r_eps": 0.8}}
REMOVAL = {"task": "removal", "inputs": {"doc": 2.0, "woc": 5.0, "vf": 400.0, "L": 100.0,
                                         "rho": 0.00785, "stock_vol": 200000.0}}


def _crit(scenario, **over):
    c = {"type": "derivation_verified", "key": "derivation_verified", "scenario": scenario}
    c.update(over)
    return c


def _ws_crit(scenario, **over):
    c = {"type": "world_state_verified", "key": "world_state_verified", "scenario": scenario}
    c.update(over)
    c.setdefault("must_compare", sorted(resolve(scenario["task"], scenario["inputs"])))
    return c


def _answer(scenario, derivation, state=None):
    obj = {"derivation": derivation}
    if state is not None:
        obj["world_state"] = state
    return json.dumps(obj, ensure_ascii=False)


def test_gold_derivation_passes():
    from virtu_eval.graders import _wm_verifier

    scenario = REMOVAL
    ref = _wm_verifier().recompute(scenario)
    ans = _answer(scenario, resolve("removal", scenario["inputs"]),
                  {k: round(v, 4) for k, v in ref.items()})
    scored = score_case(ans, [_crit(scenario)])
    assert scored["score"] == 100.0, scored["criteria"][0]["evidence"]


def test_right_law_wrong_multiplication_passes_physics_and_fails_arithmetic():
    """The decomposition this whole change exists to make measurable."""
    scenario = ROUGH
    ans = _answer(scenario, {"surface_roughness_ra_um": "1000*(0.12)^2/(8*(0.8))"},
                  {"surface_roughness_ra_um": 1.8})
    laws = score_case(ans, [_crit(scenario)])
    assert laws["score"] == 100.0, laws["criteria"][0]["evidence"]

    arith = score_case(ans, [_ws_crit(scenario)])
    assert arith["score"] == 0.0
    assert "surface_roughness_ra_um" in arith["criteria"][0]["evidence"]

    # and the law score must say out loud that the printed number disagrees
    assert "printed=1.8" in laws["criteria"][0]["evidence"]


@pytest.mark.parametrize("expr,why", [
    ("1000*(0.12)^2/(8*1.0)", "invented"),          # remembered default nose radius
    ("1000*(0.12)^2/(0.8)", "rel_err"),             # dropped the /8 -> wrong law
    ("1000*(0.25)^2/(8*(0.8))", "invented"),        # bound the wrong feed
    ("1000*f^2/(8*r_eps)", "expression_unparsable"),  # law named, nothing bound
])
def test_bad_derivation_is_rejected_with_a_name(expr, why):
    scored = score_case(_answer(ROUGH, {"surface_roughness_ra_um": expr}), [_crit(ROUGH)])
    assert scored["score"] == 0.0, scored["criteria"][0]["evidence"]
    assert why in scored["criteria"][0]["evidence"], scored["criteria"][0]["evidence"]


def test_missing_derivation_block_is_not_credited_for_a_correct_number():
    ans = json.dumps({"world_state": {"surface_roughness_ra_um": 2.25}})
    scored = score_case(ans, [_crit(ROUGH)])
    assert scored["score"] == 0.0
    assert "no_derivation_block" in scored["criteria"][0]["evidence"]


def test_partial_binding_fails_and_names_the_unbound_fields():
    gold = resolve("removal", REMOVAL["inputs"])
    partial = {k: gold[k] for k in list(gold)[:2]}
    scored = score_case(_answer(REMOVAL, partial), [_crit(REMOVAL)])
    assert scored["score"] == 0.0
    ev = scored["criteria"][0]["evidence"]
    assert "unbound" in ev and ev.count("unbound") >= 3, ev


def test_min_graded_allows_partial_credit_when_asked():
    gold = resolve("removal", REMOVAL["inputs"])
    partial = {k: gold[k] for k in list(gold)[:2]}
    scored = score_case(_answer(REMOVAL, partial), [_crit(REMOVAL, min_graded=2)])
    assert scored["score"] == 100.0, scored["criteria"][0]["evidence"]


def test_two_field_laws_are_each_bound_independently():
    """material_removed does not imply mrr: the model must bind vf, not reuse L."""
    gold = resolve("removal", REMOVAL["inputs"])
    swapped = dict(gold)
    swapped["mrr_mm3_per_min"] = "(2.0)*(5.0)*(100.0)"   # used L where vf belongs
    scored = score_case(_answer(REMOVAL, swapped), [_crit(REMOVAL)])
    assert scored["score"] == 0.0
    assert "mrr_mm3_per_min" in scored["criteria"][0]["evidence"]


def test_expanding_a_chained_quantity_into_its_inputs_is_not_invention():
    """Calibration measured 2026-11-04: the strict per-field literal set flagged equivalent
    rewrites dozens of times (2.0/5.0/100.0 are all given in the problem), which punishes
    notation instead of physics. Numbers the problem stated must be allowed anywhere."""
    from virtu_eval.graders import _wm_verifier

    ref = _wm_verifier().recompute(REMOVAL)
    deriv = dict(resolve("removal", REMOVAL["inputs"]))
    deriv["removed_mass_g"] = "(2.0)*(5.0)*(100.0)*(0.00785)"
    scored = score_case(_answer(REMOVAL, deriv, {k: round(v, 4) for k, v in ref.items()}),
                        [_crit(REMOVAL)])
    assert scored["score"] == 100.0, scored["criteria"][0]["evidence"]


def test_a_number_the_problem_never_gave_is_still_invention():
    """The loosened set must not become a free pass: 1.0 was never stated in this problem."""
    scored = score_case(_answer(ROUGH, {"surface_roughness_ra_um": "1000*(0.12)^2/(8*1.0)"}),
                        [_crit(ROUGH)])
    assert scored["score"] == 0.0
    assert "invented=[1.0]" in scored["criteria"][0]["evidence"]


def test_reusing_its_own_stated_intermediate_is_not_fabrication():
    """Measured on derivation-h04: both arms wrote after="(25000)+(-1571)" right after stating
    delta_volume_mm3=-1571. Chaining off one's own intermediate is what rule F permits, and a wrong
    intermediate still fails because it changes what the later expression evaluates to."""
    scen = {"task": "geom_delta", "inputs": {"feature_vol": 1570.8, "before": 25000.0}}
    ans = json.dumps({"world_state": {"after_volume_mm3": 23429, "before_volume_mm3": 25000,
                                      "delta_volume_mm3": -1571, "feature_volume_mm3": 1570.8},
                      "derivation": {"after_volume_mm3": "(25000)+(-1571)",
                                     "before_volume_mm3": "(25000)",
                                     "delta_volume_mm3": "-(1570.8)",
                                     "feature_volume_mm3": "(1570.8)"}}, ensure_ascii=False)
    scored = score_case(ans, [_crit(scen)])
    assert scored["score"] == 100.0, scored["criteria"][0]["evidence"]


def test_a_self_consistent_but_wrong_chain_still_fails():
    """The permission above must not become an escape hatch: reuse a wrong intermediate and the
    value check catches it, even though every literal is traceable."""
    scen = {"task": "geom_delta", "inputs": {"feature_vol": 1570.8, "before": 25000.0}}
    ans = json.dumps({"world_state": {"after_volume_mm3": 23429},
                      "derivation": {"after_volume_mm3": "(25000)+(-15710)",
                                     "before_volume_mm3": "(25000)",
                                     "delta_volume_mm3": "-(15710)",
                                     "feature_volume_mm3": "(1570.8)"}}, ensure_ascii=False)
    scored = score_case(ans, [_crit(scen)])
    assert scored["score"] == 0.0
    assert "rel_err" in scored["criteria"][0]["evidence"]


def test_grader_is_registered_and_refuses_unknown_tasks():
    from virtu_eval.graders import GRADERS

    assert "derivation_verified" in GRADERS
    scored = score_case("{}", [{"type": "derivation_verified", "key": "d",
                               "scenario": {"task": "nope", "inputs": {}}}])
    assert scored["score"] == 0.0
    assert "no registered laws" in scored["criteria"][0]["evidence"]
