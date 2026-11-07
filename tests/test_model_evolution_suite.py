# -*- coding: utf-8 -*-
"""tests/test_model_evolution_suite.py — Test Suite for Virtu Frontier Model Evolution & Reasoning Suite.

Verifies:
1. DeepSeek-R1 / RLVR GRPO: Group Relative Policy Optimization, verifiable physics rewards, advantage normalization.
2. DARE & TIES-Merging: Task arithmetic parameter space fusion, sign consensus election, rogue vector suppression.
3. OpenAI o1 PRM: Process-supervised stepwise evaluation of G-code and CAD feature sequences, Look-Ahead collision interception.
4. MIT DeepCAD B-Rep DSL: Constrained grammar validation, Jordan closed curve verification, Euler-Poincaré invariants.
5. Super Agent Facet Integration: facet_rlvr_eval, facet_prm_audit, facet_brep_compile.
6. Rule 4 Falsifiable Gates: All 4 mutation probes pass.
"""

import os
import sys
import torch
import pytest

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from virtu_omni.model_evolution_suite import get_model_evolution_suite, VirtuFrontierModelSuite
from virtu_omni.training.rlvr_grpo_engine import VirtuGRPOEngine, PhysicalRewardEnvironment
from virtu_omni.models.task_arithmetic_merger import VirtuTaskArithmeticEngine, TaskVector
from virtu_omni.reasoning.process_reward_model import ProcessSupervisedRewardModel
from virtu_omni.reasoning.brep_grammar_dsl import DeepCADBRepGrammarEngine, CADCommand
from virtu_omni.agent import VirtuSuperAgent


def test_01_rlvr_grpo_engine(tmp_path):
    """Verify RLVR evaluation, group relative advantage, and loss computation."""
    engine = VirtuGRPOEngine(group_size=3, log_dir=str(tmp_path))

    traj_good = (
        "<think>\n屈服极限 355MPa，外载峰值应力 150MPa，按 Lamé 理论 FOS = 2.37 >= 1.5 满足安全设计规范。\n</think>\n"
        "G90 G54 G00 Z50.0\nG01 Z-1.5 F100.0\n# FOS = 2.37"
    )
    traj_marginal = (
        "<think>\n简易估算安全系数\n</think>\n"
        "G90 G54 G00 Z20.0\nG01 Z-1.0 F80.0\n# FOS = 1.3"
    )
    traj_bad = (
        "<think>\n盲目进给\n</think>\n"
        "G90 G54 G00 Z-8.0\n# 撞刀下扎"
    )

    cands = engine.evaluate_group(
        prompt="车削轴承档",
        candidate_outputs=[traj_good, traj_marginal, traj_bad],
        context={"yield_strength_mpa": 355.0, "peak_stress_mpa": 150.0, "stock_top_z_mm": 0.0},
    )

    assert len(cands) == 3
    # Best trajectory should have highest reward and strictly positive advantage
    assert cands[0].composite_reward > cands[1].composite_reward
    assert cands[0].advantage > 0.0
    # Worst trajectory (colliding) should have zero reward and negative advantage
    assert cands[2].composite_reward == 0.0
    assert cands[2].advantage < 0.0

    # Test GRPO loss computation
    policy_lp = torch.tensor([[-0.5, -0.6, -0.7]], requires_grad=True)
    old_lp = torch.tensor([[-0.52, -0.58, -0.71]])
    ref_lp = torch.tensor([[-0.51, -0.60, -0.69]])
    adv = torch.tensor([[c.advantage for c in cands]])

    loss, metrics = engine.compute_grpo_loss(policy_lp, old_lp, ref_lp, adv)
    assert loss is not None
    assert "policy_loss" in metrics
    assert "kl_div" in metrics

    # Rule 4 Falsifiable Gate
    assert engine.falsifiable_rlvr_probe() is True


def test_02_task_arithmetic_ties_merging():
    """Verify DARE pruning, TIES sign election, and multi-domain parameter fusion."""
    engine = VirtuTaskArithmeticEngine(dare_drop_rate=0.2, ties_topk=0.6)

    # Base weight (e.g., projection layer)
    base_w = {"transformer.proj.weight": torch.zeros(16, 16)}

    # 3 Domain task vectors: CAD, CAM, CAE
    tv_cad = TaskVector("CAD", {"transformer.proj.weight": torch.randn(16, 16) * 0.1})
    tv_cam = TaskVector("CAM", {"transformer.proj.weight": torch.randn(16, 16) * 0.1})
    tv_cae = TaskVector("CAE", {"transformer.proj.weight": torch.randn(16, 16) * 0.1})

    merged, prov = engine.merge_task_vectors(base_w, [tv_cad, tv_cam, tv_cae])

    assert "transformer.proj.weight" in merged
    assert merged["transformer.proj.weight"].shape == (16, 16)
    assert prov.num_parameters_merged == 256
    assert prov.basis == "measured"
    assert prov.merge_id.startswith("TIES_MERGE_")

    # Rule 4 Falsifiable Gate (Rogue vector suppression)
    assert engine.falsifiable_ties_probe() is True


