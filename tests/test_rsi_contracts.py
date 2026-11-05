"""No-network tests for RSI configuration, split isolation, and sealed storage."""

import json
from pathlib import Path

import pytest

from virtu_omni.rsi.contracts import (Budget, BudgetExhausted, Config, RSIError,
                                      inside, load_cases, local_url, scenario_keys, split_cases)
from virtu_omni.rsi.storage import FileLock, RunStore


@pytest.mark.parametrize("url", ["https://example.com:443", "http://127.0.0.1.evil:80",
                                  "http://user:pass@127.0.0.1:80", "http://127.0.0.1:80/x",
                                  "http://localhost:80?key=x", "file:///tmp/x"])
def test_remote_or_ambiguous_url_denied(url):
    with pytest.raises(RSIError):
        local_url(url)


@pytest.mark.parametrize("changes", [{"rounds": 9}, {"max_calls": 0}, {"max_seconds": 1.5},
                                     {"min_gain": float("nan")}, {"limit": -1},
                                     {"synthetic_per_task": 201}, {"validation_fraction": 1}])
def test_config_denies_invalid_budgets(changes):
    with pytest.raises(RSIError):
        Config(**changes)


def test_budget_enforced_without_extra_call():
    now = [0.0]
    b = Budget(Config(max_calls=1), clock=lambda: now[0])
    assert b.acquire() > 0
    with pytest.raises(BudgetExhausted):
        b.acquire()
    b = Budget(Config(max_seconds=10), clock=lambda: now[0])
    now[0] = 9.0
    with pytest.raises(BudgetExhausted):
        b.acquire()
    assert b.calls == 0


def test_path_escape_denied(tmp_path):
    with pytest.raises(RSIError):
        inside(tmp_path, "../outside")


def _case(i, scenario=None):
    c = {"id": str(i), "dimension": "physics", "tier": "easy",
         "prompt": f"Question number {i}", "criteria": [{"type": "not_empty"}]}
    if scenario:
        c["criteria"] = [{"type": "world_state_verified", "scenario": scenario}]
    return c


def test_split_groups_same_scenario_and_is_deterministic():
    scenario = {"task": "roughness", "inputs": {"f": .13, "r_eps": .8}}
    cases = [_case(i) for i in range(12)]
    cases[0] = _case(0, scenario)
    cases[1] = _case(1, scenario)
    d, v = split_cases(cases, Config())
    assert (d, v) == split_cases(list(reversed(cases)), Config())
    assert {c["id"] for c in d}.isdisjoint(c["id"] for c in v)
    assert {k for c in d for k in scenario_keys(c)}.isdisjoint(k for c in v for k in scenario_keys(c))


def test_duplicate_case_id_and_question_denied(tmp_path):
    p = tmp_path / "physics.jsonl"
    a, b = _case(0), _case(1)
    b["id"] = a["id"]
    p.write_text("\n".join(json.dumps(c) for c in (a, b)), encoding="utf-8")
    with pytest.raises(RSIError, match="Duplicate case id"):
        load_cases(tmp_path, ".")
    b["id"] = "new"
    b["prompt"] = "  question   NUMBER 0 "
    p.write_text("\n".join(json.dumps(c) for c in (a, b)), encoding="utf-8")
    with pytest.raises(RSIError, match="Duplicate normalized"):
        load_cases(tmp_path, ".")


def test_unknown_grader_and_nan_weight_denied(tmp_path):
    p = tmp_path / "physics.jsonl"
    c = _case(0)
    c["criteria"][0]["type"] = "llm_self_score"
    p.write_text(json.dumps(c), encoding="utf-8")
    with pytest.raises(RSIError):
        load_cases(tmp_path, ".")
    c["criteria"] = [{"type": "not_empty", "weight": -1}]
    p.write_text(json.dumps(c), encoding="utf-8")
    with pytest.raises(RSIError):
        load_cases(tmp_path, ".")


def test_seal_detects_tampering_and_path_escape(tmp_path):
    s = RunStore(tmp_path)
    s.write("candidate.json", {"strategy": "verify input"})
    e = s.seal({})
    assert s.verify()["review_sha256"] == e["review_sha256"]
    with pytest.raises(RSIError):
        s.write("../escape.json", {})
    (s.path / "candidate.json").write_text("{}", encoding="utf-8")
    with pytest.raises(RSIError, match="modified"):
        s.verify()


def test_wrong_review_hash_denied(tmp_path):
    s = RunStore(tmp_path)
    s.write("candidate.json", {})
    s.seal({})
    with pytest.raises(RSIError):
        s.verify("wrong")


def test_lock_rejects_concurrent_writer_and_releases(tmp_path):
    path = tmp_path / ".lock"
    with FileLock(path):
        with pytest.raises(RSIError):
            with FileLock(path):
                pass
    with FileLock(path):
        assert path.is_file()
