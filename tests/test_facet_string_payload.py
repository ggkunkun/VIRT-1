# -*- coding: utf-8 -*-
"""反证测试：工程 facet 必须兼容真实 REACT 深度引擎发来的字符串载荷。

缺陷态（修复前）：深度引擎按广播 schema 发 ``{"payload": "<自然语言规格>"}``，
解包后单参 dict facet 收到字符串，delegate.run() 对字符串调 ``.get()`` 抛
AttributeError，REACT 真实路径 6 步里 4 步 FACET_ERROR。
本测试按 AGENTS.md §8.4 固化修复：字符串载荷必须可调用且产出真实工程结果，
dict 载荷契约不回归，desktop_gui 对非对象载荷返回结构化错误而非崩溃。
"""
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

os.environ.setdefault("VIRTU_DESKTOP_INPUT", "0")
os.environ.setdefault("VIRTU_TRAINING_KB", "off")

from virtu_omni.agent.super_agent import VirtuSuperAgent

SPEC = "法兰盘：外径160mm，内径80mm，厚12mm，6个M12孔，材料Q235"


@pytest.fixture(scope="module")
def agent():
    return VirtuSuperAgent()


@pytest.mark.parametrize("facet_name", [
    "facet_generate_cad", "facet_generate_standards",
    "facet_generate_cam", "facet_audit_sandbox",
])
def test_engineering_facet_accepts_string_payload(agent, facet_name):
    result = getattr(agent, facet_name)(SPEC)
    assert isinstance(result, dict)
    assert result.get("status") == "COMPLETED", f"{facet_name} 字符串载荷未产出工程结果"


def test_audit_sandbox_string_payload_audits_real_artifacts(agent):
    result = agent.facet_audit_sandbox(SPEC)
    # 字符串载荷必须先派生建模/加工产物再审计，不能空审假绿
    assert "audit_breakdown" in result
    assert "solidworks_vba_audit" in result["audit_breakdown"]
    assert "macro_b_audit" in result["audit_breakdown"]


def test_dict_payload_contract_not_regressed(agent):
    arch = agent.facet_parse_intent(SPEC)
    cad = agent.facet_generate_cad({"user_prompt": SPEC, "architecture": arch})
    assert cad.get("status") == "COMPLETED"
    assert cad.get("geometry_family")
    assert "bbox_mm" in cad


def test_desktop_gui_non_object_payload_returns_error_not_crash(agent):
    result = agent.facet_desktop_gui(SPEC)
    assert result.get("status") == "error"
    assert result.get("input_sent") is False


def test_falsification_delegate_still_requires_dict(agent):
    """反证：delegate 本体仍要求 dict（证明修复在 facet 归一化层，而非放松 delegate）。

    若有人把 _spec_context 去掉，字符串会直达 delegate 并复现 AttributeError。
    """
    with pytest.raises(AttributeError):
        agent._delegate_modeler.run(SPEC)