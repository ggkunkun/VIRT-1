# -*- coding: utf-8 -*-
"""tests/test_sleep_framework.py — Google Sleep 框架有效性验证（AGENTS.md §5/§8）。

核心约束（2026-11-12 修复后）：
- 无真实 model_caller 时 basis=unmeasured、gate=False，绝不假通过。
- 稳态门禁为绝对阈值（S>=0.95 / P>=0.90 / CF<=0.05）+ 独立 sleep 前基线。
- 梦境 oracle 通过率纳入能力门禁；解析解自证只标 self_check，不计实测。
- 未实测 token 不得用字符长度估算；空梦境不得记 1.0。
"""

import json
import math
from pathlib import Path
import re
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
    build_ollama_model_caller,
)
from virtu_omni.agent.super_agent import VirtuSuperAgent


@pytest.fixture
def tmp_dir():
    d = Path(tempfile.mkdtemp(prefix="virtu_sleep_test_"))
    yield d
    shutil.rmtree(d, ignore_errors=True)


def expert_caller(prompt: str) -> str:
    """确定性专家 stub（单元测试用，不作为真实模型能力证据）。"""
    p = prompt.lower()
    if "g71" in p:
        return "G71 第二行的 U 参数代表 X 轴方向的单边径向精加工余量。"
    if "内压" in p or "径向应力" in p:
        return "厚壁圆筒受内压作用下，内壁处的径向应力等于 -Pi（受压状态）。"
    if "mmc" in p or "最大实体" in p:
        return "M 外带圆圈表示最大实体要求 (MMC)，实际尺寸偏离时允许公差放宽补偿。"
    if "vba" in p or "sweqnmgr" in p:
        return "SOLIDWORKS VBA 宏向 swEqnMgr 添加方程式时，双引号必须双重转义。"
    if "15706" in p:
        return "GB/T 15706 对应国际标准 ISO 12100（机械安全设计通则）。"
    return ("sigma_vm = sqrt(sigma_t^2 + sigma_r^2 - sigma_t*sigma_r); "
            "FOS >= 1.5; n = 1000*Vc/(pi*D); 体积守恒; Vc; 应力; fos")


def analytic_caller(prompt: str) -> str:
    """能正确解梦境题的 stub，用于验证完整有效路径（仍非真实模型证据）。"""
    def num(key: str) -> float:
        m = re.search(re.escape(key) + r"\s*=\s*([\d.]+)", prompt)
        return float(m.group(1)) if m else 0.0

    if "梦境仿真题" in prompt:
        di, do, pi, sy = num("D_i"), num("D_o"), num("P_i"), num("Sy")
        ri, ro = di / 2.0, do / 2.0
        st = pi * (ro**2 + ri**2) / (ro**2 - ri**2)
        sr = -pi
        sz = (pi * ri**2) / (ro**2 - ri**2)
        vm = math.sqrt(0.5 * ((st - sr)**2 + (sr - sz)**2 + (sz - st)**2))
        fos = sy / vm
        return f"von Mises 应力 = {vm:.2f} MPa, 安全系数 FOS = {fos:.2f}, 合规: {fos >= 1.5}"
    if "梦境加工题" in prompt:
        d, vc = num("D"), num("Vc")
        return f"计算公式 n = 1000*Vc/(pi*D)，代入求得 n = {round(1000.0*vc/(math.pi*d))} r/min"
    if "梦境建模题" in prompt:
        d, h, hd = num("D"), num("H"), num("d")
        v = math.pi * ((d/2)**2 - (hd/2)**2) * h
        return f"理论体积 V = {round(v)} mm^3"
    return expert_caller(prompt)


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
    for i in range(10):
        buf.record(prompt=f"Task {i}", completion=f"Done {i}")
    assert len(buf) == 5


def test_02_knowledge_seeding_consolidation(monkeypatch):
    import virtu_omni.memory.sleep_framework as sf_mod
    monkeypatch.setattr(sf_mod, "VirtuHindsightMemory", None)
    buf = WakeExperienceBuffer()
    buf.record(
        prompt="厚壁圆筒Lamé应力分析：材质45号钢，内径50，外径100，内压20MPa",
        completion="根据Lamé公式计算sigma_vm=46.5MPa，屈服强度355MPa，FOS=7.63>=1.5，满足要求。",
        tokens_prompt=120, tokens_completion=250,
        verified_facts={"D_inner": 50.0, "D_outer": 100.0, "P_internal": 20.0},
    )
    buf.record(
        prompt="数控车削计算主轴转速：工件直径D=80mm，推荐线速度Vc=120m/min",
        completion="主轴转速公式 n=1000*Vc/(pi*D)，代入计算得 n=477 r/min。",
        tokens_prompt=80, tokens_completion=150,
        verified_facts={"D": 80.0, "Vc": 120.0, "n": 477},
    )
    buf.record(
        prompt="法兰三维CAD建模：外径100mm，通孔30mm，高度40mm",
        completion="执行旋转凸台并切除中心孔，理论体积V=285885mm^3，体积守恒校验合格。",
        tokens_prompt=90, tokens_completion=180,
        verified_facts={"D": 100.0, "hole_d": 30.0, "H": 40.0},
    )
    consolidated = KnowledgeSeeder().consolidate(buf.get_unconsolidated())
    assert len(consolidated) == 3
    assert {"cae_simulation", "cnc_machining", "cad_modeling"} == {c.domain for c in consolidated}
    for c in consolidated:
        assert c.token_basis == "measured"
        assert isinstance(c.compression_ratio, float)
        assert c.compression_ratio > 0.40
        assert len(c.provenance_hash) == 64


