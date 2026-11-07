# -*- coding: utf-8 -*-
"""tests/test_google_deepmind_suite.py — Test Suite for Virtu-Google DeepMind Suite.

Verifies:
1. FunSearch Engine: Multi-island population, program compilation sandbox, mutation, evaluation, falsifiable probe.
2. AlphaGeometry Symbolic Engine: Constraint satisfaction (well-constrained, under-constrained), exact area/volume calculation, code synthesis, falsifiable probe.
3. SayCan Affordance Engine: Physical state checking across SolidWorks & SSCNC, action ranking, remediation suggestion, falsifiable probe.
4. Rest-MCTS Process Planner: Sequential operation planning, Process Reward Model (PRM) scoring, sequence inversion veto, falsifiable probe.
5. Super Agent Integration: Calling all four new facets through VirtuSuperAgent.
6. Measurement Constitution (Section 8): Provenance capture and verified assertions.
"""

import os
import sys
import pytest

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from virtu_omni.google_suite import get_google_suite, VirtuGoogleDeepMindSuite
from virtu_omni.evolution import VirtuFunSearchEngine, ProgramSandbox
from virtu_omni.reasoning import (
    AlphaGeometrySymbolicEngine,
    AlphaGeometryCodeSynthesizer,
    SketchIntent,
    GeometricPrimitive,
    GeometricConstraint,
    ConstraintType,
    ConstraintStatus,
    VirtuRestMCTSPlanner,
    MachiningOperation,
    MachiningState,
    MachiningPRM,
)
from virtu_omni.affordance import (
    SayCanAffordanceEngine,
    SoftwareStateSnapshot,
    IndustrialSoftwareTarget,
)
from virtu_omni.agent import VirtuSuperAgent


def test_01_funsearch_evolution(tmp_path):
    """Verify FunSearch multi-island evolution, sandbox safety, and falsifiable probe."""
    engine = VirtuFunSearchEngine(num_islands=2, capacity_per_island=5, save_dir=str(tmp_path))
    best_init = engine.get_best_program()
    assert best_init is not None
    assert best_init.score > 0.0
    assert best_init.valid is True

    # Mutate and evolve 2 generations
    cand1 = engine.evolve_step()
    assert cand1 is not None
    assert cand1.generation == 1

    cand2 = engine.evolve_step()
    assert cand2 is not None
    assert cand2.generation == 2

    # Check provenance
    summary = engine.get_provenance_summary()
    assert summary["total_programs_evaluated"] >= 3
    assert summary["basis"] == "measured"

    # Rule 4 Falsifiable Gate
    assert engine.falsifiable_mutation_probe() is True


def test_02_alpha_geometry_symbolic_solving():
    """Verify AlphaGeometry exact coordinate deduction and Green's Theorem volume integration."""
    # Define a 40x25 mm rectangle on Front Plane extruded 15 mm
    intent = SketchIntent(
        sketch_id="RECT_40x25",
        plane="Front",
        primitives=[
            GeometricPrimitive("P1", "POINT"),
            GeometricPrimitive("P2", "POINT"),
            GeometricPrimitive("P3", "POINT"),
            GeometricPrimitive("P4", "POINT"),
        ],
        constraints=[
            GeometricConstraint("C1", ConstraintType.FIXED_ORIGIN, ["P1"]),
            GeometricConstraint("C2", ConstraintType.HORIZONTAL, ["P1", "P2"]),
            GeometricConstraint("C3", ConstraintType.DISTANCE_X, ["P1", "P2"], value=40.0),
            GeometricConstraint("C4", ConstraintType.VERTICAL, ["P2", "P3"]),
            GeometricConstraint("C5", ConstraintType.DISTANCE_Y, ["P2", "P3"], value=25.0),
            GeometricConstraint("C6", ConstraintType.HORIZONTAL, ["P4", "P3"]),
            GeometricConstraint("C7", ConstraintType.VERTICAL, ["P1", "P4"]),
        ],
        extrusion_depth_mm=15.0,
    )

    solved = AlphaGeometrySymbolicEngine.solve_sketch(intent)
    assert solved.status == ConstraintStatus.WELL_CONSTRAINED
    assert solved.dof == 0
    assert solved.points["P1"] == (0.0, 0.0)
    assert solved.points["P2"] == (40.0, 0.0)
    assert solved.points["P3"] == (40.0, 25.0)
    assert solved.points["P4"] == (0.0, 25.0)

    # Exact area = 40 * 25 = 1000.0 mm2
    assert abs(solved.exact_profile_area_mm2 - 1000.0) < 1e-4
    # Exact volume = 1000 * 15 = 15000.0 mm3
    assert abs(solved.theoretical_volume_mm3 - 15000.0) < 1e-4
    assert solved.volume_conservation_passed is True

    # Synthesize build123d code
    code = AlphaGeometryCodeSynthesizer.synthesize_build123d(solved, intent)
    assert "Polygon" in code
    assert "extrude(amount=15.0)" in code
    assert "Volume Conservation Violated" in code

    # Rule 4 Falsifiable Gate
    from virtu_omni.reasoning.neuro_symbolic_geometry import falsifiable_alpha_geometry_probe
    assert falsifiable_alpha_geometry_probe() is True


