# -*- coding: utf-8 -*-
"""Falsifiability and end-to-end verification gates for Chain-of-Thought (CoT) strengthening.

Adheres strictly to RULE[d:\\Virtu模型\\AGENTS.md] Section 8:
- Rule 4: Every gate is tested with planted bad samples that MUST turn the verdict red.
- Rule 5: Authoritative laws come solely from virtu_eval.derivation.LAWS and scripts/wm_verifier.recompute.
"""

from __future__ import annotations

import json
import pytest

from scripts.anti_hallucination_guard import Guard
import scripts.wm_contract as wm_contract
from virtu_omni.model_evolution_suite import get_model_evolution_suite
from virtu_omni.reasoning.chain_of_thought import COT_STAGES, StructuredCoTEngine
from virtu_omni.reasoning.process_reward_model import ProcessSupervisedRewardModel
from virtu_omni.training.rlvr_grpo_engine import VirtuGRPOEngine


@pytest.mark.parametrize(
    "scenario,prompt",
    [
        (
            {"task": "removal", "inputs": {"doc": 2.0, "woc": 10.0, "L": 150.0, "vf": 300.0, "rho": 0.00785, "stock_vol": 50000.0}},
            "【场景】铣削去除材料：切深 2 mm，切宽 10 mm，走刀长 150 mm，进给速度 300 mm/min，毛坯体积 50000 mm3，密度 0.00785 g/mm3。",
        ),
        (
            {"task": "fea_fos", "inputs": {"Sy": 355.0, "sigma": 180.0}},
            "【场景】结构强度校核：材料屈服强度 Sy=355 MPa，峰值应力 sigma=180 MPa。",
        ),
        (
            {"task": "roughness", "inputs": {"f": 0.12, "r_eps": 0.8}},
            "【场景】车削表面粗糙度预测：每转进给 f=0.12 mm/rev，刀尖圆弧半径 r_eps=0.8 mm。",
        ),
        (
            {"task": "invalid", "inputs": {"doc": -2.0, "woc": 10.0}, "reason": "negative_cut_depth: 负切削深度非法"},
            "【场景】铣削：切削深度 DOC=-2 mm，切宽 10 mm。",
        ),
    ],
)
def test_synthesized_cot_covers_all_five_stages_and_passes_verification(scenario, prompt):
    traj = StructuredCoTEngine.synthesize_cot(scenario, prompt=prompt)
    assert traj.thinking_text
    assert "<think>" in traj.full_response and "</think>" in traj.full_response
    assert len(traj.steps) == 5
    rep = StructuredCoTEngine.verify_cot_faithfulness(traj.full_response, prompt=prompt, scenario=scenario)
    assert rep.passed is True
    assert rep.has_think_block is True
    assert rep.overall_cot_score >= 0.95
    assert set(rep.stages_covered) == set(COT_STAGES)


@pytest.mark.parametrize(
    "bad_response,expected_error_field",
    [
        (
            "<think>\n[STAGE 4: SYMBOLIC_DERIVATION] safety_factor = 355 / 180 = 2.85\n</think>\n"
            '{"world_state": {"safety_factor": 2.85, "fos_gate": "pass"}}',
            "arithmetic_errors",
        ),
        (
            "<think>\n[STAGE 4: SYMBOLIC_DERIVATION] safety_factor = 355 / 180 = 1.9722\n</think>\n"
            '{"world_state": {"safety_factor": 1.10, "fos_gate": "fail"}}',
            "faithfulness_conflicts",
        ),
        (
            "<think>\n[STAGE 4: SYMBOLIC_DERIVATION] safety_factor = 355 / 250 = 1.42\n</think>\n"
            '{"world_state": {"safety_factor": 1.18, "fos_gate": "pass"}}',
            "faithfulness_conflicts",
        ),
        (
            "<think>\n[STAGE 4: SYMBOLIC_DERIVATION] safety_factor = 600 / 180 = 3.3333\n</think>\n"
            '{"world_state": {"safety_factor": 3.3333, "fos_gate": "pass"}}',
            "ungrounded_literals",
        ),
        (
            '{"world_state": {"safety_factor": 1.9722, "fos_gate": "pass"}}',
            "gate_violations",
        ),
    ],
)
def test_cot_verifier_must_reject_planted_bad_samples(bad_response, expected_error_field):
    """Rule 4: Every planted bad CoT sample MUST fail verification."""
    scenario = {"task": "fea_fos", "inputs": {"Sy": 355.0, "sigma": 180.0}}
    prompt = "【场景】梁受载：材料屈服强度 Sy=355 MPa，最大应力 sigma=180 MPa。"
    rep = StructuredCoTEngine.verify_cot_faithfulness(bad_response, prompt=prompt, scenario=scenario, require_think=True)
    assert rep.passed is False
    assert getattr(rep, expected_error_field), f"Expected non-empty {expected_error_field} on planted bad sample"


