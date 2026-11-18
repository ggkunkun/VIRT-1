# -*- coding: utf-8 -*-
"""virtu_omni/reasoning/chain_of_thought.py — Structured Industrial Chain-of-Thought (CoT) Engine.

Grounded in:
1. DeepSeek-R1 / OpenAI o1 Verifiable Reasoning Traces (<think>...</think>).
2. Faithful Chain-of-Thought Reasoning (Lanham et al. / Lyu et al.):
   Thought traces must not merely look plausible; every equation inside <think>
   must be arithmetically valid, grounded in prompt/scenario inputs, and
   strictly consistent (faithful) with the final answer.
3. RULE[d:\\Virtu模型\\AGENTS.md] Section 8 (Measurement Constitution):
   - Rule 4: Falsifiable gates (planted bad CoT samples MUST fail).
   - Rule 5: Single source of truth for physical laws (imports virtu_eval.derivation.LAWS,
     virtu_eval.audit_case_arithmetic.eval_expr, and scripts/wm_verifier.recompute).
"""

from __future__ import annotations

import dataclasses
from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS_DIR = os.path.join(WORKSPACE_DIR, "scripts")
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from virtu_eval.audit_case_arithmetic import eval_expr
from virtu_eval.derivation import LAWS, PREDICATE_FIELDS, resolve as resolve_laws

try:
    import wm_verifier
except Exception:  # pragma: no cover
    wm_verifier = None

try:
    import wm_derivation
except Exception:  # pragma: no cover
    wm_derivation = None


# Canonical 5 stages of industrial engineering Chain-of-Thought
COT_STAGES: Tuple[str, ...] = (
    "INTENT_AND_GIVENS",
    "LAW_SELECTION",
    "DIMENSIONAL_AUDIT",
    "SYMBOLIC_DERIVATION",
    "SAFETY_GATE_VERIFICATION",
)

# Physical/mathematical constants allowed in law substitutions without appearing in prompt
ALLOWED_LAW_CONSTANTS: Set[float] = {
    0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0, 16.0, 32.0, 60.0,
    100.0, 180.0, 1000.0, 25.4, 0.3048, round(math.pi, 6), 3.1416, 3.14159, 3.141593,
}

_THINK_TAG_RE = re.compile(r"<think>([\s\S]*?)</think>", re.IGNORECASE)
_UNCLOSED_THINK_RE = re.compile(r"<think>([\s\S]*)$", re.IGNORECASE)
_STAGE_HEADER_RE = re.compile(
    r"\[STAGE\s*(\d+)\s*:\s*([A-Z_]+)\]|(?:Step|阶段|步骤)\s*(\d+)\s*[：:\-\]]\s*([^\n]+)",
    re.IGNORECASE,
)
_NUM_TOKEN_RE = re.compile(r"(?<![0-9.])(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)")

# Matches inline equations like:
#   safety_factor = 355 / 180 = 1.9722
#   material_removed_mm3: 10 * 20 * 50 = 10000
_INLINE_EQ_RE = re.compile(
    r"([A-Za-z_][A-Za-z0-9_]*)\s*[=:]\s*"
    r"([0-9().+\-*/^\s]+(?:[*+/^-][0-9().+\-*/^\s]+)+)"
    r"(?:\s*=\s*(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?))?"
)

# Matches pure arithmetic chains like: 355 / 180 = 1.972
_BARE_ARITH_EQ_RE = re.compile(
    r"(?<![A-Za-z0-9_.])"
    r"(\d+(?:\.\d+)?(?:\s*[*+/^-]\s*\(?\d+(?:\.\d+)?\)?)+)"
    r"\s*=\s*(-?\d+(?:\.\d+)?)"
)


def _canon_num(val: float) -> float:
    return round(float(val), 6)


def _extract_numbers(text: str) -> Set[float]:
    out: Set[float] = set()
    for m in _NUM_TOKEN_RE.findall(text or ""):
        try:
            v = float(m)
            if math.isfinite(v):
                out.add(_canon_num(v))
                out.add(_canon_num(abs(v)))
        except ValueError:
            pass
    return out


