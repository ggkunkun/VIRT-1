#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Recursive Blind-Test Engine for Virtu Manufacturing Model
=============================================================================
Performs a fully randomized, double-blind evaluation across all 8 industrial
engineering domains with self-recursive refinement loops.

Blind Protocol:
  1. The model is given only the task requirements, with no gold answers or rubrics.
  2. If the response fails deterministic oracle verification, feedback is sanitized
     into blind diagnostics (indicating failure modes like schema error, physical
     invariant breach, out-of-tolerance, or syntax error without leaking the answer).
  3. The model recursively self-reflects, re-derives, and self-corrects until 0 errors
     or circuit-breaker limit (max 4 rounds).
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from virtu_eval.graders import score_case, parse_json_candidate

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

DOMAIN_FILES = {
    "toolcall": os.path.join(ROOT, "data", "benchmark", "virtu_eval_v1", "toolcall.jsonl"),
    "reasoning": os.path.join(ROOT, "data", "benchmark", "virtu_eval_v1", "reasoning.jsonl"),
    "knowledge": os.path.join(ROOT, "data", "benchmark", "virtu_eval_v1", "knowledge.jsonl"),
    "instruction": os.path.join(ROOT, "data", "benchmark", "virtu_eval_v1", "instruction.jsonl"),
    "boundary": os.path.join(ROOT, "data", "benchmark", "virtu_eval_v1", "boundary.jsonl"),
    "generation": os.path.join(ROOT, "data", "benchmark", "virtu_eval_v1", "generation.jsonl"),
    "generalization": os.path.join(ROOT, "data", "benchmark", "virtu_eval_v1", "generalization.jsonl"),
    "physics_worldmodel": os.path.join(ROOT, "data", "benchmark", "virtu_eval_phys_v1", "physics.jsonl"),
}


def ollama_generate(model: str, prompt: str, system: Optional[str] = None,
                    num_predict: int = 512, temperature: float = 0.0,
                    timeout: int = 120) -> Tuple[str, float]:
    """Call Ollama API with think=False to prevent token exhaustion."""
    body: Dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {
            "temperature": temperature,
            "seed": 2026,
            "num_predict": num_predict,
        },
    }
    if system:
        body["system"] = system

    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    resp = json.load(OPENER.open(req, timeout=timeout))
    latency = round(time.time() - t0, 3)
    return resp.get("response", "").strip(), latency


def sanitize_blind_feedback(criteria_results: List[Dict[str, Any]]) -> List[str]:
    """Generate blind error diagnostics without leaking gold answers or target values."""
    feedback = []
    for c in criteria_results:
        if c.get("passed"):
            continue
        c_type = c.get("type", "")
        key = c.get("key", "")
        evidence = c.get("evidence", "")

        if c_type == "json_object":
            feedback.append(f"Format Failure: Output must be a strictly valid JSON object containing required keys. Avoid markdown formatting or invalid syntax.")
        elif c_type == "enum_field":
            feedback.append(f"Field Domain Error: The value specified for action/enum field '{key}' is invalid or outside the recognized domain standard.")
        elif c_type == "numeric_near":
            feedback.append(f"Mathematical/Physics Error: Calculated numerical parameter '{key}' deviates beyond allowable physical tolerance. Re-verify formulas, cutting parameters, and unit conversions.")
        elif c_type == "physics_invariant":
            feedback.append(f"Physical Invariant Breach: Conservation laws or physical boundary conditions violated (e.g. material removal must have delta_volume < 0, FOS >= 1.5 gating consistency).")
        elif c_type == "world_state_verified":
            feedback.append(f"World Model Recalculation Mismatch: Physical closed-loop solver recomputation failed for '{key}'. Verify mechanical principles, cutting geometry, or material properties.")
        elif c_type == "gcode_structure":
            feedback.append(f"NC Syntax Error: G-code block structure invalid. Missing required safety retract (G00 Z), tool definition, feed mode, or spindle commands.")
        elif c_type == "refusal":
            feedback.append(f"Safety Gate Violation: The prompt contains hazardous or out-of-range operating conditions. You must enforce machine safety boundaries and refuse dangerous execution.")
        elif c_type == "python_parses":
            feedback.append(f"Code Syntax Error: Python script failed AST parse validation.")
        elif c_type == "literal_all" or c_type == "literal_any":
            feedback.append(f"Content Requirement Error: Missing essential engineering specifications or keywords required for '{key}'.")
        else:
            feedback.append(f"Verification Check Failed: Check '{key}' did not pass standard industrial criteria.")
    return feedback


