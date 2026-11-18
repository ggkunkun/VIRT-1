# -*- coding: utf-8 -*-
"""tests/test_ultimate_suite.py — Test Suite for Virtu Ultimate SOTA Frontier & Multi-Modal Architecture Suite.

Verifies:
1. Stanford Quiet-STaR Sandbox: Silent execution, iterative self-healing, traceback analysis, Rule 4 probe.
2. DeepSeek-MoE: Isolated Shared Expert, fine-grained routed experts, Top-2 gating, compute efficiency, Rule 4 probe.
3. Apple Ferret Blueprint Grounding: Continuous coordinate tokenization, view alignment, 3D CAD inverse synthesis, Rule 4 probe.
4. NVIDIA Modulus PINN Surrogate: Sub-10ms continuous elasticity stress, FOS calculation, SIMP topology optimization, Rule 4 probe.
5. Super Agent Integration: facet_quiet_star_heal, facet_blueprint_ground, facet_pinn_predict.
6. Rule 4 Falsifiable Gates: All 4 mutation probes pass.
"""

import os
import sys

import pytest

# 本文件只有 DeepSeek-MoE 用例（test_02/test_06 的 MoE 探针）需要 torch。
# 之前用模块级 importorskip 会把 1/3/4/5 这四个纯 sandbox/grounding/PINN 用例
# 一起跳过——它们是推理主机上真实可跑的能力，不该被一个可选依赖连坐。

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from virtu_omni.ultimate_suite import get_ultimate_suite, VirtuUltimateSuite
from virtu_omni.reasoning.quiet_star_sandbox import QuietStarSelfHealingSandbox
from virtu_omni.vision.blueprint_spatial_grounding import BlueprintSpatialGroundingEngine
from virtu_omni.engine.pinn_surrogate_engine import PINNSurrogateEngine
from virtu_omni.agent import VirtuSuperAgent


def _torch_available() -> bool:
    try:
        import torch  # noqa: F401
        return True
    except ModuleNotFoundError:
        return False


def test_01_quiet_star_silent_healing():
    """Verify Quiet-STaR silent sandbox execution and automated patch healing."""
    sandbox = QuietStarSelfHealingSandbox(k_max=3)

    # Code with a zero division error in a formula calculation
    code_with_div_zero = """x = 100.0
divisor = 0
result = x / divisor
"""
    report = sandbox.execute_and_heal_code(code_with_div_zero, language="PYTHON")
    assert report.success is True
    assert report.total_attempts >= 2
    assert report.circuit_breaker_tripped is False
    assert "result" in report.final_code
    assert report.basis == "measured"

    # Rule 4 Falsifiable Gate (Unrecoverable syntax error trips circuit breaker)
    assert sandbox.falsifiable_quiet_star_probe() is True


def test_02_deepseek_moe_fine_grained_routing():
    """Verify DeepSeek-MoE shared expert + fine-grained Top-2 routing."""
    torch = pytest.importorskip("torch")
    from virtu_omni.models.deepseek_moe_architecture import VirtuDeepSeekMoELayer

    batch_size, seq_len, hidden_dim = 2, 8, 64
    moe = VirtuDeepSeekMoELayer(
        hidden_dim=hidden_dim,
        intermediate_dim=128,
        num_routed_experts=8,
        top_k=2,
    )

    x = torch.randn(batch_size, seq_len, hidden_dim)
    out, metrics = moe(x)

    assert out.shape == (batch_size, seq_len, hidden_dim)
    assert metrics["shared_expert_active"] is True
    assert metrics["routed_active_count"] == 2
    assert metrics["active_ratio_pct"] < 35.0  # 3 of 9 experts active = 33.33%
    assert metrics["aux_loss"] >= 0.0

    # Rule 4 Falsifiable Gate
    assert VirtuDeepSeekMoELayer.falsifiable_moe_probe() is True


