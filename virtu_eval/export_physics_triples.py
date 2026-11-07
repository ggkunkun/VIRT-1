"""Export (intent, prediction, measured outcome) triples from a scored physics run.

The point of the solver-backed grader is that every verdict carries a real recomputation, so a
run is simultaneously a training corpus: prompt = intent, world_state = prediction,
``wm_verifier.recompute`` = measured outcome with per-field error. The label is the grader's own
verdict (it is called directly), so the corpus can never disagree with the ruler.

Usage:
    python -m virtu_eval.export_physics_triples <run_dir> [--case-dir DIR] [--out FILE]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from virtu_eval.graders import GRADERS, _world_state_of, _wm_verifier  # noqa: E402

VERIFIED_TYPE = "world_state_verified"


def load_cases(case_dir):
    cases = {}
    for fname in sorted(os.listdir(case_dir)):
        if not fname.endswith(".jsonl"):
            continue
        with open(os.path.join(case_dir, fname), encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line)
                    cases[rec["id"]] = rec
    return cases


def _rel_err(pred, ref):
    if not isinstance(pred, (int, float)) or not isinstance(ref, (int, float)):
        return None
    if isinstance(pred, bool) or isinstance(ref, bool):
        return None
    denom = max(abs(float(ref)), 1e-9)
    return round(abs(float(pred) - float(ref)) / denom, 6)


def build_triple(record, case, wm):
    """Return the triple for one scored record, or None if the case is not physics-graded."""
    crit = next((c for c in case.get("criteria", []) if c.get("type") == VERIFIED_TYPE), None)
    if crit is None:
        return None
    scenario = crit.get("scenario") or {}
    response = record.get("response") or ""
    pred, err = _world_state_of(response)
    ref = wm.recompute(scenario) if scenario else {}
    scalar = [k for k, v in ref.items() if v is None or isinstance(v, (int, float, str))]

    if pred is None:
        fields = [{"field": k, "pred": None, "ref": ref[k], "rel_err": None, "graded": False}
                  for k in scalar]
    else:
        fields = [{"field": k, "pred": pred.get(k), "ref": ref[k],
                   "rel_err": _rel_err(pred.get(k), ref[k]),
                   "graded": isinstance(ref[k], (int, float, str))}
                  for k in scalar]

    # The corpus label is the grader's verdict itself - never a second implementation.
    passed, evidence = GRADERS[VERIFIED_TYPE](response, crit)
    return {
        "case_id": record.get("case_id"),
        "dimension": record.get("dimension"),
        "tier": record.get("tier"),
        "tags": record.get("tags", []),
        "task": scenario.get("task"),
        "inputs": scenario.get("inputs"),
        "intent": case.get("prompt"),
        "prediction": pred,
        "prediction_error": err if pred is None else None,
        "reference": ref,
        "fields": fields,
        "tol_rel": float(crit.get("tol_rel", wm.REL_TOL)),
        "verified": bool(passed),
        "verdict": record.get("verdict"),
        "score": record.get("score"),
        "evidence": evidence,
    }


def export(run_dir, case_dir=None, out=None):
    raw_path = os.path.join(run_dir, "raw.jsonl")
    if not os.path.exists(raw_path):
        raise SystemExit(f"missing {raw_path} - run the runner first")
    manifest_path = os.path.join(run_dir, "manifest.json")
    if case_dir is None:
        if not os.path.exists(manifest_path):
            raise SystemExit("pass --case-dir, or run next to a manifest.json")
        case_dir = json.load(open(manifest_path, encoding="utf-8")).get("case_dir")
    cases = load_cases(case_dir)
    wm = _wm_verifier()

    out = out or os.path.join(run_dir, "triples.jsonl")
    n = kept = 0
    with open(raw_path, encoding="utf-8") as f, open(out, "w", encoding="utf-8",
                                                    newline="\n") as fh:
        for line in f:
            if not line.strip():
                continue
            record = json.loads(line)
            case = cases.get(record.get("case_id"))
            if case is None:
                continue
            n += 1
            triple = build_triple(record, case, wm)
            if triple is None:
                continue
            kept += 1
            fh.write(json.dumps(triple, ensure_ascii=False) + "\n")
    return out, n, kept


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--case-dir")
    ap.add_argument("--out")
    args = ap.parse_args()

    out, n, kept = export(args.run_dir, args.case_dir, args.out)
    if not kept:
        print(f"[warn] {n} records scanned, 0 physics-graded triples - this run used a "
              f"case set without {VERIFIED_TYPE} criteria")
        return 2
    print(f"[ok] {kept}/{n} triples -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
