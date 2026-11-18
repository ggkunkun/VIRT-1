# -*- coding: utf-8 -*-
"""E7 反证测试：13 个 desktop_* 工具必须受中央 schema 闸门管辖。

修复前 ``get_tool_parameter_schemas()`` 只取 CADCAM_TOOLS_DEFINITION + INTERNAL，
desktop_* 无 schema ⇒ ``validate_tool_arguments`` 返回 [] ⇒ ``schema_gate`` 空转放行。
本测试按 AGENTS.md §8.4「植入坏样本 ⇒ 必须红」固化修复，并证明缺 schema 时闸门确实空转。
"""
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from bridges import tool_calling_specs as tcs

EXPECTED_DESKTOP_TOOLS = {
    "desktop_status", "desktop_list_displays", "desktop_list_apps",
    "desktop_list_windows", "desktop_snapshot", "desktop_find",
    "desktop_click", "desktop_type", "desktop_press", "desktop_focus_window",
    "desktop_screenshot", "desktop_launch", "desktop_batch",
}


@pytest.fixture(autouse=True)
def _fresh_schema_cache(monkeypatch):
    monkeypatch.setattr(tcs, "_SCHEMA_CACHE", {})
    monkeypatch.setenv(tcs.TOOL_SCHEMA_MODE_ENV, "enforce")
    yield


def test_all_desktop_tools_have_central_schema():
    schemas = tcs.get_tool_parameter_schemas()
    missing = EXPECTED_DESKTOP_TOOLS - set(schemas)
    assert not missing, f"desktop_* 工具缺中央 schema（闸门空转回归）: {sorted(missing)}"


def test_schema_gate_blocks_missing_required():
    block = tcs.schema_gate("desktop_click", {})
    assert block is not None, "缺必填 target 必须被拦截"
    assert block["verdict_code"] == "TOOL_SCHEMA_VIOLATION"
    assert any(e["field"] == "target" and e["reason"] == "required_missing"
               for e in block["errors"])


def test_schema_gate_blocks_type_mismatch():
    block = tcs.schema_gate("desktop_type", {"text": 123})
    assert block is not None, "text 非字符串必须被拦截"
    assert any(e["field"] == "text" and e["reason"] == "type_mismatch"
               for e in block["errors"])


def test_schema_gate_allows_valid_calls():
    assert tcs.schema_gate("desktop_press", {"combo": "ctrl+s"}) is None
    assert tcs.schema_gate("desktop_status", {}) is None
    assert tcs.schema_gate("desktop_list_windows", {"app": "SLDWORKS"}) is None


def test_falsification_without_schema_gate_is_noop(monkeypatch):
    """反证：若 desktop_* 没有 schema，闸门对坏样本也放行（空转）。

    这恰是修复前的缺陷态——证明上面的拦截断言确实依赖 schema 存在，
    一旦有人把 desktop_* 移出 schema 源，拦截测试会立即变红。
    """
    monkeypatch.setattr(tcs, "_SCHEMA_CACHE", {"desktop_click": None})
    assert tcs.validate_tool_arguments("desktop_click", {}) == []
    assert tcs.schema_gate("desktop_click", {}) is None