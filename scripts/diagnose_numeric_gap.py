#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Classify every numeric_near failure on an identity-stamped leg and measure what the
deterministic layers can actually reach.

Why this exists: the discipline ledger closed tier E with one number -- ``numeric_near``
failing 62/100 checks, 51 of them with a relative error above 1% -- and the sentence
"部分缓解". That is not actionable: it does not say which failures a deterministic solver
can reach today, which need a registered law, and which are only reachable by training
weights (and therefore blocked by the no-GPU-rental constraint). This script turns that
one number into a per-case attribution plus a measured replay, using CPU only.

Two rulers are kept apart on purpose:

  * classification  -- what kind of error is it (structural factor / missing number /
    transcription of a given value / genuinely wrong arithmetic)?
  * reachability    -- would ``virtu_real_backend``'s deterministic passes
    (``_fix_explicit_equation`` + ``_numeric_problems``/``_apply_numeric_corrections``)
    change this answer, and would the re-scored case then pass?

Replay uses the *same* grader and the *same* criteria as the leg, and never asks the model
again, so the numbers are attributable to the post-processing layer, not to sampling noise
(``temperature=0`` is not reproducible on this host -- measured 2026-11-04).

Usage::

    .venv/Scripts/python.exe scripts/diagnose_numeric_gap.py                 # frozen leg
    .venv/Scripts/python.exe scripts/diagnose_numeric_gap.py --raw <path>    # another leg
    .venv/Scripts/python.exe scripts/diagnose_numeric_gap.py --selftest      # reverse probes
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LEG = ROOT / "runs" / "eval" / "fullboard_20261105_0930" / "board7__frozen_comp_v5__v4" / "raw.jsonl"
OUT_JSON = ROOT / "benchmarks" / "VIRTU_NUMERIC_GAP_2026-11-05.json"
OUT_MD = ROOT / "benchmarks" / "VIRTU_NUMERIC_GAP_2026-11-05.md"

# Structural factors this repository has already observed in model arithmetic:
# dropping/multiplying by pi, radius<->diameter, mm<->inch, g/cm^3<->g/mm^3, min<->s.
FACTOR_FAMILIES = (
    ("pi_dropped_or_kept", math.pi),
    ("radius_vs_diameter", 2.0),
    ("mm_vs_inch", 25.4),
    ("rho_g_cm3_vs_g_mm3", 1000.0),
    ("min_vs_s", 60.0),
    ("order_of_magnitude_10", 10.0),
    ("order_of_magnitude_100", 100.0),
)

_EVIDENCE_RE = re.compile(r"closest=(-?[\d.eE+-]+)\s+target=(-?[\d.eE+-]+)\s+tol=(-?[\d.eE+-]+)")


def _classify(criterion_evidence: str):
    """Return (class, ratio) for a failed numeric_near criterion, from its stored evidence."""
    if "no number in response" in criterion_evidence:
        return "no_number_emitted", None
    m = _EVIDENCE_RE.search(criterion_evidence)
    if not m:
        return "unparsable_evidence", None
    closest, target, tol = (float(m.group(i)) for i in (1, 2, 3))
    if target == 0:
        return "target_zero", None
    ratio = closest / target
    for name, factor in FACTOR_FAMILIES:
        if abs(ratio - factor) <= 0.02 * factor or abs(ratio - 1.0 / factor) <= 0.02 / factor:
            return name, ratio
    rel = abs(closest - target) / abs(target)
    if rel <= 0.5:
        return "arithmetic_off_by_small_factor", ratio
    return "wrong_by_more_than_half", ratio


def _replay(response: str, prompt: str, criteria: list):
    """Apply the backend's deterministic numeric passes and re-grade with the same criteria."""
    from virtu_eval.graders import score_case
    import virtu_real_backend as rb

    messages = [{"role": "user", "content": prompt}]
    text = rb._fix_explicit_equation(response)
    text = rb._apply_numeric_corrections(text, rb._numeric_problems(messages))
    return score_case(text, criteria)