@dataclass
class CoTStep:
    """A single parsed reasoning step inside <think>...</think>."""
    step_index: int
    stage: str
    content: str
    bound_field: Optional[str] = None
    expression: Optional[str] = None
    claimed_value: Optional[float] = None
    evaluated_value: Optional[float] = None
    arithmetic_valid: bool = True
    grounding_valid: bool = True
    error_detail: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CoTTrajectory:
    """Synthesized or parsed full Chain-of-Thought trajectory."""
    trajectory_id: str
    task_family: str
    thinking_text: str
    steps: List[CoTStep]
    world_state: Optional[Dict[str, Any]]
    derivation: Dict[str, str]
    full_response: str
    basis: str = "measured"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CoTVerificationReport:
    """Deterministic verification report for a Chain-of-Thought response."""
    run_id: str
    passed: bool
    has_think_block: bool
    stages_covered: List[str]
    steps: List[CoTStep]
    extracted_derivations: Dict[str, str]
    ungrounded_literals: List[str] = field(default_factory=list)
    arithmetic_errors: List[str] = field(default_factory=list)
    faithfulness_conflicts: List[str] = field(default_factory=list)
    gate_violations: List[str] = field(default_factory=list)
    overall_cot_score: float = 0.0
    basis: str = "measured"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class StructuredCoTEngine:
    """Deterministic 5-stage industrial Chain-of-Thought synthesizer, parser, and verifier."""

    @staticmethod
    def extract_think_and_answer(raw_text: str) -> Tuple[str, str, bool]:
        """Separates <think>...</think> from the final answer body.

        Returns (think_content, answer_body, is_closed_think).
        """
        if not raw_text:
            return "", "", False
        text = str(raw_text)
        matches = list(_THINK_TAG_RE.finditer(text))
        if matches:
            think_parts = [m.group(1).strip() for m in matches if m.group(1).strip()]
            body = _THINK_TAG_RE.sub("", text).strip()
            return "\n".join(think_parts), body, True

        unclosed = _UNCLOSED_THINK_RE.search(text)
        if unclosed:
            think_part = unclosed.group(1).strip()
            body = text[:unclosed.start()].strip()
            return think_part, body, False

        return "", text.strip(), False

    @classmethod
    def extract_cot_derivations(cls, think_text: str) -> Dict[str, str]:
        """Extracts canonical field -> arithmetic expression bindings from <think> text."""
        derivations: Dict[str, str] = {}
        if not think_text:
            return derivations

        for m in _INLINE_EQ_RE.finditer(think_text):
            field_name = m.group(1).strip()
            expr = m.group(2).strip()
            # Clean trailing "=" or whitespace
            expr = expr.rstrip("= \t")
            if not expr:
                continue
            val, err = eval_expr(expr)
            if err == "" and val is not None and math.isfinite(val):
                derivations[field_name] = expr
        return derivations

    @classmethod
    def parse_cot_steps(
        cls,
        think_text: str,
        allowed_numbers: Optional[Set[float]] = None,
        tol_rel: float = 0.05,
    ) -> List[CoTStep]:
        """Parses <think> content into atomic reasoning steps and audits inline equations."""
        if not think_text or not think_text.strip():
            return []

        raw_lines = [ln.strip() for ln in think_text.splitlines() if ln.strip()]
        steps: List[CoTStep] = []
        current_stage = "INTENT_AND_GIVENS"
        running_allowed: Set[float] = set(allowed_numbers or ()) | ALLOWED_LAW_CONSTANTS

        stage_map = {
            "1": "INTENT_AND_GIVENS",
            "2": "LAW_SELECTION",
            "3": "DIMENSIONAL_AUDIT",
            "4": "SYMBOLIC_DERIVATION",
            "5": "SAFETY_GATE_VERIFICATION",
        }

        for idx, line in enumerate(raw_lines, 1):
            # Detect stage transitions
            sh = _STAGE_HEADER_RE.search(line)
            if sh:
                if sh.group(2) and sh.group(2).upper() in COT_STAGES:
                    current_stage = sh.group(2).upper()
                elif sh.group(1) in stage_map:
                    current_stage = stage_map[sh.group(1)]
                elif sh.group(3) in stage_map:
                    current_stage = stage_map[sh.group(3)]
            else:
                low = line.lower()
                if any(k in low for k in ("定律", "公式", "law", "formula")):
                    current_stage = "LAW_SELECTION"
                elif any(k in low for k in ("量纲", "单位", "边界", "dimension", "unit")):
                    current_stage = "DIMENSIONAL_AUDIT"
                elif any(k in low for k in ("代入", "计算", "求得", "derivation", "=")):
                    current_stage = "SYMBOLIC_DERIVATION"
                elif any(k in low for k in ("闸门", "安全", "校核", "gate", "fos_gate", "autodiff", "volume_conservation")):
                    current_stage = "SAFETY_GATE_VERIFICATION"

            bound_field: Optional[str] = None
            expr_str: Optional[str] = None
            claimed_val: Optional[float] = None
            eval_val: Optional[float] = None
            arith_ok = True
            ground_ok = True
            err_detail: Optional[str] = None

            eq_m = _INLINE_EQ_RE.search(line)
            if eq_m:
                bound_field = eq_m.group(1).strip()
                expr_str = eq_m.group(2).strip().rstrip("= \t")
                if eq_m.group(3) is not None:
                    try:
                        claimed_val = float(eq_m.group(3))
                    except ValueError:
                        claimed_val = None
            else:
                bare_m = _BARE_ARITH_EQ_RE.search(line)
                if bare_m:
                    expr_str = bare_m.group(1).strip()
                    try:
                        claimed_val = float(bare_m.group(2))
                    except ValueError:
                        claimed_val = None

            if expr_str:
                # 1. Check literal grounding if allowed_numbers provided
                if allowed_numbers is not None:
                    expr_lits = _extract_numbers(expr_str)
                    ungrounded = [
                        x for x in expr_lits
                        if not any(abs(x - a) <= max(1e-4, abs(a) * 1e-3) for a in running_allowed)
                    ]
                    if ungrounded:
                        ground_ok = False
                        err_detail = f"算式 {expr_str!r} 含无出处字面量 {ungrounded}"

                # 2. Evaluate expression with authoritative eval_expr
                val, err = eval_expr(expr_str)
                if err == "" and val is not None and math.isfinite(val):
                    eval_val = float(val)
                    running_allowed.add(_canon_num(eval_val))
                    running_allowed.add(_canon_num(abs(eval_val)))
                    if claimed_val is not None:
                        running_allowed.add(_canon_num(claimed_val))
                        diff = abs(eval_val - claimed_val)
                        tol = max(1e-2, abs(eval_val) * tol_rel)
                        if diff > tol:
                            arith_ok = False
                            msg = f"算术失真: {expr_str} 实算={eval_val:.6g} != 声称={claimed_val:.6g}"
                            err_detail = f"{err_detail}; {msg}" if err_detail else msg

            steps.append(
                CoTStep(
                    step_index=idx,
                    stage=current_stage,
                    content=line,
                    bound_field=bound_field,
                    expression=expr_str,
                    claimed_value=claimed_val,
                    evaluated_value=eval_val,
                    arithmetic_valid=arith_ok,
                    grounding_valid=ground_ok,
                    error_detail=err_detail,
                )
            )

        return steps

    @classmethod
    def synthesize_cot(
        cls,
        scenario: Dict[str, Any],
        prompt: str = "",
        include_json_answer: bool = True,
    ) -> CoTTrajectory:
        """Synthesizes a deterministic, 5-stage verified <think> trace + world_state JSON."""
        task = str((scenario or {}).get("task") or "unknown")
        inputs = dict((scenario or {}).get("inputs") or {})

        # Handle invalid family or missing critical parameters
        if task == "invalid":
            reason = str((scenario or {}).get("reason") or "negative_cut_depth: 输入参数违反物理约束或缺失必要量")
            think_lines = [
                f"[STAGE 1: INTENT_AND_GIVENS] 识别任务族 task=invalid，审视输入参数: {json.dumps(inputs, ensure_ascii=False)}",
                "[STAGE 2: PHYSICAL_LAW_SELECTION] 检查前置物理合法性约束（非负切削深度、非零分母、必备材料物性）。",
                f"[STAGE 3: DIMENSIONAL_AND_BOUNDARY_AUDIT] 命中非法输入判据: {reason}，严禁使用默认物性或强行计算。",
                "[STAGE 4: SYMBOLIC_SUBSTITUTION_AND_DERIVATION] 非法输入不执行算式代入，world_state 置为 null。",
                "[STAGE 5: SAFETY_GATE_VERIFICATION] 触发 invalid 拒答闸门，输出规范错误结构。",
            ]
            think_text = "\n".join(think_lines)
            payload = {"world_state": None, "invalid": True, "reason": reason}
            full_resp = f"<think>\n{think_text}\n</think>\n{json.dumps(payload, ensure_ascii=False)}" if include_json_answer else f"<think>\n{think_text}\n</think>"
            steps = cls.parse_cot_steps(think_text)
            tid = f"COT_{hashlib.sha256(full_resp.encode('utf-8')).hexdigest()[:10]}"
            return CoTTrajectory(
                trajectory_id=tid,
                task_family=task,
                thinking_text=think_text,
                steps=steps,
                world_state=None,
                derivation={},
                full_response=full_resp,
                basis="measured",
            )

        # Compute authoritative reference via wm_verifier.recompute & virtu_eval.derivation.resolve
        ref_ws: Dict[str, Any] = {}
        if wm_verifier is not None:
            try:
                ref_ws = dict(wm_verifier.recompute(scenario) or {})
            except Exception:
                ref_ws = {}

        law_derivations: Dict[str, str] = {}
        law_values: Dict[str, float] = {}
        try:
            law_derivations, law_values = resolve_laws(task, inputs)
        except Exception:
            pass

        if wm_derivation is not None:
            try:
                flat_s = dict(inputs)
                flat_s["task"] = task
                rich_der = wm_derivation.derive(flat_s)
                for k, v in rich_der.items():
                    law_derivations.setdefault(k, v)
            except Exception:
                pass

        for k, v in law_values.items():
            ref_ws.setdefault(k, round(float(v), 4))

        laws_spec = LAWS.get(task, [])
        law_desc = "; ".join(f"{f} = {expr}" for f, expr in laws_spec) if laws_spec else "wm_verifier.recompute"

        sub_lines: List[str] = []
        for f_name, expr in law_derivations.items():
            val, err = eval_expr(expr)
            if err == "" and val is not None and math.isfinite(val):
                sub_lines.append(f"{f_name} = {expr} = {round(float(val), 6):g}")
            else:
                sub_lines.append(f"{f_name} = {expr}")

        gate_checks: List[str] = []
        for gk in ("fos_gate", "volume_conservation", "autodiff", "within_limit", "tolerance_pass", "gouge"):
            if gk in ref_ws:
                gate_checks.append(f"{gk}={ref_ws[gk]!r}")
        if not gate_checks:
            gate_checks.append("数值量纲与守恒律复核通过")

        think_lines = [
            f"[STAGE 1: INTENT_AND_GIVENS] 任务族 task={task}，给定参数 inputs={json.dumps(inputs, ensure_ascii=False)}",
            f"[STAGE 2: PHYSICAL_LAW_SELECTION] 绑定权威物理定律 (virtu_eval.derivation.LAWS): {law_desc}",
            "[STAGE 3: DIMENSIONAL_AND_BOUNDARY_AUDIT] 核验输入量纲（mm / mm3 / MPa / g/mm3）一致，分母非零且参数处于物理有效域。",
            "[STAGE 4: SYMBOLIC_SUBSTITUTION_AND_DERIVATION] " + ("；".join(sub_lines) if sub_lines else "由求解器直接绑定数值"),
            "[STAGE 5: SAFETY_GATE_VERIFICATION] 安全闸门判定: " + "，".join(gate_checks),
        ]
        think_text = "\n".join(think_lines)
        payload = {
            "world_state": ref_ws,
            "derivation": law_derivations,
        }
        full_resp = (
            f"<think>\n{think_text}\n</think>\n{json.dumps(payload, ensure_ascii=False)}"
            if include_json_answer
            else f"<think>\n{think_text}\n</think>"
        )
        allowed_nums = _extract_numbers(prompt) | _extract_numbers(json.dumps(inputs, ensure_ascii=False))
        steps = cls.parse_cot_steps(think_text, allowed_numbers=allowed_nums)
        tid = f"COT_{hashlib.sha256(full_resp.encode('utf-8')).hexdigest()[:10]}"
        return CoTTrajectory(
            trajectory_id=tid,
            task_family=task,
            thinking_text=think_text,
            steps=steps,
            world_state=ref_ws,
            derivation=law_derivations,
            full_response=full_resp,
            basis="measured",
        )

    @classmethod
    def verify_cot_faithfulness(
        cls,
        raw_output: str,
        prompt: str = "",
        scenario: Optional[Dict[str, Any]] = None,
        require_think: bool = True,
        tol_rel: float = 0.05,
    ) -> CoTVerificationReport:
        """Audits a response's <think> trace for grounding, arithmetic accuracy, and answer faithfulness."""
        think_text, body_text, is_closed = cls.extract_think_and_answer(raw_output)
        has_think = bool(think_text.strip()) and is_closed

        # Collect grounded numbers from prompt + scenario inputs
        allowed_nums: Set[float] = _extract_numbers(prompt) | ALLOWED_LAW_CONSTANTS
        if scenario and isinstance(scenario.get("inputs"), dict):
            allowed_nums |= _extract_numbers(json.dumps(scenario["inputs"], ensure_ascii=False))

        # Also allow authoritative solver reference values if scenario is available
        ref_ws: Dict[str, Any] = {}
        if scenario and scenario.get("task") and wm_verifier is not None and scenario.get("task") != "invalid":
            try:
                ref_ws = dict(wm_verifier.recompute(scenario) or {})
            except Exception:
                ref_ws = {}

        steps = cls.parse_cot_steps(
            think_text,
            allowed_numbers=allowed_nums if (prompt or scenario) else None,
            tol_rel=tol_rel,
        )
        stages_covered = list(dict.fromkeys(s.stage for s in steps))
        extracted_der = cls.extract_cot_derivations(think_text)

        ungrounded: List[str] = []
        arith_errors: List[str] = []
        faithfulness_conflicts: List[str] = []
        gate_violations: List[str] = []

        if require_think and not has_think:
            gate_violations.append("缺失闭合的 <think>...</think> 思维链块")

        for s in steps:
            if not s.grounding_valid and s.error_detail:
                ungrounded.append(f"Step {s.step_index}: {s.error_detail}")
            if not s.arithmetic_valid and s.error_detail:
                arith_errors.append(f"Step {s.step_index}: {s.error_detail}")

        # Parse final body JSON (if structured output) or key=value pairs in code/text
        body_ws: Dict[str, Any] = {}
        body_der: Dict[str, str] = {}
        if body_text:
            try:
                clean_body = re.sub(r"^```(?:json|python)?\s*|\s*```$", "", body_text.strip(), flags=re.I | re.M).strip()
                start_idx = clean_body.find("{")
                if start_idx >= 0:
                    obj, _ = json.JSONDecoder().raw_decode(clean_body[start_idx:])
                    if isinstance(obj, dict):
                        if isinstance(obj.get("world_state"), dict):
                            body_ws = dict(obj["world_state"])
                        elif "world_state" not in obj and "tool" not in obj:
                            body_ws = dict(obj)
                        if isinstance(obj.get("derivation"), dict):
                            body_der = {str(k): str(v) for k, v in obj["derivation"].items() if isinstance(v, str)}
            except Exception:
                pass

        # Check Thought-to-Answer numerical faithfulness:
        # Every field evaluated inside <think> must agree with body_ws[field] (or inline FOS in code)
        cot_field_vals: Dict[str, float] = {}
        for s in steps:
            if s.bound_field and s.evaluated_value is not None:
                cot_field_vals[s.bound_field] = s.evaluated_value
            elif s.bound_field and s.claimed_value is not None:
                cot_field_vals[s.bound_field] = s.claimed_value

        # Also extract explicit `FOS = X` or `safety_factor = X` mentions in <think> (excluding `>= 1.5` thresholds)
        for m in re.finditer(
            r"\b(safety_factor|FOS)\s*(?<![><!])=\s*(?:[^=\n<>]+(?<![><!])=\s*)*(-?\d+(?:\.\d+)?)",
            think_text,
            re.I,
        ):
            key = "safety_factor"
            try:
                cot_field_vals.setdefault(key, float(m.group(2)))
            except ValueError:
                pass

        # Compare CoT derived fields against JSON world_state
        for fk, cot_val in cot_field_vals.items():
            canon_fk = "safety_factor" if fk.upper() == "FOS" else fk
            if canon_fk in body_ws and isinstance(body_ws[canon_fk], (int, float)) and not isinstance(body_ws[canon_fk], bool):
                ans_val = float(body_ws[canon_fk])
                diff = abs(cot_val - ans_val)
                tol = max(1e-2, abs(cot_val) * tol_rel)
                if diff > tol:
                    faithfulness_conflicts.append(
                        f"思维链与最终答案矛盾 ({canon_fk}): <think> 推导值={cot_val:.6g} != 输出值={ans_val:.6g}"
                    )

        # Compare CoT FOS against code/prose FOS if body is not JSON
        if not body_ws and "safety_factor" in cot_field_vals and body_text:
            ans_fos_m = re.search(r"(?:FOS|safety_factor|安全系数)[^\d\n]{0,10}(-?\d+(?:\.\d+)?)", body_text, re.I)
            if ans_fos_m:
                ans_fos = float(ans_fos_m.group(1))
                cot_fos = cot_field_vals["safety_factor"]
                if abs(cot_fos - ans_fos) > max(1e-2, abs(cot_fos) * tol_rel):
                    faithfulness_conflicts.append(
                        f"思维链与代码结论矛盾 (FOS): <think> 推导值={cot_fos:.4g} != 代码声称值={ans_fos:.4g}"
                    )

        # Check Gate Faithfulness: e.g. <think> derives FOS < 1.5 (or says fos_gate=fail) while answer says fos_gate=pass
        if "safety_factor" in cot_field_vals and "fos_gate" in body_ws:
            cot_fos = cot_field_vals["safety_factor"]
            expected_gate = "pass" if cot_fos >= 1.5 else "fail"
            actual_gate = str(body_ws["fos_gate"]).strip().lower()
            if expected_gate != actual_gate:
                faithfulness_conflicts.append(
                    f"思维链安全门自相矛盾: <think> 算出 FOS={cot_fos:.3g} (应为 {expected_gate})，但输出 fos_gate={actual_gate!r}"
                )

        # Check G00 rapid plunge faithfulness between <think> and G-code body
        if re.search(r"\b(?:G00|G0)\b", body_text, re.I):
            stock_top = 0.0
            if scenario and isinstance(scenario.get("inputs"), dict):
                stock_top = float(scenario["inputs"].get("stock_top", scenario["inputs"].get("stock_top_z_mm", 0.0)))
            z_rapids = re.findall(r"\b(?:G00|G0)(?![0-9])[^Z\n]*Z(-?\d+(?:\.\d+)?)", body_text, re.I)
            for zs in z_rapids:
                zv = float(zs)
                if zv < stock_top:
                    gate_violations.append(f"刀轨含致命 G00 快速下扎碰撞: Z={zv} < 毛坯顶面 {stock_top}")

        # Score computation
        score = 1.0
        if not has_think and require_think:
            score -= 0.5
        if ungrounded:
            score -= 0.35 * len(ungrounded)
        if arith_errors:
            score -= 0.4 * len(arith_errors)
        if faithfulness_conflicts:
            score = 0.0  # Unfaithful CoT is a hard veto
        if gate_violations:
            score = 0.0

        score = round(max(0.0, min(1.0, score)), 4)
        passed = (
            (has_think or not require_think)
            and not ungrounded
            and not arith_errors
            and not faithfulness_conflicts
            and not gate_violations
        )

        h = hashlib.sha256(f"{raw_output}_{prompt}_{passed}".encode("utf-8", "replace")).hexdigest()[:10]
        return CoTVerificationReport(
            run_id=f"COT_AUDIT_{h}",
            passed=passed,
            has_think_block=has_think,
            stages_covered=stages_covered,
            steps=steps,
            extracted_derivations=extracted_der,
            ungrounded_literals=ungrounded,
            arithmetic_errors=arith_errors,
            faithfulness_conflicts=faithfulness_conflicts,
            gate_violations=gate_violations,
            overall_cot_score=score,
            basis="measured",
        )

    @classmethod
    def falsifiable_cot_probe(cls) -> bool:
        """Rule 4 Falsifiability Gate:
        Injects 4 distinct bad CoT samples (arithmetic lie, unfaithful answer, ungrounded literal, missing think)
        and 1 clean synthesized trajectory. Asserts all 4 bad samples FAIL and the clean sample PASSES.
        """
        scenario = {"task": "fea_fos", "inputs": {"Sy": 355.0, "sigma": 180.0}}
        prompt = "【场景】梁受载：材料屈服强度 Sy=355 MPa，最大 von Mises 应力 sigma=180 MPa。"

        # 1. Clean synthesized CoT -> MUST PASS
        clean_traj = cls.synthesize_cot(scenario, prompt=prompt)
        clean_rep = cls.verify_cot_faithfulness(clean_traj.full_response, prompt=prompt, scenario=scenario)
        if not clean_rep.passed or clean_rep.overall_cot_score < 0.95:
            return False

        # 2. Bad sample A: Arithmetic error inside <think> (355 / 180 = 2.60) -> MUST FAIL
        bad_arith = (
            "<think>\n[STAGE 4: SYMBOLIC_SUBSTITUTION_AND_DERIVATION] safety_factor = 355 / 180 = 2.60\n</think>\n"
            '{"world_state": {"safety_factor": 2.60, "fos_gate": "pass"}}'
        )
        rep_arith = cls.verify_cot_faithfulness(bad_arith, prompt=prompt, scenario=scenario)
        if rep_arith.passed or not rep_arith.arithmetic_errors:
            return False

        # 3. Bad sample B: Unfaithful CoT (<think> derives 1.9722, but JSON outputs 1.15 / fail) -> MUST FAIL
        bad_unfaithful = (
            "<think>\n[STAGE 4: SYMBOLIC_SUBSTITUTION_AND_DERIVATION] safety_factor = 355 / 180 = 1.9722\n</think>\n"
            '{"world_state": {"safety_factor": 1.15, "fos_gate": "fail"}}'
        )
        rep_unfaithful = cls.verify_cot_faithfulness(bad_unfaithful, prompt=prompt, scenario=scenario)
        if rep_unfaithful.passed or not rep_unfaithful.faithfulness_conflicts:
            return False

        # 4. Bad sample C: Ungrounded hallucinated literal in <think> (uses 500 instead of 355) -> MUST FAIL
        bad_ungrounded = (
            "<think>\n[STAGE 4: SYMBOLIC_SUBSTITUTION_AND_DERIVATION] safety_factor = 500 / 180 = 2.7778\n</think>\n"
            '{"world_state": {"safety_factor": 2.7778, "fos_gate": "pass"}}'
        )
        rep_ungrounded = cls.verify_cot_faithfulness(bad_ungrounded, prompt=prompt, scenario=scenario)
        if rep_ungrounded.passed or not rep_ungrounded.ungrounded_literals:
            return False

        # 5. Bad sample D: Missing <think> block when required -> MUST FAIL
        bad_no_think = '{"world_state": {"safety_factor": 1.9722, "fos_gate": "pass"}}'
        rep_no_think = cls.verify_cot_faithfulness(bad_no_think, prompt=prompt, scenario=scenario, require_think=True)
        if rep_no_think.passed or rep_no_think.has_think_block:
            return False

        return True
