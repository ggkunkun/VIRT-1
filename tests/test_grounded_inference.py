# -*- coding: utf-8 -*-
"""推理侧接地层契约测试（离线、零 Ollama）。

三类证据：
  A. 回放 2026-11-18 审计里 v3 的**真实失败输出** ⇒ 新门必须判红（植入坏样本 ⇒ 必红）。
  B. 新门与仓内既有独立门交叉核对（scripts/g71_semantic_check、cloud_train_pack 令牌门、
     skills/cae-fos-gate 的 Lamé 闭式解）——一套定律只有一个参照，两份实现必须一致。
  C. 编排：模型连错 ⇒ 确定性兜底且标 source=deterministic_*、model_passed=False；
     模型修正 ⇒ source=model；无模型/传输错误不得当作模型答案。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from virtu_omni.agent.grounded_inference import (  # noqa: E402
    G71Spec, GroundedResponder, check_lame_answer, generate_g71_program,
    lame_thick_cylinder, parse_g71_request, parse_lame_request, render_lame_answer,
    validate_g71_against_spec,
)


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


G71_OFFICIAL_PROMPT = ("用 FANUC ISO/G 格式为 Ø60 棒料编写 G71 粗车+G70 精车台阶轴程序"
                       "（第一台阶 Ø38 长 20 mm，总长 45 mm），含 G50 S1800、G96 S150 M03、T0101、F0.25 与 M30，只输出程序。")
G71_GEN_PROMPT = ("用 FANUC ISO/G 格式为 Ø80 棒料编写 G71 粗车+G70 精车台阶轴程序（第一台阶 Ø46 长 25 mm，总长 60 mm），"
                  "含 G50 S1800、G96 S150 M03、T0101、F0.25 与 M30，只输出程序。")
LAME_OFFICIAL_PROMPT = "按 Lamé 厚壁圆筒理论：内径 Di=60 mm，外径 Do=120 mm，内压 Pi=20 MPa。计算内壁环向应力 σ_θ（保留 2 位小数）与径向应力 σ_r，单位 MPa。"
LAME_GEN_PROMPT = "按 Lamé 厚壁圆筒理论：内径 Di=50 mm，外径 Do=100 mm，内压 Pi=24 MPa。计算内壁环向应力 σ_θ（保留 2 位小数）与径向应力 σ_r，单位 MPa。"

# --- 2026-11-18 审计实录（virtu-six-software:v3, digest 35cd9e06…）-------------------
V3_G71_OFFICIAL = ("G50 S1800\r\nG96 S150 M03\r\nT0101\r\nG71 U1.5 R0.4\r\nG71 P1 Q2 U0.75 W0.1 F0.25\r\n"
                   "N1 G00 X28.0 Z2.0\r\nN2 G01 Z0.0 F0.12\nG00 X68.0\nG70 P1 Q2\nM30")
V3_G71_GEN = ("```nc\r\n%\r\nO1007 (FANUC G71/G70 STEP-UP TURN)\nG50 S1800\nG96 S150 M03\nT0101\nG0 X82.0 Z2.0\n"
              "G71 U1.5 R0.7\nG71 P1 Q2 U0.4 W0.1 R0.2\nN1 G0 X46.0\nN2 G0 Z-25.0\nG0 Z-60.0\nT0202\n"
              "G00 X82.0 Z-60.0\nG70 P1 Q2 U0.2 W0.05\nM30\n%\n```")


# =========================== Lamé ==========================================

def test_lame_closed_form_matches_independent_reference():
    ref = _load(ROOT / "skills/cae-fos-gate/scripts/fos_crosscheck.py", "fos_crosscheck")
    for di, do, p in [(60, 120, 20), (50, 100, 24), (30, 90, 12.5), (80, 100, 7)]:
        r = lame_thick_cylinder(di, do, p)
        vm_ref, st_ref = ref.lame(di, do, p)
        assert r["sigma_theta_inner_mpa"] == pytest.approx(st_ref, rel=1e-12)
        assert r["sigma_r_inner_mpa"] == pytest.approx(-p, rel=1e-12)
        assert r["von_mises_inner_mpa"] == pytest.approx(vm_ref, rel=1e-12)
        assert r["sigma_r_outer_mpa"] == pytest.approx(0.0, abs=1e-9)


def test_lame_known_values_and_external_pressure():
    assert lame_thick_cylinder(60, 120, 20)["sigma_theta_inner_mpa"] == pytest.approx(33.3333, abs=1e-3)
    assert lame_thick_cylinder(50, 100, 24)["sigma_theta_inner_mpa"] == pytest.approx(40.0, abs=1e-9)
    r = lame_thick_cylinder(50, 100, 0, 10)   # 纯外压：σr(ro) = −Po，σθ(ri) = −2·Po·ro²/(ro²−ri²)
    assert r["sigma_r_outer_mpa"] == pytest.approx(-10.0)
    assert r["sigma_theta_inner_mpa"] == pytest.approx(-2 * 10 * 50 ** 2 / (50 ** 2 - 25 ** 2))
    with pytest.raises(ValueError):
        lame_thick_cylinder(100, 50, 10)


def test_lame_parser_extracts_and_refuses_to_invent():
    assert parse_lame_request(LAME_GEN_PROMPT) == {"di_mm": 50, "do_mm": 100, "pi_mpa": 24, "po_mpa": 0.0}
    assert parse_lame_request("Lamé 厚壁圆筒，内半径 25 mm，外半径 50 mm，内压 24 MPa")["di_mm"] == 50
    assert parse_lame_request("按 Lamé 理论计算一下应力") is None          # 缺参数 ⇒ 不臆造
    assert parse_lame_request("内径 Di=50 外径 Do=100 内压 Pi=24") is None   # 无 Lamé 触发
    assert parse_lame_request("Lamé：Di=100 mm，Do=50 mm，Pi=10 MPa") is None  # 几何非法


def test_lame_gate_rejects_memorized_official_answer_on_new_params():
    """v3 的记忆型错误：换参数后仍写出官方题的 33.33 ⇒ 必须红。"""
    params = parse_lame_request(LAME_GEN_PROMPT)
    res = lame_thick_cylinder(**params)
    bad = "σθ = 24·(50²+25²)/(50²−25²) = 33.33 MPa；σr = −24 MPa"
    v = check_lame_answer(bad, params, res)
    assert not v["passed"]
    assert any("missing_sigma_theta_inner" in x for x in v["violations"])
    assert any("unsupported_MPa_value(33.33)" in x for x in v["violations"])
    # 正确数值但混入一个编造的 MPa 值 ⇒ 仍红
    v2 = check_lame_answer("σθ = 40.00 MPa，σr = −24 MPa，许用应力 180 MPa", params, res)
    assert not v2["passed"] and "unsupported_MPa_value(180)" in v2["violations"]
    # 正确答案（含 LaTeX 与 U+2212）⇒ 绿
    good = r"$\sigma_\theta = 40.00\,\text{MPa}$，$\sigma_r = −24\,\text{MPa}$"
    assert check_lame_answer(good, params, res)["passed"]
    assert check_lame_answer(render_lame_answer(params, res), params, res)["passed"]


def test_lame_fallback_passes_official_grader():
    grader = _load(ROOT / "cloud_train_pack/deploy_trained_adapter.py", "deploy_trained_adapter_t")
    p = parse_lame_request(LAME_OFFICIAL_PROMPT)
    assert grader.evaluate_lame_stress_probe(render_lame_answer(p, lame_thick_cylinder(**p)))["passed"]


# =========================== G71 ===========================================

def test_g71_parser():
    s = parse_g71_request(G71_GEN_PROMPT)
    assert (s.stock_d, s.steps, s.total_len, s.s_clamp, s.vc, s.feed, s.tool) == \
        (80, [(46, 25)], 60, 1800, 150, 0.25, "T0101")
    assert parse_g71_request("写一段 G71 程序") is None
    assert parse_g71_request("G71：Ø60 棒料，台阶 Ø70 长 20，总长 45") is None   # 台阶大于毛坯 ⇒ 拒绝
    multi = parse_g71_request("G71 为 Ø60 棒料加工：台阶 Ø30 长 10，台阶 Ø45 长 15，总长 50")
    assert multi.steps == [(30, 10), (45, 15)]


@pytest.mark.parametrize("text,prompt", [(V3_G71_OFFICIAL, G71_OFFICIAL_PROMPT), (V3_G71_GEN, G71_GEN_PROMPT)])
def test_g71_gate_rejects_recorded_v3_failures(text, prompt):
    v = validate_g71_against_spec(text, parse_g71_request(prompt))
    assert not v["passed"]


def test_g71_gate_catches_specific_v3_defects():
    v = validate_g71_against_spec(V3_G71_GEN, parse_g71_request(G71_GEN_PROMPT))["violations"]
    assert "unsafe_G00_negative_Z_plunge" in v
    assert "profile_has_no_feed_cut" in v
    assert "G70_must_not_have_U_W" in v
    assert "missing_F0.25" in v
    v0 = validate_g71_against_spec(V3_G71_OFFICIAL, parse_g71_request(G71_OFFICIAL_PROMPT))["violations"]
    assert "profile_first_block_has_Z(TypeI)" in v0
    assert any(x.startswith("profile_missing_diameter_38") for x in v0)


@pytest.mark.parametrize("prompt", [
    G71_OFFICIAL_PROMPT, G71_GEN_PROMPT,
    "G71 为 Ø60 棒料加工：台阶 Ø30 长 10，台阶 Ø45 长 15，总长 50，G50 S2000 G96 S180 F0.2",
    "G71：Ø50 棒料，台阶 Ø40 长 30，总长 30",   # 台阶即全长，无毛坯直径段
])
def test_generator_output_passes_all_gates(prompt):
    spec = parse_g71_request(prompt)
    prog = generate_g71_program(spec)
    assert validate_g71_against_spec(prog, spec)["passed"], validate_g71_against_spec(prog, spec)
    sem = _load(ROOT / "virtu_omni/agent/cnc_semantic_gate.py", "cnc_semantic_gate_t")
    assert sem.validate_g71_program(prog)["passed"]
    grader = _load(ROOT / "cloud_train_pack/deploy_trained_adapter.py", "deploy_trained_adapter_t2")
    assert grader.evaluate_fanuc_g71_safety_probe(prog)["passed"]


def test_generator_agrees_with_independent_official_semantic_check():
    chk = _load(ROOT / "scripts/g71_semantic_check.py", "g71_semantic_check_t")
    prog = generate_g71_program(parse_g71_request(G71_OFFICIAL_PROMPT))
    assert chk.check_g71_step_shaft(prog)["passed"], chk.check_g71_step_shaft(prog)
    assert not chk.check_g71_step_shaft(V3_G71_OFFICIAL)["passed"]


@pytest.mark.parametrize("mutate,expect", [
    (lambda p: p.replace("G01 Z-25.0", "G00 Z-25.0"), "unsafe_G00_negative_Z_plunge"),
    (lambda p: p.replace("G01 Z-25.0", "G01 Z-15.0"), "profile_diameter_46_wrong_length"),
    (lambda p: p.replace("G71 U1.5 R0.5", "G71 U-1.5 R0.5"), "G71_U_must_be_positive"),
    (lambda p: p.replace("G00 X82.0 Z2.0", "G00 X70.0 Z2.0"), "cycle_start_not_outside_stock"),
    (lambda p: p.replace("G01 X82.0", "G01 X70.0"), "profile_does_not_exit_stock"),
    (lambda p: p.replace("N10 G00 X46.0", "N10 G00 X46.0 Z2.0"), "profile_first_block_has_Z(TypeI)"),
    (lambda p: p.replace("G70 P10", "G70 U0.2 P10"), "G70_must_not_have_U_W"),
    (lambda p: p.replace("G01 Z-60.0", "G01 Z-40.0"), "profile_diameter_80_wrong_length"),
    (lambda p: p.replace("M30", "M05"), "missing_program_end"),
    (lambda p: "", "no_gcode_lines"),
])
def test_planted_defects_must_turn_red(mutate, expect):
    spec = parse_g71_request(G71_GEN_PROMPT)
    good = generate_g71_program(spec)
    assert validate_g71_against_spec(good, spec)["passed"]
    bad = mutate(good)
    assert bad != good
    v = validate_g71_against_spec(bad, spec)
    assert not v["passed"]
    assert any(x.startswith(expect) for x in v["violations"]), v["violations"]


# =========================== 编排 ==========================================

class _Scripted:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def __call__(self, messages):
        self.calls.append(messages)
        return self.outputs.pop(0) if self.outputs else None


def test_g71_model_keeps_failing_falls_back_honestly():
    model = _Scripted([V3_G71_GEN] * 4)
    out = GroundedResponder(model, max_repairs=3).respond([{"role": "user", "content": G71_GEN_PROMPT}])
    g = out["grounding"]
    assert g["source"] == "deterministic_generator" and g["model_passed"] is False
    assert len(g["attempts"]) == 4 and all(a["violations"] for a in g["attempts"])
    assert g["fallback_gate"]["passed"] and out["content"]
    # 重写提示必须带回违规清单
    assert "unsafe_G00_negative_Z_plunge" in model.calls[1][-1]["content"]


def test_g71_model_repairs_on_second_try():
    spec = parse_g71_request(G71_GEN_PROMPT)
    model = _Scripted([V3_G71_GEN, generate_g71_program(spec)])
    out = GroundedResponder(model).respond([{"role": "user", "content": G71_GEN_PROMPT}])
    assert out["grounding"]["source"] == "model" and out["grounding"]["model_passed"]
    assert len(out["grounding"]["attempts"]) == 2


def test_lame_model_wrong_then_fallback_and_no_model_paths():
    msgs = [{"role": "user", "content": LAME_GEN_PROMPT}]
    out = GroundedResponder(_Scripted(["σθ = 33.33 MPa，σr = −24 MPa"] * 4)).respond(msgs)
    assert out["grounding"]["source"] == "deterministic_closed_form"
    assert "40.00 MPa" in out["content"]
    # 注入的已核验结果必须出现在发给模型的上下文里
    ok = GroundedResponder(_Scripted(["σθ = 40.00 MPa，σr = −24 MPa"])).respond(msgs)
    assert ok["grounding"]["source"] == "model"
    # 无模型 / 传输错误 / ERROR 字符串都不得算作模型答案
    for caller in (None, _Scripted([None]), _Scripted(["ERROR: timeout"]),
                   lambda m: (_ for _ in ()).throw(RuntimeError("boom"))):
        o = GroundedResponder(caller).respond(msgs)
        assert o["grounding"]["source"] == "deterministic_closed_form"
        assert o["grounding"]["model_passed"] is False


def test_hint_is_injected_for_lame():
    model = _Scripted(["σθ = 40.00 MPa，σr = −24 MPa"])
    GroundedResponder(model).respond([{"role": "user", "content": LAME_GEN_PROMPT}])
    assert model.calls[0][0]["role"] == "system" and "40.00" in model.calls[0][0]["content"]


def test_non_applicable_passthrough():
    model = _Scripted(["你好"])
    out = GroundedResponder(model).respond([{"role": "user", "content": "介绍一下 SOLIDWORKS 基准面"}])
    assert out == {"content": "你好", "grounding": {"applicable": False, "kind": None, "source": "model"}}
