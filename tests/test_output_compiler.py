import json

from virtu_omni.serving.answer_pipeline import clean_served_answer
from virtu_omni.serving.output_compiler import (
    compile_output,
    markdown_table_to_csv,
    split_one_line_list,
    strip_output_label,
    unwrap_tool_envelope,
)


def test_csv_conversion_preserves_values():
    text = "| TOOL | D_mm |\n| T1 | 12 |\n| T2 | 8 |"
    assert markdown_table_to_csv(text) == "TOOL,D_mm\nT1,12\nT2,8"


def test_csv_conversion_groups_a_one_line_table():
    prompt = "| TOOL | D_mm |\n| T1 | 12 |\n"
    text = "| TOOL | D_mm | T1 | 12 | T2 | 8 |"
    assert markdown_table_to_csv(text, 2) == "TOOL,D_mm\nT1,12\nT2,8"


def test_compile_csv_only_when_requested():
    text = "| A | B |\n| 1 | 2 |"
    assert compile_output("把表改成 CSV", text) == "A,B\n1,2"
    assert compile_output("看看这个表", text) == text


def test_structured_json_is_not_text_rewritten():
    prompt = "输出 JSON 对象，键为 a 和 b。只输出 JSON。"
    text = '{"a": 1, "b": 2}'
    assert compile_output(prompt, text) == text


def test_tool_request_is_never_unwrapped():
    prompt = "输出 JSON：tool=cadcam_x，action=run。"
    text = '{"tool": "cadcam_x", "arguments": {"action": "run"}}'
    assert unwrap_tool_envelope(prompt, text) == text
    assert compile_output(prompt, text) == text


def test_plain_json_request_unwraps_arguments():
    prompt = "输出一个 JSON 对象，键只能是 part_name 和 material。"
    text = '{"tool": "cadcam_part", "arguments": {"part_name": "法兰盘", "material": "45 钢"}}'
    out = compile_output(prompt, text)
    assert json.loads(out) == {"part_name": "法兰盘", "material": "45 钢"}


def test_label_is_stripped_only_for_output_only_string_requests():
    prompt = "把工件号全部大写，只输出改完后的字符串本身，不加说明。"
    assert strip_output_label(prompt, "工件号是：W026-FLANGE") == "W026-FLANGE"
    assert strip_output_label("解释一下这个工件号", "工件号是：W026-FLANGE") == "工件号是：W026-FLANGE"


def test_label_is_not_stripped_from_json():
    prompt = "只输出这个 JSON 对象。"
    text = '{"tool": "x", "coating": "TiAlN"}'
    assert strip_output_label(prompt, text) == text


def test_one_line_list_splits_when_count_matches():
    prompt = "按顺序逐行展开 4 个缩写，共 4 行。"
    text = "CNC: 数控 CAM: 辅助制造 CAD: 辅助设计 MRR: 去除率"
    out = split_one_line_list(prompt, text)
    assert out.count("\n") == 3


def test_one_line_list_is_left_alone_when_count_differs():
    prompt = "输出恰好 5 行。"
    text = "a b c"
    assert split_one_line_list(prompt, text) == text


def test_pipeline_removes_empty_think_and_loop_then_compiles():
    prompt = "把下面这张表改成 CSV，输出 2 行。\n| A | B |\n| 1 | 2 |"
    text = "<think>\n\n</think>\n\n| A | B | | 1 | 2 |\n" + "| A | B | | 1 | 2 |\n" * 6
    result = clean_served_answer(prompt, text)
    assert result.think_removed
    assert result.loop_trimmed
    assert result.compiler_applied
    assert result.text == "A,B\n1,2"


def test_pipeline_is_identity_for_a_normal_answer():
    prompt = "解释一下顺铣。"
    text = "<think></think>顺铣是刀具旋转方向与进给方向相同的铣削方式。"
    result = clean_served_answer(prompt, text)
    assert result.text == "顺铣是刀具旋转方向与进给方向相同的铣削方式。"
    assert result.think_removed
    assert not result.loop_trimmed
    assert not result.compiler_applied


def test_plain_json_request_unwraps_result_container():
    prompt = "输出一个 JSON 对象，键只能是 part_name 和 material。"
    text = '{"result": {"part_name": "法兰盘", "material": "45 钢"}}'
    out = compile_output(prompt, text)
    assert json.loads(out) == {"part_name": "法兰盘", "material": "45 钢"}


def test_compile_strips_markdown_fence_and_preamble_for_pure_json():
    prompt = "需要通过 SolidWorks 创建底板。请直接输出标准工具调用 JSON。"
    text = '收到需求，为您生成如下调用：\n```json\n{"tool": "cadcam_solidworks_model", "parameters": {"length": 120}}\n```\n模型已建立。'
    out = compile_output(prompt, text)
    assert json.loads(out) == {"tool": "cadcam_solidworks_model", "parameters": {"length": 120}}


def test_clean_served_answer_fixes_explicit_equation_slip():
    prompt = "计算切削转速。"
    text = "根据公式计算：\nn = 1000 * 120 / (3.14159 * 25) ≈ 1837 r/min"
    result = clean_served_answer(prompt, text)
    assert "≈ 1528 r/min" in result.text


