"""Independent recomputation audit for single-answer machining arithmetic.

The expected value comes from the prompt, not from the gold derivation. Cases
with several numeric targets are skipped here and covered by the derivation
audit. A run that checks zero cases is an error, never a passing audit.
"""
from __future__ import annotations

import json
import math
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "benchmark", "virtu_eval_v1", "reasoning.jsonl")


def _number(pattern, text, flags=re.I):
    match = re.search(pattern, text, flags)
    return float(match.group(1)) if match else None


def _single_target(case):
    criteria = [c for c in case.get("criteria", []) if c.get("type") == "numeric_near"]
    if len(criteria) != 1:
        return None
    return float(criteria[0]["value"])


def recompute(case):
    """Return (expected, target) for supported single-answer cases, else None."""
    target = _single_target(case)
    if target is None:
        return None
    prompt = case["prompt"]

    if all(token in prompt for token in ("MRR", "ap", "ae", "Vf")):
        ap = _number(r"\bap\s*=\s*([\d.]+)", prompt)
        ae = _number(r"\bae\s*=\s*([\d.]+)", prompt)
        vf = _number(r"\bVf\s*=\s*([\d.]+)", prompt)
        if None not in (ap, ae, vf):
            divisor = 1000.0 if ("cm³" in prompt or "cm^3" in prompt) else 1.0
            return ap * ae * vf / divisor, target

    if "1000" in prompt and "Vc" in prompt and "π" in prompt and "转速" in prompt:
        vc = _number(r"\bVc\s*=\s*([\d.]+)", prompt)
        diameter = _number(r"\bD\s*=\s*([\d.]+)", prompt)
        if None not in (vc, diameter):
            return 1000.0 * vc / (math.pi * diameter), target

    if "Vf" in prompt and "齿数" in prompt and "f*z*n" in prompt:
        feed = _number(r"\bf\s*=\s*([\d.]+)", prompt)
        teeth = _number(r"\bz\s*=\s*(\d+)", prompt)
        rpm = _number(r"\bn\s*=\s*([\d.]+)", prompt)
        if None not in (feed, teeth, rpm):
            return feed * teeth * rpm, target

    if "T=L/Vf" in prompt:
        length = _number(r"\bL\s*=\s*([\d.]+)", prompt)
        vf = _number(r"\bVf\s*=\s*([\d.]+)", prompt)
        if None not in (length, vf):
            wants_seconds = (("单位 s" in prompt or "单位为秒" in prompt or "单位秒" in prompt)
                             and "不要换算成秒" not in prompt)
            factor = 60.0 if wants_seconds else 1.0
            return length / vf * factor, target
    return None


def main(path=PATH):
    mismatches, checked = [], 0
    with open(path, encoding="utf-8") as stream:
        for line in stream:
            case = json.loads(line)
            result = recompute(case)
            if result is None:
                continue
            expected, target = result
            checked += 1
            relative_error = abs(expected - target) / max(abs(expected), 1e-9)
            if relative_error > 0.03:
                mismatches.append(
                    f"{case['id']}: target={target} recomputed={expected:.6f} "
                    f"rel_err={relative_error:.1%}")
    print(f"independently recomputed {checked} numeric golds")
    if checked == 0:
        print("ERROR: no cases matched; this audit cannot be used as pass evidence")
        return 2
    if mismatches:
        print("MISMATCHES:")
        for item in mismatches:
            print("  -", item)
        return 1
    print("all recomputable single-answer reasoning golds match their prompts")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else PATH))
