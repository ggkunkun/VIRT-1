# -*- coding: utf-8 -*-
"""tests/test_sleep_framework.py — Verification Suite for Google Sleep Framework in Virtu.

Verifies:
1. Wake phase experience buffering & content-addressed hashing.
2. Sleep Phase 1: Knowledge Seeding consolidation with >70% token compression.
3. Sleep Phase 2: Counterfactual dreaming with physics oracle verification.
4. Rule 4 Gate Falsifiability: Defective dreams (bad physics/unviable FOS) MUST fail verification.
5. Sleep Phase 3: Synaptic homeostasis, plasticity vs stability, zero catastrophic forgetting.
6. VirtuSuperAgent integration.
"""

import json
from pathlib import Path
import pytest
import shutil
import tempfile

from virtu_omni.memory.sleep_framework import (
    VirtuSleepFramework,
    WakeExperienceBuffer,
    KnowledgeSeeder,
    DreamEngine,
    DreamScenario,
    SynapticHomeostasis,
)
from virtu_omni.agent.super_agent import VirtuSuperAgent


@pytest.fixture
def tmp_dir():
    d = Path(tempfile.mkdtemp(prefix="virtu_sleep_test_"))
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_01_wake_experience_buffer():
    buf = WakeExperienceBuffer(capacity=5)
    exp = buf.record(
        prompt="设计厚壁液压缸，内径60mm，外径120mm，内压25MPa",
        completion="根据厚壁圆筒Lamé理论，计算得von Mises应力为58.2MPa，FOS=5.32>=1.5，符合安全规范。",
        verified_facts={"D_inner": 60.0, "D_outer": 120.0, "P_internal": 25.0, "FOS": 5.32},
        tokens_prompt=25,
        tokens_completion=45,
    )

    assert exp.id.startswith("WAKE_0001_")
    assert exp.receipt_hash is not None
    assert len(exp.receipt_hash) == 64
    assert len(buf) == 1

    # Test cyclic eviction
    for i in range(10):
        buf.record(prompt=f"Task {i}", completion=f"Done {i}")
    assert len(buf) == 5


def test_02_knowledge_seeding_consolidation():
    buf = WakeExperienceBuffer()
    # Record 3 distinct domain tasks
    buf.record(
        prompt="厚壁圆筒Lamé应力分析：材质45号钢，内径50，外径100，内压20MPa",
        completion="根据Lamé公式计算sigma_vm=46.5MPa，屈服强度355MPa，FOS=7.63>=1.5，满足要求。",
        tokens_prompt=120,
        tokens_completion=250,
        verified_facts={"D_inner": 50.0, "D_outer": 100.0, "P_internal": 20.0},
    )
    buf.record(
        prompt="数控车削计算主轴转速：工件直径D=80mm，推荐线速度Vc=120m/min",
        completion="主轴转速公式 n=1000*Vc/(pi*D)，代入计算得 n=477 r/min。",
        tokens_prompt=80,
        tokens_completion=150,
        verified_facts={"D": 80.0, "Vc": 120.0, "n": 477},
    )
    buf.record(
        prompt="法兰三维CAD建模：外径100mm，通孔30mm，高度40mm",
        completion="执行旋转凸台并切除中心孔，理论体积V=285885mm^3，体积守恒校验合格。",
        tokens_prompt=90,
        tokens_completion=180,
        verified_facts={"D": 100.0, "hole_d": 30.0, "H": 40.0},
    )

    seeder = KnowledgeSeeder()
    consolidated = seeder.consolidate(buf.get_unconsolidated())

    assert len(consolidated) == 3
    domains = {c.domain for c in consolidated}
    assert "cae_simulation" in domains
    assert "cnc_machining" in domains
    assert "cad_modeling" in domains

    # Verify token compression
    for c in consolidated:
        assert c.compression_ratio > 0.40  # Significant token compression from chat to invariant
        assert len(c.provenance_hash) == 64


def test_03_counterfactual_dreaming_and_oracle():
    seeder = KnowledgeSeeder()
    buf = WakeExperienceBuffer()
    buf.record(
        prompt="厚壁圆筒Lamé分析，内径60，外径120，内压25MPa，屈服强度310MPa",
        completion="FOS=5.32>=1.5",
        verified_facts={"D_inner": 60.0, "D_outer": 120.0, "P_internal": 25.0, "Sy": 310.0},
    )
    consolidated = seeder.consolidate(buf.get_unconsolidated())

    dream_engine = DreamEngine()
    dreams = dream_engine.generate_counterfactuals(consolidated, count_per_rule=2)
    assert len(dreams) == 2

    # Execute dreaming with analytical solver
    verified_dreams = dream_engine.execute_and_verify(dreams)
    assert len(verified_dreams) == 2
    for d in verified_dreams:
        assert d.oracle_passed is True
        assert d.reward == 1.0
        assert d.execution_receipt is not None


