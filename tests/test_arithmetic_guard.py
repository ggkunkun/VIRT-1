"""Regression tests for the deterministic arithmetic guard (n/Vf/MRR/T chain)."""
import json
import os
import re

import pytest

from virtu_real_backend import (
    _numeric_problems,
    _spindle_speed_problem,
    _verify_arithmetic_response,
)

PROMPT = "工件直径 D=16 mm，切削速度 Vc=120 m/min，求主轴转速 n。"
MESSAGES = [{"role": "user", "content": PROMPT}]
CASE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data", "benchmark", "virtu_eval_v1")
_ANSWER_NUM_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")


def msgs(text):
    return [{"role": "user", "content": text}]


def test_spindle_problem_extracted():
    vc, d, n = _spindle_speed_problem(MESSAGES)
    assert (vc, d) == (120.0, 16.0)
    assert n == pytest.approx(2387.32, abs=0.05)


@pytest.mark.parametrize("wrong", ["1000", "n = 241.67 r/min", "主轴转速约为 382 r/min（按经验估算）"])
def test_wrong_bare_answer_is_replaced(wrong):
    out = _verify_arithmetic_response(wrong, MESSAGES)
    assert "2387.3" in out
    assert "1000·Vc/(π·D)" in out


def test_correct_answer_is_untouched():
    text = "n = 2387.3 r/min"
    assert _verify_arithmetic_response(text, MESSAGES) == text


def test_long_answer_gets_authoritative_correction():
    text = "主轴转速的计算需要先确认刀具直径和切削速度。" * 5 + " 结果约为 1000 r/min。"
    out = _verify_arithmetic_response(text, MESSAGES)
    assert "2387.3" in out
    assert "[确定性核算]" in out


def test_explicit_equation_still_corrected():
    out = _verify_arithmetic_response("n=1000*120/(3.1416*16)=238.7")
    assert "2387" in out


def test_unrelated_prompt_untouched():
    text = "答案是 42。"
    assert _verify_arithmetic_response(text, [{"role": "user", "content": "今天天气如何？"}]) == text


def test_no_vc_or_d_returns_none():
    assert _spindle_speed_problem([{"role": "user", "content": "直径 16 mm，求转速"}]) is None


def test_diameter_symbol_and_feed_chain():
    """Ø is the diameter symbol used on real machining cards, and Vf chains off n."""
    problems = _numeric_problems(
        msgs("铣削 Ø10 mm、3 齿立铣刀，Vc=200 m/min，每齿进给 f=0.15 mm/齿。"
             "按 n=1000*Vc/(π*D) 算主轴转速，再算 Vf=f*z*n。"))
    names = [name for name, _, _ in problems]
    assert names == ["主轴转速", "进给速度"]
    assert problems[0][2] == pytest.approx(6366.1977, abs=0.01)
    assert problems[1][2] == pytest.approx(2864.789, abs=0.01)


def test_english_prompt_is_covered():
    problems = _numeric_problems(
        msgs("A face mill has a diameter of 80 mm and 6 teeth. The handbook cutting "
             "speed is Vc = 180 m/min and the feed per tooth is 0.2 mm. Using "
             "n = 1000*Vc/(pi*D) and Vf = f*z*n, report the spindle speed first."))
    assert [name for name, _, _ in problems] == ["主轴转速", "进给速度"]
    assert problems[1][2] == pytest.approx(859.437, abs=0.01)


def test_formula_terms_are_not_read_as_assignments():
    """The 「保留 1 位小数」 must not become feed-per-tooth via the bare "f" in "f*z*n"."""
    problems = _numeric_problems(
        msgs("刀盘直径 80，6 个齿，手册给的切削速度 180，每齿 0.2。"
             "公式 n=1000*Vc/(π*D)、Vf=f*z*n，结果保留 1 位小数，按 n 再 Vf 的顺序给数。"))
    feed = [v for name, _, v in problems if name == "进给速度"]
    assert feed and abs(feed[0] - 859.437) < 0.01


def test_mrr_and_time_formulas():
    mrr = _numeric_problems(
        msgs("已知材料去除率公式 MRR=ap*ae*Vf。背吃刀量 ap=2 mm，铣削宽度 ae=5 mm，"
             "进给速度 Vf=800 mm/min。只计算 MRR。"))
    assert [name for name, _, _ in mrr] == ["材料去除率"]
    assert mrr[0][2] == pytest.approx(8000.0, abs=0.01)

    duration = _numeric_problems(
        msgs("一条直线铣削行程长度 L=720 mm，进给速度 Vf=240 mm/min。"
             "按公式 T=L/Vf 计算走刀时间，单位 min。"))
    assert [name for name, _, _ in duration] == ["走刀时间"]
    assert duration[0][2] == pytest.approx(3.0, abs=0.001)


