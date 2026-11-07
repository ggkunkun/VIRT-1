"""Unit and Integration Tests for Virtu Industrial Multi-Agent Team (Agent Team).

Tests:
1. Headless Sandbox Verifier: VBA COM model, Macro B kinematics collision detection.
2. Dense Vector Long-Term Memory: Semantic search and episodic memory commitment.
3. Self-Reflection Optimizer: In-the-loop virtual simulation and self-repair.
4. IndustrialAgentTeam Pipeline: End-to-end multi-agent collaborative execution.
5. WorkBuddy Bridge Integration: OpenAI-compatible response formatting with Agent Team.
"""

import sys
import os
import json
import pytest

WORKSPACE_DIR = r"D:\Virtu模型"
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from virtu_omni.agent import (
    HeadlessSandboxVerifier,
    SelfReflectionOptimizer,
    SkillWriterAndMemory,
    IndustrialAgentTeam,
    ChiefArchitectAgent,
    ParametricModelingAgent,
    StandardsAndGDAgent,
    MachiningAndToolpathAgent,
    AuditorAndSandboxAgent,
    EvolutionAndMemoryAgent,
)


def test_headless_sandbox_vba():
    verifier = HeadlessSandboxVerifier()
    
    # Invalid VBA code
    invalid_code = "Sub main()\n    Dim swApp As Object\n"
    res1 = verifier.verify_solidworks_vba(invalid_code)
    assert not res1["passed"]
    assert any("End Sub" in e for e in res1["errors"])
    assert any("ForceRebuild3" in e for e in res1["errors"])

    # Valid VBA code
    valid_code = """
Sub main()
    Dim swApp As SldWorks.SldWorks
    Dim swModel As SldWorks.ModelDoc2
    Dim swFeatMgr As SldWorks.FeatureManager
    Set swFeatMgr = swModel.FeatureManager
    Set swEqnMgr = swModel.GetEquationMgr
    swEqnMgr.Add -1, "\"D\" = 50.0"
    swEqnMgr.EvaluateAll
    swModel.ForceRebuild3 True
    swModel.ViewZoomtofit2
End Sub
"""
    res2 = verifier.verify_solidworks_vba(valid_code)
    assert res2["passed"]
    assert len(res2["errors"]) == 0


def test_headless_sandbox_macro_b_collision():
    verifier = HeadlessSandboxVerifier()

    # Code with rapid crash into negative Z
    crash_code = """
O0001
G21 G40
M03 S1200
G00 Z-15.0 (CRITICAL PLUNGE CRASH)
G01 X50.0 F0.2
M30
"""
    res1 = verifier.verify_cimco_macro_b(crash_code)
    assert not res1["passed"]
    assert res1["collision_detected"]
    assert any("KINEMATIC COLLISION" in e for e in res1["errors"])

    # Safe code with controlled feed
    safe_code = """
O0001
G21 G40 G28 U0.0 W0.0
M03 S1200
G00 Z2.0
G01 Z-15.0 F0.15
G01 X50.0 F0.2
M30
"""
    res2 = verifier.verify_cimco_macro_b(safe_code)
    assert res2["passed"]
    assert not res2["collision_detected"]


def test_dense_vector_memory():
    memory_path = r"D:\Virtu模型\data\memory\test_vector_memory.json"
    if os.path.exists(memory_path):
        os.remove(memory_path)

    mem = SkillWriterAndMemory(memory_path=memory_path, embedding_dim=128)
    assert mem.vector_store is not None

    # Commit test pattern
    rec = mem.commit_experience(
        task_signature="Aero_Flange_Turning",
        problem_summary="航空钛合金耐高温法兰端面与止口精密切削",
        solution_strategy="采用圆弧刀头车削，主轴线速控制在60m/min，配合G71精车余量",
        key_rules_learned=["钛合金必须强冷冷却", "防止刀尖磨损加剧必须降低转速"]
    )
    assert rec["id"].startswith("EXP_")
    assert len(mem.vector_store.documents) == 1

    # Dense Vector Query (semantic keywords without exact wording match)
    hits = mem.query_memory("航空耐高温法兰切削加工", top_k=2)
    assert len(hits) >= 1
    assert hits[0]["id"] == rec["id"]

    # Cleanup
    if os.path.exists(memory_path):
        os.remove(memory_path)


def test_self_reflection_in_the_loop_repair():
    optimizer = SelfReflectionOptimizer()
    
    # Code with missing ForceRebuild3 and missing EqnMgr
    raw_code = """
Sub main()
    Set swFeatMgr = swModel.FeatureManager
    MsgBox "Done"
End Sub
"""
    audit = optimizer.audit_code(raw_code, "solidworks")
    assert not audit["passed"]
    assert len(audit["issues"]) > 0

    # Reflect and optimize
    opt_code, refl = optimizer.reflect_and_optimize(raw_code, audit)
    assert "ForceRebuild3" in opt_code
    assert "GetEquationMgr" in opt_code
    assert "二次沙箱回归验证" in refl

    # Re-verify through sandbox
    re_audit = optimizer.audit_code(opt_code, "solidworks")
    assert re_audit["passed"]


def test_industrial_agent_team_solve():
    team = IndustrialAgentTeam()
    res = team.solve("我想制造一款外径60mm，内孔22mm，长度80mm，材质为AL7075-T6的高强连杆衬套")

    assert res["status"] == "SUCCESS"
    assert res["runtime_seconds"] > 0
    assert len(res["team_collaboration_log"]) == 7

    # Check ChiefArchitectAgent output
    arch = res["architecture"]
    assert arch["status"] == "COMPLETED"
    assert arch["parsed_spec"]["material"] == "AL7075-T6"

    # Check ParametricModelingAgent output
    pm = res["parametric_model"]
    assert pm["status"] == "COMPLETED"
    assert len(pm["feature_tree"]) > 0
    assert "equations" in pm

    # Check StandardsAndGDAgent output
    std = res["standards_gdt"]
    assert std["status"] == "COMPLETED"
    assert len(std["drawing_spec"]["fit_tolerances"]) >= 1

    # Check MachiningAndToolpathAgent output
    mach = res["machining_cnc"]
    assert mach["status"] == "COMPLETED"
    assert "G71" in mach["macro_b_code"]

    # Check AuditorAndSandboxAgent output
    audit = res["sandbox_audit"]
    assert audit["passed"] is True
    assert "verified_sw_vba" in audit

    # Check EvolutionAndMemoryAgent output
    mem = res["memory_evolution"]
    assert mem["status"] == "COMPLETED"
    assert mem["memory_id"].startswith("EXP_")


def test_bridge_has_no_fake_synthesis_fallback():
    """The bridge must never resurrect the fixed 7,420-token fake report path."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "scripts" / "workbuddy_virtu_bridge.py").read_text(
        encoding="utf-8")
    assert "def _synthesize_response" not in src
    assert "100% PASS" not in src
    assert "沙箱仿真校验" not in src
