# -*- coding: utf-8 -*-
"""Unit tests for BuiltinWorkingMemory & LongTaskHallucinationSentinel.

Enforces Measurement Constitution (AGENTS.md Section 8):
- All verified facts carry provenance (basis, source, evidence_hash).
- Falsifiability: Mutated/bad samples must turn RED (fail the sentinel).
- Fact immutability: Unverified outputs cannot overwrite ground-truth facts.
- Context compaction retains 100% of critical invariants.
"""

import json
import pytest
import time
from virtu_omni.memory.working_memory import (
    BuiltinWorkingMemory,
    LongTaskHallucinationSentinel,
    MilestoneStatus,
    MilestoneStep,
    TaskGoal,
    VerifiedFact,
)


@pytest.fixture
def memory(tmp_path):
    persist_file = str(tmp_path / "test_working_memory.json")
    mem = BuiltinWorkingMemory(session_id="test_session", persist_path=persist_file)
    return mem


def test_working_memory_goal_and_invariants(memory):
    """Test goal initialization and invariant preservation."""
    memory.set_task_goal(
        intent="完成高精度回转法兰盘 3D 建模与 CAM 仿真",
        invariants={"outer_diameter": 60.0, "bore_diameter": 16.0, "material": "HT200"},
        forbidden_actions=["短接安全门联锁", "屏蔽软限位"],
    )

    assert memory.goal.intent == "完成高精度回转法兰盘 3D 建模与 CAM 仿真"
    assert memory.get_fact("outer_diameter") == 60.0
    assert memory.get_fact("bore_diameter") == 16.0
    assert memory.get_fact("material") == "HT200"

    # Invariants are automatically recorded as verified facts with basis='asserted'
    fact = memory.facts["outer_diameter"]
    assert fact.verified is True
    assert fact.basis == "asserted"


def test_verified_fact_immutability(memory):
    """Rule: Once a fact is verified by measurement/tool, unverified claims cannot overwrite it."""
    # 1. Tool measures volume
    memory.record_fact("rebuild_volume_mm3", 12500.5, unit="mm³", source="cadcam_solidworks_model", verified=True)
    assert memory.get_fact("rebuild_volume_mm3") == 12500.5

    # 2. Unverified hallucinated overwrite attempt
    memory.record_fact("rebuild_volume_mm3", 9999.0, unit="mm³", source="unverified_llm_hallucination", verified=False)
    # Must remain original verified value!
    assert memory.get_fact("rebuild_volume_mm3") == 12500.5


def test_milestone_progression_and_provenance(memory):
    """Test milestone addition, progress, and receipt hash tracking."""
    ms1 = memory.add_milestone("1. 2D工程图解析与尺寸提取")
    ms2 = memory.add_milestone("2. SolidWorks 参数化三维建模")

    assert ms1.step_idx == 1
    assert ms1.status == MilestoneStatus.PENDING

    # Complete Step 1 with execution receipt
    receipt = {"extracted_dimensions": {"outer_diameter": 60.0}, "status": "PASS"}
    updated = memory.update_milestone(1, MilestoneStatus.COMPLETED, receipt=receipt)

    assert updated.status == MilestoneStatus.COMPLETED
    assert updated.evidence_hash is not None
    assert len(updated.evidence_hash) == 64  # SHA256 length
    assert memory.current_step_idx == 2


def test_render_memory_prompt(memory):
    """Test formatting into the <BUILTIN_WORKING_MEMORY> XML block."""
    memory.set_task_goal(
        intent="法兰盘设计",
        invariants={"outer_diameter": 60.0},
        forbidden_actions=["禁止G00扎刀"],
    )
    memory.record_fact("safety_factor", 1.82, source="solver:PyNite", verified=True)
    memory.add_milestone("步骤1: 建模")
    memory.record_lesson("圆角特征必须在主凸台拉伸之后生成")

    rendered = memory.render_memory_prompt()
    assert "<BUILTIN_WORKING_MEMORY>" in rendered
    assert "</BUILTIN_WORKING_MEMORY>" in rendered
    assert "[TASK_GOAL]: 法兰盘设计" in rendered
    assert "outer_diameter: 60.0" in rendered
    assert "safety_factor = 1.82" in rendered
    assert "步骤1: 建模" in rendered
    assert "圆角特征必须在主凸台拉伸之后生成" in rendered


