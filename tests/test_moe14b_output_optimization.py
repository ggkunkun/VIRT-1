# -*- coding: utf-8 -*-
"""Verification tests for Virtu 13.63B (virtu-moe-14b) output optimization.

Follows the Measurement Constitution (测量宪法):
- Every gate must have falsifiable assertions and planted bad samples.
- Covers:
  1. Internal persona/expert cosplay monologue removal
  2. Special token & think block hygiene
  3. Token/line repetition loop collapse
  4. Markdown fence & conversational preamble stripping for strict JSON
  5. Container unwrapping (e.g. {"result": ...} -> {...})
  6. Deterministic explicit-equation arithmetic correction
  7. End-to-end clean_served_answer integration
  8. Ollama Modelfile parameter & stop token integrity gates
"""
import json
import pytest

from virtu_omni.serving.answer_pipeline import clean_served_answer
from virtu_omni.serving.output_compiler import (
    compile_output,
    strip_json_fence_and_preamble,
    unwrap_tool_envelope,
)
from virtu_omni.serving.output_hygiene import (
    collapse_token_runs,
    hygiene,
    strip_cosplay,
    strip_special_tokens,
    strip_think,
)
from virtu_omni.serving.numeric_repair import fix_explicit_equation


def test_cosplay_monologue_is_stripped():
    raw_response = (
        "🧠 Virtu-MoE 工业超级智能体正在调用工业制造与智能体工具专家：\n"
        "- 调用 Siemens NX API 计算切削速度与主轴转速关系。\n"
        "- 调用 CIMCO 软件库验证标准公差与表面粗糙度参数。\n\n"
        "🔧 材料力学理论与逆向推理专家正在校核：\n"
        "- 45 钢的弹性模量 E=210 GPa，泊松比 μ=0.3。\n\n"
        "主轴转速推荐为 n = 1528 r/min，进给速度 Vf = 300 mm/min。"
    )
    cleaned = strip_cosplay(raw_response)
    assert "正在调用" not in cleaned
    assert "正在校核" not in cleaned
    assert cleaned == "主轴转速推荐为 n = 1528 r/min，进给速度 Vf = 300 mm/min。"


def test_cosplay_fallback_when_only_monologue():
    """If the model produced nothing but the monologue, do not return empty text."""
    monologue = "🧠 Virtu-MoE 正在调用工业制造专家。"
    assert strip_cosplay(monologue) == monologue


def test_special_tokens_hygiene():
    raw = "[PAD151667]主轴转速 n=1528 r/min[PAD151668]<｜begin▁of▁thinking｜>先算n<｜end▁of▁thinking｜></tool_call>"
    assert strip_special_tokens(raw) == "主轴转速 n=1528 r/min先算n"


def test_empty_think_and_repetitive_loop_collapse():
    raw = (
        "<think>\n\n</think>\n\n"
        "请补充加工工艺参数：\n"
        + "进给" * 50
    )
    cleaned = hygiene(raw)
    assert "<think>" not in cleaned
    assert cleaned == "请补充加工工艺参数：\n进给"


def test_periodic_line_tail_collapse():
    raw = (
        "G代码程序：\n"
        "G00 X0 Y0\n"
        + "G01 Z-5 F100\nG00 Z10\n" * 5
    )
    cleaned = hygiene(raw)
    assert cleaned.count("G01 Z-5 F100") == 1


def test_strict_json_strips_fences_and_preamble():
    prompt = "需要通过 SolidWorks 创建基础底板零件。请直接输出标准工具调用 JSON。"
    response = (
        "收到设计需求，为您封装如下工具调用：\n"
        "```json\n"
        "{\n"
        '  "tool": "cadcam_solidworks_model",\n'
        '  "parameters": {\n'
        '    "length": 120,\n'
        '    "width": 80,\n'
        '    "thickness": 15\n'
        "  }\n"
        "}\n"
        "```\n"
        "模型已建立完毕，请在 SolidWorks 中查看。"
    )
    compiled = compile_output(prompt, response)
    obj = json.loads(compiled)
    assert obj["tool"] == "cadcam_solidworks_model"
    assert obj["parameters"] == {"length": 120, "width": 80, "thickness": 15}


def test_single_key_container_unwrapped():
    prompt = "输出一个 JSON 对象，键只能是 part_name 和 material。"
    response = '{"result": {"part_name": "底座法兰", "material": "6061-T6"}}'
    compiled = compile_output(prompt, response)
    assert json.loads(compiled) == {"part_name": "底座法兰", "material": "6061-T6"}


def test_native_tool_call_never_rewritten():
    prompt = "输出 JSON：tool=cadcam_preflight，action=diagnose。"
    response = '{"tool": "cadcam_preflight", "arguments": {"action": "diagnose"}}'
    compiled = compile_output(prompt, response)
    assert compiled == response


def test_explicit_equation_arithmetic_slip_fixed():
    response = "根据公式计算主轴转速：\nn = 1000 * 120 / (3.14159 * 25) ≈ 1837 r/min。"
    fixed = fix_explicit_equation(response)
    assert "≈ 1528 r/min" in fixed


def test_end_to_end_answer_pipeline_on_noisy_moe_output():
    prompt = "车削直径 D=25 mm，Vc=120 m/min。请计算主轴转速 n（单位 r/min）。"
    noisy_text = (
        "<think>\n\n</think>\n\n"
        "🧠 Virtu-MoE 工业超级智能体正在调用工业制造专家：\n"
        "- 计算转速与进给关系。\n\n"
        "[PAD151667]根据转速公式计算：\n"
        "n = 1000 * 120 / (3.14159 * 25) ≈ 1837 r/min。\n\n"
        + "推荐转速" * 20
    )
    res = clean_served_answer(prompt, noisy_text)
    assert res.think_removed
    assert "正在调用" not in res.text
    assert "[PAD" not in res.text
    assert "≈ 1528 r/min" in res.text
    assert "推荐转速推荐转速" not in res.text


def test_modelfile_and_serving_discipline_gate():
    """Verify that Modelfile configurations adhere to 13.63B safety & formatting bounds."""
    from pathlib import Path
    mf_path = Path("checkpoints/Modelfile.virtu_moe_14b")
    assert mf_path.exists(), "checkpoints/Modelfile.virtu_moe_14b must exist"
    content = mf_path.read_text(encoding="utf-8")

    # Gate 1: stop <|im_start|> must NOT be present (causes premature empty tool-call truncation)
    assert 'stop "<|im_start|>"' not in content
    assert "stop <|im_start|>" not in content

    # Gate 2: stop <|im_end|> MUST be present
    assert "<|im_end|>" in content

    # Gate 3: Cosplay terms claiming internal networks must NOT be in system prompt
    assert "你的内部包含" not in content
    assert "两大专精网络：" not in content
    assert "材料力学理论与逆向推理专家正在校核" not in content

    # Gate 4: repeat_penalty must be >= 1.1 to prevent token repetition loops
    assert "PARAMETER repeat_penalty 1.15" in content

    # Gate 5: num_ctx must not exceed 4096 on safe budget
    assert "PARAMETER num_ctx 4096" in content