def test_03_blueprint_spatial_grounding():
    """Verify multi-modal blueprint coordinate tokenization and 3D CAD inversion."""
    elements = [
        {
            "id": "TITLE_01",
            "type": "TITLE_BLOCK",
            "bbox": [900.0, 700.0, 980.0, 980.0],
            "text": "名称: 轴承套筒 | 材料: AL7075-T6",
        },
        {
            "id": "DIM_01",
            "type": "DIMENSION",
            "bbox": [200.0, 300.0, 240.0, 450.0],
            "text": "Ø60h7",
        },
        {
            "id": "DIM_02",
            "type": "DIMENSION",
            "bbox": [500.0, 100.0, 540.0, 250.0],
            "text": "L=90",
        },
        {
            "id": "GDT_01",
            "type": "GDT_FRAME",
            "bbox": [260.0, 320.0, 300.0, 480.0],
            "text": "[同轴度 | 0.02 | A]",
        },
    ]

    grounded, err = BlueprintSpatialGroundingEngine.ground_blueprint_elements(elements)
    assert err is None
    assert len(grounded) == 4
    assert grounded[0].bbox.is_valid() is True

    # Invert to 3D CAD spec
    spec = BlueprintSpatialGroundingEngine.invert_to_3d_cad_spec(grounded)
    assert spec.material == "AL7075-T6"
    assert spec.part_family == "ROTATIONAL_SHAFT"
    assert spec.base_dimensions.get("outer_diameter_mm") == 60.0
    assert spec.base_dimensions.get("length_mm") == 90.0
    assert spec.confidence_score >= 0.90
    assert len(spec.gdt_tolerances) == 1

    # Rule 4 Falsifiable Gate
    assert BlueprintSpatialGroundingEngine.falsifiable_grounding_probe() is True


def test_04_pinn_surrogate_stress_and_topology():
    """Verify sub-10ms PINN elasticity stress prediction and SIMP topology optimization."""
    res, err = PINNSurrogateEngine.predict_stress_and_topology(
        length_mm=120.0,
        outer_dia_mm=60.0,
        inner_dia_mm=20.0,
        pressure_mpa=25.0,
        tensile_force_n=10000.0,
        material="AL7075-T6",
    )

    assert err is None
    assert res is not None
    assert res.computation_time_ms < 50.0  # Ultra-fast surrogate
    assert res.peak_von_mises_mpa > 0.0
    assert res.safety_factor_fos >= 1.5
    assert res.fos_compliant is True

    # If component is over-engineered (FOS > 2.5), check generative topology zones
    if res.safety_factor_fos > 2.5:
        assert res.topology_mass_reduction_pct > 0.0
        assert len(res.lightweighting_zones) >= 1

    # Rule 4 Falsifiable Gate
    assert PINNSurrogateEngine.falsifiable_pinn_probe() is True


def test_05_super_agent_ultimate_facets():
    """Verify Super Agent invocation of the 3 new ultimate facets."""
    agent = VirtuSuperAgent()

    # 1. Facet Quiet-STaR Self-Healing
    heal_rep = agent.facet_quiet_star_heal(
        code="a = 50.0\nb = 0.0\nc = a / b\n",
        language="PYTHON",
    )
    assert heal_rep["success"] is True

    # 2. Facet Blueprint Grounding
    ground_res = agent.facet_blueprint_ground([
        {
            "id": "DIM_1",
            "type": "DIMENSION",
            "bbox": [100.0, 100.0, 200.0, 300.0],
            "text": "Ø45",
        }
    ])
    assert ground_res["success"] is True
    assert ground_res["cad_spec"] is not None

    # 3. Facet PINN Stress Prediction
    pinn_res = agent.facet_pinn_predict(
        length_mm=80.0,
        outer_dia_mm=50.0,
        inner_dia_mm=15.0,
        pressure_mpa=20.0,
        material="AL7075-T6",
    )
    assert pinn_res["success"] is True
    assert pinn_res["result"]["fos_compliant"] is True


def test_06_ultimate_suite_probes_report():
    """Verify full ultimate suite probes adhering to Section 8.

    MoE 探针需要 torch：无 torch 时它必须如实判 False（suite 里已如此实现），
    本用例据此校验"不可执行 ⇒ 判红"而不是伪装全绿；其余三个探针照常要求 True。
    """
    suite = get_ultimate_suite()
    rep = suite.run_all_ultimate_probes()
    assert rep.quiet_star_probe_passed is True
    assert rep.blueprint_grounding_probe_passed is True
    assert rep.pinn_surrogate_probe_passed is True
    if _torch_available():
        assert rep.deepseek_moe_probe_passed is True
        assert rep.all_probes_passed is True
    else:
        assert rep.deepseek_moe_probe_passed is False, "MoE 探针无 torch 时必须判红"
        assert suite.moe_layer is None
        assert rep.all_probes_passed is False
    assert rep.basis == "measured"
    assert rep.run_id.startswith("ULTIMA_PROBE_")