@pytest.mark.parametrize("prompt", [
    # Table/multiplier rules transform Vc: recomputing from the un-transformed entry
    # would publish 3972.4 r/min as authoritative over the correct 2546.5.
    "档位表：档1 基准 Vc=200 m/min，硬度每提高一档乘 0.8。刀具 Ø16 mm、3 齿。"
    "按 n=1000*Vc/(π*D) 求转速。",
    "工艺规则卡：档 R3 Vc=150 m/min；加工不锈钢时表中 Vc 一律乘系数 0.65。"
    "刀具 Ø20 mm、3 齿，求主轴转速。",
])
def test_transformed_inputs_are_vetoed(prompt):
    assert _numeric_problems(msgs(prompt)) == []


def test_ambiguous_input_is_vetoed():
    """Two different diameters means we cannot tell which one the question is about."""
    prompt = "先用直径 80 mm 的铣刀粗铣，再用直径 60 mm 精铣，切削速度 Vc=120 m/min，求主轴转速。"
    assert _spindle_speed_problem(msgs(prompt)) is None
    assert _numeric_problems(msgs(prompt)) == []


def test_missing_input_never_invents_a_formula():
    assert _numeric_problems(
        msgs("已知切削速度 Vc=120 m/min，直接给出这把铣刀的主轴转速 n 并写进程序。")) == []
    assert _numeric_problems(msgs("今天天气如何？")) == []


def test_answer_within_rounding_tolerance_is_left_alone():
    """Gold rounds n to an integer before Vf; the guard must not fight that."""
    prompt = ("铣削 Ø10 mm、3 齿立铣刀，Vc=200 m/min，每齿进给 f=0.15 mm/齿。"
              "先算主轴转速并四舍五入到整数，再代入 Vf=f*z*n。")
    text = "n = 6366 r/min；Vf = 2864.7 mm/min"
    assert _verify_arithmetic_response(text, msgs(prompt)) == text


def test_every_published_value_matches_the_case_gold():
    """Whole-corpus guard audit: a formula the guard would append must agree with the
    gold's own numbers. This is the property that makes wider coverage safe."""
    fired = published = 0
    disagreements = []
    for fname in sorted(os.listdir(CASE_DIR)):
        if not fname.endswith(".jsonl"):
            continue
        with open(os.path.join(CASE_DIR, fname), encoding="utf-8") as handle:
            for line in handle:
                case = json.loads(line)
                problems = _numeric_problems(msgs(case.get("prompt", "")))
                if not problems:
                    continue
                fired += 1
                targets = [float(c["value"]) for c in (case.get("criteria") or [])
                           if c.get("type") == "numeric_near" and c.get("value") is not None]
                gold = case.get("gold")
                answer = gold.get("answer", "") if isinstance(gold, dict) else str(gold or "")
                targets += [float(raw.replace(",", ""))
                            for raw in _ANSWER_NUM_RE.findall(answer)]
                for name, _, value in problems:
                    published += 1
                    if not any(abs(value - t) <= max(0.02 * abs(t), 0.05) for t in targets):
                        disagreements.append(f"{case['id']} [{name}] {value:.4f}")
    assert fired >= 10, f"guard coverage collapsed to {fired} cases"
    assert published >= 20, f"guard only published {published} values"
    assert disagreements == []


def test_derivation_recalculation_overwrites_hallucination():
    """Live case test: model wrote derivation (120)*(80)*(30-25) but hallucinates 6000."""
    prompt = "【场景】铣削去除材料：毛坯 120x80x30 mm，加工后工件 120x80x25 mm，钢密度 7.85 g/cm3。"
    raw_response = json.dumps({
        "world_state": {"material_removed_mm3": 6000, "delta_volume_mm3": -6000, "resulting_mass_g": 945},
        "derivation": {
            "material_removed_mm3": "(120)*(80)*(30-25)",
            "delta_volume_mm3": "-((120)*(80)*(30-25))",
            "resulting_mass_g": "(120)*(80)*(30)*(0.00785)-((120)*(80)*(30-25))*(0.00785)"
        }
    })
    corrected_text = _verify_arithmetic_response(raw_response, msgs(prompt))
    parsed = json.loads(corrected_text)
    ws = parsed["world_state"]
    assert ws["material_removed_mm3"] == 48000.0
    assert ws["delta_volume_mm3"] == -48000.0
    assert abs(ws["resulting_mass_g"] - 1884.0) < 0.1
    assert ws["volume_conservation"] == "pass_cut_negative"


