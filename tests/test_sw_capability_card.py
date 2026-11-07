# -*- coding: utf-8 -*-
"""Grounding tests for the SW capability card, the defect oracle, and the arm scorer.

Two duties: the suite must catch what it claims to catch, and it must not pass for
the wrong reason. Every "detected" is paired with a non-vacuity proof.
"""

import math
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from virtu_eval import capability_card as cc
from virtu_eval import minimal_repair as mr
from virtu_eval import planted_defects as pd
from virtu_eval import run_defect_arm as rd


@pytest.fixture(scope="module")
def surface():
    try:
        return cc.load_typelib_surface()
    except cc.SurfaceUnavailable as exc:
        pytest.fail("typelib surface unavailable, so no API claim is grounded: %s" % exc)


@pytest.fixture(scope="module")
def cards():
    doc, _path = cc.load_cards("solidworks")
    return doc


@pytest.fixture(scope="module")
def executor():
    try:
        return pd.load_executor()
    except pd.ExecUnavailable as exc:
        pytest.fail("executor rules not importable; judge would be ungrounded: %s" % exc)


def test_surface_enumerates_real_interfaces(surface):
    assert len(surface["interfaces"]) > 100
    assert "ISketchManager" in surface["interfaces"]
    assert "CreateCircleByRadius" in surface["interfaces"]["ISketchManager"]["methods"]


def test_every_card_api_claim_resolves(cards, surface):
    report = cc.verify_cards(cards, surface)
    bad = [(c["id"], f) for c in report["cards"] if not c["api_ok"] for f in c["api_findings"]]
    assert not bad, bad
    assert not report["problems"], report["problems"]


def test_deprecated_overload_arity_is_distinguished(surface):
    """FeatureCut3 exists twice with different arities; the card must pick 26."""
    assert cc.check_api_entry({"api": "IFeatureManager::FeatureCut3", "args": 26}, surface)["ok"]
    wrong = cc.check_api_entry({"api": "IFeatureManager::FeatureCut3", "args": 16}, surface)
    assert not wrong["ok"] and wrong["reason"] == "arity_mismatch"
    short = cc.check_api_entry({"api": "IModelDoc2::FeatureCut3", "args": 16}, surface)
    assert short["ok"] and short["typelib_args"] == 16


def test_invented_or_misfiled_member_is_rejected(surface):
    for entry, reason in (
        ({"api": "IFeatureManager::FeatureExtrusion9"}, "unknown_method"),
        ({"api": "IFeatureManagr::FeatureCut3", "args": 26}, "unknown_interface"),
        ({"api": "IModelDoc2::Extension"}, "is_a_property_not_a_method"),
    ):
        finding = cc.check_api_entry(entry, surface)
        assert not finding["ok"], entry
        assert finding["reason"] == reason, finding


def test_injection_block_carries_only_verified_cards(cards):
    block = cc.render_for_injection(cards)
    assert "sw_drawing_annotate_gbt" not in block
    assert block.count("CAPABILITY ") == sum(
        1 for c in cards["cards"] if c["readiness"] == cc.VERIFIED)
    assert "ISketchManager::CreateCircleByRadius" in block


def test_postconditions_are_expressions_not_adjectives(cards):
    comparisons = ("==", "!=", "<=", ">=", "<", ">")
    for card in cards["cards"]:
        for probe in card["postconditions"]:
            assert any(op in probe["expression"] for op in comparisons), (card["id"], probe)
            assert "tolerance" in probe, (card["id"], probe["probe"])


def test_unit_lanes_are_rendered_as_two_layers_not_one(cards):
    """Measured failure: one mixed unit paragraph made the model 'fix' a mm/inch
    slip by x1000, turning a repairable error into an unrepairable one."""
    block = cc.render_for_injection(cards)
    assert block.count("UNIT LAYER") == 2
    user = next(l for l in block.splitlines() if "user_parameters" in l)
    com = next(l for l in block.splitlines() if "com_arguments" in l)
    assert "x25.4" in user and "x1000" in user
    assert "0.001" in com


FORMULA_SAFE = re.compile(r"^[0-9A-Za-z_+\-*/()., ^=]+$")


