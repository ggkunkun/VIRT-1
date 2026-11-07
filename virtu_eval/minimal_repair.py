# -*- coding: utf-8 -*-
"""Deterministic minimal repair for a defective parameter set.

The measurement that motivated this: handing the model the inequalities raised
localisation from 0.0 to 1.0 but left accepted repairs at 0.0, and its edits created
new violations. Satisfying five coupled inequalities at once is constraint solving,
which is not what an 8B is good at, and a machinist does not do it in their head
either - they compute it. So the solver goes outside the model and the model is
asked only to verify, which is separately checkable because a verifier that says
"yes" to everything is caught by a negative control.

Two findings are baked into the search. The scan is a fine grid, not a factor list:
a coarse multiplicative grid falsely reported D1 unsolvable when PCD=40.5 works.
And the answer is a set, not a value: several single-field changes satisfy every
constraint, so which one the user meant (chamfer 2 mm, not 0.5 mm) is not something
the physics can decide - unit-restoring candidates are flagged instead of assumed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from virtu_eval import planted_defects as pd

GRID_STEP = 0.5
SPAN = (0.2, 5.0)
TOP_N = 6
SOLVER_KEYS = ("D_outer", "D_hub", "D_bore", "PCD", "D_bolt", "t_base", "H_total", "chamfer")


def candidate_values(key, current):
    """Fine grid near the current value, plus the exact unit restorations.

    The ×25.4 candidate deliberately escapes the SPAN cap: a unit slip is by
    definition far from the current magnitude, so bounding the search by distance
    would hide the one repair that recovers what the user actually meant.
    """
    lo, hi = pd.MM_PLAUSIBLE.get(key, (0.5, 4000.0))
    if key == "n_bolts":
        grid_lo = max(2, int(lo))
        grid_hi = min(12, int(hi))
        return sorted(set(range(grid_lo, grid_hi + 1)))
    span_lo = max(lo, float(current) * SPAN[0])
    span_hi = min(hi, float(current) * SPAN[1])
    steps = int((span_hi - span_lo) / GRID_STEP) + 1
    grid = [round(span_lo + i * GRID_STEP, 4) for i in range(max(steps, 0))]
    exact = [value for value in (round(current * 25.4, 4), round(current / 25.4, 4))
             if lo <= value <= hi]
    return sorted(set(value for value in grid + exact if value > 0))


def find_repair(executor, params, oracle=None, top=TOP_N):
    """Every feasible single-field change, cheapest first.

    Cost is relative magnitude, so answers stay near the user's intent, but the
    full set is returned because the constraint system is under-determined.
    """
    oracle = oracle or pd.oracle
    if oracle(executor, params)["clean"]:
        return {"applicable": False, "reason": "parameters already satisfy the oracle", "feasible": []}
    feasible = []
    for key in SOLVER_KEYS:
        if key not in params:
            continue
        current = params[key]
        for value in candidate_values(key, current):
            if value == current:
                continue
            trial = dict(params)
            trial[key] = value
            if oracle(executor, trial)["clean"]:
                feasible.append({
                    "field": key, "from": current, "to": value,
                    "relative_change": round(abs(float(value) - float(current)) / max(abs(float(current)), 1e-9), 4),
                    "unit_restored": abs(value - round(current * 25.4, 4)) < 1e-6,
                })
    if not feasible:
        return {"applicable": False, "reason": "no single-field change reaches a valid design", "feasible": []}
    feasible.sort(key=lambda item: item["relative_change"])
    return {"applicable": True, "repair": feasible[0], "feasible_count": len(feasible),
            "feasible": feasible[:top]}


def near_miss_variant(executor, params, repair):
    """A repair-shaped wrong answer, used as the negative control for the verifier.

    Perturbing the solver's own value by the smallest amount that re-breaks a
    constraint is what a rubber-stamping verifier cannot tell apart from a fix.
    """
    if not repair:
        trial = dict(params, PCD=float(params["PCD"]) * 1.35)
        return trial if not pd.oracle(executor, trial)["clean"] else dict(params)
    base = dict(params)
    base[repair["field"]] = repair["to"]
    for factor in (0.98, 1.02, 0.95, 1.05, 0.9, 1.1, 0.8, 1.25):
        trial = dict(base)
        value = float(repair["to"]) * factor
        trial[repair["field"]] = int(round(value)) if repair["field"] == "n_bolts" else round(value, 4)
        if not pd.oracle(executor, trial)["clean"]:
            return {"field": repair["field"], "to": trial[repair["field"]], "params": trial}
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Solve the minimal repair for each defect.")
    parser.add_argument("--report", default=os.path.join("scratch", "minimal_repair.json"))
    args = parser.parse_args(argv)
    executor = pd.load_executor()
    rows = []
    for defect in pd.build_defects(executor):
        got = pd.oracle(executor, defect["params"], defect.get("steps"), defect.get("claim_mm3"))
        if len(got["violations"]) != 1:
            rows.append({"id": defect["id"], "error": "not isolated", "violations": got["violations"]})
            continue
        solved = find_repair(executor, defect["params"])
        row = {"id": defect["id"], "planted_rule": defect["rule"], **solved}
        if solved["applicable"]:
            merged = dict(defect["params"])
            merged[solved["repair"]["field"]] = solved["repair"]["to"]
            row["accepted_by_oracle"] = pd.oracle(executor, merged)["clean"]
            row["suite_repair_alternative_is_also_clean"] = pd.oracle(executor, defect["repair"])["clean"]
            near = near_miss_variant(executor, defect["params"], solved["repair"])
            row["near_miss"] = {k: v for k, v in (near or {}).items() if k != "params"}
            row["near_miss_is_dirty"] = bool(near) and not pd.oracle(executor, near["params"])["clean"]
        rows.append(row)
        print("%-24s applicable=%-5s feasible=%-4s first=%s->%s cost=%-7s unit_restore=%-5s near_miss_dirty=%s" % (
            defect["id"], solved["applicable"], solved.get("feasible_count", 0),
            solved.get("repair", {}).get("field"), solved.get("repair", {}).get("to"),
            solved.get("repair", {}).get("relative_change"),
            solved.get("repair", {}).get("unit_restored"), row.get("near_miss_is_dirty")))
    report = args.report if os.path.isabs(args.report) else os.path.join(ROOT, args.report)
    os.makedirs(os.path.dirname(report), exist_ok=True)
    with open(report, "w", encoding="utf-8") as handle:
        json.dump(rows, handle, ensure_ascii=False, indent=2)
    print("REPORT %s" % report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