def test_03_saycan_physical_affordance():
    """Verify SayCan affordance filtering for SolidWorks and SSCNC."""
    # 1. SolidWorks: Open sketch contour cannot be extruded
    sw_state = SoftwareStateSnapshot(
        software=IndustrialSoftwareTarget.SOLIDWORKS_2021,
        has_active_sketch=True,
        sketch_is_closed=False,
    )
    res_sw = SayCanAffordanceEngine.evaluate_affordance("EXTRUDE_BOSS", sw_state, p_llm=0.95)
    assert res_sw.is_executable is False
    assert res_sw.p_affordance == 0.0
    assert "unclosed" in res_sw.veto_reason
    assert res_sw.remediation_action == "CLOSE_SKETCH_CONTOUR"

    # 2. SSCNC: Attempt Cycle Start while in EDIT mode
    sscnc_state = SoftwareStateSnapshot(
        software=IndustrialSoftwareTarget.SSCNC_7_2,
        mode="EDIT",
        door_closed=True,
        alarm_active=False,
    )
    res_sscnc = SayCanAffordanceEngine.evaluate_affordance("CYCLE_START", sscnc_state, p_llm=0.9)
    assert res_sscnc.is_executable is False
    assert res_sscnc.p_affordance == 0.0
    assert res_sscnc.remediation_action == "SWITCH_PANEL_MODE_TO_AUTO"

    # 3. Action filtering & ranking
    ranked = SayCanAffordanceEngine.filter_actions(
        [("CYCLE_START", 0.95), ("JOG_X_PLUS", 0.3)],
        sscnc_state,
    )
    assert len(ranked) == 2

    # Rule 4 Falsifiable Gate
    assert SayCanAffordanceEngine.falsifiable_affordance_probe() is True


def test_04_rest_mcts_process_planner():
    """Verify Rest-MCTS multi-operation process planning and PRM scoring."""
    ops = [
        MachiningOperation(op_id="OP10", op_name="Face_Rough", op_type="ROUGHING", tool_id="T01"),
        MachiningOperation(op_id="OP20", op_name="Turn_OD_Finish", op_type="FINISHING", tool_id="T02"),
        MachiningOperation(op_id="OP30", op_name="Cut_Thread_M24", op_type="THREADING", tool_id="T03"),
    ]

    planner = VirtuRestMCTSPlanner(max_simulations=40)
    best_ops, total_reward, metrics = planner.plan_process_route(ops)

    assert len(best_ops) == 3
    # Roughing OP10 MUST come before Finishing or Threading
    op_ids = [op.op_id for op in best_ops]
    assert op_ids.index("OP10") < op_ids.index("OP20")
    assert op_ids.index("OP10") < op_ids.index("OP30")
    assert total_reward > 0.0
    assert metrics["total_simulations"] == 40

    # Rule 4 Falsifiable Gate
    assert VirtuRestMCTSPlanner.falsifiable_mcts_probe() is True


def test_05_super_agent_deepmind_facets():
    """Verify Super Agent facet invocation for all 4 DeepMind modules."""
    agent = VirtuSuperAgent()

    # 1. Facet FunSearch
    res_fs = agent.facet_funsearch_evolve(steps=1)
    assert "program_id" in res_fs
    assert res_fs["valid"] is True

    # 2. Facet AlphaGeometry
    intent_data = {
        "sketch_id": "TEST_SQUARE",
        "primitives": [
            {"elem_id": "P1", "elem_type": "POINT"},
            {"elem_id": "P2", "elem_type": "POINT"},
            {"elem_id": "P3", "elem_type": "POINT"},
            {"elem_id": "P4", "elem_type": "POINT"},
        ],
        "constraints": [
            {"constraint_id": "C1", "constraint_type": "FIXED_ORIGIN", "target_ids": ["P1"]},
            {"constraint_id": "C2", "constraint_type": "HORIZONTAL", "target_ids": ["P1", "P2"]},
            {"constraint_id": "C3", "constraint_type": "DISTANCE_X", "target_ids": ["P1", "P2"], "value": 20.0},
            {"constraint_id": "C4", "constraint_type": "VERTICAL", "target_ids": ["P2", "P3"]},
            {"constraint_id": "C5", "constraint_type": "DISTANCE_Y", "target_ids": ["P2", "P3"], "value": 20.0},
            {"constraint_id": "C6", "constraint_type": "HORIZONTAL", "target_ids": ["P4", "P3"]},
            {"constraint_id": "C7", "constraint_type": "VERTICAL", "target_ids": ["P1", "P4"]},
        ],
        "extrusion_depth_mm": 5.0,
    }
    res_geo = agent.facet_solve_geometry(intent_data)
    assert res_geo["status"] == "WELL_CONSTRAINED"
    assert res_geo["exact_profile_area_mm2"] == 400.0
    assert res_geo["theoretical_volume_mm3"] == 2000.0
    assert res_geo["volume_conservation_passed"] is True

    # 3. Facet SayCan Affordance
    res_aff = agent.facet_check_affordance(
        action="CYCLE_START",
        software="SSCNC_7_2",
        state={"mode": "EDIT", "door_closed": True},
    )
    assert res_aff["is_executable"] is False
    assert res_aff["p_affordance"] == 0.0

    # 4. Facet Rest-MCTS
    res_mcts = agent.facet_mcts_plan(
        operations=[
            {"op_id": "OP01", "op_name": "Rough", "op_type": "ROUGHING", "tool_id": "T1"},
            {"op_id": "OP02", "op_name": "Finish", "op_type": "FINISHING", "tool_id": "T2"},
        ]
    )
    assert len(res_mcts["planned_operations"]) == 2
    assert res_mcts["planned_operations"][0]["op_id"] == "OP01"


def test_06_suite_verification_report():
    """Verify full suite health and provenance report adhering to Section 8."""
    suite = get_google_suite()
    report = suite.run_all_falsifiable_probes()
    assert report.all_probes_passed is True
    assert report.funsearch_probe_passed is True
    assert report.alpha_geometry_probe_passed is True
    assert report.saycan_affordance_probe_passed is True
    assert report.rest_mcts_probe_passed is True
    assert report.basis == "measured"
    assert report.run_id.startswith("GSUITE_PROBE_")
