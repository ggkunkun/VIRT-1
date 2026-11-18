# -*- coding: utf-8 -*-
"""tests/test_super_agent.py — Comprehensive Test Suite for Virtu Super Agent.

Verifies:
1. Super Agent initialization and all 8+ integrated domain facets.
2. Mode AUTONOMOUS: Full-lifecycle closed-loop industrial design, CAE FOS >= 1.5,
   volume conservation, and stage-gated memory reclamation.
3. Mode REACT: Dynamic Thought -> Action -> Observation reasoning loop.
4. Mode MODALITY: Single-turn explicit modality tool dispatch with fallbacks.
5. Circuit Breaker Axiom: k_max = 3 budget, failure containment, rollback, and RCFA report.
6. Analytical CAE Stress & Lamé elasticity verification.
7. Backwards compatibility bridging with IndustrialAgentTeam and CADCAMAutonomousAgent.
"""

import os
import sys
import time
import pytest

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from virtu_omni.agent import (
    VirtuSuperAgent,
    SuperAgent,
    SuperAgentMode,
    SuperAgentExecutionResult,
    CircuitBreakerException,
    IndustrialAgentTeam,
    CADCAMAutonomousAgent,
    AgentExecutionReport,
)


def test_01_super_agent_initialization():
    """Verify Super Agent initialization, registered facets, and architecture explanation."""
    agent = VirtuSuperAgent()
    assert agent is not None
    assert agent.wish_engine is not None
    assert agent.sandbox_verifier is not None
    assert agent.reclaimer is not None
    assert agent.dispatcher is not None

    arch_info = agent.explain_architecture()
    assert arch_info["name"] == "Virtu Industrial Super Agent"
    assert arch_info["architecture_type"] == "Unified Omni-Agent (全能超级智能体)"
    assert len(arch_info["modes"]) >= 4
    assert "AUTONOMOUS" in arch_info["modes"]
    assert "REACT" in arch_info["modes"]
    assert len(arch_info["facets"]) >= 7
    assert len(arch_info["registered_tools"]) >= 8


def test_02_super_agent_autonomous_solve(tmp_path):
    """Verify full-lifecycle autonomous engineering solve with stage-gated memory reclamation."""
    agent = VirtuSuperAgent()
    out_dir = str(tmp_path / "super_agent_run")
    prompt = "我想制造一款外径60mm，内孔22mm，长度80mm，材质为AL7075-T6的高强连杆衬套"

    res = agent.solve(prompt, mode=SuperAgentMode.AUTONOMOUS, output_dir=out_dir, memory_safe=True)

    assert isinstance(res, SuperAgentExecutionResult)
    assert res.success is True
    assert res.runtime_seconds > 0.0
    assert len(res.facets_engaged) >= 6
    assert len(res.trace_log) >= 7

    # Verify artifacts
    arts = res.artifacts
    assert "architecture" in arts
    assert arts["architecture"]["status"] == "COMPLETED"
    assert arts["architecture"]["parsed_spec"]["material"] == "AL7075-T6"

    assert "parametric_model" in arts
    assert len(arts["parametric_model"]["feature_tree"]) > 0

    assert "standards_gdt" in arts
    assert len(arts["standards_gdt"]["drawing_spec"]["fit_tolerances"]) >= 1

    assert "machining_cnc" in arts
    assert "G71" in arts["machining_cnc"]["macro_b_code"]

    # CAE stress and safety factor check (FOS >= 1.5)
    assert "cae_simulation" in arts
    cae = arts["cae_simulation"]
    assert cae["fos_passed"] is True
    assert cae["safety_factor_fos"] >= 1.5
    assert cae["theoretical_volume_mm3"] > 0.0
    assert cae["estimated_weight_grams"] > 0.0

    # Auditor and memory check
    assert "sandbox_audit" in arts
    assert arts["sandbox_audit"]["passed"] is True

    assert "memory_evolution" in arts
    assert arts["memory_evolution"]["status"] == "COMPLETED"

    # Verify summary report markdown
    md = res.summary_markdown()
    assert "[PASS]" in md
    assert "安全系数 FOS" in md


