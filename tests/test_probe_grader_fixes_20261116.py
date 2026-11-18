#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""反证测试：探针判分器 2026-11-16 测量缺陷修复（probes-2026-11-16-v3）。

背景（reports/V4_LOCAL_REPAIR_READING_2026-11-16.md 与 FULL_STRENGTHEN_2026-11-16.md）：
  F1  Lamé 负号正则尾部 `\\b`：数字与单位字母之间无词界，`-20MPa`/`−20MPa`（无空格）
      被误判 missing_negative_sigma_r_-20 —— ASCII 与 U+2212 同杀，属字符集/词界缺陷。
  F2  sw_coordinate / autodiff 的失败路径只带 segment 不带 sample ⇒ runner 回执
      sample 为空串，19:06 的失败无法自证（「空样本悬案」的测量侧根因）。
  F3  runner 的 full_response 实为 160 字片段；判分器现在输出完整可见文本。
  F4  空响应被归类为 missing_plane / missing_sigma（模型缺陷），应单列 empty_response。

每条新放行的表述都配对应坏样本仍判红（AGENTS.md §8.4）。
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (ROOT, os.path.join(ROOT, "cloud_train_pack")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import deploy_trained_adapter as D  # noqa: E402

GOOD_HOOP = "σ_θ = 33.33 MPa。"


# ---------------------------------------------------------------------------
# F1 负号 + 单位紧邻（无空格）必须放行；错误数值/符号必须仍红
# ---------------------------------------------------------------------------
def test_lame_ascii_minus_adjacent_unit_passes():
    v = D.evaluate_lame_stress_probe(GOOD_HOOP + " σ_r = -20MPa")
    assert v["passed"] is True, v


def test_lame_unicode_minus_adjacent_unit_passes():
    v = D.evaluate_lame_stress_probe(GOOD_HOOP + " σ_r≈\u221220MPa。")
    assert v["passed"] is True, v


def test_lame_fullwidth_minus_adjacent_unit_passes():
    v = D.evaluate_lame_stress_probe(GOOD_HOOP + " σ_r≈\uff0d20MPa。")
    assert v["passed"] is True, v


def test_lame_sentence_final_minus_twenty_still_passes():
    """句尾 `-20.` 的点不是小数部分，不得被新前瞻误杀。"""
    v = D.evaluate_lame_stress_probe(GOOD_HOOP + " 径向应力为 -20.")
    assert v["passed"] is True, v


def test_lame_minus_two_hundred_still_fails():
    """-200 不得借 `20` 前缀混过（量纲错 10 倍）。"""
    v = D.evaluate_lame_stress_probe(GOOD_HOOP + " σ_r = -200MPa")
    assert v["passed"] is False
    assert "missing_negative_sigma_r_-20" in v["reason"], v


def test_lame_minus_twenty_point_five_still_fails():
    v = D.evaluate_lame_stress_probe(GOOD_HOOP + " σ_r = -20.5 MPa")
    assert v["passed"] is False
    assert "missing_negative_sigma_r_-20" in v["reason"], v


def test_lame_positive_twenty_still_fails():
    """径向应力是压应力，+20 符号错必须红。"""
    v = D.evaluate_lame_stress_probe(GOOD_HOOP + " σ_r = +20 MPa")
    assert v["passed"] is False
    assert "missing_negative_sigma_r_-20" in v["reason"], v


def test_lame_missing_radial_still_fails():
    v = D.evaluate_lame_stress_probe(GOOD_HOOP + " 径向应力略。")
    assert v["passed"] is False
    assert "missing_negative_sigma_r_-20" in v["reason"], v


# ---------------------------------------------------------------------------
# F4 空响应单列 empty_response，不得冒充模型缺陷
# ---------------------------------------------------------------------------
def test_sw_empty_response_is_not_model_defect():
    v = D.evaluate_sw_coordinate_probe("")
    assert v["passed"] is False
    assert v["reason"] == "empty_response", v


def test_lame_empty_response_is_not_model_defect():
    v = D.evaluate_lame_stress_probe("")
    assert v["passed"] is False
    assert v["reason"] == "empty_response", v


# ---------------------------------------------------------------------------
# F2 失败回执必须带非空 sample + full_response（失败可自证）
# ---------------------------------------------------------------------------
def test_sw_missing_normal_failure_carries_evidence():
    v = D.evaluate_sw_coordinate_probe("Front plane 是默认基准面之一，Top 与 Right 也是。")
    assert v["passed"] is False
    assert v["reason"].startswith("missing_normal:"), v
    assert v.get("sample"), v
    assert v.get("full_response"), v


def test_sw_missing_plane_failure_carries_evidence():
    v = D.evaluate_sw_coordinate_probe("只有 Top plane 法向 +Y 与 Right plane 法向 +X。")
    assert v["passed"] is False
    assert v["reason"] == "missing_plane:front", v
    assert v.get("full_response"), v


def test_sw_wrong_normal_still_fails_with_evidence():
    v = D.evaluate_sw_coordinate_probe(
        "Front plane 法向为 +Z（也有写作 +Y 的情况）；Top plane 法向 +Y；Right plane 法向 +X。"
    )
    assert v["passed"] is False
    assert v["reason"] == "wrong_normal_axis:front", v
    assert v.get("sample"), v


def test_autodiff_swapped_meaning_failure_carries_evidence():
    bad = (
        "红色：代表过切，必须停机。\n"
        "蓝色：代表残料（合格）。\n"
        "绿色：代表公差内。\n"
    )
    v = D.evaluate_vericut_autodiff_probe(bad)
    assert v["passed"] is False
    assert v["reason"] == "swapped_meaning:blue", v
    assert v.get("sample"), v
    assert v.get("full_response"), v


# ---------------------------------------------------------------------------
# F3 full_response 必须是完整可见文本，不是 160/180 字片段
# ---------------------------------------------------------------------------
def test_full_response_is_not_truncated_to_sample():
    pad = "说明文字。" * 60  # 远超 160 字
    text = (
        "Front plane 法向 +Z。\nTop plane 法向 +Y。\nRight plane 法向 +X。\n" + pad
    )
    v = D.evaluate_sw_coordinate_probe(text)
    assert v["passed"] is True, v
    assert len(v["sample"]) <= 160
    assert v["full_response"] == text.strip()
    assert len(v["full_response"]) > 160


def test_lame_full_response_present_on_failure():
    bad = GOOD_HOOP + " σ_r = -200MPa"
    v = D.evaluate_lame_stress_probe(bad)
    assert v["passed"] is False
    assert v.get("full_response") == bad


def test_fanuc_full_response_present():
    bad = "G71 U1.5 R0.5\nG71 P1 Q2 U0.4 W0.02\nN1 G0 X38.0\nN2 G0 Z-25.0\nM30"
    v = D.evaluate_fanuc_g71_safety_probe(bad)
    assert v["passed"] is False
    assert "unsafe_G00_negative_Z_plunge" in v["reason"], v
    assert v.get("full_response") == bad


# ---------------------------------------------------------------------------
# 版本身份：判分器改动必须体现在 measurement_version（§8.2）
# ---------------------------------------------------------------------------
def test_measurement_version_bumped():
    assert D.MEASUREMENT_VERSION != "probes-2026-11-15-v2"
    assert D.MEASUREMENT_VERSION.startswith("probes-2026-11-16"), D.MEASUREMENT_VERSION


# ---------------------------------------------------------------------------
# F5（probes-2026-11-16-v4）autodiff 锚点回退根因修复：
#   def_pat 只认半角括号，模型用全角（Red）+加粗 ** 时 def_matches=0；旧回退
#   matches[-1] 取末尾负面警示提及（严禁将红色误判为合格）作锚点，完整正确的
#   三色答案被误判 missing_meaning:red（v5-repair r1 实测假阴性）。
#   新回退取窗口内含正/负语义的首个出现。每条放行配坏样本仍红。
# ---------------------------------------------------------------------------
_GOOD_AUTODIFF_FULLWIDTH = (
    "在 VERICUT 9.6 的 Auto-Diff 偏差图中，不同颜色代表不同的加工偏差含义：\r\n\r\n"
    "- **红色（Red）**：表示 **过切（Gouge）**，刀具切除了超出零件设计边界的部分，"
    "属于严重加工错误，必须立即停机排查 NC 程序、刀路、刀具半径或余量设定并重新仿真修正后再跑刀。"
    "严禁将红色误判为合格或忽略；\r\n"
    "- **蓝色（Blue）**：表示 **残料/欠切（Excess material / Undercut）**，"
    "零件表面仍有未切到位的多余材料，需补半精加工或精加工刀路；\r\n"
    "- **绿色（Green）**：表示 **尺寸在公差内（In tolerance）**，合格。\r\n"
)


def test_autodiff_fullwidth_bold_with_caution_passes():
    """完整正确三色 + 全角括号加粗 + 末尾负面警示提及：不得被误判 missing_meaning:red。"""
    v = D.evaluate_vericut_autodiff_probe(_GOOD_AUTODIFF_FULLWIDTH)
    assert v["passed"] is True, v


def test_autodiff_fullwidth_swapped_still_fails():
    bad = (
        "Auto-Diff 颜色含义：\r\n"
        "- **红色（Red）**：表示 **合格（In tolerance）**，无需处理。严禁将红色误判为过切；\r\n"
        "- **蓝色（Blue）**：表示 **过切（Gouge）**，必须停机排查刀路。\r\n"
        "- **绿色（Green）**：表示 **残料（Excess）**。\r\n"
    )
    v = D.evaluate_vericut_autodiff_probe(bad)
    assert v["passed"] is False, v
    assert v["reason"] in ("missing_meaning:red", "swapped_meaning:red"), v


def test_autodiff_incomplete_only_red_still_fails():
    bad = "- **红色（Red）**：表示 **过切（Gouge）**，必须立即停机排查刀路。\r\n"
    v = D.evaluate_vericut_autodiff_probe(bad)
    assert v["passed"] is False, v
    assert v["reason"] == "missing_color:blue", v


def test_autodiff_enumeration_only_still_fails():
    bad = "VERICUT Auto-Diff 偏差图用红色、蓝色、绿色三种颜色表示加工偏差。"
    v = D.evaluate_vericut_autodiff_probe(bad)
    assert v["passed"] is False, v
    assert v["reason"].startswith("missing_meaning:"), v


# ---------------------------------------------------------------------------
# F6（2026-11-16 E5）语义互换 vs 语义缺失：归因必须可区分
# ---------------------------------------------------------------------------
# 旧实现先查正语义，查不到就一律报 missing_meaning:<color>；于是「蓝色段写
# 「过切（Gouge）」」这种**语义互换**被误报成「意思没写」。两者都判红，但回执必须
# 说清模型到底犯了哪种错，否则无法定位问题（AGENTS.md §8.2）。
# 反证要求：①互换必须报 swapped；②否定句（不是过切）不得误报成 swapped；
#          ③真的没写意思仍是 missing；④正确答案不受影响。

_GOOD_THREE_COLOR = (
    "### ✅ **红色 (Red)**\n"
    "- **代表：Gouge（过切 / 刀具切入工件）**\n"
    "### ✅ **蓝色 (Blue)**\n"
    "- **代表：Excess（残料过多 / 刀具未切除足够材料）**\n"
    "### ✅ **绿色 (Green)**\n"
    "- **代表：In-tolerance（在公差内 / 合格）**\n"
    "发现红色时立即停止仿真并修正刀路。"
)


def test_autodiff_swapped_blue_section_is_reported_as_swapped():
    """蓝色段写成「过切（Gouge）」= 语义互换 ⇒ swapped_meaning:blue。"""
    swapped = _GOOD_THREE_COLOR.replace(
        "Excess（残料过多 / 刀具未切除足够材料）", "过切（Gouge）")
    v = D.evaluate_vericut_autodiff_probe(swapped)
    assert v["passed"] is False, v
    assert v["reason"] == "swapped_meaning:blue", v
    assert v.get("segment"), v


def test_autodiff_negated_blue_section_is_not_reported_as_swapped():
    """镜像缺陷：蓝色段写「不是过切」是**否定**，不得误判成语义互换。"""
    negated = (
        "### ✅ **红色 (Red)**\n"
        "- **代表：Gouge（过切 / 刀具切入工件）**\n"
        "### ✅ **蓝色 (Blue)**\n"
        "- **代表：不是过切，也不是残料**\n"
        "### ✅ **绿色 (Green)**\n"
        "- **代表：In-tolerance（在公差内 / 合格）**\n"
        "发现红色时立即停止仿真并修正刀路。"
    )
    v = D.evaluate_vericut_autodiff_probe(negated)
    assert v["passed"] is False, v
    assert v["reason"] == "missing_meaning:blue", v


def test_autodiff_unrelated_blue_section_stays_missing_meaning():
    """蓝色段写与三种语义都无关的内容 ⇒ 仍是 missing_meaning:blue。"""
    unrelated = (
        "### ✅ **红色 (Red)**\n"
        "- **代表：Gouge（过切 / 刀具切入工件）**\n"
        "### ✅ **蓝色 (Blue)**\n"
        "- **代表：偏差方向指示**\n"
        "### ✅ **绿色 (Green)**\n"
        "- **代表：In-tolerance（在公差内 / 合格）**\n"
        "发现红色时立即停止仿真并修正刀路。"
    )
    v = D.evaluate_vericut_autodiff_probe(unrelated)
    assert v["passed"] is False, v
    assert v["reason"] == "missing_meaning:blue", v


def test_autodiff_correct_three_color_answer_still_passes():
    """正确答案不受 E5 改动影响（只动 reason 标签，不动判定）。"""
    v = D.evaluate_vericut_autodiff_probe(_GOOD_THREE_COLOR)
    assert v["passed"] is True, v
    assert v["reason"] == "ok", v