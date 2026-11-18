# -*- coding: utf-8 -*-
"""24 案例基准的判分器敏感度复核（辅助证据，不改判分器、不覆盖 measured 分数）。

背景：slot_exact_v2 把连续汉字串切成单个 token，候选「背吃刀」无法命中
「每次切削的背吃刀量」，于是内容正确的回答会被判 0。本脚本用**旧口径**
substring_any_v1 对同一批已封存的原始回答重算一遍，量化口径差异，
并把「slot 判 0 但子串命中 >= 2/3」的题逐条列为可人工复核的证据。

口径声明：本脚本产出的数一律 basis=inferred，仅用于解释基准的局限，
不得当作模型能力分数发布，也不得与 slot_exact_v2 的 measured 分混用。
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import run_domain_ab as D24  # noqa: E402


def substring_score(text, case):
    """旧口径：候选 any-of 项做普通子串包含（含 violations 惩罚）。"""
    low = D24.norm(D24.strip_think(text))
    groups = case.get("must") or []
    if not groups:
        raise ValueError(f"空匹配集 {case['id']}")
    hits = sum(1 for g in groups if any(D24.norm(a) in low for a in g))
    viol = sum(1 for v in case.get("violations", []) if any(D24.norm(a) in low for a in v))
    return round(max(0.0, (hits - viol) / len(groups)) * 100, 1), hits, len(groups), viol


def main():
    out = ROOT / "runs" / "eval_full_board_20261115"
    raw = out / "domain24" / "raw.jsonl"
    cases = {c["id"]: c for c in json.loads(
        (ROOT / "benchmarks" / "virtu_domain_cases_2026-11-06.json").read_text(encoding="utf-8"))["cases"]}
    rows = [json.loads(l) for l in raw.read_text(encoding="utf-8").splitlines() if l.strip()]
    by_model = {}
    flagged = []
    for r in rows:
        tag = r["model"]
        by_model.setdefault(tag, {"slot": [], "substr": [], "n": 0})
        s, hits, groups, viol = substring_score(r.get("answer") or "", cases[r["case_id"]])
        by_model[tag]["slot"].append(r["score"])
        by_model[tag]["substr"].append(s)
        by_model[tag]["n"] += 1
        if r["score"] == 0.0 and s >= 60.0:
            flagged.append({"model": tag, "case_id": r["case_id"],
                            "slot_score": r["score"], "substring_score": s,
                            "hits": hits, "groups": groups,
                            "missed_by_slot": (r.get("detail") or {}).get("missed"),
                            "answer_excerpt": (r.get("answer") or "")[:400]})
    summary = {}
    for tag, v in by_model.items():
        summary[tag] = {
            "n": v["n"],
            "slot_exact_v2_mean": round(statistics.mean(v["slot"]), 2),
            "substring_v1_mean": round(statistics.mean(v["substr"]), 2),
            "delta_mean": round(statistics.mean(v["substr"]) - statistics.mean(v["slot"]), 2),
        }
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "basis": "inferred",
        "purpose": "判分器口径敏感度复核；不作为能力分数发布",
        "evidence": str(raw.relative_to(ROOT)),
        "cases": "benchmarks/virtu_domain_cases_2026-11-06.json",
        "slot_grader_version": D24.GRADER_VERSION,
        "alternate_grader": "substring_any_v1 (historical, deprecated)",
        "per_model": summary,
        "content_correct_but_slot_zero_n": len(flagged),
        "flagged_cases": flagged,
    }
    dest = out / "domain24_grader_sensitivity.json"
    dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"per_model": summary,
                      "content_correct_but_slot_zero_n": len(flagged)},
                     ensure_ascii=False, indent=2))
    print("->", dest.relative_to(ROOT))


if __name__ == "__main__":
    main()
