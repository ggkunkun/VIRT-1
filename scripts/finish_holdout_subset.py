# -*- coding: utf-8 -*-
"""留出集分层子集补跑（收口用，2026-11-15）。

背景：全量 105 题配对腿跑到 30/105 时被外部 Ollama 客户端抢占显存，
出现 TimeoutError；已完成的前 30 题只覆盖 2 个维度，直接统计会给出偏斜结论。
本脚本按 dimension 分层抽样一个可配对子集，复用已完成的有效记录，
只补生成缺失题，并与同一份 baseline 全量腿按 id 严格配对。

诚实口径：
  * 只发布子集 n 的 measured 结果，全量 105 题标「未完成/未测」；
  * 生成失败/超时的题不记 0 分、不计入 n；有效样本不足 80% 时 basis=partial；
  * subset 结论是方向性证据，不得写成「105 题通过率」。
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import statistics
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from virtu_eval import provenance as P  # noqa: E402
from virtu_eval.arms import OllamaNativeArm  # noqa: E402
from virtu_eval.graders import score_case  # noqa: E402
from scripts.eval_vericut_e_training import build_case_messages  # noqa: E402

PRIMARY = "virtu-vericut96:v2"
BASELINE = "virtu-master-fixed:latest"
# 每维目标题数；总和 32，八维全覆盖
TARGET = {"nc_safety_diagnosis": 7, "setup_workoffset": 6, "tool_assembly": 6,
          "runtime_toolcall": 5, "pdf_curriculum_qa": 4, "machine_kinematics": 2,
          "boundary": 1, "vericut_setup_facts": 1}


def tags_digest(tag):
    """优先实时读 /api/tags；并发占用导致超时时回退到起链时已封存的身份快照。"""
    try:
        op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with op.open("http://127.0.0.1:11434/api/tags", timeout=30) as r:
            d = json.loads(r.read().decode("utf-8"))
        hit = next((m.get("digest") for m in d.get("models", []) if m["model"] == tag), None)
        if hit:
            return hit
    except Exception as exc:  # noqa: BLE001
        print(f"[identity] live tags unavailable ({type(exc).__name__}), using pinned snapshot", flush=True)
    snap = ROOT / "runs/eval_full_board_20261115/identity.json"
    if snap.is_file():
        doc = json.loads(snap.read_text(encoding="utf-8"))
        return (doc.get("models", {}).get(tag) or {}).get("tags_digest")
    return None


def load_jsonl(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="runs/eval_full_board_20261115/holdout")
    ap.add_argument("--max-tokens", type=int, default=512)
    ap.add_argument("--num-ctx", type=int, default=4096)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    out = ROOT / args.out_dir
    cases = load_jsonl(ROOT / "data/sft/vericut_e_training/vericut_e_holdout.jsonl")
    by_dim = collections.defaultdict(list)
    for c in cases:
        by_dim[c["dimension"]].append(c)

    base_rows = {r["id"]: r for r in load_jsonl(out / "raw_baseline_holdout.jsonl")}
    cand_rows = {r["id"]: r for r in load_jsonl(out / "raw_candidate_holdout.jsonl")
                 if not r.get("error") and r.get("text")}
    raw_new = out / "holdout_subset_raw.jsonl"
    if raw_new.is_file():  # 断点续跑：复用上一次已生成且有效的记录
        for r in load_jsonl(raw_new):
            if not r.get("error") and r.get("text"):
                cand_rows[r["id"]] = r

    # 分层选样：先复用已完成的有效题，再按 id 确定性补齐，保证每维覆盖
    selected = []
    for dim, k in TARGET.items():
        pool = sorted(by_dim.get(dim, []), key=lambda c: c["id"])
        have = [c for c in pool if c["id"] in cand_rows]
        need = [c for c in pool if c["id"] not in cand_rows]
        selected.extend((have + need)[:k])
    selected.sort(key=lambda c: c["id"])
    selected_ids = [c["id"] for c in selected]
    print(f"[subset] n={len(selected_ids)} dims={dict(collections.Counter(c['dimension'] for c in selected))}",
          flush=True)

    fingerprint = hashlib.sha256(json.dumps({
        "model": tags_digest(PRIMARY), "case_ids": selected_ids,
        "cases_sha256": P.sha256_file(str(ROOT / "data/sft/vericut_e_training/vericut_e_holdout.jsonl")),
        "grader_sha256": P.sha256_file(str(ROOT / "virtu_eval/graders.py")),
        "params": {"seed": args.seed, "max_tokens": args.max_tokens,
                   "num_ctx": args.num_ctx, "temperature": 0.0, "think": False},
    }, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]

    todo = [c for c in selected if c["id"] not in cand_rows]
    print(f"[subset] reuse={len(selected) - len(todo)} to_generate={len(todo)} run_id={fingerprint}", flush=True)

    if todo:
        arm = OllamaNativeArm(model_id=PRIMARY, num_ctx=args.num_ctx, think=False,
                              strip_think=True, retries=1, timeout=300)
        with open(raw_new, "a", encoding="utf-8") as fh:
            for i, c in enumerate(todo, 1):
                try:
                    gen = arm.generate(build_case_messages(c), max_tokens=args.max_tokens,
                                       temperature=0.0, top_p=1.0, seed=args.seed,
                                       tools=c.get("tools"))
                except Exception as exc:  # noqa: BLE001
                    gen = {"text": "", "error": f"{type(exc).__name__}:{exc}",
                           "elapsed_s": None, "completion_tokens": None, "finish_reason": None}
                text = gen.get("text") or ""
                if gen.get("error") or not text:
                    rec = {"id": c["id"], "dimension": c["dimension"], "score": None,
                           "error": gen.get("error") or "empty_response", "text": ""}
                else:
                    sc = score_case(text, c["criteria"])
                    rec = {"id": c["id"], "dimension": c["dimension"], "score": sc["score"],
                           "all_passed": sc["all_passed"], "error": None, "text": text,
                           "criteria_details": sc["criteria"],
                           "elapsed_s": gen.get("elapsed_s"),
                           "completion_tokens": gen.get("completion_tokens"),
                           "finish_reason": gen.get("finish_reason"),
                           "served_layers": gen.get("served_layers")}
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fh.flush()
                cand_rows[c["id"]] = rec
                print(f"  [{i}/{len(todo)}] {c['id']} score={rec['score']} err={rec['error']}",
                      flush=True)

    rows = []
    for c in selected:
        b, x = base_rows.get(c["id"]), cand_rows.get(c["id"])
        rows.append({"id": c["id"], "dimension": c["dimension"],
                     "baseline_score": (b or {}).get("score"),
                     "candidate_score": (x or {}).get("score")})
    valid = [r for r in rows if r["baseline_score"] is not None and r["candidate_score"] is not None]
    bmean = statistics.mean(r["baseline_score"] for r in valid) if valid else None
    cmean = statistics.mean(r["candidate_score"] for r in valid) if valid else None
    bpass = 100.0 * sum(1 for r in valid if r["baseline_score"] >= 99.999) / len(valid) if valid else None
    cpass = 100.0 * sum(1 for r in valid if r["candidate_score"] >= 99.999) / len(valid) if valid else None
    by_dimension = {}
    for dim in TARGET:
        v = [r for r in valid if r["dimension"] == dim]
        if v:
            by_dimension[dim] = {
                "n": len(v),
                "baseline_mean": round(statistics.mean(r["baseline_score"] for r in v), 2),
                "candidate_mean": round(statistics.mean(r["candidate_score"] for r in v), 2),
                "delta_mean": round(statistics.mean(r["candidate_score"] for r in v) -
                                    statistics.mean(r["baseline_score"] for r in v), 2),
            }
    coverage = len(valid) / len(selected) if selected else 0
    report = {
        "basis": "measured" if coverage >= 0.8 else "partial",
        "scope": "stratified_subset_not_full_holdout",
        "note": ("全量 105 题腿因外部 Ollama 并发占用显存出现超时而中止；"
                 "此处只发布分层子集配对结果，全量 105 题结论标未测"),
        "run_id": fingerprint,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "model": PRIMARY, "baseline": BASELINE,
        "model_digest": tags_digest(PRIMARY), "baseline_digest": tags_digest(BASELINE),
        "cases_file": "data/sft/vericut_e_training/vericut_e_holdout.jsonl",
        "cases_sha256": P.sha256_file(str(ROOT / "data/sft/vericut_e_training/vericut_e_holdout.jsonl")),
        "grader_sha256": P.sha256_file(str(ROOT / "virtu_eval/graders.py")),
        "params": {"seed": args.seed, "max_tokens": args.max_tokens,
                   "num_ctx": args.num_ctx, "temperature": 0.0, "think": False},
        "evidence": {"candidate_new": str(raw_new.relative_to(ROOT)),
                     "candidate_full_partial": str((out / "raw_candidate_holdout.jsonl").relative_to(ROOT)),
                     "baseline_full": str((out / "raw_baseline_holdout.jsonl").relative_to(ROOT))},
        "n_selected": len(selected), "n_valid": len(valid), "coverage_pct": round(100 * coverage, 1),
        "target_per_dimension": TARGET,
        "n_by_dimension": dict(collections.Counter(r["dimension"] for r in valid)),
        "baseline_mean": round(bmean, 2) if bmean is not None else None,
        "candidate_mean": round(cmean, 2) if cmean is not None else None,
        "delta_mean": round(cmean - bmean, 2) if bmean is not None and cmean is not None else None,
        "baseline_pass_pct": round(bpass, 2) if bpass is not None else None,
        "candidate_pass_pct": round(cpass, 2) if cpass is not None else None,
        "by_dimension": by_dimension,
        "rows": rows,
        "full_105_leg": "未完成，未测；历史同题板全量对照见 runs/eval_vericut_e_training_r2/comparison_report.json (run_id 3dcc89b28e586675)",
    }
    dest = out / "holdout_subset_report.json"
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("basis", "n_selected", "n_valid", "baseline_mean",
                                             "candidate_mean", "delta_mean", "by_dimension")},
                     ensure_ascii=False, indent=2), flush=True)
    print("->", dest.relative_to(ROOT), flush=True)


if __name__ == "__main__":
    main()
