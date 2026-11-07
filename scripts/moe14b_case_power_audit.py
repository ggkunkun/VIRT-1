# -*- coding: utf-8 -*-
"""
scripts/moe14b_case_power_audit.py — 用例判别力审计（先问这把尺有没有刻度，再问谁更长）

2026-11-06 的教训：判据噪声测出来后（σ_复测 8.84 / 23.57），配对统计显示今晚四个对比全部不可判，
根因不是 n 不够，而是**用例本身不区分两臂**——toolcall 维两臂 25/30 题分数完全相同。
加同质题永远判不出来；要判必须先知道哪些题有信息。

本脚本只用已经落盘的腿（零 GPU 成本），产出三件事：
  A. 饱和结构：各臂同分的题占多少、同分时是"都全对"还是"都全错"（后者是判据坏了，不是简单）
  B. 工具面真相：tools_supported / tools_requested / tools_dropped 逐臂统计
     —— 即使 arms 补了 schema，若服务端把工具协议丢弃，toolcall 维依然是空转
  C. cross-fitting 功效：在 A 半随机分一半"选题"、另一半"测量"，估计
     「只考有判别力的题」能否判出今晚的 Δ̄，以及需要多少题（两方向都算，防自选偏置）

用法：
  python scripts/moe14b_case_power_audit.py --runs runs/moe14b_ab_tools2/moe14b_gate_random,runs/moe14b_ab_tools2/dense_merged_v2_p11435
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import random
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = 20261106


def load(dirpath):
    out = {}
    raw = os.path.join(dirpath, "raw.jsonl")
    if not os.path.exists(raw):
        raise SystemExit(f"[FATAL] 缺腿：{raw} 不存在")
    with open(raw, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("verdict") == "transport_error" or r.get("score") is None:
                continue
            gen = r.get("gen") or {}
            out[r["case_id"]] = {"score": float(r["score"]), "dim": r.get("dimension"),
                                 "finish": gen.get("finish_reason"),
                                 "tools_supported": gen.get("tools_supported"),
                                 "tools_requested": gen.get("tools_requested"),
                                 "tools_dropped": gen.get("tools_dropped_for_json_protocol"),
                                 "served": gen.get("served_model")}
    return out


def saturation(scores_by_case, other_arms, cid):
    """饱和 = 本题所有臂同分；全零饱和说明判据或协议坏了，不是题简单。"""
    vals = [scores_by_case[cid]["score"]] + [o[cid]["score"] for o in other_arms if cid in o]
    if len(set(vals)) == 1:
        return ("all_zero" if vals[0] == 0.0 else "all_full" if vals[0] == 100.0 else "all_mid")
    return "informative"


def paired_ci(a, b, ids):
    d = [b[i]["score"] - a[i]["score"] for i in ids if i in a and i in b]
    n = len(d)
    if n < 2:
        return None
    mean = statistics.mean(d)
    sd = statistics.stdev(d)
    se = sd / math.sqrt(n)
    return {"n": n, "mean": round(mean, 2), "sigma_delta": round(sd, 2),
            "ci95": round(1.96 * se, 2), "t": round(mean / se, 2) if se else None,
            "attributable": bool(abs(mean) > 1.96 * se)}


def difficulty(ids, arms_list):
    """题面难度 = 各臂该题分数的均值（一个可在未来题上复算的属性，不泄漏臂身份）。"""
    return {i: statistics.mean([a[i]["score"] for a in arms_list if i in a]) for i in ids}


def informative_rule(mean_score):
    """饱和题（都全对 / 都全错）不含判别信息；中间难度带才可能区分两臂。"""
    return 15.0 <= mean_score <= 85.0


def crossfit(arms_list, ids, seed=SEED, alpha=0.5):
    """选题规则只用"题面难度带"，不用"这题 id 曾分歧" —— 后者无法向新题迁移（上一版就是错在这）。

    流程：随机对半，一半只用来估计难度分布（这里等价于不估计，直接用固定带），
    另一半按同一带筛题后测量。因为规则与臂无关也不引用具体 id，测半边的结果是可外推的。
    """
    rng = random.Random(seed)
    pruned_res, full_res = [], []
    for _ in range(300):
        ids2 = ids[:]
        rng.shuffle(ids2)
        test = ids2[int(len(ids2) * alpha):]
        dif = difficulty(test, arms_list)
        keep = [i for i in test if informative_rule(dif[i])]
        if len(keep) >= 4 and len(test) >= 6 and len(arms_list) >= 2:
            one = paired_ci_multi(arms_list, keep)
            two = paired_ci_multi(arms_list, test)
            if one and two:
                pruned_res.append(one)
                full_res.append(two)
    if not pruned_res:
        return {"splits_used": 0, "note": "难度带内题数不足，无法评估筛选收益"}
    med = lambda xs, k: round(statistics.median([x[k] for x in xs]), 2)
    rate = lambda xs: round(sum(1 for x in xs if x["attributable"]) / len(xs), 3)
    return {"splits_used": len(pruned_res),
            "median_n_kept": med(pruned_res, "n"), "median_n_all": med(full_res, "n"),
            "median_ci_kept": med(pruned_res, "ci95"), "median_ci_all": med(full_res, "ci95"),
            "median_t_kept": med(pruned_res, "t"), "median_t_all": med(full_res, "t"),
            "attributable_rate_kept": rate(pruned_res),
            "attributable_rate_all": rate(full_res),
            "note": "规则=题面合并难度落在 15~85 带（各臂同分的饱和题会被剔除）；"
                    "若 kept 的 CI 明显小于 all 且可判率上升，则值得按该带重造题单"}


def paired_ci_multi(arms_list, ids):
    """取第一、二条臂做配对（其余臂只用于难度估计）。"""
    a, b = arms_list[0], arms_list[1]
    return paired_ci(a, b, ids)


def power_arithmetic(arms_list, ids, target_delta):
    """从观测的逐题 Δ 分布反解：要判出 target_delta 需要多少道**判别性**题。"""
    a, b = arms_list[0], arms_list[1]
    d = [b[i]["score"] - a[i]["score"] for i in ids if i in a and i in b]
    if len(d) < 2:
        return None
    sd = statistics.stdev(d)
    n_disc = sum(1 for x in d if abs(x) > 1e-9)
    return {"observed_sigma_delta": round(sd, 2), "n_cases": len(d),
            "n_discordant": n_disc,
            "discordant_rate": round(n_disc / len(d), 3),
            "cases_needed_at_this_sigma": math.ceil((1.96 * sd / target_delta) ** 2),
            "cases_needed_if_every_case_discords": math.ceil((1.96 * sd / target_delta) ** 2),
            "note": "σ(Δ) 由分歧题的幅度决定；把分歧率从当前值提到 1 只能把所需题数降到 "
                    "所需分歧题数，而不能缩小 σ(Δ) 本身"}


def audit_run_id(dirs, dim):
    """判别力审计的 run_id：证据字节 sha + 本脚本 sha + 维度。

    哈希函数复用 scripts/moe14b_ab_verdict.py 的 sha256_of —— 一套定律只有一个参照，
    两处各自实现会算出两个都对但互不相等的指纹，那正是归因失效的方式。
    """
    spec = importlib.util.spec_from_file_location(
        "_verdict_ruler", os.path.join(ROOT, "scripts", "moe14b_ab_verdict.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    parts = [mod.sha256_of(os.path.join(d, "raw.jsonl")) for d in dirs]
    parts.append(mod.sha256_of(os.path.abspath(__file__)))
    parts.append(dim)
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True, help="逗号分隔的 run 目录")
    ap.add_argument("--dim", default="toolcall")
    ap.add_argument("--out", default=os.path.join(ROOT, "runs", "moe14b_case_power_audit.json"))
    ap.add_argument("--allow-toolsless", action="store_true",
                    help="显式允许审计从未发过 tools 的 toolcall 维（默认拒绝）")
    args = ap.parse_args()

    dirs = [d.strip() for d in args.runs.split(",") if d.strip()]
    if len(dirs) < 2:
        raise SystemExit("[FATAL] 至少要两条臂才能比较判别力")
    arms = {}
    for d in dirs:
        full = d if os.path.isabs(d) else os.path.join(ROOT, d)
        name = os.path.basename(full.rstrip("/\\"))
        data = {k: v for k, v in load(full).items() if v["dim"] == args.dim}
        if not data:
            raise SystemExit(f"[FATAL] {name} 里没有 dimension={args.dim} 的有效记录")
        arms[name] = data
    names = sorted(arms)
    # 与判定脚本同一套身份口径：响应无法归因（served_model 为空）的题不占样本位，
    # 否则一次服务侧空响应会被读成"这题两臂分歧"，把判别力算虚高。
    dropped_unattributed = sorted({cid for n in names for cid, v in arms[n].items() if not v["served"]})
    for n in names:
        for cid in dropped_unattributed:
            arms[n].pop(cid, None)
    common = sorted(set.intersection(*[set(arms[n]) for n in names]))
    if len(common) < 5:
        raise SystemExit(f"[FATAL] 各臂共同题只有 {len(common)} 道，无法审计")

    # I4（与 moe14b_ab_verdict 同口径）：toolcall 维从没发过 tools ⇒ 审的是空转数据
    requested_any = any(arms[n][c]["tools_requested"] for n in names for c in common)
    if args.dim == "toolcall" and not requested_any and not args.allow_toolsless:
        raise SystemExit("[GATE_FAILED] 该 toolcall 维没有任何一题发过 tools schema —— "
                         "判别力审计在空转数据上无意义；确认要审请加 --allow-toolsless")

    cats = {}
    for cid in common:
        cats[cid] = saturation(arms[names[0]], [arms[n] for n in names[1:]], cid)
    counts = {k: sum(1 for v in cats.values() if v == k) for k in
              ("informative", "all_zero", "all_full", "all_mid")}

    tooling = {}
    for n in names:
        rows = [arms[n][c] for c in common]
        tooling[n] = {
            "served_model": sorted({r["served"] for r in rows if r["served"]}),
            "tools_requested_any": sum(1 for r in rows if r["tools_requested"]),
            "tools_supported_true": sum(1 for r in rows if r["tools_supported"] is True),
            "tools_supported_false": sum(1 for r in rows if r["tools_supported"] is False),
            "tools_supported_unknown": sum(1 for r in rows if r["tools_supported"] is None),
            "tools_dropped_for_json_protocol": sum(1 for r in rows if r["tools_dropped"]),
            "finish_not_stop": sum(1 for r in rows if r["finish"] not in ("stop", None)),
        }

    a, b = names[0], names[1]
    arms_list = [arms[n] for n in names]
    cf = crossfit(arms_list, common)
    whole = paired_ci(arms[a], arms[b], common)
    power = power_arithmetic(arms_list, common, target_delta=abs(whole["mean"]) or 5.0)

    doc = {
        "basis": "measured", "dimension": args.dim, "arms": names,
        "run_id": audit_run_id(dirs, args.dim),
        "dropped_unattributable_cases": dropped_unattributed,
        "tools_schema_was_sent": requested_any,
        "n_common_cases": len(common),
        "saturation": {**counts, "informative_rate": round(counts["informative"] / len(common), 3),
                       "per_case": cats},
        "tool_call_plumbing": tooling,
        "paired_whole_set": whole,
        "crossfit": cf, "power_arithmetic": power,
        "verdict": ("用例无分辨率：绝大多数题两臂同分，必须先构造判别性题单，加同质题无用"
                    if counts["informative"] / len(common) < 0.35 else
                    "用例尚有分辨率，功效不足主要受 σ(Δ) 与 n 限制"),
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)

    print(f"=== 判别力审计 · dimension={args.dim} · 共同题 {len(common)} ===")
    print("饱和结构:", json.dumps({k: counts[k] for k in
                                   ("informative", "all_zero", "all_full", "all_mid")}, ensure_ascii=False),
          f"⇒ 有信息题占比 {doc['saturation']['informative_rate']:.0%}")
    print(f"全集配对: Δ̄={whole['mean']:+.2f} σ(Δ)={whole['sigma_delta']} 95%CI=±{whole['ci95']} "
          f"t={whole['t']} ⇒ {'可判' if whole['attributable'] else '不可判'}")
    print("cross-fitting（按难度带筛题，可外推）:",
          json.dumps({k: v for k, v in cf.items() if k != "note"}, ensure_ascii=False))
    print("  " + cf["note"])
    if power:
        print("功效算术:", json.dumps(power, ensure_ascii=False))
    print("工具面真相:", json.dumps(tooling, ensure_ascii=False, indent=1))
    print("⇒", doc["verdict"])
    print(f"[out] {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
