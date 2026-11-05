"""Trusted analytic candidates; no eval-answer copying or fake physical passes."""

import json

import pytest

from virtu_omni.rsi.candidates import _formula_overlap, build_sft_candidates
from virtu_omni.rsi.contracts import Config, fingerprint
from virtu_omni.rsi.evaluation import policy_messages, strict_score
from virtu_omni.rsi.storage import RunStore


SCENARIO = {"task": "roughness", "inputs": {"f": .12, "r_eps": .8}}
CRITERIA = [{"type": "world_state_verified", "scenario": SCENARIO}]


@pytest.mark.parametrize("value", ["2.25", float("nan"), float("inf"), True, None, -4])
def test_strict_physics_rejects_fake_scalar(value):
    result = strict_score(json.dumps({"world_state": {"surface_roughness_ra_um": value}}), CRITERIA)
    assert not result["all_passed"]


def test_strict_physics_accepts_recomputed_and_denies_missing():
    assert strict_score('{"world_state":{"surface_roughness_ra_um":2.25}}', CRITERIA)["all_passed"]
    assert not strict_score('{"world_state":{}}', CRITERIA)["all_passed"]


def test_collision_boolean_cannot_be_string():
    scenario = {"task": "collision", "inputs": {"z_safe": 10, "z_min_rapid": -2, "stock_top": 0}}
    criteria = [{"type": "world_state_verified", "scenario": scenario}]
    state = {"safe_plane_z_mm": 10, "rapid_min_z_mm": -2, "stock_top_z_mm": 0,
             "collision_risk": "high", "gouge": "false", "autodiff": "red"}
    assert not strict_score(json.dumps({"world_state": state}), criteria)["all_passed"]


def test_oracle_free_tasks_not_fabricated(tmp_path):
    s = RunStore(tmp_path)
    rows, report = build_sft_candidates({"weak_tasks": {"mass_props": 2}}, [], [], Config(), s)
    assert rows == []
    assert report["skipped"]["no_trusted_oracle:mass_props"] == 1


def test_generated_data_verified_disjoint_and_repeatable(tmp_path):
    protected = [{"id": "eval", "prompt": "Never train this exact question", "criteria": CRITERIA}]
    config = Config(synthetic_per_task=4)
    s1, s2 = RunStore(tmp_path), RunStore(tmp_path)
    a, report = build_sft_candidates({"weak_tasks": {"roughness": 1, "collision": 2}}, protected, [], config, s1)
    b, _ = build_sft_candidates({"weak_tasks": {"roughness": 1, "collision": 2}}, protected, [], config, s2)
    assert a == b and len(a) == 8 and report["valid"]
    for row in a:
        assert row["meta"]["scenario_sha256"] != fingerprint(SCENARIO)
        assert row["messages"][-1]["role"] == "assistant"
        cs = [{"type": "world_state_verified", "scenario": row["meta"]["scenario"]}]
        assert strict_score(row["messages"][-1]["content"], cs)["all_passed"]
    assert report["requires_manual_training_approval"]


def test_rephrased_scenario_collision_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr("virtu_omni.rsi.candidates._draw", lambda *args: SCENARIO)
    s = RunStore(tmp_path)
    protected = [{"id": "eval", "prompt": "same parameters, different words", "criteria": CRITERIA}]
    rows, report = build_sft_candidates({"weak_tasks": {"roughness": 1}}, protected, [],
                                        Config(synthetic_per_task=1), s)
    assert rows == [] and report["skipped"]["scenario_overlap"] > 0


def test_hard_formula_parameter_rephrase_rejected():
    scenario = {"task": "process", "inputs": {"D": 89, "vc": 71, "f": .2}}
    assert _formula_overlap(scenario, [{"kind": "n", "prompt": "D=89 mm，Vc=71 m/min"}])
    assert not _formula_overlap(scenario, [{"kind": "n", "prompt": "D=90 mm，Vc=71 m/min"}])


def test_inference_messages_never_include_gold_or_criteria():
    case = {"prompt": "compute", "system": "task contract", "context": [],
            "gold": "TOP_SECRET_GOLD", "criteria": CRITERIA}
    messages = policy_messages(case, "check units")
    assert "TOP_SECRET_GOLD" not in json.dumps(messages)
    assert "scenario" not in json.dumps(messages)
    assert "task contract" in messages[0]["content"]