def evaluate_card_formula(expr, params):
    """Evaluate the card's own formula text, so the claim tested is the card's."""
    assert FORMULA_SAFE.match(expr), expr
    env = {"pi": math.pi}
    env.update(params)
    return eval(expr.replace("^", "**"), {"__builtins__": {}}, env)


def test_card_formulas_reproduce_the_executors_analytic_deltas(cards, executor):
    """The card must not drift from the physics the actuator enforces."""
    params = pd.baseline(executor)
    expected = executor.analytic_dv(params)
    for tag, formula in cards["analytic_expectations"].items():
        if tag == "note":
            continue
        got = evaluate_card_formula(formula, dict(params))
        assert abs(got - expected[tag]) < 1e-3, (tag, got, expected[tag])
    assert set(expected) == {t for t in cards["analytic_expectations"] if t != "note"}


def test_invariants_in_the_card_are_the_ones_the_executor_enforces(cards, executor):
    block = cc.render_for_injection(cards, mode=cc.FORMULA)
    assert "EXPECTED PER-FEATURE VOLUME DELTA" in block
    assert "base_disk = pi" in block
    assert ">= 1 mm" in block and ">= 2 mm" in block
    assert cc.render_for_injection(cards, mode=cc.CONTRACT).count("CAPABILITY ") == block.count("CAPABILITY ")


def test_clean_baseline_is_green(executor):
    base = pd.baseline(executor)
    steps = pd.readback_steps(executor, base)
    verdict = pd.oracle(executor, base, steps, round(sum(executor.analytic_dv(base).values()), 3))
    assert verdict["clean"], verdict["violations"]


def test_single_field_inch_slip_keeps_every_inequality_green(executor):
    """Non-vacuity of the unit rule.

    A 0.079 mm chamfer satisfies every executor inequality - it is positive and it
    is smaller than the geometry it must fit on - so only a magnitude check can see
    it. If the executor grows a chamfer floor this fails and R_UNIT stops being the
    sole detector, which is exactly the drift worth being told about.
    """
    base = pd.baseline(executor)
    slip = dict(base, chamfer=base["chamfer"] / 25.4)
    assert executor.validate(slip) == []
    assert pd.check_unit_plausibility(slip), "unit rule must be the one that fires"


def test_wholesale_inch_slip_also_trips_the_absolute_floors(executor):
    """Recorded so nobody re-claims homogeneity: rim >= 2 mm and gap >= 1 mm are
    absolute, so scaling every length by 1/25.4 trips them as a side effect."""
    inch = {k: (v if k == "n_bolts" else v / 25.4) for k, v in pd.baseline(executor).items()}
    assert executor.validate(inch)


def test_each_defect_is_isolated_to_exactly_one_violation(executor):
    """A payload with two independent problems cannot say which one was missed.

    D1 originally carried an unplanned D_bore < D_hub break inherited from the
    baseline, and the model's correct report of that break was scored as a blind
    spot. This invariant is what keeps attribution honest.
    """
    for defect in pd.build_defects(executor):
        got = pd.oracle(executor, defect["params"], defect.get("steps"), defect.get("claim_mm3"))
        assert len(got["violations"]) == 1, (defect["id"], got["violations"])
        assert got["violations"][0]["rule"] == defect["rule"], (defect["id"], got["violations"])


def test_each_defect_is_detected_then_repaired(executor):
    for defect in pd.build_defects(executor):
        got = pd.oracle(executor, defect["params"], defect.get("steps"), defect.get("claim_mm3"))
        fired = [v for v in got["violations"] if v["rule"] == defect["rule"]
                 and defect["expect_hint"].lower() in (v.get("hint") or "").lower()]
        assert fired, (defect["id"], got["violations"])
        steps = defect.get("repair_steps", defect.get("steps"))
        repaired = pd.oracle(executor, defect["repair"], steps,
                             defect.get("repair_claim_mm3", defect.get("claim_mm3")))
        assert repaired["clean"], (defect["id"], repaired["violations"])