def test_03_counterfactual_dreaming_and_oracle(monkeypatch):
    import virtu_omni.memory.sleep_framework as sf_mod
    monkeypatch.setattr(sf_mod, "VirtuHindsightMemory", None)
    buf = WakeExperienceBuffer()
    buf.record(
        prompt="厚壁圆筒Lamé分析，内径60，外径120，内压25MPa，屈服强度310MPa",
        completion="FOS=5.32>=1.5",
        verified_facts={"D_inner": 60.0, "D_outer": 120.0, "P_internal": 25.0, "Sy": 310.0},
    )
    consolidated = KnowledgeSeeder().consolidate(buf.get_unconsolidated())
    dream_engine = DreamEngine()
    dreams = dream_engine.generate_counterfactuals(consolidated, count_per_rule=2)
    assert len(dreams) == 2
    verified = dream_engine.execute_and_verify(dreams)
    for d in verified:
        assert d.oracle_passed is True
        assert d.reward == 1.0
        assert d.execution_receipt is not None
        # 关键：解析解自证必须被显式标注，不能冒充模型实测
        assert d.solution_source == "analytic_baseline"
        assert d.evidence_basis == "self_check"


def test_04_falsifiable_mutation_probe():
    framework = VirtuSleepFramework()
    probe = framework.falsifiable_mutation_probe()
    assert probe["oracle_rejected_defect"] is True
    assert probe["probe_passed"] is True


def test_05_synaptic_homeostasis_audit(tmp_dir, monkeypatch):
    import virtu_omni.memory.sleep_framework as sf_mod
    monkeypatch.setattr(sf_mod, "VirtuHindsightMemory", None)
    homeostasis = SynapticHomeostasis()
    buf = WakeExperienceBuffer()
    buf.record(prompt="厚壁圆筒Lamé分析", completion="sigma_vm = 58.2; FOS >= 1.5",
               verified_facts={"D_inner": 60.0, "D_outer": 120.0, "P_internal": 25.0, "Sy": 310.0})
    consolidated = KnowledgeSeeder().consolidate(buf.get_unconsolidated())
    verdict = homeostasis.audit_homeostasis(
        model_caller=expert_caller,
        newly_consolidated=consolidated,
        run_id="TEST_RUN_001",
        output_dir=tmp_dir,
        pre_baseline_score=1.0,  # 独立实测基线，禁止缺省自比较
    )
    assert verdict.basis == "measured"
    assert verdict.baseline_provided is True
    assert verdict.stability_score >= 0.95
    assert verdict.plasticity_score >= 0.90
    assert verdict.catastrophic_forgetting_rate <= 0.05
    assert verdict.gate_passed is True
    assert Path(verdict.evidence_path).exists()


def test_06_no_caller_cycle_is_honest(tmp_dir, monkeypatch):
    """无模型调用时：三阶段仍执行，但一律 unmeasured + gate=False，绝不假通过。"""
    import virtu_omni.memory.sleep_framework as sf_mod
    monkeypatch.setattr(sf_mod, "VirtuHindsightMemory", None)
    framework = VirtuSleepFramework(output_dir=tmp_dir)
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
    report = framework.run_sleep_cycle(run_id="HONEST_NO_CALLER_TEST")
    assert report["wake_experiences_processed"] == 2
    assert report["consolidated_units"] >= 2
    assert report["dreams_generated"] >= 2
    assert report["dream_evidence_basis"] == "self_check"
    assert report["dream_oracle_pass_rate"] == 0.0
    assert report["average_token_compression"] == "unmeasured"
    assert report["token_basis"] == "unmeasured"
    assert report["basis"] == "unmeasured"
    assert report["measurement_valid"] is False
    assert report["homeostasis_gate_passed"] is False
    assert any("no_model_caller" in r for r in report["reasons"])
    assert Path(report["evidence_path"]).exists()


def test_07_super_agent_sleep_facet():
    agent = VirtuSuperAgent()
    assert hasattr(agent, "sleep_framework")
    assert "trigger_sleep_cycle" in agent._tool_registry
    agent.sleep_framework.record_wake_step(
        prompt="厚壁圆筒受压分析", completion="FOS >= 1.5",
        verified_facts={"D_inner": 60.0, "D_outer": 120.0, "P_internal": 25.0, "Sy": 310.0},
    )
    res = agent.facet_sleep_consolidation("SUPER_AGENT_SLEEP_TEST")
    assert res["consolidated_units"] >= 1
    # SuperAgent 默认不隐式发网络请求，必须诚实降级
    assert res["measurement_valid"] is False
    assert res["homeostasis_gate_passed"] is False


