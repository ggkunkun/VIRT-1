"""Re-score a stored probe ledger without re-running the model.

Reads scratch/_p02_probe_<tag>.jsonl (which keeps every raw ``content``), replays
``graders.score_case`` under the *current* grader, and reports the delta against
the score that was stamped at capture time. A score that moves here did not move
because the model changed -- the ruler did. That distinction is the whole point
of AGENTS.md §8.2.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from virtu_eval import graders  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--cases", default="data/benchmark/virtu_eval_cl_v1/toolrouting.jsonl")
    ap.add_argument("--write", action="store_true", help="overwrite stamped scores in place")
    args = ap.parse_args()

    ledger = args.ledger if os.path.isabs(args.ledger) else os.path.join(ROOT, args.ledger)
    cases = {}
    case_path = args.cases if os.path.isabs(args.cases) else os.path.join(ROOT, args.cases)
    for line in open(case_path, encoding="utf-8"):
        if line.strip():
            c = json.loads(line)
            cases[c["id"]] = c

    rows = [json.loads(l) for l in open(ledger, encoding="utf-8") if l.strip()]
    moved = []
    for r in rows:
        case = cases[r["case_id"]]
        scored = graders.score_case(r["content"], case["criteria"])
        r["score_replayed"] = scored["score"]
        r["criteria_replayed"] = scored["criteria"]
        if abs(scored["score"] - r["score"]) > 1e-9:
            moved.append((r["case_id"], r["score"], scored["score"]))

    old_mean = sum(r["score"] for r in rows) / len(rows)
    new_mean = sum(r["score_replayed"] for r in rows) / len(rows)
    old_pass = sum(1 for r in rows if r["score"] >= 99.999)
    new_pass = sum(1 for r in rows if r["score_replayed"] >= 99.999)

    print(f"ledger={os.path.basename(ledger)}  n={len(rows)}")
    print(f"stamped : mean={old_mean:.2f}  all_passed={old_pass}/{len(rows)}")
    print(f"replayed: mean={new_mean:.2f}  all_passed={new_pass}/{len(rows)}")
    print(f"moved   : {len(moved)} case(s)")
    for cid, a, b in moved:
        print(f"   {cid}: {a:.2f} -> {b:.2f}")

    if args.write:
        with open(ledger, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print("rewritten:", ledger)


if __name__ == "__main__":
    main()
