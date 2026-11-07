#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/run_domain_ab.py — 同尺域内 A/B（关键词判分，可复算）。

用法：
  python scripts/run_domain_ab.py \
      --models virtu-comprehensive:fast,virtu-moe-14b:fast,virtu-dense-ties:q4 \
      --nruns 1 --out runs/domain_ab_20261106
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

API = "http://localhost:11434/api/generate"
ROOT = Path(__file__).resolve().parent.parent

THINK_RE = re.compile(r"<think>.*?</think>", re.S)


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").lower()


def strip_think(s: str) -> str:
    return THINK_RE.sub("", s or "").strip()


def gen(model: str, prompt: str, num_predict: int, temperature: float, timeout: int = 600):
    body = {"model": model, "prompt": prompt, "stream": False, "keep_alive": "20s",
            "options": {"num_predict": num_predict, "temperature": temperature}}
    req = urllib.request.Request(API, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        r = json.load(urllib.request.urlopen(req, timeout=timeout))
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", "replace")[:200]
        return None, {"error": msg, "wall": time.time() - t0}
    ec = r.get("eval_count", 0) or 0
    ed = (r.get("eval_duration", 1) or 1) / 1e9
    return r.get("response", ""), {"eval_count": ec, "eval_duration": ed,
                                   "tok_s": (ec / ed if ed else 0), "wall": time.time() - t0}


def unload(model: str, wait_s: int = 25):
    """卸载模型并等 ollama ps 清空，避免切臂时两模型共存把系统内存打爆。"""
    subprocess.run(["ollama", "stop", model], capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
    for _ in range(wait_s):
        out = subprocess.run(["ollama", "ps"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace").stdout
        if len(out.strip().splitlines()) <= 1:
            return True
        time.sleep(1)
    return False


def score(text: str, case: dict):
    t = norm(strip_think(text))
    groups = case["must"]
    hits, missed = 0, []
    for g in groups:
        if any(norm(alt) in t for alt in g):
            hits += 1
        else:
            missed.append(g[0])
    viol = 0
    for v in case.get("violations", []):
        if any(norm(alt) in t for alt in v):
            viol += 1
    raw = hits / len(groups) if groups else 0.0
    s = max(0.0, (hits - viol) / len(groups))
    return round(s * 100, 1), {"hits": hits, "groups": len(groups),
                               "violations": viol, "missed": missed, "raw": round(raw * 100, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True)
    ap.add_argument("--cases", default="benchmarks/virtu_domain_cases_2026-11-06.json")
    ap.add_argument("--out", default="runs/domain_ab")
    ap.add_argument("--num-predict", type=int, default=260)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    cases = json.loads((ROOT / args.cases).read_text(encoding="utf-8"))["cases"]
    if args.limit:
        cases = cases[: args.limit]
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    out_dir = ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {}
    raw_path = out_dir / "raw.jsonl"
    with open(raw_path, "w", encoding="utf-8") as raw_f:
        for model in models:
            scores, speeds = [], []
            t_start = time.time()
            for i, case in enumerate(cases, 1):
                text, meta = gen(model, case["q"], args.num_predict, args.temperature)
                if text is None:
                    sc, det = 0.0, {"error": meta.get("error")}
                else:
                    sc, det = score(text, case)
                    speeds.append(meta["tok_s"])
                scores.append(sc)
                raw_f.write(json.dumps({
                    "model": model, "case_id": case["id"], "cat": case["cat"],
                    "score": sc, "detail": det, "tok_s": meta.get("tok_s"),
                    "answer": strip_think(text or "")[:1200],
                }, ensure_ascii=False) + "\n")
                raw_f.flush()
                print(f"  [{model}] {i:>2}/{len(cases)} {case['id']:<16} {sc:>5.1f} "
                      f"{meta.get('tok_s', 0):>6.2f} tok/s", flush=True)
            summary[model] = {
                "n": len(cases),
                "mean_score": round(statistics.mean(scores), 2),
                "median_score": round(statistics.median(scores), 2),
                "min_score": min(scores), "max_score": max(scores),
                "mean_tok_s": round(statistics.mean(speeds), 2) if speeds else None,
                "elapsed_s": round(time.time() - t_start, 1),
            }
            unload(model)
            print(f"== {model}: mean={summary[model]['mean_score']} "
                  f"tok/s={summary[model]['mean_tok_s']} ({summary[model]['elapsed_s']}s)", flush=True)

    (out_dir / "summary.json").write_text(json.dumps({
        "when": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "cases": str(ROOT / args.cases),
        "num_predict": args.num_predict,
        "temperature": args.temperature,
        "summary": summary,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== SUMMARY ===")
    for m, s in summary.items():
        print(f"{m:34s} score={s['mean_score']:>6} (median {s['median_score']}) "
              f"tok/s={s['mean_tok_s']} n={s['n']}")


if __name__ == "__main__":
    main()