def test_mutants_reach_the_branch_they_claim(executor):
    base = pd.baseline(executor)
    clean = pd.readback_steps(executor, base)
    flipped = pd.readback_steps(executor, base, corrupt_tag="bore_cut")
    clean_row = next(s for s in clean if s["tag"] == "bore_cut")
    flip_row = next(s for s in flipped if s["tag"] == "bore_cut")
    assert clean_row["dv_mm3"] < 0 < flip_row["dv_mm3"]

    defects = {d["id"]: d for d in pd.build_defects(executor)}
    sources = [s["volume_mm3"] for s in clean]
    claim = defects["D5_fabricated_volume"]["claim_mm3"]
    assert min(abs(claim - v) / abs(v) for v in sources) > 1e-3
    undercut = defects["D1_hub_undercut"]["params"]
    assert undercut["PCD"] / 2 - undercut["D_bolt"] / 2 - undercut["D_hub"] / 2 < 1.0


def test_givencalc_prompt_hands_over_numbers_and_drops_the_arithmetic_request(executor):
    """The fourth arm isolates judgement: if it still must produce the numbers, the
    arm measures arithmetic again and the false-alarm question stays unanswerable."""
    case = rd.control_case(executor)
    expectations = pd.derived_expectations(executor, case["params"], case["steps"])
    plain = rd.build_case_prompt(case, "")
    given = rd.build_case_prompt(case, "", expectations)
    assert "先算再判" in plain and "先算再判" not in given
    assert "执行器已算好的校验量" in given and "执行器已算好的校验量" not in plain
    assert given.count('"computed"') == 0


def test_rates_denominator_excludes_not_applicable_rows(executor):
    """D4/D5 have no machine-checkable repair; dividing their n/a by all reps would
    read as a failure rate rather than as not applicable."""
    defect = next(d for d in pd.build_defects(executor) if d["id"] == "D4_cut_adds_material")
    planted = pd.oracle(executor, defect["params"], defect["steps"], defect["claim_mm3"])["violations"]
    expectations = pd.derived_expectations(executor, defect["params"], defect["steps"])
    row = rd.score_reply(defect, {"defect_found": True, "offending_field": "bore_cut",
                                  "reason": "x", "repaired_params": None}, executor, planted, expectations)
    assert row["repair_accepted"] is None


def test_prompts_do_not_leak_the_expected_answer(executor):
    """A case that names its own answer measures reading comprehension, not physics.

    expected_dv_mm3 stays inside the readback on purpose: the real executor emits
    it, and the point of D4 is that the model misreads a number put in front of it.
    """
    doc, _ = cc.load_cards("solidworks")
    block = cc.render_for_injection(doc)
    for defect in pd.build_defects(executor):
        prompt = rd.build_case_prompt(defect, block)
        assert defect["expect_hint"] not in prompt
        assert defect["rule"] not in prompt
        assert defect["id"] not in prompt


def test_citation_targets_exist_for_readback_defects(executor):
    """Sign and provenance hints carry no digits, so targets must come from the
    numeric fields too, otherwise 'cited the offending magnitude' can never fire.

    Parameter-level defects deliberately get no citation target: a derived value
    like the -4.00 mm rim web collides numerically with n_bolts=4, so field naming
    is the unambiguous route there.
    """
    for defect in pd.build_defects(executor):
        assert rd.ADMISSIBLE_FIELDS[defect["id"]], defect["id"]
        if defect["rule"] not in (pd.R_SIGN, pd.R_PROVENANCE):
            continue
        violations = pd.oracle(executor, defect["params"], defect.get("steps"),
                               defect.get("claim_mm3"))["violations"]
        targets = rd.violation_magnitudes(violations, defect)
        assert targets, (defect["id"], violations)


def test_control_case_punishes_indiscriminate_defect_claims(executor):
    case = rd.control_case(executor)
    planted = pd.oracle(executor, case["params"], case["steps"], case["claim_mm3"])["violations"]
    expectations = pd.derived_expectations(executor, case["params"], case["steps"])
    shouty = {"defect_found": True, "offending_field": "PCD", "reason": "体积不符", "repaired_params": None}
    calm = {"defect_found": False, "offending_field": None, "reason": "自洽", "repaired_params": None}
    assert rd.score_reply(case, shouty, executor, planted, expectations)["false_alarm"] is True
    assert rd.score_reply(case, calm, executor, planted, expectations)["false_alarm"] is False


