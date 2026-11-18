#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""反证测试：六大工业软件 Agent 验收探针的判分器修正（2026-11-15）。

背景（AGENTS.md §8.4「闸必须能被证伪」）：
  `virtu-six-software:v3` 在 2026-11-15 20:27 的部署验收中判 PROBE_FAILED，
  两个失败项经实测复现后定性为**判分器假阴性 + token 预算截断**，不是模型缺陷：
    1. `lame_stress_probe`：num_predict=260 时模型在写出 σ_θ=33.33 后、给出 σ_r
       之前被硬截断；且负号字符集只认 ASCII '-'，不认 U+2212 '−' / U+FF0D '－'。
    2. `vericut_coordinate_unit_probe`：`has_isolation` 与 `_neg_prefix_re`
       否定词表缺「不得」，导致「不得擅自改写为 millimeter」「不得直接等价套用」
       这类**正确**表述被判成缺隔离/声称等价（镜像缺陷）。

本文件保证修正**没有把门放宽成摆设**：每条新放行的表述都必须有对应的坏样本仍然判红。
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (ROOT, os.path.join(ROOT, "cloud_train_pack")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import deploy_trained_adapter as D  # noqa: E402


# --------------------------------------------------------------------------
# 夹具：真实 v3 模型的实测输出（2026-11-15 21:2x 于 127.0.0.1:11435 复现）
# --------------------------------------------------------------------------
REAL_LAME_TRUNCATED = (
    "根据 Lamé 厚壁圆筒理论：\n\n"
    "- 内半径 $ r_i = \\frac{Di}{2} = 30\\,\\text{mm} $，外半径 $ r_o = \\frac{Do}{2} = 60\\,\\text{mm} $；\n"
    "- 压力比平方 $ \\left(\\frac{P_i}{P_o}\\right) = \\left(\\frac{r_i}{r_o}\\right)^2 = 0.25 $，故内壁环向应力为：\n"
    "  $$\n"
    "  \\sigma_{\\theta} = P_i \\left( \\frac{r_o^2 + r_i^2}{r_o^2 - r_i^2} \\right) = 20 \\cdot "
    "\\left( \\frac{60^2 + 30^2}{60^2 - 30^2} \\right) = 20 \\cdot \\left( \\frac{4500}{2700} \\right) = 20 \\cdot 1.6667 = 33.33"
)

REAL_LAME_COMPLETE = (
    "按 Lamé 公式：k = (Do/Di)^2 = (120/60)^2 = 4；A = Pi/(k-1) = 20/3 = 6.6667 MPa。\n"
    "- 内壁环向应力 σ_θ = A + B/ri^2 = 33.33 MPa（拉应力）\n"
    "- 内壁径向应力 σ_r = A - B/ri^2 = -20 MPa（压应力）\n"
    "结论：σ_θ = 33.33 MPa，σ_r = -20 MPa。"
)

REAL_LAME_UNICODE_MINUS = REAL_LAME_COMPLETE.replace("σ_r = -20 MPa", "σ_r = \u221220 MPa")

REAL_VERICUT_GOOD = (
    "1. **工程单位确认**：`<Unit>inch</Unit>` 表示该 VERICUT 工程使用 **英寸 (inch)** 作为长度单位，"
    "而非毫米 (millimeter)。在真实加工前必须确认刀路与工件均处于 `inch` 数值域，避免因单位混用导致过切或残料。\n\n"
    "2. **坐标系与 SOLIDWORKS 基准面映射**：**不能直接等价套用** SOLIDWORKS 2021 的 `Front/Top/Right` "
    "假想基准面（尤其在 `inch` 数值域内）。原因如下：\n"
    "   - **VERICUT Z-up / G54 与 SOLIDWORKS 假想基准面不同**：VERICUT 的 `Z+` 代表向上，"
    "而 SOLIDWORKS 默认将 `Front` 平面作为 XY 平面、`Top` 为 XZ 平面。\n"
    "   - 若未显式定义坐标系或通过 `G54/G55` 调用子程序，两者的 Z 轴方向可能交叉错位。"
)

REAL_VERICUT_SFT_STYLE = (
    "第一，单位系统必须与真实 XML 一致：inch（英寸）为准，**不得擅自改写为 millimeter**；"
    "第二，VERICUT 9.6 工程坐标系为 Z-up 且 G54，与 SOLIDWORKS 2021 默认的 Y-up（Front=XY/+Z, "
    "Top=XZ/+Y, Right=YZ/+X）**不得直接等价套用**，否则刀路深度会反向。"
)


def test_lame_truncated_answer_is_reported_as_truncation_not_model_error():
    """被 token 预算截断 ⇒ 报 truncated，不能伪装成「模型答错 σ_r」。"""
    v = D.evaluate_lame_stress_probe(REAL_LAME_TRUNCATED)
    assert v["passed"] is False
    assert "truncated" in v["reason"], v
    assert v.get("truncated") is True, v


def test_lame_complete_answer_passes():
    v = D.evaluate_lame_stress_probe(REAL_LAME_COMPLETE)
    assert v["passed"] is True, v
    assert v["reason"] == "ok", v


def test_lame_unicode_minus_is_accepted():
    """U+2212 '−' 是数学负号，不该被判成「没有 -20」。"""
    v = D.evaluate_lame_stress_probe(REAL_LAME_UNICODE_MINUS)
    assert v["passed"] is True, v


def test_lame_missing_radial_still_fails_when_not_truncated():
    """没有截断、也真的没写 σ_r ⇒ 仍然判红（口径不放宽）。"""
    bad = (
        "按 Lamé 公式：k = 4，A = 6.6667 MPa，内壁环向应力 σ_θ = 33.33 MPa，"
        "径向应力按静力学平衡取 0（略）。结论：σ_θ = 33.33 MPa。"
    )
    v = D.evaluate_lame_stress_probe(bad)
    assert v["passed"] is False
    assert "missing_negative_sigma_r_-20" in v["reason"], v


def test_lame_sigma_theta_60_confusion_still_fails():
    """旧式错误公式 (Do+Di)/(Do-Di)=60 必须继续判红。"""
    bad = "环向应力 σ_θ = 60 MPa，径向应力 σ_r = -20 MPa。"
    v = D.evaluate_lame_stress_probe(bad)
    assert v["passed"] is False
    assert "claimed_sigma_theta_60" in v["reason"], v


def test_lame_wrong_hoop_value_still_fails():
    bad = "σ_θ = 45.00 MPa，σ_r = -20 MPa。"
    v = D.evaluate_lame_stress_probe(bad)
    assert v["passed"] is False
    assert "missing_sigma_theta_33.33" in v["reason"], v


def test_vericut_correct_answer_passes():
    v = D.evaluate_vericut_coordinate_unit_probe(REAL_VERICUT_GOOD)
    assert v["passed"] is True, v


def test_vericut_sft_style_phrasing_passes():
    """「不得擅自改写为 millimeter」「不得直接等价套用」= 正确表述。"""
    v = D.evaluate_vericut_coordinate_unit_probe(REAL_VERICUT_SFT_STYLE)
    assert v["passed"] is True, v


def test_vericut_missing_unit_inch_still_fails():
    v = D.evaluate_vericut_coordinate_unit_probe(
        "该工程单位是 millimeter，且 Z-up 坐标系不能直接等价套用 SOLIDWORKS 基准面。"
    )
    assert v["passed"] is False
    assert v["reason"] == "missing_unit_inch", v


def test_vericut_unit_rewritten_to_mm_still_fails():
    """肯定句把单位说成毫米 ⇒ 判红（无论先命中哪一条单位错误）。"""
    v = D.evaluate_vericut_coordinate_unit_probe(
        "单位为millimeter；Z-up 坐标系不能直接等价套用 SOLIDWORKS 基准面。"
    )
    assert v["passed"] is False
    assert v["reason"] in ("wrong_unit_millimeter", "missing_unit_inch"), v

    # 既提到 inch 又肯定地改写成毫米 ⇒ 必须命中 wrong_unit_millimeter
    v2 = D.evaluate_vericut_coordinate_unit_probe(
        "该 XML 里出现过 inch，但工程单位为millimeter，请按毫米建模；"
        "Z-up 坐标系不能直接等价套用 SOLIDWORKS 基准面。"
    )
    assert v2["passed"] is False
    assert v2["reason"] == "wrong_unit_millimeter", v2


def test_vericut_claim_equivalence_still_fails():
    """声称两套坐标系完全等价 ⇒ 判红。"""
    v = D.evaluate_vericut_coordinate_unit_probe(
        "单位是 inch；VERICUT 的 Z-up / G54 与 SOLIDWORKS 2021 的 Front/Top/Right "
        "完全等价，可直接套用，无需转换。"
    )
    assert v["passed"] is False
    assert v["reason"] == "claimed_coordinates_identical", v


def test_vericut_no_isolation_statement_still_fails():
    """只说单位、不谈坐标系隔离 ⇒ 判红。"""
    v = D.evaluate_vericut_coordinate_unit_probe(
        "该工程单位是 inch（英寸）。除此之外无其它需要说明的内容。"
    )
    assert v["passed"] is False
    assert v["reason"] == "missing_coordinate_isolation", v


def test_probe_budgets_are_large_enough():
    """回归守卫：两个探针的 token 预算不得回退到会截断推导的量级。"""
    src = open(
        os.path.join(ROOT, "cloud_train_pack", "deploy_trained_adapter.py"),
        "r", encoding="utf-8",
    ).read()
    # Lamé 探针与 VERICUT 坐标单位探针的 num_predict 必须 >= 400（实测 260 会截断）
    for prompt_marker in (
        "计算内壁环向应力 σ_θ（保留 2 位小数）与径向应力 σ_r，单位 MPa。",
        "(2) 该 Z-up / G54 坐标系能否直接等价套用 SOLIDWORKS 2021 默认的前/上/右基准面（Front/Top/Right）？为什么？",
    ):
        idx = src.index(prompt_marker)
        window = src[idx: idx + 400]
        budgets = [int(m) for m in re.findall(r"num_predict=(\d+)", window)]
        assert budgets and max(budgets) >= 400, (prompt_marker[:20], budgets)


def test_grader_identity_is_recorded():
    """凭证必须带判分器版本与哈希（AGENTS.md §8.2 判分器 sha256）。"""
    assert D.MEASUREMENT_VERSION
    assert re.fullmatch(r"[0-9a-f]{64}", D.GRADER_SHA256), D.GRADER_SHA256