def build_recursive_prompt(original_prompt: str, prev_response: str,
                           blind_feedback: List[str], round_idx: int) -> str:
    """Construct prompt for recursive self-correction."""
    feedback_bullets = "\n".join([f"- {fb}" for fb in blind_feedback])
    return (
        f"{original_prompt}\n\n"
        f"--- [RECURSIVE CORRECTION ROUND {round_idx}] ---\n"
        f"Your previous response failed external verification oracle checks with the following diagnostics:\n"
        f"{feedback_bullets}\n\n"
        f"CRITICAL INSTRUCTIONS FOR SELF-CORRECTION:\n"
        f"1. Carefully reflect on the diagnostics and identify where your derivation, logic, or format was wrong.\n"
        f"2. Re-compute calculations, correct field names, and eliminate invalid syntax or physical breaches.\n"
        f"3. Output ONLY your revised, fully corrected complete response."
    )


def load_stratified_cases(seed: int = 20261104, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Sample 1 Easy, 1 Medium, 1 Hard case from each of the 8 domains."""
    random.seed(seed)
    selected_cases = []

    for domain, fpath in DOMAIN_FILES.items():
        if not os.path.exists(fpath):
            raise FileNotFoundError(f"Benchmark file missing: {fpath}")

        with open(fpath, "r", encoding="utf-8") as f:
            cases = [json.loads(line) for line in f if line.strip()]

        by_tier = {"easy": [], "medium": [], "hard": []}
        for c in cases:
            tier = c.get("tier", "medium")
            if tier in by_tier:
                by_tier[tier].append(c)

        for tier in ["easy", "medium", "hard"]:
            pool = by_tier[tier]
            if not pool:
                pool = cases
            chosen = random.choice(pool)
            chosen["_domain"] = domain
            selected_cases.append(chosen)

    if limit is not None and limit > 0:
        selected_cases = selected_cases[:limit]

    return selected_cases


def run_recursive_test(model: str = "virtu-wm-v3:latest",
                       max_rounds: int = 4,
                       limit: Optional[int] = None,
                       output_path: Optional[str] = None) -> Dict[str, Any]:
    cases = load_stratified_cases(limit=limit)
    print(f"================================================================================")
    print(f"  VIRTU MODEL ALL-DOMAIN RECURSIVE BLIND TEST BENCHMARK")
    print(f"  Target Model : {model}")
    print(f"  Total Cases  : {len(cases)} (8 domains x 3 difficulty tiers: Easy, Med, Hard)")
    print(f"  Max Rounds   : {max_rounds} (Round 1: Zero-shot blind, Rounds 2-{max_rounds}: Recursive repair)")
    print(f"  Blind Mode   : Strict Oracle Diagnostics (Zero Gold Answer Leakage)")
    print(f"================================================================================\n")

    summary_records = []
    domain_stats = {d: {"total": 0, "r1_pass": 0, "final_pass": 0, "rounds_to_pass": []}
                    for d in DOMAIN_FILES.keys()}

    t_start = time.time()

    for idx, case in enumerate(cases, 1):
        case_id = case.get("id", f"case_{idx:02d}")
        domain = case["_domain"]
        tier = case.get("tier", "medium")
        prompt = case.get("prompt", "")
        system = case.get("system", None)
        criteria = case.get("criteria", [])

        print(f"[{idx:02d}/{len(cases):02d}] Domain: {domain:<18} | Tier: {tier:<6} | ID: {case_id}", flush=True)

        history = []
        converged = False
        final_round = 0
        final_score = 0.0

        current_prompt = prompt

        for r in range(1, max_rounds + 1):
            resp, latency = ollama_generate(model, current_prompt, system=system)
            grading = score_case(resp, criteria)
            score = grading.get("score", 0.0)
            all_passed = grading.get("all_passed", False)

            step_record = {
                "round": r,
                "latency_s": latency,
                "score": score,
                "all_passed": all_passed,
                "response_snippet": resp[:120].replace("\n", " "),
                "failing_criteria": [c for c in grading.get("criteria", []) if not c.get("passed")],
            }
            history.append(step_record)

            print(f"   -> Round {r}: Score {score:>6.2f}% ({'PASS 0-ERROR' if all_passed else 'FAIL'}) [{latency}s]", flush=True)

            if all_passed:
                converged = True
                final_round = r
                final_score = score
                break

            # If not passed and rounds remain, prepare blind feedback
            if r < max_rounds:
                blind_fb = sanitize_blind_feedback(grading.get("criteria", []))
                # Check for stagnation: if identical response as previous round
                if len(history) >= 2 and history[-1]["response_snippet"] == history[-2]["response_snippet"]:
                    print(f"      [Circuit Breaker] Response stagnation detected. Halting recursion.", flush=True)
                    final_round = r
                    final_score = score
                    break
                current_prompt = build_recursive_prompt(prompt, resp, blind_fb, r + 1)
            else:
                final_round = r
                final_score = score

        domain_stats[domain]["total"] += 1
        if history[0]["all_passed"]:
            domain_stats[domain]["r1_pass"] += 1
        if converged:
            domain_stats[domain]["final_pass"] += 1
            domain_stats[domain]["rounds_to_pass"].append(final_round)

        case_record = {
            "case_id": case_id,
            "domain": domain,
            "tier": tier,
            "prompt": prompt,
            "converged": converged,
            "rounds_needed": final_round if converged else None,
            "initial_score": history[0]["score"],
            "final_score": final_score,
            "rounds_history": history,
        }
        summary_records.append(case_record)
        print(flush=True)

    total_time = round(time.time() - t_start, 2)

    # Compile overall metrics
    total_cases = len(cases)
    r1_passes = sum(1 for r in summary_records if r["rounds_history"][0]["all_passed"])
    final_passes = sum(1 for r in summary_records if r["converged"])
    all_rounds = [r["rounds_needed"] for r in summary_records if r["rounds_needed"] is not None]
    avg_rounds_when_converged = round(sum(all_rounds) / len(all_rounds), 2) if all_rounds else 0.0

    report = {
        "model": model,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_cases": total_cases,
        "total_time_seconds": total_time,
        "round_1_pass_count": r1_passes,
        "round_1_pass_rate": round(100.0 * r1_passes / total_cases, 2),
        "final_pass_count": final_passes,
        "final_pass_rate": round(100.0 * final_passes / total_cases, 2),
        "average_rounds_to_zero_error": avg_rounds_when_converged,
        "domain_statistics": domain_stats,
        "detailed_results": summary_records,
    }

    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"[Export] Saved benchmark report to: {output_path}")

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Recursive Blind Test Engine")
    parser.add_argument("--model", type=str, default="virtu-wm-v3:latest")
    parser.add_argument("--rounds", type=int, default=4)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output", type=str, default=os.path.join(ROOT, "benchmarks", "VIRTU_RECURSIVE_BLIND_TEST_RESULTS.json"))
    args = parser.parse_args()

    run_recursive_test(model=args.model, max_rounds=args.rounds, limit=args.limit, output_path=args.output)
