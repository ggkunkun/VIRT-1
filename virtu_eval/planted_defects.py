# -*- coding: utf-8 -*-
"""Planted-defect suite for the SOLIDWORKS capability card.

Definition of "understands the software": catching a defect it has never seen
and repairing it, not reciting a menu tree. So every defect ships with an oracle
that is independent of the model, and every oracle is mutation-proved red before
any model is consulted.

The engineering inequalities are delegated to the executor's own validate() so
that judge and actuator cannot drift apart; re-deriving them here would let the
two disagree and the model would be graded against a second set of physics.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO_PATH = os.path.join(ROOT, "scripts", "sw_flange_demo.py")

VOLUME_TOL = 0.01
FEATURE_TAGS = ("base_disk", "hub_boss", "bore_cut", "bolt_holes", "bore_chamfer")
DIAMETER_KEYS = ("D_outer", "D_hub", "D_bore", "PCD", "D_bolt")
LENGTH_KEYS = ("t_base", "H_total", "chamfer")
MM_PLAUSIBLE = {
    "D_outer": (30.0, 4000.0),
    "D_hub": (10.0, 3000.0),
    "D_bore": (3.0, 2000.0),
    "PCD": (15.0, 3500.0),
    "D_bolt": (2.0, 100.0),
    "t_base": (1.0, 500.0),
    "H_total": (2.0, 1000.0),
    "chamfer": (0.2, 50.0),
}

R_ENGINEERING = "engineering_inequality"
R_UNIT = "unit_plausibility"
R_SIGN = "dv_sign"
R_AGREE = "dv_agreement"
R_PROVENANCE = "claim_provenance"
RULES = (R_ENGINEERING, R_UNIT, R_SIGN, R_AGREE, R_PROVENANCE)


class ExecUnavailable(RuntimeError):
    """The executor's rules could not be imported; the suite has no physics."""


