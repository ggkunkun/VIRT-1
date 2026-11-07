# -*- coding: utf-8 -*-
"""Recompute any quantity a prompt already defines, instead of trusting the model's乘法.

Measured motivation (``benchmarks/VIRTU_NUMERIC_GAP_2026-11-05.md``, attributable leg
``board7__frozen_comp_v5__v4``, n=210, identity-stamped):

* 100 ``numeric_near`` checks, 54 failed;
* of those 54, 22 are already reachable by ``virtu_real_backend``'s hand-written formula
  ladder (spindle ``n``, ``Vf``, ``MRR``, ``T``, chord, arc) and 32 are not;
* reading the 32, a large share are prompts that **state their own law and every input** --
  ``按 S=1000*VC/(π*D)、F=fz*z*S 出参数``, ``h 约等于 s^2/(8R)``, ``RSS = sqrt(0.20^2+0.10^2+0.05^2)``,
  ``1 英寸=25.4 mm`` -- and the model still mis-multiplies.

Hand-writing one regex per family is the pattern this repository keeps having to undo (the
same spindle formula exists in three places today). This module is the general version:
if the prompt *is* the specification, solve it and compare.

Design rules, inherited from the 测量宪法:

* one parser -- expressions go through ``virtu_eval.audit_case_arithmetic.eval_expr`` and
  symbol substitution through ``virtu_eval.derivation._substitute``; there is no second
  expression engine here;
* fail closed -- an ambiguous symbol (same name, two values), a prompt that transforms its
  own inputs (档位/查表/乘系数), or an unparsable right-hand side yields *no* reference rather
  than a guessed one; publishing a confidently wrong number is worse than not checking;
* it never rewrites the model's text: it returns references, and the caller decides whether
  to append them (``_apply_numeric_corrections`` policy: short answer replaces, long answer
  appends ``[确定性核算]``).

Not covered on purpose, and recorded as such in the ledger: prompts whose answer comes from
a *table* in the prompt (标准公差等级计数、代码对照表、离散圆整表), unit-factor chains
requiring multi-step dimensional analysis (ft→mm), GD&T maximum-material bonus
(must be defined against a datum rule first), and cutter-compensation geometry
(needs a path simulator, not an algebraic substitution).
"""
from __future__ import annotations

import math
import re
import unicodedata

from virtu_eval.audit_case_arithmetic import eval_expr
from virtu_eval.derivation import _substitute

# Same vocabulary the serving guard uses, imported rather than copied so the two can never
# drift apart (agents.md §8.5: one physical rule, one reference).
from virtu_real_backend import _TRANSFORMED_RE  # noqa: F401  (re-exported below as TRANSFORM)

TRANSFORM = _TRANSFORMED_RE

# ``D80``/``z6``/``VC180``/``fz0.2`` style: symbol glued to its value, or separated by ``=``
# or ``:``. Kept deliberately narrow (letter-led, <=7 chars) so prose like ``GB400`` or
# ``IT18`` is not read as an input -- and so the symbol may be a single letter followed by
# digits, which is the notation ``generalization-h04/-h05`` actually uses.
_GIVEN_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?P<sym>[A-Za-zΦØ⌀][A-Za-z0-9_]{0,6})"
    r"(?:\s*(?:[=＝]|[:：])?\s*)(?P<val>[-+]?\d+(?:\.\d+)?)")
# ``S=1000*VC/(π*D)``: the prompt states the law for a symbol it did not give a value for.
# ``≈`` and ``约等于`` count: the scallop family writes ``h 约等于 s^2/(8R)``.
_STATED_RE = re.compile(
    r"(?<![\w)])(?P<sym>[A-Za-zΦØ⌀][A-Za-z0-9_]{0,6})\s*"
    r"(?:[=＝≈]|约等于|近似等于|约为)\s*"
    r"(?P<rhs>[0-9A-Za-zΦØ⌀π×·*÷/+\-().^²³\s]{3,90})")
_NUM_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")
# Diameter written with its symbol glued and no separator (``Ø12 mm``, ``⌀20``) is the most
# common CAD-drawing notation; bind it to ``D`` because every registered law calls it ``D``.
_DIAM_RE = re.compile(r"[Ø⌀Φ]\s*(?P<val>\d+(?:\.\d+)?)")
# A law symbol is a short mathematical name, not a prose word: ``RSS``, ``S``, ``F``, ``h``.
_SYMBOL_MAX = 4
_NOISE = {
    "mm", "min", "mpa", "g", "kg", "s2", "r", "in", "ft", "hb", "it", "gb", "iso",
    "pi", "e", "sqrt", "sin", "cos", "tan", "if", "for", "and", "or",
}
# ``1000*VC/(π*D)`` is a law; ``0.15 mm/`` is a value wearing a unit. The difference is an
# operator sitting between two operands.
_OPERATOR_BETWEEN = re.compile(r"[\w)\]]\s*[+\-*/^]\s*[\w(\[]")
_BANNED_IN_RHS = re.compile(r"[A-Za-zΦØ⌀]{5,}")


def normalize(text: str) -> str:
    out = unicodedata.normalize("NFKC", text or "")
    return (out.replace("×", "*").replace("·", "*").replace("÷", "/")
               .replace("＝", "=").replace("：", "=").replace("，", ","))


def _is_noise(symbol: str) -> bool:
    return symbol.lower() in _NOISE or symbol.isdigit()


