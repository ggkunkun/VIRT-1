from virtu_omni.serving.output_hygiene import (
    collapse_exact_halves,
    collapse_periodic_tail,
    collapse_repeated_lines,
    collapse_token_runs,
    hygiene,
    split_think,
    strip_cosplay,
    strip_special_tokens,
    strip_think,
)


def test_split_think_returns_body_and_visible():
    body, visible = split_think("<think>先算 n</think>最终 n=1.0")
    assert body == "先算 n"
    assert visible == "最终 n=1.0"


def test_split_think_tolerates_unclosed_tag():
    body, visible = split_think("<think>只写了一半")
    assert body == "只写了一半"
    assert visible == ""


def test_strip_think_falls_back_to_thinking_when_content_empty():
    assert strip_think("<think>{\"tool\": \"x\"}</think>") == "{\"tool\": \"x\"}"


def test_hygiene_removes_only_the_empty_think_block():
    answer = "无法计算：缺少刀具直径 D，请补充。"
    assert hygiene(f"<think>\n\n</think>\n\n{answer}") == answer


def test_hygiene_preserves_multi_line_layout():
    text = "<think>\n\n</think>\n\n第一行\n第二行\n第三行"
    assert hygiene(text) == "第一行\n第二行\n第三行"


def test_hygiene_collapses_a_long_repeated_line_run():
    text = "结论：缺参数\n" + "结论：缺参数\n" * 12
    assert hygiene(text).count("结论：缺参数") == 1


def test_hygiene_keeps_two_legitimate_identical_lines():
    text = "G1 X10\nG1 X10\nG0 Z5"
    assert hygiene(text) == text


def test_hygiene_collapses_a_token_loop():
    text = "请补充：" + "进给" * 80
    cleaned = hygiene(text)
    assert cleaned == "请补充：进给"


def test_hygiene_collapses_a_periodic_block_tail():
    block = "X=1\nY=2\n"
    text = "答案\n" + block * 5
    cleaned = hygiene(text)
    assert cleaned.count("X=1") == 1
    assert cleaned.startswith("答案")


def test_hygiene_collapses_an_exact_duplicated_answer():
    answer = "最终结果：n=2387.3 r/min，Vf=573.0 mm/min，保留一位小数。"
    text = answer + answer
    assert collapse_exact_halves(text) == answer
    assert hygiene(text) == answer


def test_repeated_lines_threshold_does_not_touch_three():
    text = "A\nA\nA\nB"
    assert collapse_repeated_lines(text) == text


def test_token_collapse_does_not_touch_a_normal_number_list():
    text = "1, 2, 3, 4, 5"
    assert collapse_token_runs(text) == text


def test_strip_special_tokens():
    text = "[PAD151667]这是一段工程回答[PAD151668] <｜begin▁of▁thinking｜>中间<｜end▁of▁thinking｜></tool_call>"
    assert strip_special_tokens(text) == "这是一段工程回答 中间"


def test_strip_cosplay_removes_internal_expert_monologue():
    text = (
        "🧠 Virtu-MoE 工业超级智能体正在调用工业制造与智能体工具专家：\n"
        "- 调用 Siemens NX API 计算切削速度与主轴转速关系。\n"
        "- 调用 CIMCO 软件库验证标准公差与表面粗糙度参数。\n\n"
        "🔧 材料力学理论与逆向推理专家正在校核：\n"
        "- 45 钢的弹性模量 E=210 GPa，泊松比 μ=0.3。\n\n"
        "根据主轴转速公式 n = 1000*Vc/(pi*D)，转速为 1528 r/min。"
    )
    cleaned = strip_cosplay(text)
    assert "正在调用" not in cleaned
    assert "正在校核" not in cleaned
    assert cleaned == "根据主轴转速公式 n = 1000*Vc/(pi*D)，转速为 1528 r/min。"


def test_hygiene_removes_cosplay_and_think_together():
    text = (
        "<think>\n\n</think>\n\n"
        "🧠 Virtu-MoE 正在调用工业制造专家：\n"
        "- 计算转速。\n\n"
        "最终转速：n=1528 r/min"
    )
    assert hygiene(text) == "最终转速：n=1528 r/min"

