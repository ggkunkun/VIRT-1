# -*- coding: utf-8 -*-
"""分析 disciplined 评测 raw.jsonl：能力（score/pass_rate）+ token 效率。

输入：_eval_disciplined_text_v2/raw.jsonl（或任意 virtu_eval 输出目录）
输出：纯文本维度的 before/after 所需指标。
"""
from __future__ import annotations
import json, os, sys, statistics


def load_raw(path):
    recs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                recs.append(json.loads(line))
            except Exception:
                pass
    return recs


def pct(x):
    return f"{x*100:.1f}%"


def summarize(recs):
    # 按维度聚合
    dims = {}
    tokens_all = []
    scores_all = []
    passes = 0
    for r in recs:
        d = r.get("dimension")
        score = float(r.get("score", 0.0) or 0.0)
        verdict = r.get("verdict")
        gen = r.get("gen") or {}
        ct = gen.get("completion_tokens")
        dims.setdefault(d, {"scores": [], "tokens": [], "pass": 0, "n": 0})
        bucket = dims[d]
        bucket["scores"].append(score)
        bucket["n"] += 1
        if verdict == "pass":
            bucket["pass"] += 1
            passes += 1
        if isinstance(ct, int):
            bucket["tokens"].append(ct)
            tokens_all.append(ct)
        scores_all.append(score)

    print(f"总样本 n={len(recs)}  整体 pass={pct(passes/len(recs)) if recs else 'NA'}  "
          f"整体均分={statistics.mean(scores_all):.1f}" if scores_all else "无")
    print(f"{'维度':<14}{'n':>4}{'pass%':>9}{'均分':>8}{'tok_med':>9}{'tok_mean':>9}{'tok_p90':>9}{'tok_max':>9}")
    for d in sorted(dims):
        b = dims[d]
        toks = sorted(b["tokens"])
        med = statistics.median(toks) if toks else 0
        mean = statistics.mean(toks) if toks else 0
        p90 = toks[int(len(toks)*0.9)-1] if toks else 0
        mx = max(toks) if toks else 0
        print(f"{d:<14}{b['n']:>4}{pct(b['pass']/b['n']):>9}{statistics.mean(b['scores']):>8.1f}"
              f"{med:>9.0f}{mean:>9.0f}{p90:>9.0f}{mx:>9.0f}")
    if tokens_all:
        toks = sorted(tokens_all)
        med = statistics.median(toks)
        mean = statistics.mean(toks)
        p90 = toks[int(len(toks)*0.9)-1]
        print(f"{'ALL':<14}{len(recs):>4}{pct(passes/len(recs)):>9}"
              f"{statistics.mean(scores_all):>8.1f}{med:>9.0f}{mean:>9.0f}{p90:>9.0f}{max(toks):>9.0f}")


if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else "_eval_disciplined_text_v2/raw.jsonl"
    if not os.path.exists(p):
        print("missing", p)
        raise SystemExit(2)
    recs = load_raw(p)
    print(f"=== {p} (n={len(recs)}) ===")
    summarize(recs)