def _mask_law_spans(text: str) -> str:
    """Blank out ``X=expression`` spans so ``1000`` inside a law is not read as a given value.

    Without this, ``按 S=1000*VC/(π*D)`` would register ``S=1000`` as an input and the law
    would then be discarded as a re-definition -- the exact failure mode a naked
    symbol/value regex produces.
    """
    masked = list(text)
    for match in _STATED_RE.finditer(text):
        for i in range(match.start(), min(match.end(), len(text))):
            masked[i] = " "
    return "".join(masked)


def given_values(text: str) -> dict:
    """symbol -> the single value the prompt assigns it; ambiguous symbols are dropped.

    Ambiguity vetoes the symbol entirely (``_unique_assignment`` policy): silently choosing
    one of two diameters and publishing it as authoritative is worse than not checking.
    """
    seen: dict = {}
    conflicts: set = set()
    for match in _GIVEN_RE.finditer(_mask_law_spans(text)):
        sym, raw = match.group("sym"), match.group("val")
        if _is_noise(sym):
            continue
        try:
            value = float(raw)
        except ValueError:
            continue
        if value <= 0:
            continue
        if sym in seen and abs(seen[sym] - value) > 1e-12:
            conflicts.add(sym)
            continue
        seen.setdefault(sym, value)
    for sym in conflicts:
        seen.pop(sym, None)
    return seen


def stated_laws(text: str, givens: dict) -> list:
    """[(symbol, rhs_text)] the prompt itself states, excluding re-definitions of a given."""
    out, seen = [], set()
    for match in _STATED_RE.finditer(text):
        sym, rhs = match.group("sym"), match.group("rhs").strip()
        if _is_noise(sym) or sym in seen or rhs.startswith("="):
            continue
        if sym in givens:      # ``r_eps=0.8 mm`` is an input, not a law
            continue
        if not _NUM_RE.search(rhs) and not re.search(r"[A-Za-zΦØ⌀π]", rhs):
            continue
        if not re.search(r"[+*/^\-]", rhs) and "(" not in rhs:
            continue           # a bare number is not a law
        seen.add(sym)
        out.append((sym, rhs))
    return out


def _symbols_in(expression: str) -> set:
    found = set()
    for match in re.finditer(r"[A-Za-zΦØ⌀][A-Za-z0-9_]{0,6}", expression):
        token = match.group(0)
        if not _is_noise(token):
            found.add(token)
    return found


def solve(prompt: str, max_rounds: int = 6) -> dict:
    """Return {"references": [(symbol, expression, value)], "veto": str|None, ...}.

    Chained laws resolve in dependency order: ``S`` from ``VC``/``D``, then ``F`` from ``fz``
    ``z`` and the freshly computed ``S`` -- which is the exact case
    ``generalization-h04``/``-h05`` failed with four wrong numbers at once.
    """
    text = normalize(prompt or "")
    if not text:
        return {"references": [], "veto": "empty_prompt", "givens": {}, "laws": []}
    givens = given_values(text)
    laws = stated_laws(text, givens)
    if not laws:
        return {"references": [], "veto": "no_stated_law", "givens": givens, "laws": []}

    scope = dict(givens)
    resolved, pending, notes = [], list(laws), []
    for _ in range(max_rounds):
        progressed = False
        remaining = []
        for sym, rhs in pending:
            needed = _symbols_in(rhs)
            missing = sorted(s for s in needed if s not in scope)
            if missing:
                remaining.append((sym, rhs))
                continue
            try:
                substituted = _substitute(rhs, scope)
            except (TypeError, ValueError) as exc:  # non-numeric scope entry
                notes.append(f"{sym}:substitute_error:{type(exc).__name__}")
                continue
            parsed = eval_expr(substituted)
            if parsed is None:
                notes.append(f"{sym}:unparsable:{substituted[:60]}")
                continue
            value = parsed[0]
            if not math.isfinite(value):
                notes.append(f"{sym}:nonfinite")
                continue
            scope[sym] = value
            resolved.append((sym, substituted, float(value)))
            progressed = True
        pending = remaining
        if not pending or not progressed:
            break

    veto = None
    if not resolved:
        # Distinguish "we could not parse it" from "this prompt must not be recomputed".
        veto = "transformed_inputs" if TRANSFORM.search(text) else "nothing_resolved"
    elif TRANSFORM.search(text):
        # A table/derating prompt may still resolve algebraically while the *intended* inputs
        # are the transformed ones. Refuse rather than publish a plausible wrong reference.
        veto, resolved = "transformed_inputs", []
    return {"references": resolved, "veto": veto, "givens": givens,
            "laws": [(s, r) for s, r in laws], "pending": [(s, r) for s, r in pending],
            "notes": notes}


def present(text: str, value: float, rel: float = 0.002, abs_tol: float = 0.005) -> bool:
    """Is ``value`` already stated in ``text`` at writing precision? (guard policy, same tol.)"""
    return any(abs(float(x) - value) <= max(abs_tol, abs(value) * rel)
               for x in _NUM_RE.findall(text or ""))


def missing_references(prompt: str, answer: str) -> list:
    """[(label, expression, value)] the prompt defines, the answer omits or mis-states."""
    solved = solve(prompt)
    if solved["veto"]:
        return []
    return [(sym, expr, value) for sym, expr, value in solved["references"]
            if not present(answer, value)]


def render(references: list) -> str:
    return "；".join(f"{sym} = {expr} = {value:g}" for sym, expr, value in references)