def test_fea_safety_factor_prevents_fake_pass():
    """Safety gate test: FOS=1.17 < 1.5 must NEVER pass as green."""
    prompt = "黄铜H62构件，屈服强度 Sy=200 MPa，FEA 算得峰值 von Mises 应力 σ_vm=171.3 MPa。预测安全系数并判定 FOS≥1.5 是否通过。"
    raw_response = json.dumps({
        "world_state": {"safety_factor": 1.768, "status": "PASS (FOS >= 1.5)"}
    })
    corrected_text = _verify_arithmetic_response(raw_response, msgs(prompt))
    parsed = json.loads(corrected_text)
    ws = parsed["world_state"]
    assert ws["fos_gate"] == "FOS<1.5_FAIL"
    assert "FAIL" in ws.get("status", "")
    assert abs(ws["safety_factor"] - (200.0 / 171.3)) < 0.05


def _published(prompt):
    return {name: (expr, value) for name, expr, value in _numeric_problems(msgs(prompt))}


def test_mmc_bonus_is_capped_at_the_size_tolerance():
    """Reverse probe: an over-size hole earns 0.030 bonus, not 0.035, and the 0.135
    answer the MMC trap invites must never be published."""
    prompt = ("图样（单位 mm）：孔 Ø20 上偏差 +0.030、下偏差 0；位置度公差 Ø0.10 带最大实体要求"
              "（符号 M 圈）。三坐标实测孔径 Ø20.035、实测位置度 Ø0.120。求按最大实体要求可获得的"
              "位置度补偿量、此时允许的位置度公差。")
    published = _published(prompt)
    assert published["允许位置度公差"][1] == pytest.approx(0.130, abs=1e-9)
    assert published["尺寸超差"][1] == pytest.approx(0.005, abs=1e-9)
    assert "0.135" not in " ".join(expr for expr, _ in published.values())


def test_scallop_uses_the_formula_the_prompt_states():
    """Exact h=R-sqrt(R²-(s/2)²) must not be replaced by the small-angle s²/(8R)."""
    exact = _published("球头铣刀半径 R=5 mm，行距 s=6 mm。残留高度公式 h=R-sqrt(R²-(s/2)²)。")
    assert exact["残留高度"][1] == pytest.approx(1.000, abs=1e-9)
    approx = _published("用 R6 球头立铣刀加工曲面，行距取 3 mm，按近似公式 h 约等于 s^2/(8R) 估算残留高度。")
    assert approx["残留高度"][1] == pytest.approx(0.1875, abs=1e-9)


def test_tolerance_stack_ignores_the_drawing_requirement():
    """The '图纸要求 28±0.30' is the target, not a ring: worst case stays 0.350."""
    prompt = ("四层垫片叠装：t1=10±0.15，t2=8±0.05，t3=6±0.05，t4=4±0.10。"
              "总厚的图纸要求是 28±0.30 mm。用极值法与 RSS 统计法求合成公差的单边值。")
    published = _published(prompt)
    assert published["极值法单边公差"][1] == pytest.approx(0.350, abs=1e-9)
    assert published["RSS单边公差"][1] == pytest.approx(0.194, abs=1e-3)


def test_incomplete_dimension_chain_is_refused():
    """A ring without a tolerance must veto the whole stack -- never fabricate 0.3."""
    prompt = ("一维尺寸链：L0=L1-L2-L3。已知 L1=40±0.10、L2=25±0.05，L3 只标注了名义尺寸 12 mm "
              "而没有标注公差。要求给出 L0 的公差带宽度。")
    assert _numeric_problems(msgs(prompt)) == []


def test_gcode_modal_final_position_follows_g90_g91():
    prompt = ("FANUC 程序片段（单位 mm）：N10 G90 X100.0 Y50.0；N20 G91 X10.0 Y-5.0；"
              "N30 G90 X80.0 Y60.0；N40 G91 X5.0；N50 G91 Y-10.0。G90 为绝对编程、"
              "G91 为增量编程且模态有效。求执行完 N50 时刀具的绝对坐标。")
    published = _published(prompt)
    assert published["终点X"][1] == pytest.approx(85.0, abs=1e-9)
    assert published["终点Y"][1] == pytest.approx(50.0, abs=1e-9)


def test_rss_plain_list_and_square_sum():
    prompt = "尺寸链组成环公差（单边值，mm）：0.20、0.10、0.05。按统计法 RSS 求合成单边公差。"
    published = _published(prompt)
    assert published["根号内平方和"][1] == pytest.approx(0.0525, abs=1e-9)
    assert published["RSS单边公差"][1] == pytest.approx(0.229, abs=1e-3)


def test_radius_table_rounds_up_to_discrete_values():
    prompt = ("标准圆角半径表（只允许下列离散值 2、3、5、8 mm）：把请求半径向上圆整到表内最小的"
              "可选值。按「请求 → 结果（Øxx mm）」每行一个输出：R1.2、R2.5。")
    published = _published(prompt)
    assert published["第一直径"][1] == pytest.approx(4.0, abs=1e-9)
    assert published["第二直径"][1] == pytest.approx(6.0, abs=1e-9)


