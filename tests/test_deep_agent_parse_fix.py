# -*- coding: utf-8 -*-
"""deep_agent 两处缺陷的反证测试（植入坏样本 ⇒ 必须红）。

  1) parse_json_loose 对 JSON 数组直接返回 list（违反 dict|None 契约）→ 下游
     sanitize_plan 的 plan.get("steps") / 验收路径 (data or {}).get("items")
     对 list 调 .get 触发 AttributeError 崩溃。修复后：数组 ⇒ (None, "failed")。
  2) coerce_arg 把 Python int 映射成 vt="integer"，仅声明 "number" 的参数拒绝它
     （JSON Schema number 本就接受整数）→ 合法数值参数被 sanitize_plan 静默丢弃。

运行： .venv/Scripts/python.exe -m pytest tests/test_deep_agent_parse_fix.py -q
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bridges.deep_agent import parse_json_loose, coerce_arg  # noqa: E402


# ---------------------------------------------------------------------------
# 1. parse_json_loose 不得返回非 dict（数组崩溃根因）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("arr", ['[1, 2, 3]', '[]', '```json\n[1,2]\n```'])
def test_json_array_returns_none_not_list(arr):
    plan, how = parse_json_loose(arr)
    assert plan is None, f"数组被当成计划返回（{type(plan).__name__}），下游 .get 必崩"
    assert how == "failed"
    # 验收路径表达式 (data or {}).get("items") 必须不崩
    assert (plan or {}).get("items") is None


@pytest.mark.parametrize("text", ['[1,2,3]', '[{"a": 1}]', '[]', "['a','b']",
                                  '{"steps": []}', '噪声 {"x":1} 尾'])
def test_never_returns_non_dict(text):
    """通用契约：返回值只能是 dict 或 None，绝不能是 list（崩溃根因）。"""
    plan, _ = parse_json_loose(text)
    assert plan is None or isinstance(plan, dict), f"返回了 {type(plan).__name__}"
    # 下游两处 .get 表达式在任何返回下都不得 AttributeError
    assert (plan or {}).get("items") is None or isinstance(plan, dict)


def test_python_literal_array_returns_none():
    plan, how = parse_json_loose("['a', 'b']")
    assert plan is None


def test_json_dict_still_parses():
    plan, how = parse_json_loose('{"steps": [], "analysis": "x"}')
    assert isinstance(plan, dict)
    assert how == "json"
    assert plan["analysis"] == "x"


def test_python_literal_dict_still_parses():
    plan, how = parse_json_loose("{'steps': [], 'analysis': 'y'}")
    assert isinstance(plan, dict)
    assert how == "literal_eval"


def test_embedded_dict_extracted():
    plan, how = parse_json_loose("前言噪声 {\"steps\": []} 后缀")
    assert isinstance(plan, dict)
    assert how in ("json_extracted", "literal_extracted")


# ---------------------------------------------------------------------------
# 2. coerce_arg：number 必须接受整数
# ---------------------------------------------------------------------------
def test_int_accepted_for_number():
    val, ok, note = coerce_arg({"type": "number"}, 640)
    assert ok is True, "Python int 被 number 参数拒绝（合法数值会被静默丢弃）"
    assert val == 640


def test_float_accepted_for_number():
    val, ok, _ = coerce_arg({"type": "number"}, 3.14)
    assert ok is True and val == 3.14


def test_int_accepted_for_integer():
    val, ok, _ = coerce_arg({"type": "integer"}, 7)
    assert ok is True and val == 7


def test_float_rejected_for_integer():
    """正对照：非整数浮点 for integer 仍应拒绝（JSON Schema integer 语义）。"""
    _, ok, _ = coerce_arg({"type": "integer"}, 3.5)
    assert ok is False


def test_int_accepted_for_number_anyof():
    val, ok, _ = coerce_arg({"anyOf": [{"type": "number"}, {"type": "null"}]}, 5)
    assert ok is True and val == 5


def test_string_rejected_for_number_still():
    """边界：描述性字符串 for number 不得被静默接受（避免假数值）。"""
    _, ok, _ = coerce_arg({"type": "number"}, "centered")
    assert ok is False


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-o", "addopts=", "-p", "no:cacheprovider"]))