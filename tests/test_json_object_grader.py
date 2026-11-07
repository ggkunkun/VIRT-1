"""Falsification tests for the ``json_object`` shape grader (AGENTS.md §8.4).

Measured 2026-11-06: ``forbidden_keys`` was matched at every nesting depth, so a
correct sheet-metal routing answer lost 40 points for calling its three parts
``name``. These tests pin the fix *and* pin the failure it must still catch --
a nested key exemption that also stopped catching ``{"name": ...}`` at the top
level would be a gate that cannot be falsified.

Every case below plants a defect and asserts the grader goes red, except the two
that assert legitimate output stays green.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from virtu_eval.graders import g_json_object, score_case  # noqa: E402

ROUTING = {"type": "json_object", "key": "shape", "weight": 2,
           "required_keys": ["tool", "arguments"],
           "forbidden_keys": ["name", "function"]}


def test_top_level_name_is_still_rejected():
    """The defect the criterion was written for must still fail."""
    ok, ev = g_json_object('{"name": "cadcam_sheetmetal_nest", "arguments": {}}', ROUTING)
    assert ok is False
    assert "forbidden=['name']" in ev


def test_top_level_function_is_still_rejected():
    ok, ev = g_json_object('{"function": "x", "arguments": {}}', ROUTING)
    assert ok is False
    assert "forbidden=['function']" in ev


def test_nested_part_name_is_legitimate():
    """arguments.parts[].name is a part filename, not a protocol key."""
    resp = ('{"tool": "cadcam_sheetmetal_nest", "arguments": {"parts": '
            '[{"name": "a.dxf", "size_mm": "200x150"}, {"name": "b.dxf", "size_mm": "180x120"}]}}')
    ok, ev = g_json_object(resp, ROUTING)
    assert ok is True, ev


def test_nested_name_deep_inside_list_of_lists_is_legitimate():
    resp = '{"tool": "t", "arguments": {"bom": [[{"name": "bolt"}]]}}'
    ok, ev = g_json_object(resp, ROUTING)
    assert ok is True, ev


def test_missing_required_key_fails():
    ok, ev = g_json_object('{"tool": "t"}', ROUTING)
    assert ok is False
    assert "missing=['arguments']" in ev


def test_unparseable_response_fails_loudly():
    ok, ev = g_json_object("抱歉，我无法完成这个请求。", ROUTING)
    assert ok is False
    assert ev == "no_json_object_parsed"


def test_empty_response_fails():
    ok, ev = g_json_object("", ROUTING)
    assert ok is False


def test_recursive_scope_reproduces_pre_fix_verdict():
    """Historical legs must stay re-scorable: the old behaviour is still reachable."""
    resp = '{"tool": "t", "arguments": {"parts": [{"name": "a.dxf"}]}}'
    legacy = dict(ROUTING, forbidden_keys_scope="recursive")
    ok, ev = g_json_object(resp, legacy)
    assert ok is False
    assert "forbidden=['name']" in ev


@pytest.mark.parametrize("resp,expected", [
    ('{"tool":"t","arguments":{"name":"nested"}}', True),
    ('{"tool":"t","arguments":{}}', True),
    ('```json\n{"tool":"t","arguments":{}}\n```', True),
    ('{"tool":"t","arguments":{},"name":"leak"}', False),
])
def test_score_case_weights_shape_criterion(resp, expected):
    scored = score_case(resp, [ROUTING])
    assert (scored["score"] == 100.0) is expected


def test_gate_cannot_pass_on_empty_criteria_set():
    """A grader that silently passes nothing must raise, per §8.4."""
    with pytest.raises(ValueError):
        score_case('{"tool":"t","arguments":{}}', [])
