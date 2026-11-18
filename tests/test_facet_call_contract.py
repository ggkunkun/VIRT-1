# -*- coding: utf-8 -*-
"""facet 调用契约的回归测试（2026-11-16 D1 修复的反证用例）。

背景：注册表把 facet 当单参函数（fn(payload)），但有 10 个 facet 的真实签名是多参。
模型按广播 schema 发的 JSON 对象会被整体绑到第一个位置参数，于是这 10 个工具在
REACT 真实路径下要么抛 TypeError，要么悄悄丢掉参数（dispatch_modality 的 action
被丢成 ""、check_software_affordance 的 software 被丢成默认值）。

本文件同时钉住三件事：
  1. 正向：10 个多参 facet 经真实适配器路径，用具名参数全部可调用；
  2. 反向：**必填参数缺失必须显式失败**，不允许静默用默认值顶替（植入坏样本必须红）；
  3. 不回归：26 个单参 facet 的旧「payload 字符串」契约行为不变。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("VIRTU_DESKTOP_INPUT", "0")
os.environ.setdefault("VIRTU_DESKTOP_INPUT_DRYRUN", "1")

from virtu_omni.agent.super_agent import (  # noqa: E402
    FacetToolAdapter,
    VirtuSuperAgent,
    _bind_facet_args,
    _facet_input_schema,
    _facet_params,
)

#: 单参 facet 的旧契约（payload 字符串/裸对象）——必须保持行为不变
LEGACY_SINGLE_ARG = {
    "parse_intent": "加工一个法兰盘，外径160mm",
    "web_search": {"query": "ISO 2768", "num_results": 1},
}

#: 多参 facet 的「合法具名参数」样例：必须给满**全部必填形参**，
#: 否则连 deep_agent.validate_plan 都过不去。
NAMED_ARGS = {
    "dispatch_modality": {"prompt": "列出窗口", "modality": "FUNCTION_CALLING",
                          "target_software": "SOLIDWORKS_2021"},
    "check_software_affordance": {"action": "create_parametric_part",
                                  "software": "SOLIDWORKS_2021"},
    "mcts_plan_process_route": {"operations": [{
        "op_id": "op1", "op_name": "粗车", "op_type": "ROUGH_TURNING", "tool_id": "T1",
        "tool_ld_ratio": 3.0, "required_preconditions": [], "fixture_id": "F1"}]},
    "rlvr_grpo_eval": {"prompt": "算 FOS", "candidates": ["FOS=2.1", "FOS=0.9"]},
    "prm_stepwise_audit": {"gcode_or_steps": "G00 X100.0 Z50.0\nG01 Z-5.0 F100\nM30"},
    "brep_dsl_compile": {"commands": [{"op": "add_cylinder",
                                       "params": {"radius": 10.0, "height": 20.0}}]},
    "quiet_star_self_heal": {"code": "def f():\n    return 1\n", "language": "PYTHON"},
    "pinn_stress_surrogate": {"length_mm": 45.0, "outer_dia_mm": 160.0,
                              "inner_dia_mm": 80.0, "pressure_mpa": 10.0},
    "verify_cae_stress": {"spec": {"d_outer": 160, "d_inner": 80, "overall_len": 45}},
}

#: 单参但**形状特殊**的 facet：旧契约要求 payload 是一段 JSON 文本
#: （数组 / 整数）。schema 不变（仍是 payload 字符串），但适配器两种写法都要能接。
SPECIAL_SINGLE_ARG = {
    "blueprint_spatial_ground": {
        "named": {"raw_elements": [{"type": "circle", "center": [50.0, 50.0], "radius": 20.0}]},
        "legacy_payload": [{"type": "circle", "center": [50.0, 50.0], "radius": 20.0}],
    },
    "funsearch_evolve": {"named": {"steps": 1}, "legacy_payload": 1},
}


@pytest.fixture(scope="module")
def agent():
    return VirtuSuperAgent()


@pytest.fixture(scope="module")
def adapter(agent):
    return FacetToolAdapter(agent.tools)


# --------------------------------------------------------------------------
# 1. 正向：多参 facet 用具名参数必须可调用
# --------------------------------------------------------------------------
@pytest.mark.parametrize("tool_name", sorted(NAMED_ARGS))
def test_multi_param_facet_accepts_named_args(adapter, tool_name):
    """10 个多参 facet 经适配器用具名参数调用，必须不报 FACET_ERROR。"""
    res = adapter.call(tool_name, dict(NAMED_ARGS[tool_name]))
    assert not res.get("is_error"), (
        f"{tool_name} 用具名参数调用失败: {res.get('text')}")


def test_all_multi_param_facets_are_covered_by_the_case_table(agent):
    """反证：不能有新的多参 facet 悄悄漏出测试覆盖。"""
    multi = {name for name, (_d, fn) in agent.tools.items()
             if len(_facet_params(fn)) > 1}
    missing = multi - set(NAMED_ARGS)
    assert not missing, f"新增的多参 facet 未纳入回归用例: {sorted(missing)}"


@pytest.mark.parametrize("tool_name", sorted(SPECIAL_SINGLE_ARG))
def test_special_single_param_facet_accepts_both_shapes(adapter, tool_name):
    """单参但形状特殊的 facet：具名写法与旧 payload 写法都要能接。"""
    spec = SPECIAL_SINGLE_ARG[tool_name]
    res_named = adapter.call(tool_name, dict(spec["named"]))
    assert not res_named.get("is_error"), \
        f"{tool_name} 具名写法失败: {res_named.get('text')}"
    res_legacy = adapter.call(tool_name, {"payload": json.dumps(spec["legacy_payload"])})
    assert not res_legacy.get("is_error"), \
        f"{tool_name} 旧 payload 写法失败: {res_legacy.get('text')}"


# --------------------------------------------------------------------------
# 2. 反向：必填参数缺失必须显式失败（植入坏样本必须红）
# --------------------------------------------------------------------------
def test_missing_required_param_raises_instead_of_silently_defaulting(agent):
    """pinn_stress_surrogate 少给 outer_dia_mm 时必须报错，不能用默认值顶替。"""
    fn = agent.tools["pinn_stress_surrogate"][1]
    with pytest.raises(TypeError) as exc:
        _bind_facet_args(fn, {"length_mm": 45.0, "inner_dia_mm": 80.0})
    assert "outer_dia_mm" in str(exc.value)


def test_adapter_surfaces_missing_param_as_error_not_silent_success(adapter):
    """适配器层同样必须把「缺必填参数」报成错误，而不是当成成功返回。"""
    res = adapter.call("rlvr_grpo_eval", {"prompt": "算 FOS"})
    assert res.get("is_error"), "缺 candidates 却报成功 = 静默降级"
    assert "FACET_ERROR" in str(res.get("text"))


def test_unknown_tool_still_raises_keyerror(agent):
    """不回归：未知工具名仍然显式失败。"""
    with pytest.raises(KeyError):
        agent.call_tool("no_such_facet", {})


# --------------------------------------------------------------------------
# 3. 不回归：单参 facet 的旧 payload 契约
# --------------------------------------------------------------------------
@pytest.mark.parametrize("tool_name", sorted(LEGACY_SINGLE_ARG))
def test_single_param_facet_legacy_contract_unchanged(agent, tool_name):
    """单参 facet 仍按旧契约整体接收载荷（不因签名绑定而改变行为）。"""
    out = agent.call_tool(tool_name, LEGACY_SINGLE_ARG[tool_name])
    assert out is not None
    assert not (isinstance(out, dict) and out.get("error")), \
        f"{tool_name} 旧契约被破坏: {out}"


def test_schema_broadcasts_real_param_names_for_multi_param_tools(adapter, agent):
    """多参 facet 的 schema 必须暴露真实形参名与真实必填项。

    deep_agent 的 tool_brief 靠 properties/required 生成「参数清单」，
    validate_plan 靠 required 卡住缺参的计划 —— schema 不写真实形参，
    规划器就只能猜 payload 形状（实测 rlvr_grpo_eval / pinn_stress_surrogate
    因为无法给出第二、第三个必填参数而在 REACT 下完全不可用）。
    """
    schemas = {s["name"]: s for s in adapter.schemas()}
    for tool_name, args in NAMED_ARGS.items():
        fn = agent.tools[tool_name][1]
        real_required = _facet_input_schema(fn)["required"]
        sch = schemas[tool_name]["inputSchema"]
        props = sch["properties"]
        for key in args:
            assert key in props, f"{tool_name} 的 schema 缺少真实形参 {key}"
        # 旧的 payload 包裹写法仍要合法，不能把两种写法都堵死
        assert "payload" in props, f"{tool_name} 的 schema 丢了 payload 兼容写法"
        assert sch["required"] == real_required, (
            f"{tool_name} 的 required 与真实必填形参不一致: "
            f"{sch['required']} != {real_required}")
        # 具名参数必须给满所有必填项，否则计划过不了 validate_plan
        missing = [k for k in real_required if k not in args]
        assert not missing, f"{tool_name} 的用例没给满必填参数 {missing}"


def test_schema_keeps_legacy_payload_contract_for_single_param_tools(adapter, agent):
    """单参 facet 的 schema 一律不变（26 个已验证工具行为不变）。"""
    schemas = {s["name"]: s for s in adapter.schemas()}
    for name, (_d, fn) in agent.tools.items():
        if len(_facet_params(fn)) != 1:
            continue
        sch = schemas[name]["inputSchema"]
        assert list(sch["properties"]) == ["payload"], \
            f"{name} 的 schema 被意外改动: {list(sch['properties'])}"
        assert sch["required"] == ["payload"]