def test_03_prm_process_reward_model():
    """Verify stepwise evaluation of G-code and CAD feature tree."""
    # 1. Compliant G-code
    clean_gcode = """G90 G54 G21 G17
M03 S2500
G00 Z10.0
G01 Z-1.5 F150.0
G00 Z50.0
M05
"""
    audit = ProcessSupervisedRewardModel.audit_gcode_steps(clean_gcode, safe_plane_z=5.0, stock_top_z=0.0)
    assert audit.all_steps_passed is True
    assert audit.first_failure_step is None
    assert audit.overall_score >= 0.9

    # 2. Fatal G-code with Step 3 rapid plunge
    fatal_gcode = """G90 G54 G21
M03 S2000
G00 Z-4.0
G01 X50.0 F120.0
"""
    fatal_audit = ProcessSupervisedRewardModel.audit_gcode_steps(fatal_gcode, safe_plane_z=5.0, stock_top_z=0.0)
    assert fatal_audit.all_steps_passed is False
    assert fatal_audit.first_failure_step == 3
    assert fatal_audit.steps[2].reward == 0.0
    assert "Fatal G00 rapid plunge" in fatal_audit.fatal_error

    # 3. CAD Feature Tree Stepwise Audit
    cad_steps = [
        {"op": "SKETCH", "closed": True, "name": "BaseSketch"},
        {"op": "EXTRUDE", "depth": 25.0},
        {"op": "CUT_EXTRUDE", "depth": 10.0},
        {"op": "FILLET", "radius": 2.0},
    ]
    cad_audit = ProcessSupervisedRewardModel.audit_cad_steps(cad_steps)
    assert cad_audit.all_steps_passed is True
    assert cad_audit.overall_score == 1.0

    # Rule 4 Falsifiable Gate
    assert ProcessSupervisedRewardModel.falsifiable_prm_probe() is True


def test_04_deepcad_brep_grammar_dsl():
    """Verify MIT DeepCAD B-Rep grammar parsing, polygon simple manifold, and compilation."""
    # Valid 60x40 mm rectangular prism extruded 20 mm
    cmds = [
        CADCommand("LINE", {"x1": 0.0, "y1": 0.0, "x2": 60.0, "y2": 0.0}),
        CADCommand("LINE", {"x1": 60.0, "y1": 0.0, "x2": 60.0, "y2": 40.0}),
        CADCommand("LINE", {"x1": 60.0, "y1": 40.0, "x2": 0.0, "y2": 40.0}),
        CADCommand("LINE", {"x1": 0.0, "y1": 40.0, "x2": 0.0, "y2": 0.0}),
        CADCommand("CLOSE_LOOP", {}),
        CADCommand("EXTRUDE", {"depth": 20.0}),
    ]

    code, report = DeepCADBRepGrammarEngine.validate_and_compile(cmds, part_name="TestBlock")
    assert report.is_valid_manifold is True
    assert report.is_closed_loop is True
    assert report.is_simple_polygon is True
    assert report.euler_characteristic == 2
    assert abs(report.total_area_mm2 - 2400.0) < 1e-3
    assert abs(report.total_volume_mm3 - 48000.0) < 1e-3
    assert code is not None
    assert "BuildPart" in code
    assert "extrude(amount=20.0)" in code

    # Rule 4 Falsifiable Gate
    assert DeepCADBRepGrammarEngine.falsifiable_brep_probe() is True


def test_05_super_agent_frontier_facets():
    """Verify Super Agent invocation of the 3 new frontier facets."""
    agent = VirtuSuperAgent()

    # 1. Facet RLVR
    res_rlvr = agent.facet_rlvr_eval(
        prompt="测试工步",
        candidates=["<think>\nLamé 应力校验合格 FOS=2.1\n</think>\nG90 G00 Z50.0\nG01 Z-2.0 F100.0\n# FOS=2.1"],
        context={"yield_strength_mpa": 355.0, "peak_stress_mpa": 160.0, "stock_top_z_mm": 0.0},
    )
    assert res_rlvr["group_size"] == 1
    assert res_rlvr["best_reward"] > 0.8

    # 2. Facet PRM
    res_prm = agent.facet_prm_audit("G90 G54 G00 Z50.0\nM03 S2000\nG01 Z-1.0 F100.0\nM05")
    assert res_prm["all_steps_passed"] is True

    # 3. Facet DeepCAD
    res_brep = agent.facet_brep_compile([
        {"op": "LINE", "params": {"x1": 0.0, "y1": 0.0, "x2": 30.0, "y2": 0.0}},
        {"op": "LINE", "params": {"x1": 30.0, "y1": 0.0, "x2": 30.0, "y2": 30.0}},
        {"op": "LINE", "params": {"x1": 30.0, "y1": 30.0, "x2": 0.0, "y2": 30.0}},
        {"op": "LINE", "params": {"x1": 0.0, "y1": 30.0, "x2": 0.0, "y2": 0.0}},
        {"op": "CLOSE_LOOP", "params": {}},
        {"op": "EXTRUDE", "params": {"depth": 10.0}},
    ])
    assert res_brep["is_valid"] is True
    assert "compiled_code" in res_brep


def test_06_frontier_suite_probes_report():
    """Verify full frontier suite probes adhering to Section 8."""
    suite = get_model_evolution_suite()
    rep = suite.run_all_frontier_probes()
    assert rep.all_probes_passed is True
    assert rep.rlvr_probe_passed is True
    assert rep.ties_probe_passed is True
    assert rep.prm_probe_passed is True
    assert rep.brep_probe_passed is True
    assert rep.basis == "measured"
    assert rep.run_id.startswith("FMERS_PROBE_")