def test_computed_gate_requires_the_numbers_not_just_a_verdict(executor):
    case = rd.control_case(executor)
    planted = pd.oracle(executor, case["params"], case["steps"], case["claim_mm3"])["violations"]
    expectations = pd.derived_expectations(executor, case["params"], case["steps"])
    absent = {"defect_found": False, "offending_field": None, "reason": "x"}
    wrong = {"computed": dict(expectations, rim_web_mm=-40.0), "defect_found": False,
             "offending_field": None, "reason": "x"}
    right = {"computed": dict(expectations), "defect_found": False, "offending_field": None, "reason": "x"}
    assert rd.score_reply(case, absent, executor, planted, expectations)["computed_correct"] is False
    assert rd.score_reply(case, wrong, executor, planted, expectations)["computed_correct"] is False
    assert rd.score_reply(case, right, executor, planted, expectations)["computed_correct"] is True


def test_located_accepts_a_cited_magnitude_not_only_a_field_name(executor):
    """The old judge marked the card arm blind on D5 even though it quoted the
    fabricated number; naming power must not be the only route to credit."""
    defect = next(d for d in pd.build_defects(executor) if d["id"] == "D5_fabricated_volume")
    planted = pd.oracle(executor, defect["params"], defect["steps"], defect["claim_mm3"])["violations"]
    expectations = pd.derived_expectations(executor, defect["params"], defect["steps"])
    claim = defect["claim_mm3"]
    named = {"defect_found": True, "offending_field": "volume_mm3", "reason": "x", "repaired_params": None}
    cited = {"defect_found": True, "offending_field": "H_total",
             "reason": "体积应为 360703.0 而操作员汇报 %s" % claim, "repaired_params": None}
    vague = {"defect_found": True, "offending_field": "H_total", "reason": "高度不合理",
             "repaired_params": None}
    assert rd.score_reply(defect, named, executor, planted, expectations)["located"] is True
    assert rd.score_reply(defect, cited, executor, planted, expectations)["located"] is True
    assert rd.score_reply(defect, vague, executor, planted, expectations)["located"] is False


def test_repair_must_actually_satisfy_the_oracle(executor):
    defect = next(d for d in pd.build_defects(executor) if d["id"] == "D1_hub_undercut")
    planted = pd.oracle(executor, defect["params"], None, None)["violations"]
    expectations = pd.derived_expectations(executor, defect["params"])
    noop = {"defect_found": True, "offending_field": "PCD", "reason": "x",
            "repaired_params": {"PCD": defect["params"]["PCD"]}}
    row = rd.score_reply(defect, noop, executor, planted, expectations)
    assert row["located"] and row["repair_accepted"] is False and not row["changed_fields"]

    good = {"defect_found": True, "offending_field": "PCD", "reason": "间隙为负",
            "repaired_params": {"PCD": 40.5}}
    assert rd.score_reply(defect, good, executor, planted, expectations)["repair_accepted"] is True

    worse = {"defect_found": True, "offending_field": "H_total", "reason": "x",
             "repaired_params": {"H_total": 3.0}}
    row = rd.score_reply(defect, worse, executor, planted, expectations)
    assert row["repair_accepted"] is False and row["created_new_violation"] is True


def test_solver_solves_every_parameter_defect_and_refuses_the_rest(executor):
    """D1 regression: a coarse multiplicative grid reported it unsolvable while
    PCD=40.5 satisfies every constraint. A false 'no solution' is worse than a
    wrong one, because the harness then has nothing to put in front of the verifier."""
    for defect in pd.build_defects(executor):
        solved = mr.find_repair(executor, defect["params"])
        if defect["id"] in ("D1_hub_undercut", "D2_rim_breakout", "D3_unit_confusion"):
            assert solved["applicable"], (defect["id"], solved.get("reason"))
            merged = dict(defect["params"])
            merged[solved["repair"]["field"]] = solved["repair"]["to"]
            assert pd.oracle(executor, merged)["clean"]
        else:
            assert not solved["applicable"]
            assert solved["reason"] == "parameters already satisfy the oracle"


def test_near_miss_negative_control_is_actually_dirty(executor):
    """A verifier cannot be scored on rubber-stamping unless the wrong answer is wrong."""
    for defect in pd.build_defects(executor):
        solved = mr.find_repair(executor, defect["params"])
        if not solved["applicable"]:
            continue
        near = mr.near_miss_variant(executor, defect["params"], solved["repair"])
        assert near is not None, defect["id"]
        assert not pd.oracle(executor, near["params"])["clean"], (defect["id"], near)


