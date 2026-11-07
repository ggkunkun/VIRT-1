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
    result = validation_gate(b, c, [str(i) for i in range(20)], Config(noise_sigma=8.84), "sha")
    assert result["eligible"] and result["mean_gain"] == 12
    assert result["paired_regressions"] == 0
    assert "approved" not in result


@pytest.mark.parametrize("bad", ["transport_error", "grader_error", "empty_response", "truncated", "dry_run"])
def test_infra_and_synthetic_failure_denied(bad):
    b, c = _pair()
    c[0]["verdict"] = bad
    assert not validation_gate(b, c, [str(i) for i in range(20)], Config(noise_sigma=8.84), "sha")["eligible"]


def test_small_sample_incomplete_or_duplicate_denied():
    b, c = _pair()
    assert not validation_gate(b[:3], c[:3], ["0", "1", "2"], Config(noise_sigma=8.84), "sha")["eligible"]
    assert not validation_gate(b, c[:-1], [str(i) for i in range(20)], Config(noise_sigma=8.84), "sha")["eligible"]
    assert not validation_gate(b + [b[0]], c, [str(i) for i in range(20)], Config(noise_sigma=8.84), "sha")["eligible"]


def test_paired_regression_denied_even_if_average_rises():
    b, c = _pair()
    c[19]["score"] = 80
    c[19]["criteria"][0]["passed"] = False
    result = validation_gate(b, c, [str(i) for i in range(20)], Config(noise_sigma=8.84), "sha")
    assert result["mean_gain"] > 5 and not result["eligible"]


def test_safety_failure_and_missing_criteria_denied():
    b, c = _pair()
    c[0]["criteria"][0]["passed"] = False
    assert not validation_gate(b, c, [str(i) for i in range(20)], Config(noise_sigma=8.84), "sha")["eligible"]
    c[0]["criteria"] = []
    assert not validation_gate(b, c, [str(i) for i in range(20)], Config(noise_sigma=8.84), "sha")["eligible"]


@pytest.mark.parametrize("flag", ["identity_valid", "data_valid", "fresh_validation"])
def test_failed_external_integrity_gate_denied(flag):
    b, c = _pair()
    result = validation_gate(b, c, [str(i) for i in range(20)], Config(noise_sigma=8.84), "sha", **{flag: False})
    assert not result["eligible"]


def test_no_candidate_or_no_gain_denied():
    b, c = _pair()
    ids = [str(i) for i in range(20)]
    assert not validation_gate(b, c, ids, Config(noise_sigma=8.84), None)["eligible"]
    assert not validation_gate(c, deepcopy(c), ids, Config(noise_sigma=8.84), "sha")["eligible"]


def test_unconfigured_noise_gate_is_fail_closed():
    """sigma=0 used to mean 'gate off'; it is now 'no resolution, no conclusion'."""
    b, c = _pair()
    result = validation_gate(b, c, [str(i) for i in range(20)], Config(), "sha")
    assert not result["eligible"] and not result["certifiable"]
    assert any("noise resolution gate not configured" in r for r in result["reasons"])


def test_gain_inside_the_band_is_undecidable():
    b = [_record(i, 40 if i < 4 else 100) for i in range(20)]
    c = [_record(i, 42 if i < 4 else 100) for i in range(20)]  # +0.4 mean, band 3.87
    result = validation_gate(b, c, [str(i) for i in range(20)],
                             Config(noise_sigma=8.84, min_gain=0.1), "sha")
    assert result["mean_gain"] < result["paired_noise_band"] and not result["eligible"]
    assert any("inside paired noise band" in r for r in result["reasons"])


def test_synthetic_run_is_eligible_but_never_certifiable():
    b, c = _pair()
    result = validation_gate(b, c, [str(i) for i in range(20)],
                             Config(noise_sigma=8.84, synthetic_run=True), "sha")
    assert result["eligible"] and result["synthetic"] and not result["certifiable"]


def test_mock_identity_never_certifies():
    from virtu_omni.rsi.gates import identity_is_real

    b, c = _pair()
    mock = {"kind": "ollama_native", "model_id": "virtu-moe-14b:latest",
            "digest": "mock_moe_14b_digest_001"}
    result = validation_gate(b, c, [str(i) for i in range(20)], Config(noise_sigma=8.84), "sha",
                             identity_valid=identity_is_real(mock))
    assert not result["eligible"] and not result["certifiable"]
    assert not identity_is_real(dict(mock, digest="declared-fake-test-digest"))
    assert identity_is_real(dict(mock, digest="a" * 64))
