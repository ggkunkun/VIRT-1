"""Mutation probe: is the thinking-hygiene layer a real gate or a vacuous one?

On the identity-stamped frozen leg the layer changes no score (that leg never emitted
the empty ``<think>`` block), so a score comparison alone cannot tell whether the layer
does anything. AGENTS.md section 8.4 requires every new criterion to ship with a
"plant a bad sample and it must go red" probe, so this script injects the exact artifact
observed on the 2026-11-05 10:23 leg (an empty think block prepended to every answer)
into a clean leg and measures how much it costs and how much the layer gives back.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from statistics import mean

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from virtu_eval.graders import score_case  # noqa: E402
from virtu_eval.provenance import RunIdentity, sha256_file  # noqa: E402
from virtu_eval.report import DIM_WEIGHTS  # noqa: E402
from virtu_omni.serving.answer_pipeline import clean_served_answer  # noqa: E402

INJECTION = "<think>\n\n</think>\n\n"


def load_cases(case_dir):
    cases = {}
    for fn in sorted(os.listdir(case_dir)):
        if fn.endswith(".jsonl"):
            for line in open(os.path.join(case_dir, fn), encoding="utf-8"):
                c = json.loads(line)
                cases[c["id"]] = c
    return cases


def weighted(per_dim):
    ws = sum(DIM_WEIGHTS[d] for d in per_dim)
    return round(sum(mean(v) * DIM_WEIGHTS[d] for d, v in per_dim.items()) / ws, 2) if ws else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="runs/eval/fullboard_20261105_0930/board7__frozen_comp_v5__v4/raw.jsonl")
    ap.add_argument("--case-dir", default="data/benchmark/virtu_eval_v1")
    ap.add_argument("--out", default="runs/eval/hygiene_insurance_20261105")
    args = ap.parse_args()

    raw_path = os.path.join(ROOT, args.raw) if not os.path.isabs(args.raw) else args.raw
    case_dir = os.path.join(ROOT, args.case_dir) if not os.path.isabs(args.case_dir) else args.case_dir
    cases = load_cases(case_dir)
    rows = [json.loads(line) for line in open(raw_path, encoding="utf-8") if line.strip()]

    cols = {"clean_leg": defaultdict(list), "contaminated": defaultdict(list),
            "contaminated_then_hygiene": defaultdict(list)}
    damaged = recovered = over_fixed = 0
    for r in rows:
        case = cases.get(r["case_id"])
        if not case:
            continue
        dim = case["dimension"]
        original = r["response"]
        contaminated = INJECTION + original
        repaired = clean_served_answer(case["prompt"], contaminated).text
        s0 = score_case(original, case["criteria"])["score"]
        s1 = score_case(contaminated, case["criteria"])["score"] if contaminated else 0.0
        s2 = score_case(repaired, case["criteria"])["score"] if repaired else 0.0
        cols["clean_leg"][dim].append(s0)
        cols["contaminated"][dim].append(s1)
        cols["contaminated_then_hygiene"][dim].append(s2)
        if s1 < s0 - 0.01:
            damaged += 1
            if s2 >= s0 - 0.01:
                recovered += 1
        if s2 > s0 + 0.01:
            over_fixed += 1

    identity = RunIdentity.capture(
        model_ids=(), case_dirs=[args.case_dir],
        extra={"leg": args.raw, "leg_sha256": sha256_file(raw_path), "rows": len(rows),
               "injection": "empty  think block prepended to every answer"})
    out_dir = os.path.join(ROOT, args.out)
    os.makedirs(out_dir, exist_ok=True)

    summary = {
        "run_id": identity.run_id,
        "n": len(rows),
        "weighted": {k: weighted(v) for k, v in cols.items()},
        "cost_of_contamination": round(weighted(cols["contaminated"]) - weighted(cols["clean_leg"]), 2),
        "recovered_by_hygiene": round(weighted(cols["contaminated_then_hygiene"])
                                      - weighted(cols["contaminated"]), 2),
        "residual_after_hygiene": round(weighted(cols["contaminated_then_hygiene"])
                                        - weighted(cols["clean_leg"]), 2),
        "cases_damaged": damaged,
        "cases_recovered": recovered,
        "cases_over_fixed": over_fixed,
        "dims": {k: {d: round(mean(v), 2) for d, v in sorted(vals.items())}
                 for k, vals in cols.items()},
    }
    json.dump(summary, open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    identity.write(os.path.join(out_dir, "run_identity.json"))
    print(json.dumps({k: summary[k] for k in (
        "run_id", "n", "weighted", "cost_of_contamination", "recovered_by_hygiene",
        "residual_after_hygiene", "cases_damaged", "cases_recovered", "cases_over_fixed")},
        ensure_ascii=False, indent=2))
    if damaged == 0:
        print("PROBE INCONCLUSIVE: the injected artifact cost nothing on this leg; "
              "the gate is untested here")
        return 3
    if recovered != damaged or abs(summary["residual_after_hygiene"]) > 0.05:
        print("PROBE RED: hygiene does not fully undo the damage it claims to fix")
        return 4
    print("PROBE GREEN: contamination costs points and hygiene restores every one of them")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
