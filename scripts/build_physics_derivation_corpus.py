#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Forward-generate a verifiable physics corpus (gold never comes from a model).

Why forward and not from the runs: on ``_eval_phys_v3_*`` only 7/30 (ties) and 9/30 (base) answers
were reproducible by the solver, so model output is mostly negative data. Here every row is
generated from the law registry plus the runtime solver, and a row is kept only if all three hold:

  1. the registry agrees with ``wm_verifier.recompute`` field by field (catches parameter draws that
     trip the solver's clamps -- e.g. a flange whose bolt holes eat the whole annulus);
  2. the shipped graders score the gold at exactly 100 (``world_state_verified`` +
     ``derivation_verified`` + ``physics_invariant``), so nothing enters the corpus that the ruler
     itself would fail;
  3. the draw is not a near-copy of an eval scenario (holdout separation, per
     [[feedback-pretrained-pipeline-fit-set]]).

Rejects are counted and printed -- a silent drop would be the same假绿 this script exists to remove.

Usage:
    python scripts/build_physics_derivation_corpus.py --rows 2400
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

import wm_verifier as wm  # noqa: E402
from build_physics_acceptance_cases import FAMILIES, _given, _prompt, _round_sig  # noqa: E402
from virtu_eval.audit_case_arithmetic import eval_expr  # noqa: E402
from virtu_eval.derivation import resolve  # noqa: E402
from virtu_eval.graders import score_case  # noqa: E402
from wm_contract import SYSTEM  # noqa: E402

CASE_DIR = os.path.join(ROOT, "data", "benchmark", "virtu_eval_phys_v1")
OUT_DIR = os.path.join(ROOT, "data", "physics_derivation_v1")

MATERIALS = {"steel": 7.85e-3, "aluminium": 2.7e-3, "titanium": 4.43e-3,
             "stainless": 8.0e-3, "brass": 8.5e-3, "cast_iron": 7.2e-3}

# (low, high) physically sensible draw ranges, same units the prompts use.
RANGES = {"doc": (0.4, 6.0), "woc": (3.0, 25.0), "vf": (80.0, 2400.0), "L": (15.0, 500.0),
          "stock_vol": (2e4, 2e6), "f": (0.05, 0.5), "r_eps": (0.2, 1.6),
          "Sy": (150.0, 900.0), "sigma": (40.0, 700.0), "upper_dev": (-0.3, 0.4),
          "lower_dev": (-0.4, 0.3), "r_out": (30.0, 220.0), "r_bore": (8.0, 120.0),
          "t": (4.0, 45.0), "r_hole": (2.5, 16.0), "D": (5.0, 250.0), "ap": (0.15, 6.0),
          "vc": (40.0, 450.0), "feature_vol": (80.0, 3e4), "before": (5e2, 2e6),
          "z_safe": (15.0, 90.0), "stock_top": (0.0, 70.0), "n_max": (500.0, 12000.0)}
TASKS = ["removal", "roughness", "fea_fos", "collision", "tolerance", "geom_delta", "design",
          "process", "adapt_material", "adapt_machine"]


def _u(rng, key):
    lo, hi = RANGES[key]
    return round(rng.uniform(lo, hi), 4)


def _draw(task, rng):
    """Sample one scenario. Structural feasibility is enforced here; the two gates do the rest."""
    if task == "removal":
        return {"doc": _u(rng, "doc"), "woc": _u(rng, "woc"), "vf": _u(rng, "vf"),
                "L": _u(rng, "L"), "rho": rng.choice(list(MATERIALS.values())),
                "stock_vol": _u(rng, "stock_vol")}
    if task == "roughness":
        return {"f": _u(rng, "f"), "r_eps": _u(rng, "r_eps")}
    if task in ("fea_fos", "adapt_material"):
        # keep FOS on both sides of the 1.5 gate so the corpus is not all-passing
        sigma = _u(rng, "sigma")
        Sy = round(sigma * rng.choice([rng.uniform(0.6, 1.4), rng.uniform(1.5, 4.0)]), 3)
        return {"Sy": Sy, "sigma": sigma}
    if task == "tolerance":
        return {"tols": [round(rng.uniform(0.01, 0.2), 4) for _ in range(rng.randint(3, 6))],
                "upper_dev": _u(rng, "upper_dev"), "lower_dev": _u(rng, "lower_dev")}
    if task == "geom_delta":
        before = _u(rng, "before")
        return {"feature_vol": round(before * rng.uniform(0.02, 0.45), 4), "before": before}
    if task == "design":
        r_out = _u(rng, "r_out")
        r_bore = round(r_out * rng.uniform(0.15, 0.7), 4)
        r_hole = _u(rng, "r_hole")
        return {"r_out": r_out, "r_bore": r_bore, "t": _u(rng, "t"),
                "n_holes": rng.randint(2, 24), "r_hole": r_hole,
                "rho": rng.choice(list(MATERIALS.values()))}
    if task == "process":
        return {"D": _u(rng, "D"), "L": _u(rng, "L"), "ap": _u(rng, "ap"), "f": _u(rng, "f"),
                "vc": _u(rng, "vc"), "r_eps": _u(rng, "r_eps")}
    if task == "adapt_machine":
        D, vc = _u(rng, "D"), _u(rng, "vc")
        n = 1000.0 * vc / (math.pi * D)
        # straddle the machine limit so within_limit is not a constant
        n_max = round(n * rng.choice([rng.uniform(0.5, 0.95), rng.uniform(1.05, 3.0)]), 3)
        return {"D": D, "vc": vc, "n_max": n_max}
    if task == "collision":
        z_safe, stock_top = _u(rng, "z_safe"), _u(rng, "stock_top")
        verdict = rng.randrange(3)
        if verdict == 0:      # red: gouge into the stock
            z_min = round(stock_top - rng.uniform(0.5, min(12.0, max(0.6, stock_top))), 4)
        elif verdict == 1:    # yellow: inside the +1mm risk band, no gouge
            z_min = round(stock_top + rng.uniform(0.0, 0.95), 4)
        else:                 # green: above the safe plane
            z_min = round(z_safe + rng.uniform(1.0, 25.0), 4)
        return {"z_safe": z_safe, "z_min_rapid": z_min, "stock_top": stock_top}
    raise KeyError(task)


def _close(a, b, rel=0.02):
    if isinstance(a, (list, tuple)) or isinstance(b, (list, tuple)):
        if not (isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)) and len(a) == len(b)):
            return False
        return all(_close(x, y, rel) for x, y in zip(a, b))
    try:
        fa, fb = float(a), float(b)
    except (TypeError, ValueError):
        return a == b
    return abs(fa - fb) <= rel * max(abs(fa), 1e-9)