def test_03_super_agent_react_mode():
    """Verify dynamic ReAct loop (Thought -> Action -> Observation -> Reflection)."""
    agent = VirtuSuperAgent()
    prompt = "为航空液压泵设计一款耐磨套筒 材质Ti-6Al-4V 外径48mm 内孔18mm 长度50mm"

    res = agent.solve(prompt, mode=SuperAgentMode.REACT, max_steps=7)

    assert isinstance(res, SuperAgentExecutionResult)
    assert res.success is True
    assert res.mode == "REACT"
    assert len(res.trace_log) >= 5

    # Check that each step in scratchpad contains thought, action, and observation
    for step in res.trace_log:
        assert "thought" in step
        assert "action" in step
        assert "observation" in step
        assert len(step["thought"]) > 0
        assert len(step["observation"]) > 0


def test_04_super_agent_modality_dispatch():
    """Verify single-turn explicit modality execution through Super Agent."""
    agent = VirtuSuperAgent()
    macro_code = (
        "#100=50.0\n"
        "#101=10.0\n"
        "WHILE [#101 LE #100] DO 1\n"
        "#101=#101+5\n"
        "END 1\n"
        "M30"
    )
    rep = agent.solve(
        prompt="校验 FANUC Macro B 变量逻辑与循环",
        mode=SuperAgentMode.MODALITY,
        modality="PYTHON_SDK",
        target_software="cimco",
        action="validate_macro",
        params={"code": macro_code},
    )

    assert isinstance(rep, AgentExecutionReport)
    assert rep.success is True
    assert rep.modality == "PYTHON_SDK"
    assert rep.result_data.get("is_valid") is True
    assert "#100" in rep.result_data.get("variables", [])


def test_05_circuit_breaker_axiom():
    """Verify Circuit Breaker Axiom: k_max=3 attempt budget, abort, and RCFA generation."""
    agent = VirtuSuperAgent()
    attempts_seen = []

    def failing_step(attempt: int):
        attempts_seen.append(attempt)
        raise ValueError(f"模拟不可恢复几何拓扑自检错误 (attempt {attempt})")

    with pytest.raises(CircuitBreakerException) as excinfo:
        agent.execute_with_circuit_breaker(
            stage_name="Unrepairable_Topology_Stage",
            step_fn=failing_step,
            max_retries=3,
        )

    cb_err = excinfo.value
    assert cb_err.stage == "Unrepairable_Topology_Stage"
    assert cb_err.attempt == 3
    assert len(attempts_seen) == 3
    assert "rcfa_report" in cb_err.__dict__
    assert cb_err.rcfa_report["attempts"] == 3
    assert "阶段 [Unrepairable_Topology_Stage] 连续 3 次自查均未收敛" in cb_err.rcfa_report["actionable_advice"]


def test_06_cae_stress_analytical_lame():
    """Verify Lamé thick cylinder stress analysis and safety factor formula."""
    agent = VirtuSuperAgent()

    # Spec with AL7075-T6 (yield 503 MPa), d_outer=60, d_inner=20, P=10 MPa
    spec = {
        "material": "AL7075-T6",
        "d_outer": 60.0,
        "d_inner": 20.0,
        "overall_len": 50.0,
    }
    cae = agent.facet_verify_cae(spec, internal_pressure_mpa=10.0)

    # Analytical calculation:
    # r_out = 30, r_in = 10
    # denom = 900 - 100 = 800
    # numer = 900 + 100 = 1000
    # sigma_t = 10 * (1000 / 800) = 12.5 MPa
    # FOS = 503 / 12.5 = 40.24 >= 1.5
    assert cae["status"] == "COMPLETED"
    assert cae["max_von_mises_stress_mpa"] == 12.5
    assert cae["safety_factor_fos"] >= 1.5
    assert cae["fos_passed"] is True
    assert cae["theoretical_volume_mm3"] > 0.0


def test_07_backwards_compatibility():
    """Verify legacy classes and aliases bridge seamlessly to Super Agent."""
    # Aliases
    assert SuperAgent is VirtuSuperAgent

    # CADCAMAutonomousAgent bridges to Super Agent
    cadcam_agent = CADCAMAutonomousAgent()
    assert cadcam_agent.super_agent is not None
    assert isinstance(cadcam_agent.super_agent, VirtuSuperAgent)

    # IndustrialAgentTeam bridges to Super Agent
    team = IndustrialAgentTeam()
    sa = team.to_super_agent()
    assert isinstance(sa, VirtuSuperAgent)
