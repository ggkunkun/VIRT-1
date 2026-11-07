"""Registered defect: the serving backend rewrites correct tool-call answers.

Found 2026-11-05 by replaying ``_verify_arithmetic_response`` over the identity-stamped
frozen leg (``board7__frozen_comp_v5__v4``, 210/210 rows, 0 transport errors).
One case went 100 -> 33.33 because of it:

* ``_looks_like_tool_json`` only accepts a single object, so a correct **array** of two
  calls is treated as "no tool call was made";
* the compile fallback then replaces the model's answer with one call it derived from
  the prompt, which drops the second file and renames ``nc_file_path`` -> ``nc_path``.

These tests now assert the fixed behaviour (2026-11-05): ``_verify_arithmetic_response``
treats any parseable object *or* array of call objects as already-answered, compiles
only when the answer contains no call at all, and never renames fields the model got
right.
"""

import json

import pytest

from virtu_real_backend import (_compile_toolcall_from_prompt, _looks_like_tool_json,
                                _verify_arithmetic_response)

BATCH_PROMPT = "批量：对 runs/a.nc 与 runs/b.nc 分别做 CIMCO 校验。输出 JSON 数组两项，每项 tool/arguments。"
BATCH_ANSWER = json.dumps([
    {"tool": "cadcam_cimco_validate", "arguments": {"action": "validate_macro", "nc_file_path": "runs/a.nc"}},
    {"tool": "cadcam_cimco_validate", "arguments": {"action": "validate_macro", "nc_file_path": "runs/b.nc"}},
], ensure_ascii=False)

SINGLE_PROMPT = "对 runs/a.nc 做 CIMCO 校验。输出 JSON。"
SINGLE_ANSWER = json.dumps(
    {"tool": "cadcam_cimco_validate", "arguments": {"action": "validate_macro", "nc_file_path": "runs/a.nc"}},
    ensure_ascii=False)


def test_a_correct_array_of_tool_calls_survives_the_verifier():
    out = _verify_arithmetic_response(BATCH_ANSWER, [{"role": "user", "content": BATCH_PROMPT}])
    parsed = json.loads(out)
    assert isinstance(parsed, list), f"array was replaced by {type(parsed).__name__}"
    assert len(parsed) == 2
    assert "runs/b.nc" in out


def test_tool_json_detection_accepts_arrays_of_calls():
    assert _looks_like_tool_json(BATCH_ANSWER) is True


def test_the_verifier_keeps_the_argument_names_the_model_used():
    out = _verify_arithmetic_response(SINGLE_ANSWER, [{"role": "user", "content": SINGLE_PROMPT}])
    assert "nc_file_path" in out, out


def test_detection_ignores_non_call_json_even_when_the_word_tool_appears():
    # False-positive guard: a world_state object is not a tool call merely because the
    # answer text mentions "tool"; detection must key on the call shape, not the word.
    assert _looks_like_tool_json('调用 tool 后得到 {"world_state": {"a": 1}}') is False


def test_a_three_call_batch_keeps_every_call():
    three = json.dumps([{"tool": "cadcam_cimco_validate",
                         "arguments": {"action": "validate_macro", "nc_file_path": f"runs/{n}.nc"}}
                        for n in ("a", "b", "c")], ensure_ascii=False)
    out = _verify_arithmetic_response(three, [{"role": "user", "content": BATCH_PROMPT}])
    parsed = json.loads(out)
    assert isinstance(parsed, list) and len(parsed) == 3, out
    assert all("nc_file_path" in item["arguments"] for item in parsed)


def test_the_compiler_emits_the_argument_name_the_tool_actually_reads():
    """Second half of the same defect, found while writing up the first.

    ``bridges/tool_calling_specs.py`` reads ``args["nc_file_path"]`` when it builds the CIMCO
    request, but the compile fallback answered ``nc_path``: a compiled call could never find
    its file.  The rename is removed, so the fallback must speak the tool's real field name.
    """
    compiled = _compile_toolcall_from_prompt("用 CIMCO 校验 runs/a.nc 的宏程序")
    assert compiled is not None and compiled["tool"] == "cadcam_cimco_validate", compiled
    assert "nc_file_path" in compiled["arguments"], compiled
    assert "nc_path" not in compiled["arguments"], compiled