def load_cases(case_dir: Path) -> dict:
    """The raw leg stores only {key,type,weight,passed,evidence}; the values a grader needs
    (numeric target, tolerance, required keys, solver scenario) live in the case file, so the
    replay must be graded against the *original* criteria, not the stored summary."""
    cases = {}
    for path in sorted(case_dir.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                case = json.loads(line)
                cases[case["id"]] = case
    if not cases:
        raise SystemExit(f"no cases found under {case_dir} -> replay would be vacuous")
    return cases


def analyse(raw_path: Path, case_dir: Path) -> dict:
    from virtu_eval.graders import score_case
    from virtu_eval.report import DIM_WEIGHTS
    import virtu_real_backend as rb

    cases = load_cases(case_dir)
    rows = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    # keep the last attempt per case_id (the provenance rule for re-tried cases)
    latest = {}
    for row in rows:
        latest[row["case_id"]] = row
    rows = list(latest.values())

    klass = Counter()
    by_dimension = defaultdict(Counter)
    reachability = Counter()
    unreachable_by_field = Counter()
    unreachable_examples = defaultdict(list)
    per_case_delta = []
    missing_cases = 0
    failing_case_ids = set()
    numeric_checks = numeric_fail = 0
    replay_changed = replay_fixed = replay_broke = 0
    dim_raw = defaultdict(list)
    dim_replay = defaultdict(list)

    for row in rows:
        prompt = row.get("prompt") or ""
        response = row.get("response") or ""
        case = cases.get(row["case_id"])
        if case is None:
            missing_cases += 1
            continue
        criteria = case["criteria"]
        scored = score_case(response, criteria)
        if scored["score"] != row.get("score") and row.get("score") is not None:
            # the ruler moved since the leg ran; report it instead of silently mixing rulers
            reachability["score_differs_from_stored_ruler"] += 1
        dim_raw[row["dimension"]].append(scored["score"])
        was_fail = [c for c in scored["criteria"]
                    if c["type"] == "numeric_near" and not c["passed"]]
        numeric_checks += sum(1 for c in scored["criteria"] if c["type"] == "numeric_near")
        numeric_fail += len(was_fail)
        after = _replay(response, prompt, criteria)
        dim_replay[row["dimension"]].append(after["score"])
        if abs(after["score"] - scored["score"]) > 1e-9:
            replay_changed += 1
            if after["score"] > scored["score"]:
                replay_fixed += 1
            else:
                replay_broke += 1
        if not was_fail:
            continue
        failing_case_ids.add(row["case_id"])
        for criterion in was_fail:
            name, ratio = _classify(criterion["evidence"])
            klass[name] += 1
            by_dimension[row["dimension"]][name] += 1
            problems = rb._numeric_problems([{"role": "user", "content": prompt}])
            if problems:
                reachability["deterministic_pass_produces_a_reference"] += 1
            else:
                reachability["no_deterministic_reference_available"] += 1
                # Which quantity is being asked for, and how the case labels it. This is the
                # work list for the next deterministic law: every shape here is one the bridge
                # cannot recompute today, whether because the law is unregistered or because the
                # prompt transforms its own inputs (档位/查表/乘系数) and must stay vetoed.
                label = criterion.get("key") or "numeric_near"
                unreachable_by_field[label] += 1
                if len(unreachable_examples[label]) < 2:
                    unreachable_examples[label].append(
                        {"case_id": row["case_id"], "tier": row.get("tier"),
                         "prompt": prompt[:220], "evidence": criterion["evidence"][:160]})
            if len(per_case_delta) < 24:
                per_case_delta.append({
                    "case_id": row["case_id"], "dimension": row["dimension"], "tier": row.get("tier"),
                    "class": name, "ratio": None if ratio is None else round(ratio, 6),
                    "before_score": scored["score"], "after_score": after["score"],
                    "guard_problems": [p[0] for p in problems],
                    "evidence": criterion["evidence"][:220],
                })

    def weighted(per_dim):
        dims = [d for d in per_dim if d in DIM_WEIGHTS]
        return round(sum((sum(per_dim[d]) / len(per_dim[d])) * DIM_WEIGHTS[d] for d in dims)
                     / sum(DIM_WEIGHTS[d] for d in dims), 2) if dims else None

    return {
        "leg": raw_path.parent.name,
        "case_dir": case_dir.relative_to(ROOT).as_posix(),
        "rows": len(rows),
        "rows_without_case": missing_cases,
        "numeric_near_checks": numeric_checks,
        "numeric_near_failures": numeric_fail,
        "cases_with_numeric_failure": len(failing_case_ids),
        "class_counts": dict(klass),
        "class_by_dimension": {d: dict(c) for d, c in by_dimension.items()},
        "reachability": dict(reachability),
        "unreachable_by_field": dict(unreachable_by_field.most_common()),
        "unreachable_examples": {field: unreachable_examples[field]
                                 for field in unreachable_by_field},
        "replay": {"cases_changed_by_deterministic_pass": replay_changed,
                   "cases_raised": replay_fixed, "cases_lowered": replay_broke,
                   "weighted_raw": weighted(dict(dim_raw)),
                   "weighted_after_deterministic": weighted(dict(dim_replay)),
                   "delta": None if weighted(dict(dim_raw)) is None or weighted(dict(dim_replay)) is None
                           else round(weighted(dict(dim_replay)) - weighted(dict(dim_raw)), 2)},
        "per_case": per_case_delta,
    }


def render_md(report: dict) -> str:
    lines = [
        f"# 数值短板逐例归因（{report['leg']}，n={report['rows']}）",
        "",
        f"- `numeric_near` 判据 {report['numeric_near_checks']} 次，失败 {report['numeric_near_failures']} 次",
        f"- 确定性核算回放后分数有变化的例数：{report['replay']['cases_changed_by_deterministic_pass']}"
        f"（升 {report['replay']['cases_raised']} / 降 {report['replay']['cases_lowered']}）",
        f"- 可达性：{report['reachability']}",
        "",
        "## 失败类别",
        "",
        "| 类别 | 次数 |",
        "|---|---:|",
    ]
    for name, count in sorted(report["class_counts"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| {name} | {count} |")
    lines += ["", "## 确定性核算今天够不到的量（下一批要注册的式）", "",
              "| 被问的量（判据 key） | 失败次数 | 题面片段 |", "|---|---:|---|"]
    for field, count in report.get("unreachable_by_field", {}).items():
        sample = (report.get("unreachable_examples", {}).get(field) or [{}])[0]
        snippet = (sample.get("prompt") or "").replace("\n", " | ").replace("|", "¦")[:120]
        lines.append(f"| {field} | {count} | {snippet} |")
    lines += ["", "## 逐例（最多 24 条）", "",
              "| case | 维 | 类别 | ratio | 回放前 | 回放后 | 命中的确定性式 |", "|---|---|---|---:|---:|---:|---|"]
    for row in report["per_case"]:
        lines.append(f"| {row['case_id']} | {row['dimension']} | {row['class']} | "
                     f"{row['ratio']} | {row['before_score']} | {row['after_score']} | "
                     f"{','.join(row['guard_problems']) or '—'} |")
    lines += ["",
              "> 口径：回放只跑 `virtu_real_backend` 的两个纯函数（显式等式重算 + 题面给定量的公式重算），",
              "> 不重问模型，不含卫生层（四栈归因见 `scripts/stack_attribution_offline.py`）。", ""]
    return "\n".join(lines)


def selftest() -> int:
    failures = []
    # 1. classification must name the structural factors this repo already measured
    cases = [
        ("closest=120000.0 target=38197.1 tol=190.9", "pi_dropped_or_kept"),
        ("closest=0.00785 target=7.85 tol=0.03", "rho_g_cm3_vs_g_mm3"),
        ("closest=25.4 target=1.0 tol=0.005", "mm_vs_inch"),
    ]
    for evidence, want in cases:
        got, _ = _classify(evidence)
        if got != want:
            failures.append(f"classify {evidence[:34]!r} -> {got}, want {want}")
    # 2. an empty answer must not be classed as arithmetic
    got, _ = _classify("no number in response")
    if got != "no_number_emitted":
        failures.append(f"no-number class -> {got}")
    # 3. the replay must be falsifiable: a prompt with an explicit wrong equation has to move
    changed = _replay("n = 1000*120/(3.14*16) = 241.7 r/min",
                      "已知 Vc=120 m/min, D=16 mm，求主轴转速 n。",
                      [{"type": "numeric_near", "key": "n", "value": 2387.32, "weight": 1}])
    if changed["score"] <= 0.0:
        failures.append("replay did not reach an explicitly wrong equation -> probe is vacuous")
    # 4. and it must not invent: an unsolvable prompt stays untouched
    same = _replay("这个法兰盘的粗糙度是多少？", "这个法兰盘的粗糙度是多少？",
                   [{"type": "literal_any", "key": "l", "values": ["粗糙度"], "weight": 1}])
    if not same["all_passed"]:
        failures.append("replay damaged a case with no numeric content")
    print("[selftest]", "PASS" if not failures else "FAIL")
    for line in failures:
        print("  -", line)
    return 0 if not failures else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(LEG))
    ap.add_argument("--case-dir", default=str(ROOT / "data" / "benchmark" / "virtu_eval_v1"))
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--ablate-new-families", action="store_true",
                    help="A/B the offline replay with the numeric_repair families disabled; "
                         "prints both deltas instead of writing the report")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if args.ablate_new_families:
        import virtu_omni.serving.numeric_repair as numeric_repair
        raw, case_dir = Path(args.raw), Path(args.case_dir)
        extended = analyse(raw, case_dir)["replay"]
        original = numeric_repair.numeric_problems
        numeric_repair.numeric_problems = lambda _text: []
        try:
            baseline = analyse(raw, case_dir)["replay"]
        finally:
            numeric_repair.numeric_problems = original
        gain = (None if baseline["weighted_after_deterministic"] is None
                or extended["weighted_after_deterministic"] is None
                else round(extended["weighted_after_deterministic"]
                           - baseline["weighted_after_deterministic"], 2))
        print(json.dumps({"baseline": baseline, "extended": extended,
                          "attributable_gain": gain}, ensure_ascii=False, indent=2))
        return 0
    report = analyse(Path(args.raw), Path(args.case_dir))
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8", newline="\n")
    OUT_MD.write_text(render_md(report), encoding="utf-8", newline="\n")
    print("numeric checks=%d failures=%d classes=%s" % (
        report["numeric_near_checks"], report["numeric_near_failures"],
        json.dumps(report["class_counts"], ensure_ascii=False)))
    print("replay=%s" % json.dumps(report["replay"], ensure_ascii=False))
    print("REPORT " + OUT_MD.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
