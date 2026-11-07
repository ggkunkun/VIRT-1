"""Static validator for the case sets.

Catches broken cases *before* an expensive run:
  * schema / uniqueness / dimension-vs-filename / tier-ratio problems
  * criteria whose grader errors out
  * **a case whose own gold answer does not score 100** -> the case is unsatisfiable
    or the criteria are mis-specified, and the resulting score would be meaningless.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from virtu_eval.graders import GRADERS, score_case  # noqa: E402

REQUIRED = ("id", "dimension", "tier", "prompt", "criteria")
TIERS = ("easy", "medium", "hard")
# easy:medium:hard = 3:5:2 with +-1 tolerance per bucket
def expected_mix(n):
    return round(n * 0.3), round(n * 0.5), round(n * 0.2)


def validate(case_dir, check_images=True, verbose=False):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    problems, seen_ids, summary = [], {}, {}
    if os.path.isfile(case_dir):
        files = [os.path.basename(case_dir)]
        case_dir = os.path.dirname(case_dir)
    else:
        files = sorted(f for f in os.listdir(case_dir) if f.endswith(".jsonl"))
    if not files:
        return [f"no .jsonl case files in {case_dir}"], {}
    for fname in files:
        dim_from_name = fname[:-6]
        counts = {t: 0 for t in TIERS}
        n = 0
        with open(os.path.join(case_dir, fname), encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                where = f"{fname}:{line_no}"
                n += 1
                try:
                    c = json.loads(line)
                except Exception as e:  # noqa: BLE001
                    problems.append(f"{where} bad_json:{e}")
                    continue
                for k in REQUIRED:
                    if k not in c:
                        problems.append(f"{where} missing_field:{k}")
                if c.get("dimension") != dim_from_name:
                    problems.append(f"{where} dimension_mismatch:{c.get('dimension')!r} vs {dim_from_name!r}")
                cid = c.get("id")
                if cid in seen_ids:
                    problems.append(f"{where} duplicate_id:{cid} (first seen {seen_ids[cid]})")
                seen_ids[cid] = where
                if c.get("tier") not in TIERS:
                    problems.append(f"{where} bad_tier:{c.get('tier')!r}")
                else:
                    counts[c.get("tier")] += 1
                if not isinstance(c.get("criteria"), list) or not c["criteria"]:
                    problems.append(f"{where} criteria_empty")
                    continue
                for crit in c["criteria"]:
                    if crit.get("type") not in GRADERS:
                        problems.append(f"{where} unknown_grader:{crit.get('type')!r}")
                gold_raw = c.get("gold")
                gold = gold_raw.get("answer") if isinstance(gold_raw, dict) else gold_raw
                if gold is None:
                    problems.append(f"{where} gold_answer_missing")
                else:
                    try:
                        s = score_case(str(gold), c["criteria"])
                    except Exception as e:  # noqa: BLE001
                        problems.append(f"{where} grader_error:{type(e).__name__}:{e}")
                    else:
                        if s["score"] < 100.0:
                            failed = [d["key"] + "->" + d["evidence"] for d in s["criteria"] if not d["passed"]]
                            problems.append(f"{where} gold_scores_{s['score']}: " + " | ".join(failed)[:400])
                if check_images and c.get("images"):
                    for img in c["images"]:
                        if not os.path.exists(os.path.join(root, img.replace("/", os.sep))):
                            problems.append(f"{where} image_missing:{img}")
                if verbose:
                    print(f"  ok {where} {cid} tier={c.get('tier')}")
        exp = expected_mix(n)
        tol = 1
        loose = [f"{t}:{counts[t]}(期望≈{e})" for t, e in zip(TIERS, exp)
                 if abs(counts[t] - e) > tol]
        if n < 30:
            problems.append(f"{fname} case_count={n} < 30")
        if loose:
            problems.append(f"{fname} tier_mix_off (n={n}): " + " ".join(loose))
        summary[dim_from_name] = {"n": n, **counts}
    return problems, summary


def main():
    case_dir = sys.argv[1] if len(sys.argv) > 1 else "data/benchmark/virtu_eval_v1"
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    case_dir = case_dir if os.path.isabs(case_dir) else os.path.join(root, case_dir)
    problems, summary = validate(case_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if problems:
        print(f"\nPROBLEMS ({len(problems)}):")
        for p in problems:
            print("  -", p)
        return 1
    total = sum(v["n"] for v in summary.values())
    print(f"\nVALID: {len(summary)} dimensions, {total} cases, all gold answers score 100.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