def test_prm_cot_step_supervision_isolates_failing_step():
    scenario = {"task": "fea_fos", "inputs": {"Sy": 355.0, "sigma": 180.0}}
    prompt = "Sy=355 MPa, sigma=180 MPa"
    bad_cot = (
        "<think>\n"
        "[STAGE 1: INTENT_AND_GIVENS] 已知 Sy=355 MPa, sigma=180 MPa\n"
        "[STAGE 2: PHYSICAL_LAW_SELECTION] safety_factor = Sy / sigma\n"
        "[STAGE 4: SYMBOLIC_DERIVATION] safety_factor = 355 / 180 = 2.50\n"
        "</think>\n"
        '{"world_state": {"safety_factor": 2.50, "fos_gate": "pass"}}'
    )
    audit = ProcessSupervisedRewardModel.audit_cot_steps(bad_cot, prompt=prompt, scenario=scenario)
    assert audit.all_steps_passed is False
    assert audit.first_failure_step == 3
    assert audit.steps[2].reward == 0.0
    assert "算术失真" in (audit.steps[2].veto_reason or "")


def test_grpo_penalizes_unfaithful_and_arithmetically_broken_cot():
    engine = VirtuGRPOEngine(group_size=3)
    good = (
        "<think>\n[STAGE 4: SYMBOLIC_DERIVATION] safety_factor = 355 / 180 = 1.9722 >= 1.5\n</think>\n"
        "G90 G54 G00 Z50.0\nG01 Z-2.0 F150.0\n# FOS = 1.97"
    )
    bad_unfaithful = (
        "<think>\n[STAGE 4: SYMBOLIC_DERIVATION] safety_factor = 1.15 < 1.5\n</think>\n"
        "G90 G54 G00 Z50.0\nG01 Z-2.0 F150.0\n# FOS = 1.97"
    )
    bad_arith = (
        "<think>\n[STAGE 4: SYMBOLIC_DERIVATION] safety_factor = 355 / 180 = 2.65\n</think>\n"
        "G90 G54 G00 Z50.0\nG01 Z-2.0 F150.0\n# FOS = 1.97"
    )
    cands = engine.evaluate_group(
        prompt="屈服强度 355 MPa，峰值应力 180 MPa",
        candidate_outputs=[good, bad_unfaithful, bad_arith],
        context={"yield_strength_mpa": 355.0, "peak_stress_mpa": 180.0, "stock_top_z_mm": 0.0},
    )
    assert cands[0].composite_reward > 0.85
    assert cands[0].advantage > 0.0
    assert cands[0].r_cot > 0.9
    assert cands[1].composite_reward == 0.0
    assert cands[1].advantage < 0.0
    assert cands[2].composite_reward == 0.0
    assert cands[2].advantage < 0.0


def test_guard_cot_integration_and_contract_sync():
    guard = Guard()
    sc = {"task": "fea_fos", "inputs": {"Sy": 355.0, "sigma": 180.0}}

    # 1. Clean synthesized CoT passes guard with action="accept"
    traj = StructuredCoTEngine.synthesize_cot(sc, prompt="【场景】屈服强度 Sy=355 MPa，最大应力 sigma=180 MPa。")
    res_ok = guard.run(traj.full_response, "【场景】屈服强度 Sy=355 MPa，最大应力 sigma=180 MPa。", sc)
    assert res_ok.action == "accept"
    assert "L1_COT" not in res_ok.layers_hit
    assert "L3_EVIDENCE" not in res_ok.layers_hit

    # 2. Unfaithful <think> vs JSON triggers L1_COT and gets corrected
    bad_resp = (
        "<think>safety_factor = 355 / 180 = 1.9722</think>"
        '{"world_state": {"safety_factor": 1.12, "fos_gate": "fail", "yield_strength_mpa": 355.0, "peak_von_mises_mpa": 180.0}}'
    )
    res_bad = guard.run(bad_resp, "【场景】屈服强度 Sy=355 MPa，最大应力 sigma=180 MPa。", sc)
    assert res_bad.action == "corrected"
    assert "L1_COT" in res_bad.layers_hit
    assert abs(float(res_bad.corrected["safety_factor"]) - 355.0 / 180.0) < 1e-3

    # 3. Contract exports COT_SYSTEM with all 5 stages
    for stage in COT_STAGES:
        assert stage in wm_contract.COT_PROTOCOL_BLOCK
        assert stage in wm_contract.COT_SYSTEM

    # 4. Frontier suite probe passes all 5 subsystems
    suite_rep = get_model_evolution_suite().run_all_frontier_probes()
    assert suite_rep.all_probes_passed is True
    assert suite_rep.cot_probe_passed is True