def _near_eval(task, inputs, eval_sigs):
    """Reject draws that are near-copies of a shipped eval scenario for the same task."""
    for e_task, e_inputs in eval_sigs:
        if e_task != task or set(e_inputs) != set(inputs):
            continue
        if all(_close(e_inputs[k], inputs[k]) for k in e_inputs):
            return True
    return False


def _gold_criteria(scenario, tier="medium"):
    ref = wm.recompute(scenario)
    graded = [k for k, v in ref.items() if v is None or isinstance(v, (int, float, str))]
    return [
        {"type": "json_object", "key": "json_shape", "weight": 1,
         "required_keys": ["world_state", "derivation"]},
        {"type": "physics_invariant", "key": "invariants", "weight": 1, "scenario": scenario},
        {"type": "derivation_verified", "key": "law_and_binding", "weight": 3,
         "scenario": scenario, "tol_rel": 0.01},
        {"type": "world_state_verified", "key": "reproduced_by_solver", "weight": 3,
         "scenario": scenario, "tol_rel": 0.01, "must_compare": graded},
    ]


def _load_eval_signatures():
    sigs = []
    for fname in sorted(os.listdir(CASE_DIR)):
        if not fname.endswith(".jsonl"):
            continue
        for line in open(os.path.join(CASE_DIR, fname), encoding="utf-8"):
            if not line.strip():
                continue
            case = json.loads(line)
            for crit in case["criteria"]:
                if crit.get("type") == "world_state_verified":
                    inputs = crit["scenario"]["inputs"]
                    flat = {k: v for k, v in inputs.items()}
                    sigs.append((crit["scenario"]["task"], flat))
                    break
    return sigs


