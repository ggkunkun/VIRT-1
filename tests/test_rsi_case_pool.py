"""The RSI improvement loop must be *measurable*, and its data guard must be provable.

Two things are pinned here:

1. ``data/benchmark/virtu_rsi_pool_v1`` (built by ``scripts/build_rsi_case_pool.py``) gives RSI
   the statistical power it structurally never had: the published physics board has 30 cases,
   so with ``validation_fraction=0.4`` the largest reachable validation set is 12 while
   ``min_validation`` is 20 -- every run against that pool was doomed to
   ``"validation too small"``. The pool must therefore stay solver-verified, gold-100, and
   disjoint from every published ruler.

2. ``Config.protect_dirs`` widens the set the synthetic SFT candidates must not reproduce
   *without* widening what RSI may tune on. Before this, protection scope silently equalled
   selection scope: point RSI at a fresh pool and the published boards stopped being
   protected.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
POOL_DIR = ROOT / "data" / "benchmark" / "virtu_rsi_pool_v1"
BOARD_DIRS = [ROOT / "data" / "benchmark" / name
              for name in ("virtu_eval_phys_v1", "virtu_eval_v1", "virtu_eval_cl_v1")]


def _rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _cases(directory):
    out = []
    for path in sorted(directory.glob("*.jsonl")):
        out.extend(_rows(path))
    return out


def _scenario_keys(cases):
    keys = set()
    for case in cases:
        for crit in case.get("criteria", []):
            if isinstance(crit.get("scenario"), dict):
                keys.add(hashlib.sha256(json.dumps(crit["scenario"], sort_keys=True,
                                                   ensure_ascii=False).encode("utf-8")).hexdigest())
    return keys


@pytest.fixture(scope="module")
def pool():
    if not POOL_DIR.is_dir():
        raise AssertionError("missing pool: run scripts/build_rsi_case_pool.py --per-family 16")
    return _cases(POOL_DIR)


def test_pool_gives_rsi_a_validation_set_at_least_min_validation(pool):
    from virtu_omni.rsi.contracts import Config, load_cases, split_cases

    cfg = Config(case_dir="data/benchmark/virtu_rsi_pool_v1",
                 dimensions=("physics", "derivation"), min_validation=24)
    cases, _protected = load_cases(ROOT, cfg.case_dir, cfg.dimensions)
    dev, validation = split_cases(cases, cfg)
    assert len(validation) >= cfg.min_validation, (len(dev), len(validation))
    assert set(c["id"] for c in dev).isdisjoint(c["id"] for c in validation)


def test_the_published_board_could_never_have_been_enough():
    """The structural blocker itself, kept as a test so nobody re-disables the pool."""
    from virtu_omni.rsi.contracts import Config, load_cases, split_cases

    cases, _ = load_cases(ROOT, "data/benchmark/virtu_eval_phys_v1", ("physics",))
    dev, validation = split_cases(cases, Config(dimensions=("physics",)))
    assert len(cases) == 30
    assert len(validation) < Config().min_validation, "board grew; the blocker claim needs review"


def test_every_pool_gold_is_the_solver_output_and_scores_100(pool):
    from virtu_eval.graders import _wm_verifier, score_case

    wm = _wm_verifier()
    for case in pool:
        scenario = next(c["scenario"] for c in case["criteria"] if isinstance(c.get("scenario"), dict))
        ref = wm.recompute(scenario)
        assert ref, f"{case['id']}: solver returns no reference"
        gold = json.loads(case["gold"]["answer"])
        for field, value in ref.items():
            actual = gold["world_state"][field]
            if isinstance(value, bool) or isinstance(value, str):
                assert actual == value, (case["id"], field, actual, value)
            else:
                assert actual == pytest.approx(value, rel=1e-9), (case["id"], field)
        scored = score_case(case["gold"]["answer"], case["criteria"])
        assert scored["all_passed"], f"{case['id']} gold does not self-score 100: {scored['criteria']}"


def test_pool_is_disjoint_from_every_published_ruler(pool):
    protected = set()
    for directory in BOARD_DIRS:
        if directory.is_dir():
            protected |= _scenario_keys(_cases(directory))
    pool_keys = _scenario_keys(pool)
    assert protected, "board scenario set is empty -> this test would be vacuous"
    assert pool_keys.isdisjoint(protected), sorted(pool_keys & protected)[:5]


def test_pool_tier_mix_matches_the_published_ruler(pool):
    from virtu_eval.validate_cases import expected_mix

    for dimension in ("physics", "derivation"):
        rows = [c for c in pool if c["dimension"] == dimension]
        counts = {t: sum(1 for r in rows if r["tier"] == t) for t in ("easy", "medium", "hard")}
        assert len(rows) >= 30
        assert counts == dict(zip(("easy", "medium", "hard"), expected_mix(len(rows)))), counts


def test_pool_validator_reports_no_problems(pool):
    from virtu_eval.validate_cases import validate

    problems, _summary = validate(str(POOL_DIR))
    assert problems == [], problems[:5]


def test_unknown_tier_and_disagreeing_gold_are_rejected():
    """Reverse probes on the builder itself: the pool must not be able to ship a soft ruler."""
    import random

    from scripts.build_rsi_case_pool import TOL_BY_TIER, _build_criteria, _criteria_template, _tier_sequence
    from virtu_eval.graders import _wm_verifier, score_case

    templates = _criteria_template()
    scenario = {"task": "roughness", "inputs": {"f": 0.2, "r_eps": 0.9}}
    ref = _wm_verifier().recompute(scenario)
    criteria = _build_criteria(templates[("physics", "roughness")], scenario, ref, "easy")
    with pytest.raises(KeyError):
        _build_criteria(templates[("physics", "roughness")], scenario, ref, "nonsense-tier")
    wrong = json.dumps({"world_state": dict(
        ref, surface_roughness_ra_um=ref["surface_roughness_ra_um"] * 3)}, ensure_ascii=False)
    assert not score_case(wrong, criteria)["all_passed"]
    assert TOL_BY_TIER["hard"] < TOL_BY_TIER["easy"]
    for n in (30, 73, 144):
        counts = {}
        for tier in _tier_sequence(n, random.Random(7)):
            counts[tier] = counts.get(tier, 0) + 1
        assert sum(counts.values()) == n
        assert counts.get("hard", 0) == round(n * 0.2) or abs(counts.get("hard", 0) - round(n * 0.2)) <= 1


def test_protect_dirs_widens_protection_without_widening_selection(tmp_path):
    from virtu_omni.rsi.contracts import RSIError, load_cases, protect_cases

    board = _cases(ROOT / "data" / "benchmark" / "virtu_eval_phys_v1")
    board_keys = _scenario_keys(board)
    collected = protect_cases(ROOT, ("data/benchmark/virtu_eval_phys_v1",))
    assert collected, "protection set came back empty -> the guard would be vacuous"
    assert _scenario_keys(collected) >= board_keys
    # Selection must be untouched by protection: the pool still only selects its own cases.
    cases, _protected = load_cases(ROOT, "data/benchmark/virtu_rsi_pool_v1", ("physics",))
    assert {c["id"] for c in cases}.isdisjoint({c["id"] for c in collected})


def test_protect_dirs_fails_closed_on_missing_dir_and_bad_type():
    from virtu_omni.rsi.contracts import Config, RSIError, protect_cases

    with pytest.raises(RSIError):
        protect_cases(ROOT, ("data/benchmark/does_not_exist_v9",))
    with pytest.raises(RSIError):
        Config(protect_dirs="data/benchmark/virtu_eval_phys_v1")  # a bare string would split per char
    assert Config(protect_dirs=["a", "b"]).protect_dirs == ("a", "b")


def test_sft_candidate_protection_actually_includes_the_boards():
    """The point of protect_dirs: candidates must not reproduce a published board scenario."""
    from virtu_omni.rsi.candidates import scenario_keys as _sk  # noqa: F401  (module sanity)
    from virtu_omni.rsi.contracts import load_cases, protect_cases, scenario_keys

    pool_cases, pool_protected = load_cases(ROOT, "data/benchmark/virtu_rsi_pool_v1",
                                            ("physics", "derivation"))
    without = {k for case in pool_protected for k in scenario_keys(case)}
    with_extra = without | {k for case in protect_cases(ROOT, ("data/benchmark/virtu_eval_phys_v1",))
                             for k in scenario_keys(case)}
    board_keys = {k for case in _cases(ROOT / "data" / "benchmark" / "virtu_eval_phys_v1")
                  for k in scenario_keys(case)}
    assert board_keys, "board scenario set empty -> vacuous test"
    assert board_keys - without, "case-dir-only protection should not cover the boards"
    assert board_keys <= with_extra, "protect_dirs must fully cover the published board scenarios"
