"""M2 多目标约束优化求解引擎单元测试：可行性、权重敏感性、30s预算、动态约束与 REST API。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cam_autogen.contracts import CustomConstraint, MachineLimits, ObjectiveWeights, OptimizationRequest, ProcessType, WorkpieceSpec
from cam_autogen.examples import EXAMPLES
from cam_autogen.optimization.api import app
from cam_autogen.optimization.catalog import resolve_material
from cam_autogen.optimization.constraints import ExpressionError
from cam_autogen.optimization.engine import optimize
from cam_autogen.process_recognition import recognize


@pytest.mark.parametrize("key", ["shaft", "keyed_shaft", "block", "flange"])
def test_all_examples_feasible_and_within_30s(key):
    wp = WorkpieceSpec.model_validate(EXAMPLES[key])
    rec = recognize(wp)
    plan = optimize(OptimizationRequest(workpiece=wp, process_type=rec.process_type, time_budget_s=20.0))
    assert plan.feasible is True, f"{key} 不可行: {plan.infeasible_reasons}"
    assert plan.solver["elapsed_s"] < 30.0
    assert plan.solver["within_budget"] is True
    assert all(o.metrics.max_violation <= 1e-6 for o in plan.operations)


def test_weight_tradeoff_efficiency_vs_tool_wear_and_precision():
    wp = WorkpieceSpec.model_validate(EXAMPLES["shaft"])
    p_eff = optimize(OptimizationRequest(
        workpiece=wp, process_type=ProcessType.TURNING,
        weights=ObjectiveWeights(efficiency=0.90, tool_wear=0.03, precision=0.04, cost=0.03),
    ))
    p_wear = optimize(OptimizationRequest(
        workpiece=wp, process_type=ProcessType.TURNING,
        weights=ObjectiveWeights(efficiency=0.03, tool_wear=0.90, precision=0.04, cost=0.03),
    ))
    assert p_eff.feasible and p_wear.feasible
    assert p_eff.totals["cut_time_min"] <= p_wear.totals["cut_time_min"]
    assert p_wear.totals["tool_wear_sum"] <= p_eff.totals["tool_wear_sum"]


def test_custom_constraint_and_infeasible_detection():
    wp = WorkpieceSpec.model_validate(EXAMPLES["shaft"])
    # 动态新增自定义硬约束：全工序转速不超过 1850 rpm（默认最优会跑 2960/2191 rpm，此约束迫使优化器压低转速）
    plan = optimize(OptimizationRequest(
        workpiece=wp, process_type=ProcessType.TURNING,
        custom_constraints=[CustomConstraint(name="custom_rpm_cap", expr="n <= 1850", hard=True)],
    ))
    assert plan.feasible is True
    assert all(o.params.rpm <= 1851 for o in plan.operations)

    # 极端不合理转速上限应正确报出不可行而非静默放行
    plan_bad = optimize(OptimizationRequest(
        workpiece=wp, process_type=ProcessType.TURNING,
        machine_limits=MachineLimits(max_rpm=50, max_power_kw=0.2),
    ))
    assert plan_bad.feasible is False
    assert len(plan_bad.infeasible_reasons) > 0


def test_custom_constraint_ast_security():
    wp = WorkpieceSpec.model_validate(EXAMPLES["shaft"])
    # 允许的一元负号、函数 sqrt/min 与工序过滤
    plan_ok = optimize(OptimizationRequest(
        workpiece=wp, process_type=ProcessType.TURNING,
        disabled_constraints=["min_chip_thickness"],
        custom_constraints=[
            CustomConstraint(name="fn_ok", expr="sqrt(max(Vc, 1)) <= 500", applies_to=["face_turn"]),
            CustomConstraint(name="unary_ok", expr="-Vc <= -10"),
        ],
    ))
    assert plan_ok.feasible is True

    for bad_expr in (
        "__import__('os').system('echo 1') <= 1",
        "secret_var <= 10",
        "Vc = 10",
        "Vc % 2 <= 1",
        "not Vc <= 0",
        "'abc' <= 1",
        "Vc <= 100 <= 200",
    ):
        with pytest.raises(ExpressionError):
            optimize(OptimizationRequest(
                workpiece=wp, process_type=ProcessType.TURNING,
                custom_constraints=[CustomConstraint(name="bad", expr=bad_expr)],
            ))


def test_material_alias_and_unknown_fallback():
    wp = WorkpieceSpec.model_validate(EXAMPLES["shaft"])
    name, _, warn = resolve_material(wp.material.model_copy(update={"name": "45#"}))
    assert name == "C45" and warn is None
    name2, _, warn2 = resolve_material(wp.material.model_copy(update={"name": "MYSTERY_STEEL", "hardness_hb": 210}))
    assert warn2 is not None and name2 in ("C45", "HT250")


def test_m2_rest_api():
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert "efficiency" in str(client.get("/v1/info").json())
    r = client.post("/v1/optimize", json={"workpiece": EXAMPLES["shaft"], "process_type": "TURNING"})
    assert r.status_code == 200 and r.json()["feasible"] is True
    r_bad = client.post("/v1/optimize", json={
        "workpiece": EXAMPLES["shaft"], "process_type": "TURNING",
        "custom_constraints": [{"name": "bad", "expr": "bad_var <= 1"}],
    })
    assert r_bad.status_code == 422