def load_executor(path=DEMO_PATH):
    if not os.path.exists(path):
        raise ExecUnavailable("executor missing at %s" % path)
    spec = importlib.util.spec_from_file_location("sw_flange_demo_for_oracle", path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise ExecUnavailable("executor import failed (%s: %s)" % (type(exc).__name__, exc))
    for needed in ("validate", "analytic_dv", "P"):
        if not hasattr(module, needed):
            raise ExecUnavailable("executor has no %s; judge would be ungrounded" % needed)
    return module


def check_unit_plausibility(params):
    """Catch a dimension whose magnitude cannot be millimetres.

    The executor's ordering inequalities are homogeneous in length, but its web
    and clearance floors are absolute (rim >= 2 mm, gap >= 1 mm), so a wholesale
    inch slip trips those too. What no threshold can see is a single field entered
    in inches among millimetre fields - a 0.079 chamfer satisfies every inequality
    and machines a part with no chamfer at all. This rule is that detector.
    """
    hits = []
    for key in DIAMETER_KEYS + LENGTH_KEYS:
        if key not in params:
            continue
        lo, hi = MM_PLAUSIBLE[key]
        value = float(params[key])
        if lo <= value <= hi:
            continue
        recovered = value * 25.4
        if lo <= recovered <= hi:
            hits.append({"rule": R_UNIT, "field": key, "value": round(value, 4),
                         "hint": "looks like an inch value entered as mm; x25.4 = %.3f" % recovered})
        else:
            hits.append({"rule": R_UNIT, "field": key, "value": round(value, 4),
                         "hint": "outside plausible mm range %.1f..%.1f" % (lo, hi)})
    return hits


def readback_steps(executor, params, corrupt_tag=None):
    """The step list a clean run produces: analytic deltas read back cumulatively.

    corrupt_tag flips that feature's measured delta sign, which is what a cut that
    silently became a boss looks like from the readback alone.
    """
    dv = executor.analytic_dv(params)
    steps, running = [], 0.0
    for tag in FEATURE_TAGS:
        delta = dv[tag]
        if tag == corrupt_tag:
            delta = abs(delta)
        running += delta
        steps.append({"tag": tag, "dv_mm3": delta, "volume_mm3": running,
                      "expected_dv_mm3": dv[tag]})
    return steps


def check_readback(executor, params, steps):
    hits = []
    dv = executor.analytic_dv(params)
    for step in steps or []:
        tag = step.get("tag")
        measured = step.get("dv_mm3")
        if tag not in dv or measured is None:
            continue
        expected = dv[tag]
        if (measured > 0) != (expected > 0):
            hits.append({"rule": R_SIGN, "field": tag, "measured_dv_mm3": round(measured, 3),
                         "hint": "expected %s material, measured %s"
                                 % ("removed" if expected < 0 else "added",
                                    "added" if measured > 0 else "removed")})
            continue
        if abs(expected) > 1e-9 and abs(measured - expected) / abs(expected) > VOLUME_TOL:
            hits.append({"rule": R_AGREE, "field": tag, "measured_dv_mm3": round(measured, 3),
                         "expected_dv_mm3": round(expected, 3),
                         "hint": "per-feature delta off by %.1f%%"
                                 % (100.0 * abs(measured - expected) / abs(expected))})
    return hits


def check_claim(executor, params, steps, claim_mm3):
    """A reported volume must be sourced from a readback and agree with physics."""
    if claim_mm3 is None:
        return []
    hits = []
    analytic_total = sum(executor.analytic_dv(params).values())
    sources = [s.get("volume_mm3") for s in (steps or []) if s.get("volume_mm3") is not None]
    if not sources:
        hits.append({"rule": R_PROVENANCE, "field": "volume_mm3", "claimed": claim_mm3,
                     "hint": "no build readback exists to source the claim from"})
        return hits
    if min(abs(claim_mm3 - v) / max(abs(v), 1e-9) for v in sources) > 1e-6:
        hits.append({"rule": R_PROVENANCE, "field": "volume_mm3", "claimed": claim_mm3,
                     "nearest_readback": round(min(sources, key=lambda v: abs(v - claim_mm3)), 3),
                     "hint": "does not quote any measured volume"})
        return hits
    if analytic_total > 0 and abs(claim_mm3 - analytic_total) / analytic_total > VOLUME_TOL:
        hits.append({"rule": R_PROVENANCE, "field": "volume_mm3", "claimed": claim_mm3,
                     "analytic_total_mm3": round(analytic_total, 3),
                     "hint": "readback and analytic volume disagree, so the build is not the design"})
    return hits


def derived_expectations(executor, params, steps=None):
    """The four quantities a human checks before pronouncing on a flange.

    Asked of every case, defect or clean, so the act of computing cannot be
    recruited to answer a specific planted fault.
    """
    dv = executor.analytic_dv(params)
    out = {
        "hub_clearance_mm": round(params["PCD"] / 2 - params["D_bolt"] / 2 - params["D_hub"] / 2, 3),
        "rim_web_mm": round(params["D_outer"] / 2 - (params["PCD"] / 2 + params["D_bolt"] / 2), 3),
        "total_volume_mm3": round(sum(dv.values()), 3),
    }
    if steps:
        out["sum_feature_dv_mm3"] = round(sum(s["dv_mm3"] for s in steps), 3)
    return out


def oracle(executor, params, steps=None, claim_mm3=None):
    hits = [{"rule": R_ENGINEERING, "field": None, "hint": v}
            for v in executor.validate(params)]
    hits.extend(check_unit_plausibility(params))
    hits.extend(check_readback(executor, params, steps))
    hits.extend(check_claim(executor, params, steps, claim_mm3))
    return {"violations": hits, "clean": not hits}


def baseline(executor):
    return {k: (int(v) if k == "n_bolts" else float(v)) for k, v in executor.P.items()}


def build_defects(executor):
    """Five defects, each firing exactly one violation, each with a real repair.

    The one-violation invariant is what makes attribution honest: a payload that
    carries two independent problems cannot tell you which one the model missed,
    and a model that reports the unplanned one would be scored as blind.
    """
    base = baseline(executor)
    clean_steps = readback_steps(executor, base)
    analytic_total = sum(executor.analytic_dv(base).values())

    undercut = dict(base, D_outer=53.0, D_bore=14.0, D_hub=30.0, PCD=30.0, D_bolt=8.0)
    breakout = dict(base, PCD=150.0)
    chamfer_inch = dict(base, chamfer=base["chamfer"] / 25.4)
    flipped = readback_steps(executor, base, corrupt_tag="bore_cut")

    return [
        {
            "id": "D1_hub_undercut", "title": "螺栓孔啃进凸台（历史上被拒三次仍逐字复读的那组尺寸）",
            "rule": R_ENGINEERING, "params": undercut, "steps": None, "claim_mm3": None,
            "expect_hint": "undercut the hub",
            "repair": dict(undercut, PCD=40.5),
        },
        {
            "id": "D2_rim_breakout", "title": "螺栓孔穿出外形轮廓（轮缘余量为负）",
            "rule": R_ENGINEERING, "params": breakout, "steps": None, "claim_mm3": None,
            "expect_hint": "break out of the rim",
            "repair": dict(breakout, PCD=125.0),
        },
        {
            "id": "D3_unit_confusion",
            "title": "倒角单独按英寸填报而其余为毫米（不等式全绿，只有量纲区间看得见）",
            "rule": R_UNIT, "params": chamfer_inch, "steps": None, "claim_mm3": None,
            "expect_hint": "inch value",
            "repair": base,
        },
        {
            "id": "D4_cut_adds_material", "title": "切除特征体积反增（体积守恒违例）",
            "rule": R_SIGN, "params": base, "steps": flipped, "claim_mm3": None,
            "expect_hint": "expected removed material",
            "repair": base, "repair_steps": clean_steps,
        },
        {
            "id": "D5_fabricated_volume", "title": "宣称体积与任何一次回读都不吻合（凭空报数）",
            "rule": R_PROVENANCE, "params": base, "steps": clean_steps,
            "claim_mm3": round(analytic_total * 0.0025, 1),
            "expect_hint": "does not quote any measured volume",
            "repair": base, "repair_steps": clean_steps,
            "repair_claim_mm3": round(clean_steps[-1]["volume_mm3"], 3),
        },
    ]


def run_suite(executor):
    base = baseline(executor)
    clean_steps = readback_steps(executor, base)
    analytic_total = sum(executor.analytic_dv(base).values())
    rows = []

    control = oracle(executor, base, clean_steps, round(analytic_total, 3))
    rows.append({"id": "CONTROL_clean_baseline", "kind": "control",
                 "violations": control["violations"],
                 "detected": not control["clean"], "passed": control["clean"]})

    for defect in build_defects(executor):
        got = oracle(executor, defect["params"], defect.get("steps"), defect.get("claim_mm3"))
        fired = [v for v in got["violations"] if v["rule"] == defect["rule"]
                 and defect["expect_hint"].lower() in (v.get("hint") or "").lower()]
        mutated = (json.dumps(defect["params"], sort_keys=True)
                   != json.dumps(base, sort_keys=True)) \
            or defect.get("steps") is not None or defect.get("claim_mm3") is not None
        rep_steps = defect.get("repair_steps", defect.get("steps"))
        rep = oracle(executor, defect["repair"], rep_steps,
                     defect.get("repair_claim_mm3", defect.get("claim_mm3")))
        single = len(got["violations"]) == 1
        rows.append({
            "id": defect["id"], "kind": "defect", "title": defect["title"],
            "expected_rule": defect["rule"], "expected_hint": defect["expect_hint"],
            "violations": got["violations"], "violation_count": len(got["violations"]),
            "isolated_to_one_violation": single, "detected": bool(fired),
            "mutant_differs_from_clean": mutated, "repair_clean": rep["clean"],
            "repair_violations": rep["violations"],
            "passed": bool(fired) and mutated and rep["clean"] and single,
        })
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description="Planted-defect suite for the SW card.")
    parser.add_argument("--report", default=os.path.join("scratch", "planted_defect_report.json"))
    args = parser.parse_args(argv)

    try:
        executor = load_executor()
    except ExecUnavailable as exc:
        print("EXEC_UNAVAILABLE %s" % exc)
        return 2

    rows = run_suite(executor)
    ok = 0
    for row in rows:
        print("%-26s rule=%-22s isolated=%-5s detected=%-5s mutant=%-5s repair_clean=%-5s -> %s" % (
            row["id"], row.get("expected_rule", row["kind"]), row.get("isolated_to_one_violation", "n/a"),
            row.get("detected"), row.get("mutant_differs_from_clean", "n/a"),
            row.get("repair_clean", "n/a"), "PASS" if row["passed"] else "FAIL"))
        ok += 1 if row["passed"] else 0
    payload = {"executor": DEMO_PATH, "volume_tol": VOLUME_TOL, "rules": list(RULES),
               "rows": rows, "passed": ok, "total": len(rows)}
    report = args.report if os.path.isabs(args.report) else os.path.join(ROOT, args.report)
    os.makedirs(os.path.dirname(report), exist_ok=True)
    with open(report, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    print("SUMMARY passed=%d/%d report=%s" % (ok, len(rows), report))
    return 0 if ok == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