def build(rows, seed):
    rng = random.Random(seed)
    eval_sigs = _load_eval_signatures()
    out_rows, rejects = [], collections.Counter()
    per_task = collections.Counter()
    attempt = 0
    while len(out_rows) < rows and attempt < rows * 12:
        attempt += 1
        task = TASKS[attempt % len(TASKS)]
        try:
            inputs = _draw(task, rng)
        except ValueError:
            rejects["unfeasible_draw"] += 1
            continue
        scenario = {"task": task, "inputs": inputs}
        if _near_eval(task, inputs, eval_sigs):
            rejects["too_close_to_eval_scenario"] += 1
            continue

        ref = wm.recompute(scenario)
        if not ref:
            rejects["solver_no_reference"] += 1
            continue
        # gate 1: registry == solver, so clamped/inconsistent geometry cannot slip in
        try:
            deriv = resolve(task, inputs)
        except ValueError:
            rejects["registry_cannot_resolve"] += 1
            continue
        bad = False
        for field, expr in deriv.items():
            if not (isinstance(ref.get(field), (int, float)) and not isinstance(ref.get(field), bool)):
                continue
            if abs(eval_expr(expr)[0] - ref[field]) > 1e-6 * max(abs(ref[field]), 1.0):
                bad = True
                break
        if bad:
            rejects["registry_solver_disagreement"] += 1
            continue

        gold_obj = {"world_state": _round_sig(ref), "derivation": deriv}
        text = json.dumps(gold_obj, ensure_ascii=False)
        keys = sorted(ref)
        prompt = _prompt(FAMILIES[task]["zh"], inputs, keys, ask_derivation=True)
        # gate 2: the shipped ruler must accept this row at 100
        scored = score_case(text, _gold_criteria(scenario))
        if scored["score"] < 100.0:
            rejects["gold_fails_grader"] += 1
            continue

        per_task[task] += 1
        out_rows.append({"messages": [{"role": "system", "content": SYSTEM},
                                      {"role": "user", "content": prompt},
                                      {"role": "assistant", "content": text}],
                         # train_turnkey.py reads rec["messages"] only; the scenario rides along so a
                         # later gate can re-grade this row exactly instead of parsing the prompt back.
                         "scenario": scenario,
                         "task": task})
    return out_rows, rejects, per_task, attempt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=2400)
    ap.add_argument("--seed", type=int, default=20261104)
    ap.add_argument("--out-dir", default=OUT_DIR)
    args = ap.parse_args()

    if not os.path.isdir(CASE_DIR):
        raise SystemExit(f"eval case dir missing: {CASE_DIR}")
    rows, rejects, per_task, attempts = build(args.rows, args.seed)
    if len(rows) < args.rows:
        raise SystemExit(f"only {len(rows)}/{args.rows} rows survived; rejects={dict(rejects)}")

    os.makedirs(args.out_dir, exist_ok=True)
    path = os.path.join(args.out_dir, "derivation_sft.jsonl")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    est_tokens = [sum(len(m["content"]) for m in r["messages"]) / 1.6 for r in rows]
    est_tokens.sort()
    digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
    manifest = {"file": os.path.basename(path), "rows": len(rows), "seed": args.seed,
                "sha256": digest, "bytes": os.path.getsize(path),
                "rejects": dict(rejects), "attempts": attempts,
                "per_task": dict(per_task),
                "est_tokens_p50": round(est_tokens[len(est_tokens) // 2]),
                "est_tokens_p95": round(est_tokens[int(len(est_tokens) * 0.95)]),
                "est_tokens_max": round(est_tokens[-1]),
                "note": "gold = virtu_eval.derivation.resolve + wm_verifier.recompute, "
                        "every row scored 100 by the shipped graders before inclusion"}
    with open(os.path.join(args.out_dir, "MANIFEST.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"[ok] {len(rows)} rows -> {os.path.relpath(path, ROOT)}")
    print(f"     sha256={digest[:16]}...  rejects={dict(rejects) or 'none'}  attempts={attempts}")
    print(f"     est tokens p50={manifest['est_tokens_p50']} p95={manifest['est_tokens_p95']} "
          f"max={manifest['est_tokens_max']}")
    print(f"     per task: {dict(per_task)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