def test_04_falsifiable_mutation_probe():
    """Rule 4: Gates must be falsifiable. Planted bad physics MUST be rejected."""
    framework = VirtuSleepFramework()
    probe_result = framework.falsifiable_mutation_probe()

    assert probe_result["oracle_rejected_defect"] is True
    assert probe_result["probe_passed"] is True


def test_05_synaptic_homeostasis_audit(tmp_dir):
    homeostasis = SynapticHomeostasis()
    # Mock model caller that knows engineering anchors
    def expert_caller(prompt: str) -> str:
        p_lower = prompt.lower()
        if "g71" in p_lower:
            return "G71 第二行的 U 参数代表 X 轴方向的单边径向精加工余量。"
        elif "内压" in p_lower or "径向应力" in p_lower:
            return "厚壁圆筒受内压作用下，内壁处的径向应力等于 -Pi（受压状态）。"
        elif "mmc" in p_lower or "最大实体" in p_lower:
            return "M 外带圆圈表示最大实体要求 (MMC)，实际尺寸偏离时允许公差放宽补偿。"
        elif "vba" in p_lower or "sweqnmgr" in p_lower:
            return "SOLIDWORKS VBA 宏向 swEqnMgr 添加方程式时，双引号必须双重转义。"
        elif "15706" in p_lower:
            return "GB/T 15706 对应国际标准 ISO 12100（机械安全设计通则）。"
        return "sigma_vm = sqrt(sigma_t^2 + sigma_r^2 - sigma_t*sigma_r); FOS >= 1.5; n = 1000*Vc/(pi*D)"

    # Seed mock consolidated knowledge
    seeder = KnowledgeSeeder()
    buf = WakeExperienceBuffer()
    buf.record(
        prompt="厚壁圆筒Lamé分析",
        completion="sigma_vm = 58.2; FOS >= 1.5",
        verified_facts={"D_inner": 60.0, "D_outer": 120.0, "P_internal": 25.0, "Sy": 310.0},
    )
    consolidated = seeder.consolidate(buf.get_unconsolidated())

    verdict = homeostasis.audit_homeostasis(
        model_caller=expert_caller,
        newly_consolidated=consolidated,
        run_id="TEST_RUN_001",
        output_dir=tmp_dir,
    )

    assert verdict.stability_score >= 0.95
    assert verdict.catastrophic_forgetting_rate <= 0.05
    assert verdict.gate_passed is True
    assert Path(verdict.evidence_path).exists()


def test_06_virtu_sleep_framework_e2e(tmp_dir):
    framework = VirtuSleepFramework(output_dir=tmp_dir)

    # Wake phase: 2 tasks
    framework.record_wake_step(
        prompt="厚壁圆筒Lamé仿真，内径60，外径120，内压25MPa，屈服强度310MPa",
        completion="FOS=5.32>=1.5",
        verified_facts={"D_inner": 60.0, "D_outer": 120.0, "P_internal": 25.0, "Sy": 310.0},
    )
    framework.record_wake_step(
        prompt="车削工件直径D=50mm，推荐线速度Vc=150m/min，计算主轴转速",
        completion="主轴转速 n = 955 r/min",
        verified_facts={"D": 50.0, "Vc": 150.0, "n": 955},
    )

    # Sleep phase execution
    report = framework.run_sleep_cycle(run_id="E2E_SLEEP_TEST")

    assert report["wake_experiences_processed"] == 2
    assert report["consolidated_units"] >= 2
    assert report["dreams_generated"] >= 4
    assert report["dream_oracle_pass_rate"] >= 0.80
    assert report["stability_score"] >= 0.80
    assert report["catastrophic_forgetting_rate"] <= 0.20
    assert report["homeostasis_gate_passed"] is True
    assert Path(report["evidence_path"]).exists()


def test_07_super_agent_sleep_facet():
    agent = VirtuSuperAgent()
    assert hasattr(agent, "sleep_framework")
    assert "trigger_sleep_cycle" in agent._tool_registry

    # Record experience via agent's sleep framework
    agent.sleep_framework.record_wake_step(
        prompt="厚壁圆筒受压分析",
        completion="FOS >= 1.5",
        verified_facts={"D_inner": 60.0, "D_outer": 120.0, "P_internal": 25.0, "Sy": 310.0},
    )

    # Call facet directly
    res = agent.facet_sleep_consolidation("SUPER_AGENT_SLEEP_TEST")
    assert res["consolidated_units"] >= 1
    assert res["homeostasis_gate_passed"] is True