def test_auto_sync_from_messages(memory):
    """Test auto-extracting user requirements and tool execution receipts."""
    messages = [
        {"role": "user", "content": "请对该零件进行三维建模，外径60mm，内孔16mm，材质为HT200。"},
        {"role": "assistant", "content": "正在调用三维建模工具..."},
        {
            "role": "tool",
            "name": "cadcam_solidworks_model",
            "content": json.dumps({"volume_mm3": 15420.0, "delta_v": 15420.0, "status": "executed"}),
        },
    ]

    memory.auto_sync_from_messages(messages)
    assert memory.get_fact("outer_diameter") == 60.0
    assert memory.get_fact("bore_diameter") == 16.0
    assert memory.get_fact("material") == "HT200"
    assert memory.get_fact("rebuild_volume_mm3") == 15420.0


def test_context_compaction_preserves_memory(memory):
    """Test that context compaction trims conversation length without losing any verified state."""
    memory.set_task_goal("大型模具复杂加工全流程", invariants={"outer_diameter": 60.0, "length": 50.0})

    # Create 15 turns of conversation
    messages = [{"role": "system", "content": "你是 Virtu 工业智能体"}]
    for i in range(1, 15):
        messages.append({"role": "user", "content": f"第 {i} 步查询：当前进展怎么样？"})
        messages.append({"role": "assistant", "content": f"第 {i} 步响应：正在有序推进中。"})

    assert len(messages) == 29

    compacted = memory.compact_context(messages, max_turns_to_keep=4)
    # Must be compacted to a small number of turns
    assert len(compacted) < 10

    # System prompt must have the working memory block
    system_content = compacted[0]["content"]
    assert "<BUILTIN_WORKING_MEMORY>" in system_content
    assert "outer_diameter: 60.0" in system_content
    assert "length: 50.0" in system_content


def test_hallucination_sentinel_catches_contradictions(memory):
    """Test that the sentinel catches numerical parameter drift/contradiction."""
    memory.set_task_goal("法兰加工", invariants={"outer_diameter": 60.0})
    sentinel = LongTaskHallucinationSentinel(memory)

    # 1. Clean response matching verified fact
    clean_text = "根据设计规范，法兰盘的外径设定为 60.0mm，符合公差要求。"
    contradictions = sentinel.check_fact_contradictions(clean_text)
    assert len(contradictions) == 0

    # 2. Hallucinated response where model drifted to 50mm
    hallucinated_text = "在第 4 步拉伸特征中，我们将零件外径修改为 50.0mm 进行切除。"
    contradictions = sentinel.check_fact_contradictions(hallucinated_text)
    assert len(contradictions) == 1
    assert contradictions[0]["expected_value"] == 60.0
    assert contradictions[0]["hallucinated_value"] == 50.0


def test_hallucination_sentinel_auto_repair(memory):
    """Test that the sentinel deterministically repairs drifted numerical hallucinations."""
    memory.set_task_goal("法兰加工", invariants={"outer_diameter": 60.0})
    sentinel = LongTaskHallucinationSentinel(memory)

    hallucinated_text = "当前步骤中零件外径为 50.0mm，开始下一步操作。"
    is_clean, repaired, report = sentinel.audit_and_repair(hallucinated_text, auto_repair=True)

    assert is_clean is False
    assert report["repaired"] is True
    # In the repaired text, outer diameter should be restored to 60.0!
    assert "外径为 60.0mm" in repaired


def test_hallucination_sentinel_catches_phantom_completion(memory):
    """Test that claiming 'All steps completed / 100% PASS' without receipts is intercepted."""
    memory.add_milestone("Step 1: 建模")
    memory.add_milestone("Step 2: 有限元仿真")
    # Step 2 is still PENDING!
    sentinel = LongTaskHallucinationSentinel(memory)

    fake_success_text = "所有阶段全部完成，系统已 100% PASS，模型构建完美！"
    is_clean, repaired, report = sentinel.audit_and_repair(fake_success_text, auto_repair=True)

    assert is_clean is False
    assert len(report["phantom_claims"]) == 1
    assert "Step 1: 建模" in report["phantom_claims"][0]["uncompleted_milestones"]
    assert "【防幻觉门禁提示】" in repaired


def test_hallucination_sentinel_catches_forbidden_actions(memory):
    """Test that dangerous prohibited machine actions are intercepted."""
    memory.set_task_goal("加工操作", forbidden_actions=["短接机床安全联锁"])
    sentinel = LongTaskHallucinationSentinel(memory)

    unsafe_text = "为了加快效率，可以临时短接机床安全联锁进行连续试切。"
    is_clean, repaired, report = sentinel.audit_and_repair(unsafe_text, auto_repair=False)

    assert is_clean is False
    assert len(report["forbidden_violations"]) == 1
    assert report["forbidden_violations"][0]["action"] == "短接机床安全联锁"