def test_08_gate_rejects_missing_evidence_and_bad_model(tmp_dir, monkeypatch):
    """可证伪性：无 caller / 坏模型 / 缺独立基线，三种情况门禁都必须为 False。"""
    import virtu_omni.memory.sleep_framework as sf_mod
    monkeypatch.setattr(sf_mod, "VirtuHindsightMemory", None)
    h = SynapticHomeostasis()
    buf = WakeExperienceBuffer()
    buf.record(prompt="厚壁圆筒Lamé分析", completion="FOS >= 1.5",
               verified_facts={"D_inner": 60.0, "D_outer": 120.0, "P_internal": 25.0, "Sy": 310.0})
    consolidated = KnowledgeSeeder().consolidate(buf.get_unconsolidated())

    no_caller = h.audit_homeostasis(None, consolidated, "NO_CALLER", tmp_dir, 1.0)
    assert no_caller.basis == "unmeasured"
    assert no_caller.gate_passed is False

    bad = h.audit_homeostasis(lambda p: "不知道", consolidated, "BAD_MODEL", tmp_dir, 1.0)
    assert bad.basis == "measured"
    assert bad.gate_passed is False
    assert bad.catastrophic_forgetting_rate > 0.05
    assert any("cf_above_threshold" in r for r in bad.reasons)

    no_baseline = h.audit_homeostasis(expert_caller, consolidated, "NO_BASELINE", tmp_dir, None)
    assert no_baseline.gate_passed is False
    assert no_baseline.baseline_provided is False
    assert any("no_pre_baseline_score" in r for r in no_baseline.reasons)


def test_09_full_valid_cycle_with_measured_evidence(tmp_dir, monkeypatch):
    """完整有效路径：真实形状的模型调用 + 实测 token + 独立基线 → gate 才可通过。"""
    import virtu_omni.memory.sleep_framework as sf_mod
    monkeypatch.setattr(sf_mod, "VirtuHindsightMemory", None)
    framework = VirtuSleepFramework(
        output_dir=tmp_dir,
        model_caller=analytic_caller,
        model_caller_label="stub:analytic",
        baseline_score=1.0,
    )
    cases = [
        ("厚壁圆筒Lamé应力分析，内径60，外径120，内压25MPa", {"D_inner": 60.0, "Sy": 310.0}),
        ("数控车削主轴转速计算，刀具直径D=80mm，线速度Vc=120m/min", {"D": 80.0, "Vc": 120.0}),
        ("法兰CAD建模体积守恒，外径100mm，通孔30mm，高度40mm", {"D": 100.0, "H": 40.0}),
    ]
    for prompt, facts in cases:
        framework.record_wake_step(prompt=prompt, completion="已完成", verified_facts=facts,
                                   tokens_prompt=120, tokens_completion=250)
    report = framework.run_sleep_cycle(run_id="FULL_VALID_PATH_TEST")
    assert report["model_caller_label"] == "stub:analytic"
    assert report["model_caller_available"] is True
    assert report["basis"] == "measured"
    assert report["dream_evidence_basis"] == "measured"
    assert report["dreams_generated"] >= 4
    assert report["dream_oracle_pass_rate"] >= 0.80
    assert report["dream_gate_passed"] is True
    assert report["baseline_provided"] is True
    assert isinstance(report["average_token_compression"], float)
    assert report["stability_score"] >= 0.95
    assert report["plasticity_score"] >= 0.90
    assert report["measurement_valid"] is True
    assert report["homeostasis_gate_passed"] is True


def test_10_unmeasured_tokens_never_fabricated(monkeypatch):
    import virtu_omni.memory.sleep_framework as sf_mod
    monkeypatch.setattr(sf_mod, "VirtuHindsightMemory", None)
    buf = WakeExperienceBuffer()
    buf.record(prompt="厚壁圆筒Lamé分析", completion="FOS >= 1.5",
               verified_facts={"fos": 2.6},
               tokens_prompt="unmeasured", tokens_completion="unmeasured")
    consolidated = KnowledgeSeeder().consolidate(buf.get_unconsolidated())
    assert consolidated
    assert all(c.compression_ratio is None for c in consolidated)
    assert all(c.token_basis == "unmeasured" for c in consolidated)

    buf2 = WakeExperienceBuffer()
    buf2.record(prompt="厚壁圆筒Lamé分析", completion="FOS >= 1.5",
                verified_facts={"fos": 2.6}, tokens_prompt=120, tokens_completion=250)
    measured = KnowledgeSeeder().consolidate(buf2.get_unconsolidated())
    assert all(isinstance(c.compression_ratio, float) for c in measured)


def test_11_model_resolver_never_fakes_a_caller():
    caller, label = build_ollama_model_caller(model="__definitely_missing_model__")
    assert caller is None
    assert label.startswith(("model_not_found", "unavailable"))
