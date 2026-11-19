"""Falsification tests for the headless sandbox safety gates (§8: bad sample => red).

Each ``test_*_must_fail`` case is a program that the OLD verifier falsely passed
(comment/substring spindle pollution, no G-code modality, token-only Z parsing,
non-empty unsupported language asserted as pass). Each must now be rejected.
Control cases prove legitimate programs are NOT false-red.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from virtu_omni.agent.headless_sandbox_verifier import (  # noqa: E402
    HeadlessSandboxVerifier,
    _eval_macro_expr,
    _strip_gcode_comments,
    _strip_vba_comments,
    _strip_lisp,
)


def _v():
    return HeadlessSandboxVerifier()


# --- C1: comment / substring spindle pollution -------------------------------

def test_spindle_in_comment_must_fail():
    # M03 exists only inside a comment; the spindle is never actually started.
    code = "O0001\nG21 G40\n(M03 S1000)\nG01 Z-5.0 F0.2\nM30\n"
    r = _v().verify_cimco_macro_b(code)
    assert r["passed"] is False
    assert any("CRITICAL SAFETY VIOLATION" in e for e in r["errors"])


def test_m30_must_not_start_spindle():
    # Old substring logic treated "M3" inside "M30" as spindle-on. Placing M30
    # before the cut (with S1000 supplying speed) isolates that bug: HEAD falsely
    # enables the spindle, my word-boundary regex does not.
    code = "O0001\nG21 G40\nG97 S1000\nM30\nG01 Z-5.0 F0.2\n"
    r = _v().verify_cimco_macro_b(code)
    assert r["passed"] is False
    assert any("CRITICAL SAFETY VIOLATION" in e for e in r["errors"])


def test_vba_rebuild_in_comment_must_fail():
    code = (
        "Sub main()\n"
        "    Dim swApp As SldWorks.SldWorks\n"
        "    Dim swModel As SldWorks.ModelDoc2\n"
        "    Dim swFeatMgr As SldWorks.FeatureManager\n"
        "    ' swModel.ForceRebuild3 True\n"
        "    swModel.ViewZoomtofit2\n"
        "End Sub\n"
    )
    r = _v().verify_solidworks_vba(code)
    assert r["passed"] is False
    assert any("ForceRebuild3" in e for e in r["errors"])


# --- C2: G-code modality persists across blocks ------------------------------

def test_modal_rapid_plunge_across_blocks_must_fail():
    # G00 sets rapid; the bare Z-5.0 block inherits rapid modality.
    code = "O0001\nG21 G40\nM03 S1000\nG00 X50.0\nZ-5.0\nM30\n"
    r = _v().verify_cimco_macro_b(code)
    assert r["collision_detected"] is True
    assert r["passed"] is False
    assert any("KINEMATIC COLLISION" in e for e in r["errors"])


# --- C3: Macro B variable / expression / leading-dot Z targets ---------------

def test_macro_b_variable_negative_z_rapid_must_fail():
    code = "O0001\nG21 G40\nM03 S1000\n#100 = -5.0\nG00 Z#100\nM30\n"
    r = _v().verify_cimco_macro_b(code)
    assert r["collision_detected"] is True
    assert r["passed"] is False


def test_macro_b_bracket_expr_negative_z_rapid_must_fail():
    code = "O0001\nG21 G40\nM03 S1000\n#102 = 10.0\nG00 Z-[#102]\nM30\n"
    r = _v().verify_cimco_macro_b(code)
    assert r["collision_detected"] is True
    assert r["passed"] is False


def test_leading_dot_negative_z_rapid_must_fail():
    code = "O0001\nG21 G40\nM03 S1000\nG00 Z-.5\nM30\n"
    r = _v().verify_cimco_macro_b(code)
    assert r["collision_detected"] is True
    assert r["passed"] is False


# --- C4: fail-closed generic fallback ----------------------------------------

def test_unsupported_language_must_fail_closed():
    r = _v().verify_code_sandbox("print('hello world')", "plaintext")
    assert r["passed"] is False
    assert r["execution_status"] == "UNSUPPORTED_LANGUAGE"
    assert r["errors"]


def test_empty_code_must_fail_closed():
    r = _v().verify_code_sandbox("   ", "plaintext")
    assert r["passed"] is False
    assert r["execution_status"] == "EMPTY_CODE"


# --- safe expression evaluator: never exec -----------------------------------

def test_eval_macro_expr_whitelist_and_no_exec():
    assert _eval_macro_expr("1+2", {}) == 3.0
    assert _eval_macro_expr("#100*2", {100: 5.0}) == 10.0
    assert _eval_macro_expr("[#100+4.0]", {100: 80.0}) == 84.0
    assert _eval_macro_expr("-[#102]", {102: 10.0}) == -10.0
    assert _eval_macro_expr("#999", {}) is None          # unknown variable
    assert _eval_macro_expr("1/0", {}) is None            # divide by zero
    # A call expression must be rejected, never executed.
    assert _eval_macro_expr("__import__('os').system('echo pwned')", {}) is None
    assert _eval_macro_expr("open('x')", {}) is None


# --- AutoLISP: string/comment parens are not structure -----------------------

def test_autolisp_string_parens_not_counted():
    # Real S-expression is balanced; the string literal holds four '(' that must
    # not be counted. Old raw-count logic false-red this legitimate program.
    code = '(defun c:foo () (princ "(((("))'
    r = _v().verify_autolisp(code)
    assert r["passed"] is True
    assert not any("Unbalanced" in e for e in r["errors"])


def test_autolisp_genuinely_unbalanced_must_fail():
    code = '(defun c:foo () (princ "hi")'
    r = _v().verify_autolisp(code)
    assert r["passed"] is False
    assert any("Unbalanced" in e for e in r["errors"])


# --- Controls: legitimate programs must NOT be false-red ---------------------

def test_safe_feed_plunge_passes():
    code = "O0001\nG21 G40 G28 U0.0 W0.0\nM03 S1200\nG00 Z2.0\nG01 Z-15.0 F0.15\nG01 X50.0 F0.2\nM30\n"
    r = _v().verify_cimco_macro_b(code)
    assert r["passed"] is True
    assert r["collision_detected"] is False


def test_g71_setup_block_without_F_not_feed_flagged():
    # G71 U.. R.. setup block legitimately carries no F; only G01/G02/G03 require F.
    code = (
        "O0001\nG21 G40 G28 U0.0 W0.0\nG97 S800 M03\n"
        "G00 X82.0 Z2.0\n"
        "G71 U1.0 R0.5\n"
        "G71 P10 Q20 U0.4 W0.1 F0.2\n"
        "N10 G00 X30.0\n"
        "G01 Z0.0 F0.2\n"
        "G01 X60.0 Z-2.0 F0.2\n"
        "G01 Z-20.0 F0.2\n"
        "N20 G01 X82.0 F0.2\n"
        "G70 P10 Q20 F0.2\n"
        "M05\nM30\n"
    )
    r = _v().verify_cimco_macro_b(code)
    assert r["passed"] is True, r["errors"]
    assert r["collision_detected"] is False
    assert not any("missing feed rate" in e for e in r["errors"])


def test_comment_stripping_helpers():
    assert _strip_gcode_comments("G00 Z-15.0 (CRITICAL PLUNGE CRASH)") == "G00 Z-15.0"
    assert _strip_gcode_comments("M03 S1000 ; start") == "M03 S1000"
    assert "ForceRebuild3" not in _strip_vba_comments("    ' swModel.ForceRebuild3 True\n")
    assert _strip_lisp('(princ "(((")') .count("(") == 1


# --- C14: optimizer must not game the gate with cosmetic fixes ---------------

def test_optimizer_does_not_game_lisp_paren_gate():
    from virtu_omni.agent.self_reflection_optimizer import SelfReflectionOptimizer
    opt = SelfReflectionOptimizer()
    broken = '(defun c:foo () (princ "hi")'  # genuinely unbalanced
    audit = opt.audit_code(broken, "autolisp")
    assert audit["passed"] is False
    fixed, refl = opt.reflect_and_optimize(broken, audit)
    # The old hack appended ')' to balance the count and fabricated a pass.
    recheck = opt.verifier.verify_autolisp(fixed)
    assert recheck["passed"] is False, "optimizer must not fabricate a LISP pass"
    assert "100% 通过" not in refl
    assert "禁止据此宣称完成" in refl


def test_optimizer_cnc_spindle_detection_ignores_comments():
    import re as _re
    from virtu_omni.agent.self_reflection_optimizer import SelfReflectionOptimizer
    opt = SelfReflectionOptimizer()
    code = "O0001\nG21 G40\n(M03 S1000)\nG01 Z-5.0 F0.2\nM30\n"
    audit = opt.audit_code(code, "cimco_macro")
    fixed, _ = opt.reflect_and_optimize(code, audit)
    cleaned = "\n".join(_strip_gcode_comments(l) for l in fixed.splitlines())
    # A real spindle start (outside comments) must now exist.
    assert _re.search(r"\bM0?[34]\b", cleaned)


# --- C15: G80 是固定循环取消，不是循环本身（涡轮叶片五轴假红修复） -----------

def test_g80_cancel_then_reference_return_before_spindle_passes():
    # 涡轮叶片五轴程序的典型安全开头：G80 取消循环 + G28 回参考点（带 Z 字），
    # 都在主轴启动之前。旧实现把 G80 落进 74..89 误设 motion=cycle，于是 G28 Z0.
    # 被误判「主轴停转却切削进给」→ 合法程序假红。修复后必须通过。
    code = (
        "O5001\n"
        "G21 G40 G49 G80 G90 G17\n"
        "G28 G91 Z0.\n"
        "G90\n"
        "T1 M06\n"
        "G54\n"
        "M03 S955\n"
        "M08\n"
        "G00 B0. C0.\n"
        "G00 G43.4 H01 Z100.0\n"
        "G00 Z5.0\n"
        "G01 Z-3.0 F191\n"
        "G00 Z100.0\n"
        "M05\nM30\n"
    )
    r = _v().verify_cimco_macro_b(code)
    assert r["passed"] is True, r["errors"]
    assert not any("spindle is stopped" in e for e in r["errors"])


def test_g80_is_not_canned_cycle():
    # G80 取消循环后模态回到 rapid。若仍误把 G80 当 cycle，随后裸 Z-5.0（无 G00/G01）
    # 会被当成循环深度而跳过碰撞检查 → 假绿。修复后裸负 Z 必须判rapid扎刀碰撞。
    code = (
        "O0001\n"
        "G21 G40 G80 G90\n"
        "M03 S1000\n"
        "Z-5.0\n"
        "M30\n"
    )
    r = _v().verify_cimco_macro_b(code)
    assert r["passed"] is False
    assert r["collision_detected"] is True
    assert any("Rapid traverse G00 plunge" in e for e in r["errors"])


def test_cutting_feed_before_spindle_still_rejected():
    # 负对照：真正的「主轴未启动就切削进给」必须仍判红，证明 G80 修复未削弱主轴门。
    code = (
        "O0001\n"
        "G21 G40 G80 G90\n"
        "G01 Z-2.0 F100\n"
        "M03 S1000\n"
        "M30\n"
    )
    r = _v().verify_cimco_macro_b(code)
    assert r["passed"] is False
    assert any("spindle is stopped" in e for e in r["errors"])