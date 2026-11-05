"""Paired validation must not silently approve regression or incomplete evidence."""

from copy import deepcopy

import pytest

from virtu_omni.rsi.contracts import Config
from virtu_omni.rsi.gates import validation_gate


def _record(i, score):
    return {"case_id": str(i), "dimension": "physics", "score": score,
            "all_passed": score == 100, "verdict": "pass" if score == 100 else "partial",
            "criteria": [{"key": "physical", "type": "world_state_verified", "passed": score == 100}]}


def _pair():
    b = [_record(i, 40 if i < 4 else 100) for i in range(20)]
    c = [_record(i, 100) for i in range(20)]
    return b, c


def test_complete_improvement_eligible_but_not_approved():
    b, c = _pair()
    result = validation_gate(b, c, [str(i) for i in range(20)], Config(), "sha")
    assert result["eligible"] and result["mean_gain"] == 12
    assert result["paired_regressions"] == 0
    assert "approved" not in result


@pytest.mark.parametrize("bad", ["transport_error", "grader_error", "empty_response", "truncated", "dry_run"])
def test_infra_and_synthetic_failure_denied(bad):
    b, c = _pair()
    c[0]["verdict"] = bad
    assert not validation_gate(b, c, [str(i) for i in range(20)], Config(), "sha")["eligible"]


def test_small_sample_incomplete_or_duplicate_denied():
    b, c = _pair()
    assert not validation_gate(b[:3], c[:3], ["0", "1", "2"], Config(), "sha")["eligible"]
    assert not validation_gate(b, c[:-1], [str(i) for i in range(20)], Config(), "sha")["eligible"]
    assert not validation_gate(b + [b[0]], c, [str(i) for i in range(20)], Config(), "sha")["eligible"]


def test_paired_regression_denied_even_if_average_rises():
    b, c = _pair()
    c[19]["score"] = 80
    c[19]["criteria"][0]["passed"] = False
    result = validation_gate(b, c, [str(i) for i in range(20)], Config(), "sha")
    assert result["mean_gain"] > 5 and not result["eligible"]


def test_safety_failure_and_missing_criteria_denied():
    b, c = _pair()
    c[0]["criteria"][0]["passed"] = False
    assert not validation_gate(b, c, [str(i) for i in range(20)], Config(), "sha")["eligible"]
    c[0]["criteria"] = []
    assert not validation_gate(b, c, [str(i) for i in range(20)], Config(), "sha")["eligible"]


@pytest.mark.parametrize("flag", ["identity_valid", "data_valid", "fresh_validation"])
def test_failed_external_integrity_gate_denied(flag):
    b, c = _pair()
    result = validation_gate(b, c, [str(i) for i in range(20)], Config(), "sha", **{flag: False})
    assert not result["eligible"]


def test_no_candidate_or_no_gain_denied():
    b, c = _pair()
    ids = [str(i) for i in range(20)]
    assert not validation_gate(b, c, ids, Config(), None)["eligible"]
    assert not validation_gate(c, deepcopy(c), ids, Config(), "sha")["eligible"]
