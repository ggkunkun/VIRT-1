"""Independent arithmetic audit for the reasoning / generalization case sets.

The prompts state their own formula, so the gold's derivation chain can be checked
without trusting the author: every '=' segment of the derivation is evaluated as
arithmetic and consecutive segments must agree. This catches fabricated or slipped
arithmetic, which a gold-scores-100 check cannot (that only proves the criteria and
the gold text are consistent with each other).
"""
from __future__ import annotations

import json
import math
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASE_DIR = os.path.join(ROOT, "data", "benchmark", "virtu_eval_v1")
FILES = ["reasoning.jsonl", "generalization.jsonl"]

SEG_RE = re.compile(r"([^=]+)=([^=]+)")
NUM_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")


_TOKEN_RE = re.compile(
    r"\d+(?:\.\d+)?|\(|\)|\+|\-|\*|/|\^|pi|sqrt|sin|cos|tan|asin|acos|atan")
_UNIT_RE = re.compile(r"^[A-Za-zμ°%/]+")
_HAS_PI_RE = re.compile(r"π|\bpi\b", re.I)
_DEG_HINT_RE = re.compile(r"°|度|(?<![\d.])180(?![\d.])|(?<![\d.])360(?![\d.])")


def eval_expr(expr):
    """Evaluate a complete arithmetic expression, returning (value, unit).

    A segment is accepted only when its numeric prefix ends cleanly. This
    rejects ``1000*Vc`` (the prefix would end in an operator) instead of
    silently evaluating just ``1000``, while still accepting values followed
    by units or prose such as ``2387.3241 r/min``.
    """
    s = expr.replace("，", ",").replace(" ", "").replace(",", "")
    s = (s.replace("π", "pi").replace("×", "*").replace("·", "*").replace("÷", "/")
          .replace("√", "sqrt").replace("²", "**2").replace("³", "**3"))
    pos, tokens = 0, []
    while pos < len(s):
        match = _TOKEN_RE.match(s, pos)
        if not match:
            break
        tokens.append(match.group(0))
        pos = match.end()
    if not tokens:
        return None
    expression = "".join(tokens)
    if not expression or expression[-1] in "+-*/^(":
        return None
    leftover = s[pos:]
    if leftover and (leftover[0] in "+-*/^(" or leftover[0].isdigit()):
        return None
    unit_match = _UNIT_RE.match(leftover)
    unit = unit_match.group(0) if unit_match else ""
    expression = expression.replace("^", "**")
    use_deg = bool(_DEG_HINT_RE.search(expr)) and not bool(_HAS_PI_RE.search(expr))

    def _trig(fn):
        return (lambda x, _fn=fn: _fn(math.radians(x))) if use_deg else fn

    env = {
        "pi": math.pi, "sqrt": math.sqrt, "e": math.e,
        "sin": _trig(math.sin), "cos": _trig(math.cos), "tan": _trig(math.tan),
        "asin": math.asin, "acos": math.acos, "atan": math.atan,
    }
    try:
        val = eval(expression, {"__builtins__": {}}, env)
    except Exception:  # noqa: BLE001
        return None
    if isinstance(val, (int, float)) and math.isfinite(float(val)):
        return float(val), unit
    return None


def final_number(text):
    nums = [float(x.replace(",", "")) for x in NUM_RE.findall(text)]
    return nums[-1] if nums else None


def _units_compatible(unit_a, unit_b):
    """An omitted unit is allowed; two explicit different units are not a chain."""
    return not unit_a or not unit_b or unit_a == unit_b


def audit(case):
    gold = case.get("gold")
    deriv = (gold or {}).get("derivation") if isinstance(gold, dict) else None
    if not deriv:
        return "no_derivation", None
    problems = []
    checked_chains = 0
    vals = []
    # Independent formula clauses are separated by full punctuation. Chinese commas
    # and enumeration commas also separate formulas/tolerance notes.
    for clause in re.split(r"[；;。\n，、→]|->", str(deriv)):
        # Tolerance/explanation notes are not arithmetic and must never be evaluated.
        clause = re.split(r"[，,]\s*tol_", clause, maxsplit=1)[0]
        if re.match(r"\s*tol_", clause) or "literal_" in clause:
            continue
        parts = clause.split("=")
        if len(parts) < 2:
            continue
        evaluated = []
        for seg in parts[1:]:
            parsed = eval_expr(seg)
            if parsed is not None:
                evaluated.append(parsed)
        if len(evaluated) < 2:
            continue
        checked_chains += 1
        for i in range(1, len(evaluated)):
            (prev, prev_unit), (cur, cur_unit) = evaluated[i - 1], evaluated[i]
            if not _units_compatible(prev_unit, cur_unit):
                continue
            if abs(prev) < 1e-9:
                continue
            rel = abs(cur - prev) / max(abs(prev), 1e-9)
            if rel > 0.02:                  # written chains may round between steps
                problems.append(f"[{clause.strip()[:40]}] {prev:.6g} vs {cur:.6g} Δ{rel:.1%}")
        vals.append(evaluated[-1][0])
    if checked_chains == 0:
        return "unparsable", None
    numeric_targets = [
        float(c["value"]) for c in case.get("criteria", [])
        if c.get("type") == "numeric_near" and c.get("value") is not None
    ]
    # For multi-answer cases the last number of the answer text is not a canonical
    # target; the criteria carry all targets and are validated elsewhere.
    if len(numeric_targets) == 1 and vals:
        ans = numeric_targets[0]
        if not any(abs(ans - v) <= max(0.02 * abs(v), 1e-6) for v in vals):
            problems.append(f"最终答案 {ans} 在推导链末端值 {vals} 中找不到对应")
    return ("OK" if not problems else "MISMATCH"), problems


def main():
    stats = {"OK": 0, "MISMATCH": 0, "no_derivation": 0, "unparsable": 0}
    bad = []
    total = 0
    for fname in FILES:
        path = os.path.join(CASE_DIR, fname)
        if not os.path.exists(path):
            print("missing", path)
            continue
        for line in open(path, encoding="utf-8"):
            case = json.loads(line)
            total += 1
            status, problems = audit(case)
            stats[status] += 1
            if status == "MISMATCH":
                bad.append(f"{case['id']}: " + "; ".join(problems))
    print(f"audited {total} cases -> {stats}")
    if bad:
        print("ARITHMETIC PROBLEMS:")
        for b in bad:
            print("  -", b)
        return 1
    if stats["OK"] == 0:
        print("WARNING: 0 条被真正复核（解析器没匹配到任何推导式），此审计为空操作，不可当作通过证据")
        return 2
    print("derivation chains are arithmetically self-consistent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