def test_intent_pair_exists_and_is_flagged_not_assumed(executor):
    """Two legal chamfers, 0.2 and 2.0: the constraint set cannot choose, and a
    cheapest-first solver would silently ship the degenerate one."""
    defect = next(d for d in pd.build_defects(executor) if d["id"] == "D3_unit_confusion")
    solved = mr.find_repair(executor, defect["params"])
    unit = [f for f in solved["feasible"] if f.get("unit_restored")]
    assert unit and unit[0]["to"] == 2.0
    assert solved["repair"]["to"] != 2.0


def test_verifier_scoring_catches_a_rubber_stamp(executor):
    items = [i for i in rd.build_verify_items(executor) if i["kind"] == "accept"]
    dirty = next(i for i in items if i["expect_accept"] is False)
    clean = next(i for i in items if i["expect_accept"] is True)
    yes = {"computed": dict(dirty["expectations"]), "acceptable": True, "violated_constraint": None}
    assert rd.score_verify(dirty, yes, executor)["correct"] is False
    assert rd.score_verify(dirty, yes, executor)["note"] == "rubber_stamp"
    assert rd.score_verify(clean, yes, executor)["correct"] is True
    no = {"computed": dict(dirty["expectations"]), "acceptable": False,
          "violated_constraint": "gap >= 1"}
    assert rd.score_verify(dirty, no, executor)["correct"] is True


def test_choice_items_do_not_reward_position_bias(executor):
    """The same pair is shown in both orders, so a model that always answers A is
    caught by the flipped copy rather than credited."""
    items = [i for i in rd.build_verify_items(executor) if i["kind"] == "choice"]
    assert items and len({i["correct"] for i in items}) == 2
    straight = next(i for i in items if i["correct"] == "B")
    always_a = {"choice": "A", "reason": "x"}
    assert rd.score_verify(straight, always_a, executor)["correct"] is False


def test_repair_flags_a_new_violation_besides_the_planted_one(executor):
    """An edit that breaks a different rule is not a partial fix; it is damage."""
    defect = next(d for d in pd.build_defects(executor) if d["id"] == "D2_rim_breakout")
    planted = pd.oracle(executor, defect["params"], None, None)["violations"]
    expectations = pd.derived_expectations(executor, defect["params"])
    answer = {"defect_found": True, "offending_field": "PCD", "reason": "4.0",
              "repaired_params": {"PCD": 125.0}}
    row = rd.score_reply(defect, answer, executor, planted, expectations)
    assert row["repair_accepted"] is True and row["created_new_violation"] is False



def test_guarded_audit_eliminates_false_alarm_on_clean_control(executor):
    """The compute-first gate stops the 100% false alarm rate on clean baseline."""
    control = rd.control_case(executor)
    expectations = pd.derived_expectations(executor, control["params"])
    hallucinated_answer = {
        "defect_found": True,
        "offending_field": "PCD",
        "reason": "I think PCD is too close to hub.",
        "repaired_params": {"PCD": 120.0}
    }
    raw_row = rd.score_reply(control, dict(hallucinated_answer), executor, [], expectations, guarded=False)
    assert raw_row["false_alarm"] is True

    guarded_row = rd.score_reply(control, dict(hallucinated_answer), executor, [], expectations, guarded=True)
    assert guarded_row["false_alarm"] is False
    assert guarded_row["note"] == "correctly clean"


def test_guarded_audit_delegates_repair_to_minimal_repair_solver(executor):
    """When a real defect is detected, the deterministic solver supplies a verified repair."""
    defect = next(d for d in pd.build_defects(executor) if d["id"] == "D1_hub_undercut")
    planted = pd.oracle(executor, defect["params"], None, None)["violations"]
    expectations = pd.derived_expectations(executor, defect["params"])
    answer_no_repair = {
        "defect_found": True,
        "offending_field": "D_hub",
        "reason": "hub undercut clearance -8.0 mm",
        "repaired_params": None
    }
    guarded_row = rd.score_reply(defect, dict(answer_no_repair), executor, planted, expectations, guarded=True)
    assert guarded_row["repair_accepted"] is True
    assert guarded_row["created_new_violation"] is False
