"""The physics case set must be *derived*, not declarable.

Three properties, all checked against the shipped jsonl rather than a fixture:
  1. every gold reproduces the solver exactly (no author-typed number survives),
  2. corrupting any single graded field by 25% drops that case below 100,
  3. a case whose gold is only the solver's answer scores 100 under its own tier tolerance.

Property 2 is the one that matters: it is what stops "the report says PASS" from meaning
"the prose was fluent".
"""
import json
import os

import pytest

from virtu_eval.graders import _wm_verifier, score_case

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASE_PATH = os.path.join(ROOT, "data", "benchmark", "virtu_eval_phys_v1", "physics.jsonl")


def _cases():
    if not os.path.exists(CASE_PATH):
        pytest.skip(f"run scripts/build_physics_acceptance_cases.py first: {CASE_PATH} missing")
    with open(CASE_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


ALL = _cases()
IDS = [c["id"] for c in ALL]


def _gold_state(case):
    return json.loads(case["gold"]["answer"])["world_state"]


def _verified_crit(case):
    return [c for c in case["criteria"] if c["type"] == "world_state_verified"][0]


def test_set_covers_the_solver_families_and_tiers():
    assert len(ALL) == 30, len(ALL)
    assert len(set(IDS)) == len(ALL), "duplicate case ids"
    families = {c["tags"][1] for c in ALL}
    assert len(families) >= 9, f"only {sorted(families)}"
    tiers = {c["tier"] for c in ALL}
    assert tiers == {"easy", "medium", "hard"}


@pytest.mark.parametrize("case", ALL, ids=IDS)
def test_gold_reproduces_the_solver(case):
    """The gold is the solver's output; nobody gets to type a physics number into a case."""
    ref = _wm_verifier().recompute(_verified_crit(case)["scenario"])
    assert ref, f"{case['id']}: solver has no reference, so this case is unsatisfiable"
    gold = _gold_state(case)
    for key, value in ref.items():
        assert key in gold, f"{case['id']} gold omits solver field {key}"
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            assert gold[key] == pytest.approx(value, rel=0.01), \
                f"{case['id']}.{key}: gold {gold[key]} != solver {value}"


@pytest.mark.parametrize("case", ALL, ids=IDS)
def test_clean_gold_scores_100(case):
    scored = score_case(case["gold"]["answer"], case["criteria"])
    assert scored["score"] == 100.0, \
        {d["key"]: d["evidence"] for d in scored["criteria"] if not d["passed"]}


@pytest.mark.parametrize("case", ALL, ids=IDS)
def test_single_field_corruption_is_caught(case):
    """For every graded scalar field: mutate it by +25% and the case must stop being a pass."""
    crit = _verified_crit(case)
    ref = _wm_verifier().recompute(crit["scenario"])
    gold = _gold_state(case)
    numeric = [k for k, v in ref.items()
               if isinstance(v, (int, float)) and not isinstance(v, bool)]
    assert numeric, f"{case['id']}: nothing numeric to grade"
    caught = 0
    for key in numeric:
        state = dict(gold)
        state[key] = round(state[key] * 1.25, 6)
        scored = score_case(json.dumps({"world_state": state}, ensure_ascii=False),
                            case["criteria"])
        assert scored["score"] < 100.0, f"{case['id']}.{key}: +25% still scored 100"
        caught += 1
    assert caught == len(numeric)


def test_a_fluent_but_unstructured_answer_scores_zero():
    """Regression against the old ruler's failure mode: prose reciting numbers earned credit."""
    case = ALL[0]
    prose = "该工序材料去除率约为 4000 mm3/min，剩余质量约 1562 g，满足体积守恒。"
    scored = score_case(prose, [_verified_crit(case)])
    assert scored["score"] == 0.0
    assert "world_state_unparsed" in scored["criteria"][0]["evidence"]


@pytest.mark.parametrize("case", ALL, ids=IDS)
def test_flipping_a_gate_verdict_is_caught(case):
    """Numbers alone are not the product: red/yellow/green, gouge and within_limit must bite too."""
    crit = _verified_crit(case)
    ref = _wm_verifier().recompute(crit["scenario"])
    gold = _gold_state(case)
    gates = {k: v for k, v in ref.items()
             if isinstance(v, bool) or (isinstance(v, str) and not isinstance(v, bool))}
    alternatives = {"autodiff": [v for v in ("red", "yellow", "green") if v != gates.get("autodiff")],
                    "collision_risk": [v for v in ("high", "none") if v != gates.get("collision_risk")]}
    for key, value in gates.items():
        flipped = alternatives.get(key, [None if value else True])
        for alt in flipped:
            if alt is None:
                continue
            state = dict(gold)
            state[key] = alt
            scored = score_case(json.dumps({"world_state": state}, ensure_ascii=False),
                                case["criteria"])
            assert scored["score"] < 100.0, f"{case['id']}.{key}: {value}->{alt} still scored 100"


def test_at_least_one_case_exercises_every_gate_kind():
    """Guard against a set where verdict fields only ever appear in one direction."""
    seen = set()
    for case in ALL:
        ref = _wm_verifier().recompute(_verified_crit(case)["scenario"])
        for key, value in ref.items():
            if isinstance(value, (bool, str)):
                seen.add((key, str(value)))
    assert ("autodiff", "red") in seen and ("autodiff", "green") in seen, seen
    assert ("gouge", "True") in seen and ("gouge", "False") in seen, seen
    assert ("within_limit", "True") in seen and ("within_limit", "False") in seen, seen


def test_run_exporter_labels_triples_with_the_graders_verdict(tmp_path):
    """The corpus is a by-product of judging: one run must emit (intent, prediction, reference,
    per-field error) rows whose ``verified`` flag is literally the grader's verdict."""
    from virtu_eval.export_physics_triples import export

    case = next(c for c in ALL if c["tags"][1] == "removal")
    gold = _gold_state(case)
    corrupt = dict(gold)
    corrupt["removed_mass_g"] = round(gold["removed_mass_g"] * 1.25, 6)
    records = [
        {"case_id": case["id"], "dimension": "physics", "tier": case["tier"],
         "tags": case["tags"], "response": json.dumps({"world_state": gold}, ensure_ascii=False),
         "verdict": "pass", "score": 100.0},
        {"case_id": case["id"], "dimension": "physics", "tier": case["tier"],
         "tags": case["tags"], "response": json.dumps({"world_state": corrupt}, ensure_ascii=False),
         "verdict": "partial", "score": 25.0},
        {"case_id": case["id"], "dimension": "physics", "tier": case["tier"],
         "tags": case["tags"], "response": "去除质量约为原来的 1.25 倍，其余量略。",
         "verdict": "partial", "score": 25.0},
    ]
    raw = tmp_path / "raw.jsonl"
    raw.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records), encoding="utf-8")
    out = tmp_path / "triples.jsonl"

    path, n, kept = export(str(tmp_path),
                           case_dir=os.path.dirname(CASE_PATH), out=str(out))
    assert (n, kept) == (3, 3)
    triples = [json.loads(line) for line in
               open(path, encoding="utf-8").read().splitlines() if line.strip()]
    assert [t["verified"] for t in triples] == [True, False, False]

    mass = [f for f in triples[1]["fields"] if f["field"] == "removed_mass_g"][0]
    assert mass["rel_err"] == pytest.approx(0.25, rel=0.01)
    assert mass["ref"] == pytest.approx(gold["removed_mass_g"], rel=0.01)
    assert triples[2]["prediction"] is None
    assert triples[2]["intent"] == case["prompt"], "the intent column must be the real prompt"
