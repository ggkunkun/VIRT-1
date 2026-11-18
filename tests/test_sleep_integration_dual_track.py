# -*- coding: utf-8 -*-
"""tests/test_sleep_integration_dual_track.py — Dual-Track Sleep Integration Tests.

Validates:
1. Online Wake Phase: VirtuSuperAgent autonomous & ReAct execution automatically hooks wake steps into buffer.
2. Offline Sleep Phase: KnowledgeSeeder automatically populates VirtuHindsightMemory banks.
3. Disk Persistence: Unconsolidated wake experiences survive process recreation.
4. Maintenance Cycle: run_sleep_maintenance successfully executes and clears buffer.
"""

import json
from pathlib import Path
import pytest
import shutil
import tempfile

from virtu_omni.agent.super_agent import VirtuSuperAgent, SuperAgentMode
from virtu_omni.memory import (
    VirtuSleepFramework,
    WakeExperienceBuffer,
    KnowledgeSeeder,
    VirtuHindsightMemory,
    get_sleep_framework,
)
from scripts.run_sleep_maintenance import perform_maintenance_cycle


@pytest.fixture(autouse=True)
def _no_live_model_budget(monkeypatch):
    """本文件只验 wake-step 钩子，不需要真模型。

    REACT 默认走 deep_agent 真 LLM 循环，单次模型调用预算 90s，规划 + 验收
    两步就是 180s，必然超过 ``--timeout=120``；Windows 上 pytest-timeout 会
    直接终止整个 pytest 进程，导致全仓连跑拿不到任何 summary。把预算压到 3s
    后引擎走「超时 -> 可见降级 -> 硬编码流水线」路径：完全离线、仍能跑完整
    REACT 结果映射，且保住了降级分支的覆盖。
    """
    monkeypatch.setenv("VIRTU_REACT_BUDGET_S", "3")


@pytest.fixture
def clean_sleep_framework():
    d = Path(tempfile.mkdtemp(prefix="virtu_sleep_dual_"))
    framework = VirtuSleepFramework(output_dir=d)
    yield framework
    shutil.rmtree(d, ignore_errors=True)


def test_01_super_agent_autonomous_hooks_wake_step():
    agent = VirtuSuperAgent()
    initial_wake_count = len(agent.sleep_framework.wake_buffer)

    # Run lightweight autonomous solve
    prompt = "设计精密轴承套圈 AL7075-T6 轴套，要求具备 Lamé 安全系数 FOS >= 1.5 并复核尺寸"
    res = agent.solve(prompt, mode=SuperAgentMode.AUTONOMOUS, memory_safe=True)

    # Fail-closed：prompt 未给出压力载荷，CAE 必然 BLOCKED，工程门判负；
    # 本用例只验证 wake-step 钩子，成功与否以真实门为准。
    assert res.success is False
    # Verify wake step was automatically recorded
    assert len(agent.sleep_framework.wake_buffer) == initial_wake_count + 1
    latest_exp = agent.sleep_framework.wake_buffer.get_unconsolidated()[-1]
    assert prompt in latest_exp.prompt
    assert latest_exp.receipt_hash is not None


def test_02_super_agent_react_hooks_wake_step():
    agent = VirtuSuperAgent()
    initial_wake_count = len(agent.sleep_framework.wake_buffer)

    prompt = "查询轴套的 Lamé 应力公式"
    res = agent.solve(prompt, mode=SuperAgentMode.REACT, max_steps=1)

    # A 1-step run never reaches FINISH nor a sandbox audit, so it must not
    # claim success. This test verifies the wake-step hook, not task success.
    assert res.success is False
    assert res.metrics["completed"] is False
    assert res.metrics["audit_passed"] is None
    assert len(agent.sleep_framework.wake_buffer) == initial_wake_count + 1


def test_03_knowledge_seeding_syncs_to_hindsight(clean_sleep_framework):
    clean_sleep_framework.record_wake_step(
        prompt="厚壁圆筒Lamé理论分析：内径60，外径120，内压25MPa，屈服强度310MPa",
        completion="FOS=5.32>=1.5符合规范",
        verified_facts={"D_inner": 60.0, "D_outer": 120.0, "P_internal": 25.0, "Sy": 310.0},
    )

    unconsolidated = clean_sleep_framework.wake_buffer.get_unconsolidated()
    assert len(unconsolidated) == 1

    seeder = KnowledgeSeeder()
    consolidated = seeder.consolidate(unconsolidated)
    assert len(consolidated) >= 1

    # Verify Hindsight Memory now has the newly seeded mental model
    h_mem = VirtuHindsightMemory()
    recalled = h_mem.recall(bank_id="virtu_quality_audit", query="lame_thick_cylinder_fos")
    # Should recall the mental model
    assert len(recalled) >= 1
    found_rule = any("lame_thick_cylinder_fos" in m.get("content", "") for m in recalled)
    assert found_rule is True


def test_04_wake_buffer_disk_persistence(clean_sleep_framework):
    persist_file = clean_sleep_framework.output_dir / "wake_experiences.jsonl"
    clean_sleep_framework.record_wake_step(
        prompt="测试持久化任务 A",
        completion="完成 A",
        verified_facts={"test": True},
    )

    assert persist_file.exists()
    assert len(clean_sleep_framework.wake_buffer) == 1

    # Simulate fresh process startup using same persist path
    new_buffer = WakeExperienceBuffer(persist_path=persist_file)
    assert len(new_buffer) == 1
    assert new_buffer.get_unconsolidated()[0].prompt == "测试持久化任务 A"


def test_05_perform_maintenance_cycle_cleans_and_reports(clean_sleep_framework):
    clean_sleep_framework.record_wake_step(
        prompt="厚壁圆筒受压分析，内径60，外径120，内压25MPa，屈服强度310MPa",
        completion="FOS=5.32>=1.5",
        verified_facts={"D_inner": 60.0, "D_outer": 120.0, "P_internal": 25.0, "Sy": 310.0},
    )

    assert len(clean_sleep_framework.wake_buffer) == 1
    report = perform_maintenance_cycle(clean_sleep_framework, clean_memory=False)

    assert report is not None
    assert report["consolidated_units"] >= 1
    # 未注入真实模型调用器，必须诚实降级，不得假通过
    assert report["measurement_valid"] is False
    assert report["homeostasis_gate_passed"] is False
    # Buffer should now be cleared
    assert len(clean_sleep_framework.wake_buffer) == 0