def test_g41_offset_corner_is_intersection_not_average():
    prompt = ("编程轮廓（单位 mm）：从 (0,0) 沿 G01 走到 (20,0)，再沿 G01 走到 (20,10)。"
              "使用 G41 左刀补，补偿号 D01 存储值为 4.0。求两段偏置直线的交点坐标。")
    published = _published(prompt)
    assert published["拐角X"][1] == pytest.approx(16.0, abs=1e-9)
    assert published["拐角Y"][1] == pytest.approx(4.0, abs=1e-9)


def test_slot_width_uses_stored_minus_actual_tool_radius():
    prompt = ("铣一直槽：编程槽宽 20 mm，启用刀具半径补偿，补偿号 D02 存储值为 5.0，"
              "而实际装夹的立铣刀直径为 8.0 mm。求加工出的实际槽宽。")
    published = _published(prompt)
    assert published["实际槽宽"][1] == pytest.approx(18.0, abs=1e-9)


def test_shaft_mmc_bonus_and_code_table_count():
    shaft = _published("某轴标注 phi20f7 位置度采用最大实体要求，位置度给定公差 0.1 mm。"
                       "若该轴实际测得直径为 19.8 mm，求允许的位置度公差。")
    assert shaft["允许位置度公差"][1] == pytest.approx(0.3, abs=1e-9)
    table = _published("代码对照表：G91=绝对坐标、G90=增量坐标、G72=快速定位、G0=直线进给、"
                       "G1=圆弧插补、G38=取消刀补、M99=主轴停止。统计本表 G 代码共有几个。")
    assert table["本表G代码数"][1] == pytest.approx(6.0, abs=1e-9)


def test_hardness_rule_card_scales_vc_by_grade():
    """HB240 falls in 档3, so Vc = 200×0.8² = 128 -- not 档2's 160."""
    prompt = ("本车间切削速度规则（唯一口径）：档1 HB150-180=档1，HB181-220=档2，"
              "HB221-260=档3，HB261-300=档4；档1 基准 Vc=200 m/min，硬度每提高一档，"
              "Vc 取上一档的 80%（乘 0.8）。现用 Ø16 mm、3 齿立铣刀、每齿进给 0.15 mm 加工，"
              "实测硬度 HB240，求 Vc、n、Vf。")
    published = _published(prompt)
    assert published["切削速度"][1] == pytest.approx(128.0, abs=1e-9)
    assert published["主轴转速"][1] == pytest.approx(2546.5, abs=0.5)
    assert published["进给速度"][1] == pytest.approx(1145.9, abs=1.0)


def test_stainless_rule_card_scales_vc_and_derives_fz():
    prompt = ("工艺规则卡（本题唯一口径）：档 R3 Vc=150 m/min；加工不锈钢时表中 Vc 一律"
              "乘系数 0.65；每齿进给按 f=D/100 mm/齿 取值。现用 Ø20 mm、3 齿硬质合金立铣刀"
              "加工不锈钢，取 R3 档，按 n=1000*Vc/(π*D)、Vf=f*z*n 求 Vc、n、f、Vf。")
    published = _published(prompt)
    assert published["切削速度"][1] == pytest.approx(97.5, abs=1e-9)
    assert published["每齿进给"][1] == pytest.approx(0.2, abs=1e-9)
    assert published["主轴转速"][1] == pytest.approx(1551.7, abs=0.5)
    assert published["进给速度"][1] == pytest.approx(931.0, abs=1.0)


def test_cutting_speed_problem_extracted_and_verified():
    prompt = "工件直径D=50mm，主轴转速n=600r/min，求切削速度vc"
    published = _published(prompt)
    assert "切削速度" in published
    assert published["切削速度"][1] == pytest.approx(94.25, abs=0.05)

    # Hallucinated answer (e.g. inverted formula Vc = 1000/pi * n = 19098) is corrected
    hallucinated = "根据切削速度公式：Vc = (1000/pi)*600 ≈ 19098.593 mm/min"
    out = _verify_arithmetic_response(hallucinated, [{"role": "user", "content": prompt}])
    assert "94.25" in out
    assert "[确定性核算]" in out or "Vc = π·D·n/1000" in out

    # Correct answer is preserved
    correct = "切削速度 Vc = 94.25 m/min"
    assert "94.25" in _verify_arithmetic_response(correct, [{"role": "user", "content": prompt}])


def test_verifier_strips_empty_think_tags():
    prompt = "计算切削速度：工件直径D=50mm，主轴转速n=600r/min，求切削速度vc"
    text_with_think = "<think>\n\n</think>\n\n切削速度 Vc = 94.25 m/min"
    out = _verify_arithmetic_response(text_with_think, [{"role": "user", "content": prompt}])
    assert "<think>" not in out
    assert "</think>" not in out
    assert "94.25" in out

