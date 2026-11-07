"""Offline attribution: how much of the board gap does each stack layer actually close?

Runs three post-processors over one frozen leg's responses and re-scores them with the
current ruler, so no GPU is touched and no arm is re-issued:

  raw        - exactly what the model answered
  hygiene    - virtu_omni.serving.answer_pipeline (thinking hygiene + strict compiler)
  backend    - virtu_real_backend._verify_arithmetic_response (deterministic recompute,
               explicit-equation fix, world-state guard, toolcall compile)
  both       - backend applied after hygiene

The backend column is a *system* number, not a model number: it can recompute a value the
model got wrong and can compile a tool call from the prompt. Both are reported apart.
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
from virtu_real_backend import _verify_arithmetic_response  # noqa: E402

COLUMNS = ("raw", "hygiene", "backend", "both")


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
    ap.add_argument("--raw", default="runs/eval/fullboard_20261105_0930/board7__comprehensive/raw.jsonl")
    ap.add_argument("--case-dir", default="data/benchmark/virtu_eval_v1")
    ap.add_argument("--out", default="runs/eval/stack_attribution_20261105")
    args = ap.parse_args()

    raw_path = os.path.join(ROOT, args.raw) if not os.path.isabs(args.raw) else args.raw
    case_dir = os.path.join(ROOT, args.case_dir) if not os.path.isabs(args.case_dir) else args.case_dir
    cases = load_cases(case_dir)
    rows = [json.loads(line) for line in open(raw_path, encoding="utf-8") if line.strip()]

    scores = {c: defaultdict(list) for c in COLUMNS}
    flips = {c: {"up": 0, "down": 0} for c in COLUMNS}
    for r in rows:
        case = cases.get(r["case_id"])
        if not case:
            continue
        messages = [{"role": "user", "content": case["prompt"]}]
        text_raw = r["response"]
        text_hyg = clean_served_answer(case["prompt"], text_raw).text
        text_b = _verify_arithmetic_response(text_raw, messages)
        text_hb = _verify_arithmetic_response(text_hyg, messages)
        base = score_case(text_raw, case["criteria"])["score"]
        for col, text in zip(COLUMNS, (text_raw, text_hyg, text_b, text_hb)):
            s = score_case(text, case["criteria"])["score"] if text else 0.0
            scores[col][case["dimension"]].append(s)
            if col != "raw":
                if s > base + 0.01:
                    flips[col]["up"] += 1
                elif s < base - 0.01:
                    flips[col]["down"] += 1

    identity = RunIdentity.capture(
        model_ids=(), case_dirs=[args.case_dir],
        extra={"raw": args.raw, "raw_sha256": sha256_file(raw_path), "rows": len(rows),
               "stacks": ["answer_pipeline", "virtu_real_backend._verify_arithmetic_response"],
               "note": "offline replay over one frozen leg; not model re-generation"})

    out_dir = os.path.join(ROOT, args.out)
    os.makedirs(out_dir, exist_ok=True)
    summary = {
        "run_id": identity.run_id,
        "n": len(rows),
        "weighted": {c: weighted(scores[c]) for c in COLUMNS},
        "mean": {c: round(mean(sum(scores[c].values(), [])), 2) for c in COLUMNS},
        "flips_vs_raw": flips,
        "dims": {c: {d: round(mean(v), 2) for d, v in sorted(scores[c].items())} for c in COLUMNS},
    }
    json.dump(summary, open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    identity.write(os.path.join(out_dir, "run_identity.json"))

    dims = sorted(scores["raw"])
    print(f"n={len(rows)} run_id={identity.run_id}")
    print(f"{'dim':16s} " + " ".join(f"{c:>9s}" for c in COLUMNS))
    for d in dims:
        print(f"{d:16s} " + " ".join(f"{mean(scores[c][d]):9.2f}" for c in COLUMNS))
    print(f"{'WEIGHTED':16s} " + " ".join(f"{summary['weighted'][c]:9.2f}" for c in COLUMNS))
    print(f"{'mean':16s} " + " ".join(f"{summary['mean'][c]:9.2f}" for c in COLUMNS))
    print("flips vs raw:", json.dumps(flips, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
