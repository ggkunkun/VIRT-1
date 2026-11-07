"""Aggregate raw run records into dimension scores, rankings, and a radar chart.

Scoring contract (fixed, and restated in the report):
  * case score  = weight-hit ratio x 100
  * dimension    = arithmetic mean of VALID case scores in that dimension
  * overall      = sum(dimension score x dimension weight)
  * ``transport_error`` / ``dry_run`` records are excluded from every mean and
    reported separately as coverage loss; any other verdict counts against the
    model, because an empty or truncated answer is a real product failure.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import statistics

DIM_WEIGHTS = {
    "toolcall": 0.18,
    "reasoning": 0.17,
    "knowledge": 0.15,
    "instruction": 0.14,
    "boundary": 0.12,
    "generation": 0.10,
    "generalization": 0.08,
    "multimodal": 0.06,
}
DIM_NAMES_ZH = {
    "reasoning": "推理逻辑", "knowledge": "知识覆盖", "instruction": "指令遵循",
    "generation": "内容生成", "multimodal": "多模态理解", "generalization": "泛化适配",
    "boundary": "边界处理", "toolcall": "工具编排",
}
VALID_VERDICTS = ("pass", "partial", "partial_truncated", "fail_all_criteria", "empty_response")


def load_run(run_dir):
    raw = os.path.join(run_dir, "raw.jsonl")
    if not os.path.exists(raw):
        raise SystemExit(f"missing {raw}")
    manifest = {}
    mpath = os.path.join(run_dir, "manifest.json")
    if os.path.exists(mpath):
        manifest = json.load(open(mpath, encoding="utf-8"))
    recs = []
    with open(raw, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                recs.append(json.loads(line))
            except json.JSONDecodeError:
                recs.append(None)
    n_malformed = sum(1 for r in recs if r is None)
    recs = [r for r in recs if r]
    # A flaky backend can append several retry attempts for one case_id (each
    # transport_error before a success). Deduplicate last-wins so the score
    # reflects only the final attempt and the completeness gate stays honest.
    dedup = {}
    for r in recs:
        cid = r.get("case_id")
        if cid:
            dedup[cid] = r
    recs = list(dedup.values())
    return manifest, recs, n_malformed


def gate(manifest, recs, n_malformed):
    """Artifact completeness gate - refuse to publish scores on a broken run."""
    expected = manifest.get("n_cases_selected")
    got = len(recs)
    transport = [r for r in recs if r.get("verdict") == "transport_error"]
    rate = len(transport) / got if got else 0.0
    problems = []
    if n_malformed:
        problems.append(f"{n_malformed} 行 raw.jsonl JSON 残缺（写入被中断）")
    if expected and got < expected:
        problems.append(f"记录数 {got} < 计划用例数 {expected}（覆盖不全）")
    if rate > 0.05:
        problems.append(f"transport_error 占比 {rate:.1%} > 5%，本轮分数无效，需重跑")
    if got and all(r.get("verdict") == "transport_error" for r in recs):
        problems.append("全部记录均为传输失败，模型从未被真正问到")
    return {"expected_cases": expected, "recorded_cases": got, "malformed_lines": n_malformed,
            "transport_errors": len(transport), "transport_rate": round(rate, 4),
            "valid": not problems, "problems": problems}


def aggregate(recs, dims_filter=None):
    dims = collections.defaultdict(list)
    tiers = collections.defaultdict(lambda: collections.defaultdict(list))
    verdicts = collections.Counter()
    failed_keys = collections.Counter()
    failed_by_dim_key = collections.Counter()
    tag_scores = collections.defaultdict(list)
    latency, tput, trunc = [], [], 0
    trunc_by_dim = collections.Counter()
    clean_by_dim = collections.defaultdict(list)
    for r in recs:
        v = r.get("verdict")
        verdicts[v] += 1
        # A record that ran into the token ceiling is budget-truncated whether or not
        # the verdict label says so; counting only the label understated boundary
        # truncation as 16/30 when 21/30 records actually hit the cap.
        g0 = r.get("gen") or {}
        capped = v == "partial_truncated" or g0.get("finish_reason") == "length"
        if capped:
            trunc_by_dim[r["dimension"]] += 1
        if v in VALID_VERDICTS and not capped:
            clean_by_dim[r["dimension"]].append(r["score"])
        if v not in VALID_VERDICTS:
            continue
        d, t = r["dimension"], r.get("tier", "unknown")
        dims[d].append(r["score"])
        tiers[d][t].append(r["score"])
        for c in r.get("criteria", []):
            if not c["passed"]:
                failed_keys[f"{c['key']}({c['type']})"] += 1
                failed_by_dim_key[f"{d}/{c['key']}"] += 1
        for tag in r.get("tags", []):
            tag_scores[tag].append(r["score"])
        g = r.get("gen") or {}
        if g.get("elapsed_s"):
            latency.append(g["elapsed_s"])
        if g.get("completion_tokens") and g.get("elapsed_s"):
            tput.append(g["completion_tokens"] / g["elapsed_s"])
        if v == "partial_truncated":
            trunc += 1

    dim_stats = {}
    for d, scores in dims.items():
        tier_stats = {t: {"n": len(v), "mean": round(statistics.mean(v), 2)}
                      for t, v in sorted(tiers[d].items())}
        dim_stats[d] = {
            "name_zh": DIM_NAMES_ZH.get(d, d),
            "n_valid": len(scores),
            "score": round(statistics.mean(scores), 2),
            "median": round(statistics.median(scores), 2),
            "stdev": round(statistics.pstdev(scores), 2) if len(scores) > 1 else 0.0,
            "pass_rate": round(sum(1 for s in scores if s >= 99.999) / len(scores), 4),
            "zero_rate": round(sum(1 for s in scores if s <= 0.001) / len(scores), 4),
            # Truncation is a property of the token budget, not of the model. A
            # dimension scored mostly on truncated answers must not be quoted as a
            # capability score, so the clean-subset mean and the sample size sit next
            # to it rather than replacing it (the published 口径 stays frozen).
            "n_truncated": trunc_by_dim.get(d, 0),
            "score_untruncated_only": (round(statistics.mean(clean_by_dim[d]), 2)
                                       if clean_by_dim.get(d) else None),
            "n_untruncated": len(clean_by_dim.get(d) or []),
            "tiers": tier_stats,
        }
    if dims_filter:
        _keep = set(dims_filter)
        dim_stats = {d: v for d, v in dim_stats.items() if d in _keep}
    weighted = sum(dim_stats[d]["score"] * DIM_WEIGHTS.get(d, 0) for d in dim_stats)
    wsum = sum(DIM_WEIGHTS.get(d, 0) for d in dim_stats)
    return {
        "dimensions": dim_stats,
        # A case set whose dimensions carry no weight (physics/derivation/toolrouting) must not
        # print overall_weighted=0.0 - a reader cannot tell "scored nothing" from "no weight
        # definition here". Refuse, don't zero-fill.
        "overall_weighted": round(weighted / wsum, 2) if wsum else None,
        "weighted_dims": sorted(d for d in dim_stats if d in DIM_WEIGHTS),
        "unweighted_dims": sorted(d for d in dim_stats if d not in DIM_WEIGHTS),
        "overall_unweighted": round(statistics.mean([v["score"] for v in dim_stats.values()]), 2) if dim_stats else 0.0,
        "ranking": sorted(((d, dim_stats[d]["score"]) for d in dim_stats), key=lambda x: -x[1]),
        "verdicts": dict(verdicts),
        "top_failed_criteria": failed_keys.most_common(20),
        "top_failed_dim_criteria": failed_by_dim_key.most_common(25),
        "weakest_tags": sorted(((t, round(statistics.mean(v), 1), len(v)) for t, v in tag_scores.items()
                                if len(v) >= 2), key=lambda x: x[1])[:20],
        "latency_mean_s": round(statistics.mean(latency), 2) if latency else None,
        "latency_p95_s": round(sorted(latency)[int(len(latency) * 0.95) - 1], 2) if latency else None,
        "tok_per_s_mean": round(statistics.mean(tput), 1) if tput else None,
        "truncated_cases": trunc,
    }


def radar(arm_stats, out_png, dims_filter=None):
    """Radar chart over the eight dimensions, one polygon per arm."""
    from matplotlib import font_manager, use as mpl_use
    mpl_use("Agg")
    import matplotlib.pyplot as plt
    import math

    for cand in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "DejaVu Sans"):
        try:
            font_manager.findfont(cand, fallback_to_default=False)
            plt.rcParams["font.family"] = cand
            break
        except Exception:  # noqa: BLE001
            continue

    dims = list(dims_filter) if dims_filter else list(DIM_WEIGHTS)
    angles = [n / len(dims) * 2 * math.pi for n in range(len(dims))]
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(9.5, 9.5), subplot_kw={"polar": True})
    colors = ["#c0392b", "#2471a3", "#117a65", "#b7950b"]
    for i, (label, stats) in enumerate(arm_stats.items()):
        vals = [stats["dimensions"].get(d, {}).get("score", 0.0) for d in dims]
        vals += vals[:1]
        ax.plot(angles, vals, linewidth=2.2, label=label, color=colors[i % len(colors)])
        ax.fill(angles, vals, alpha=0.10, color=colors[i % len(colors)])
    ax.set_theta_offset(math.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels([f"{DIM_NAMES_ZH[d]}\n(w={DIM_WEIGHTS[d]:.2f})" for d in dims], fontsize=10)
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20", "40", "60", "80", "100"], fontsize=8, color="grey")
    ax.grid(alpha=0.35)
    ax.set_title("Virtu 能力雷达图（0-100 统一评分体系）", fontsize=14, pad=22)
    ax.legend(loc="upper right", bbox_to_anchor=(1.22, 1.10), fontsize=9, framealpha=0.9)
    fig.tight_layout()
    fig.savefig(out_png, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_png


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--runs", required=True, help="comma separated run dirs, label:dir pairs")
    p.add_argument("--out", default="benchmarks/virtu_capability_v1")
    p.add_argument("--radar-name", default="virtu_capability_radar.png")
    p.add_argument("--dims", default=None,
                   help="可选：仅聚合/绘制这些维度（逗号分隔），用于同口径对比")
    p.add_argument("--target", type=float, default=None,
                   help="可选：绘制一条所有维度均等于该值的参考多边形（如 90）")
    a = p.parse_args()
    a.dims = [x.strip() for x in a.dims.split(",")] if a.dims else None

    os.makedirs(a.out, exist_ok=True)
    arm_stats, gates = {}, {}
    for pair in a.runs.split(","):
        label, _, d = pair.partition(":")
        manifest, recs, mal = load_run(d)
        gates[label] = gate(manifest, recs, mal)
        arm_stats[label] = aggregate(recs, a.dims)
        arm_stats[label]["_manifest"] = {k: manifest.get(k) for k in
                                         ("git_sha", "arm", "sampling", "started", "harness")}

    payload = {"gates": gates, "arms": arm_stats, "dim_weights": DIM_WEIGHTS,
               "scoring_contract": {
                   "case_score": "命中权重/总权重 x 100",
                   "dimension": "有效用例得分算术平均",
                   "overall": "维度分 x 维度权重求和",
                   "excluded_verdicts": ["transport_error", "dry_run"]}}
    with open(os.path.join(a.out, "results.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    if a.target is not None:
        _tdims = a.dims or list(DIM_WEIGHTS)
        arm_stats[f"目标线 {a.target}"] = {
            "dimensions": {d: {"score": float(a.target), "name_zh": DIM_NAMES_ZH.get(d, d)}
                            for d in _tdims},
            "overall_weighted": float(a.target),
        }
    png = None
    try:
        png = radar({k: v for k, v in arm_stats.items()}, os.path.join(a.out, a.radar_name), a.dims)
    except ModuleNotFoundError as exc:
        if exc.name != "matplotlib":
            raise
        print("matplotlib not installed; JSON results are complete, radar chart skipped")
    print("wrote", os.path.join(a.out, "results.json"))
    if png:
        print("wrote", png)
    for label, g in gates.items():
        flag = "OK " if g["valid"] else "INVALID"
        print(f"[{flag}] {label}: recorded={g['recorded_cases']} transport={g['transport_errors']} "
              f"overall={arm_stats[label]['overall_weighted']}")
        for prob in g["problems"]:
            print("    !", prob)
    return 0 if all(g["valid"] for g in gates.values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
