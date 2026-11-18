#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/eval_vericut_e_training.py — 受控基准前/后对比评测 (Zero Fabrication)。

严格遵循 AGENTS.md §5 / §8 测量宪法：
  1. 复用 virtu_eval.arms.OllamaNativeArm + virtu_eval.graders.score_case + RunIdentity。
  2. 对比 Baseline vs Fine-Tuned 模型在同一份 holdout（及可选通用基准子集）上的表现，
     固定 temperature=0.0, seed=42, num_ctx=4096, think=False。
  3. 每条原始回答、耗时、token 数与逐判据明细全部落盘 runs/eval_vericut_e_training/raw_*.jsonl，
     结束时校对 RunIdentity.drift() == []，禁止凭记忆汇报未测指标。
"""
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from virtu_eval.arms import OllamaNativeArm  # noqa: E402
from virtu_eval.graders import score_case  # noqa: E402
from virtu_eval.provenance import RunIdentity, sha256_file  # noqa: E402


def _unload_ollama(model_id: str) -> None:
    import urllib.request

    try:
        subprocess.run(
            ["ollama", "stop", model_id],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
    except Exception:
        pass
    deadline = time.time() + 15.0
    while time.time() < deadline:
        try:
            with urllib.request.urlopen("http://127.0.0.1:11434/api/ps", timeout=3) as resp:
                ps = json.loads(resp.read().decode("utf-8"))
            names = [m.get("name") or m.get("model") for m in ps.get("models") or []]
            if model_id not in names:
                time.sleep(1.5)
                return
        except Exception:
            break
        time.sleep(0.5)


def load_jsonl(path: Path) -> List[dict]:
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def load_eval_subset(eval_dir: Path, per_file_limit: int = 4) -> List[dict]:
    """Deterministically sample up to `per_file_limit` cases per .jsonl file from an eval suite."""
    out: List[dict] = []
    for p in sorted(eval_dir.glob("*.jsonl")):
        rows = load_jsonl(p)
        out.extend(rows[:per_file_limit])
    return out


def build_case_messages(case: dict) -> List[dict]:
    msgs = []
    if case.get("system"):
        msgs.append({"role": "system", "content": case["system"]})
    for m in case.get("context") or []:
        msgs.append({"role": m["role"], "content": m["content"]})
    msgs.append({"role": "user", "content": case["prompt"]})
    return msgs


def evaluate_model(
    model_id: str,
    cases: List[dict],
    raw_out_path: Path,
    num_ctx: int = 4096,
    max_tokens: int = 768,
    skip_budget_gate: bool = False,
) -> Dict[str, Any]:
    arm = OllamaNativeArm(model_id=model_id, num_ctx=num_ctx, think=False, strip_think=True, retries=1, timeout=180)
    if not skip_budget_gate:
        arm.load()

    raw_out_path.parent.mkdir(parents=True, exist_ok=True)
    # 断点续跑：若已存在非 transport_error 的完整条目则复用
    done: Dict[str, dict] = {}
    if raw_out_path.is_file():
        for ln in raw_out_path.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            r = json.loads(ln)
            if not r.get("error") and r.get("text"):
                done[r["id"]] = r

    results: List[dict] = []
    t_start = time.time()
    mode = "a" if done else "w"
    with open(raw_out_path, mode, encoding="utf-8") as wf:
        for idx, case in enumerate(cases, 1):
            cid = case["id"]
            if cid in done:
                results.append(done[cid])
                continue
            msgs = build_case_messages(case)
            tools = case.get("tools")
            gen = arm.generate(msgs, max_tokens=max_tokens, temperature=0.0, top_p=1.0, seed=42, tools=tools)
            text = gen.get("text") or ""
            if gen.get("error"):
                scored = {"score": 0.0, "all_passed": False, "none_passed": True, "criteria": []}
            else:
                scored = score_case(text, case["criteria"])
            rec = {
                "id": cid,
                "dimension": case.get("dimension", "general"),
                "tier": case.get("tier", "core"),
                "score": scored["score"],
                "all_passed": scored["all_passed"],
                "elapsed_s": gen.get("elapsed_s"),
                "prompt_tokens": gen.get("prompt_tokens"),
                "completion_tokens": gen.get("completion_tokens"),
                "finish_reason": gen.get("finish_reason"),
                "error": gen.get("error"),
                "text": text,
                "criteria_details": scored["criteria"],
            }
            wf.write(json.dumps(rec, ensure_ascii=False) + "\n")
            wf.flush()
            results.append(rec)
            if idx % 10 == 0 or idx == len(cases):
                mean_so_far = statistics.mean(r["score"] for r in results)
                pass_so_far = sum(1 for r in results if r["all_passed"]) / len(results) * 100
                print(
                    f"  [{model_id}] {idx}/{len(cases)} mean={mean_so_far:.2f} pass@100={pass_so_far:.1f}% "
                    f"last=({cid}: {rec['score']:.1f}, {rec['elapsed_s']}s)",
                    flush=True,
                )

    _unload_ollama(model_id)
    by_dim: Dict[str, List[dict]] = defaultdict(list)
    for r in results:
        by_dim[r["dimension"]].append(r)

    dim_summary = {}
    for d, items in sorted(by_dim.items()):
        dim_summary[d] = {
            "n": len(items),
            "mean_score": round(statistics.mean(x["score"] for x in items), 2),
            "pass_rate_pct": round(sum(1 for x in items if x["all_passed"]) / len(items) * 100, 2),
            "errors": sum(1 for x in items if x.get("error")),
        }

    return {
        "model_id": model_id,
        "served_layers": arm.served_layers,
        "n": len(results),
        "overall_mean": round(statistics.mean(r["score"] for r in results), 2) if results else 0.0,
        "overall_pass_rate_pct": round(sum(1 for r in results if r["all_passed"]) / max(1, len(results)) * 100, 2),
        "transport_errors": sum(1 for r in results if r.get("error")),
        "raw_path": str(raw_out_path),
        "raw_sha256": sha256_file(raw_out_path),
        "elapsed_seconds": round(time.time() - t_start, 1),
        "by_dimension": dim_summary,
    }


def run_selftest(cases_path: Path) -> int:
    cases = load_jsonl(cases_path)
    assert len(cases) >= 90
    for c in cases:
        msgs = build_case_messages(c)
        assert msgs[-1]["role"] == "user"
        sc = score_case(c["gold"]["answer"], c["criteria"])
        assert sc["score"] == 100.0, f"{c['id']}: {sc}"
    print(f"[EVAL_SELFTEST] PASS: {len(cases)} holdout cases build+grade cleanly at 100.0 on gold")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="VERICUT E:\\training 前/后受控基准对比")
    ap.add_argument("--baseline", default="virtu-master-fixed:latest")
    ap.add_argument("--candidate", default="virtu-vericut-e:latest")
    ap.add_argument("--cases", default=str(ROOT / "data" / "sft" / "vericut_e_training" / "vericut_e_holdout.jsonl"))
    ap.add_argument("--sanity-eval-dir", default=str(ROOT / "data" / "benchmark" / "virtu_eval_v1"))
    ap.add_argument("--sanity-per-file", type=int, default=3)
    ap.add_argument("--out-dir", default=str(ROOT / "runs" / "eval_vericut_e_training"))
    ap.add_argument("--num-ctx", type=int, default=4096)
    ap.add_argument("--max-tokens", type=int, default=768)
    ap.add_argument("--skip-budget-gate", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    cases_path = Path(args.cases)
    if args.selftest:
        return run_selftest(cases_path)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    holdout_cases = load_jsonl(cases_path)

    # 锁定身份指纹 (AGENTS.md §8.2)
    identity = RunIdentity.capture(
        model_ids=[args.baseline, args.candidate],
        case_dirs=[str(cases_path.parent)],
        extra={"cases_file_sha256": sha256_file(cases_path), "seed": 42, "temperature": 0.0},
    )
    identity.write(out_dir / "identity.json")

    print(f"[Eval] Baseline={args.baseline} vs Candidate={args.candidate} | holdout n={len(holdout_cases)}")
    base_hold = evaluate_model(
        args.baseline,
        holdout_cases,
        out_dir / "raw_baseline_holdout.jsonl",
        num_ctx=args.num_ctx,
        max_tokens=args.max_tokens,
        skip_budget_gate=args.skip_budget_gate,
    )
    cand_hold = evaluate_model(
        args.candidate,
        holdout_cases,
        out_dir / "raw_candidate_holdout.jsonl",
        num_ctx=args.num_ctx,
        max_tokens=args.max_tokens,
        skip_budget_gate=args.skip_budget_gate,
    )

    sanity_report = None
    sanity_dir = Path(args.sanity_eval_dir)
    if args.sanity_per_file > 0 and sanity_dir.is_dir():
        sanity_cases = load_eval_subset(sanity_dir, args.sanity_per_file)
        if sanity_cases:
            print(f"[Eval] General non-regression sanity check n={len(sanity_cases)} ({sanity_dir})")
            b_san = evaluate_model(
                args.baseline, sanity_cases, out_dir / "raw_baseline_sanity.jsonl",
                num_ctx=args.num_ctx, max_tokens=args.max_tokens, skip_budget_gate=args.skip_budget_gate,
            )
            c_san = evaluate_model(
                args.candidate, sanity_cases, out_dir / "raw_candidate_sanity.jsonl",
                num_ctx=args.num_ctx, max_tokens=args.max_tokens, skip_budget_gate=args.skip_budget_gate,
            )
            sanity_report = {
                "n": len(sanity_cases),
                "baseline_mean": b_san["overall_mean"],
                "candidate_mean": c_san["overall_mean"],
                "delta_mean": round(c_san["overall_mean"] - b_san["overall_mean"], 2),
                "baseline_pass_pct": b_san["overall_pass_rate_pct"],
                "candidate_pass_pct": c_san["overall_pass_rate_pct"],
            }

    drift = identity.drift()
    dim_deltas = {}
    for d in sorted(set(base_hold["by_dimension"]) | set(cand_hold["by_dimension"])):
        b_d = base_hold["by_dimension"].get(d, {})
        c_d = cand_hold["by_dimension"].get(d, {})
        dim_deltas[d] = {
            "n": c_d.get("n") or b_d.get("n"),
            "baseline_mean": b_d.get("mean_score"),
            "candidate_mean": c_d.get("mean_score"),
            "delta_mean": round((c_d.get("mean_score") or 0) - (b_d.get("mean_score") or 0), 2),
            "baseline_pass_pct": b_d.get("pass_rate_pct"),
            "candidate_pass_pct": c_d.get("pass_rate_pct"),
        }

    report = {
        "basis": "measured" if not drift else "voided_due_to_drift",
        "run_id": identity.run_id,
        "identity_drift": drift,
        "cases_file": str(cases_path),
        "cases_sha256": sha256_file(cases_path),
        "holdout": {
            "n": len(holdout_cases),
            "baseline": base_hold,
            "candidate": cand_hold,
            "delta_mean": round(cand_hold["overall_mean"] - base_hold["overall_mean"], 2),
            "delta_pass_pct": round(cand_hold["overall_pass_rate_pct"] - base_hold["overall_pass_rate_pct"], 2),
            "by_dimension": dim_deltas,
        },
        "general_sanity": sanity_report,
    }
    report_path = out_dir / "comparison_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "basis": report["basis"],
        "drift": drift,
        "holdout_baseline_mean": base_hold["overall_mean"],
        "holdout_candidate_mean": cand_hold["overall_mean"],
        "holdout_delta_mean": report["holdout"]["delta_mean"],
        "holdout_delta_pass_pct": report["holdout"]["delta_pass_pct"],
        "general_sanity": sanity_report,
    }, ensure_ascii=False, indent=2))
    if drift:
        raise SystemExit(f"[FATAL] Identity drift detected during eval: {drift}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