# ---------------------------------------------------------------------------
# 2026-11-05: the compile fallback used to *answer* for the model.
#
# It filled every missing input with an invented default (``runs/macro.nc``,
# ``part_name="part"``, ``"Sub main()\\nEnd Sub"``, ``runs/nx.py``).  So a response
# containing no tool call at all was replaced by a complete JSON call and scored
# full marks -- a fake pass (VIRTU_DISCIPLINE §5.2).  These tests are the
# falsification side: inject an empty answer and the case must go red.
# ---------------------------------------------------------------------------

CIMCO_NO_PATH_PROMPT = "用 CIMCO 校验一段 Macro B 程序。输出一个 JSON 工具调用。"
CIMCO_NO_PATH_CRITERIA = [
    {"type": "json_object", "required_keys": ["tool", "arguments"], "key": "JSON"},
    {"type": "enum_field", "field_enums": {"action": ["validate_macro"]}, "key": "动作"},
    {"type": "literal_all", "values": ["cadcam_cimco_validate", "validate_macro"], "key": "要素"},
]

SW_VBA_PROMPT = "SOLIDWORKS 执行 VBA 宏，part_name=flange。输出 JSON。"
SW_VBA_CRITERIA = [
    {"type": "json_object", "required_keys": ["tool", "arguments"], "key": "JSON"},
    {"type": "enum_field", "field_enums": {"action": ["execute_vba"]}, "key": "动作"},
    {"type": "literal_all", "values": ["cadcam_solidworks_model", "execute_vba"], "key": "要素"},
]

NX_NO_SCRIPT_PROMPT = ("当前任务是把 .prt 交给 NX。输出 JSON：tool=cadcam_nx_journal，"
                       "action=run_journal；不得出现 solidworks。")


def _score(response, criteria):
    from virtu_eval.graders import score_case
    return score_case(response, criteria)


def test_an_empty_answer_is_not_compiled_into_a_full_call():
    """The fake green itself: empty output, prompt without a path -> must stay empty and score 0."""
    assert _compile_toolcall_from_prompt(CIMCO_NO_PATH_PROMPT) is None
    out = _verify_arithmetic_response("", [{"role": "user", "content": CIMCO_NO_PATH_PROMPT}])
    assert out == "", f"empty answer was compiled into {out!r}"
    assert _score(out, CIMCO_NO_PATH_CRITERIA)["score"] == 0.0, out


def test_the_compiler_never_invents_an_nc_path():
    assert _compile_toolcall_from_prompt("用 CIMCO 校验一段 Macro B 程序") is None


def test_the_compiler_never_synthesises_a_vba_body():
    assert _compile_toolcall_from_prompt(SW_VBA_PROMPT) is None
    out = _verify_arithmetic_response("", [{"role": "user", "content": SW_VBA_PROMPT}])
    assert out == "", f"empty answer was filled with a VBA stub: {out!r}"
    assert _score(out, SW_VBA_CRITERIA)["score"] == 0.0, out


def test_the_compiler_never_invents_an_nx_script_path():
    assert _compile_toolcall_from_prompt(NX_NO_SCRIPT_PROMPT) is None
    out = _verify_arithmetic_response("", [{"role": "user", "content": NX_NO_SCRIPT_PROMPT}])
    assert out == "", out


def test_the_compiler_copies_the_vba_code_the_prompt_actually_contains():
    """Fail-closed is not a blanket ban: explicitly given fields are still carried over."""
    prompt = ("SOLIDWORKS 执行 VBA 宏，part_name=flange，"
              "vba_code=Sub main()\n    Dim swApp As Object\nEnd Sub。输出 JSON。")
    compiled = _compile_toolcall_from_prompt(prompt)
    assert compiled is not None and compiled["tool"] == "cadcam_solidworks_model", compiled
    code = compiled["arguments"]["vba_code"]
    assert "Dim swApp As Object" in code, code
    assert "Sub main()" in code and "End Sub" in code, code


def test_the_compiler_still_answers_a_prompt_that_states_every_field():
    prompt = "用 CIMCO 校验 runs/a.nc 的宏程序。输出 JSON。"
    compiled = _compile_toolcall_from_prompt(prompt)
    assert compiled == {"tool": "cadcam_cimco_validate",
                        "arguments": {"action": "validate_macro", "nc_file_path": "runs/a.nc"}}
