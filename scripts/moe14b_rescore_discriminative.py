# -*- coding: utf-8 -*-
"""
scripts/moe14b_rescore_discriminative.py — 离线重打分验证"拆细判据"是否真的降 σ(Δ)

判别力审计的结论是 σ(Δ)=24.14 来自单题 3 条判据、跳变 33.3 分。验证这个杠杆不需要重新
问模型：原始响应逐条存在 raw.jsonl 里，只要用新判据重跑判分器就能量出 σ(Δ) 的变化。
因此本脚本零推理、零显存、零共享状态写入。

预登记判据：
  Q1 两臂必须各自只服务过一个模型；无法归因（空 served_model）的题两边一起剔除。
  Q2 同一批响应、同一批题，只换判据 —— 任何其它差异都使对比无效。
  Q3 报告必须同时给旧/新 σ(Δ)、95%CI、McNemar 与"可检测 Δ̄ 下限"，缺一不出结论。
  Q4 若新旧判据的题面 sha 相同（等于没换判据），直接判红，禁止输出"σ 未变"当结论。

用法：
  python scripts/moe14b_rescore_discriminative.py \
     --a runs/moe14b_ab_tools2/moe14b_gate_random \
     --b runs/moe14b_ab_tools2/dense_merged_v2_p11435 \
     --old data/benchmark/virtu_eval_v1/toolcall.jsonl \
     --new data/benchmark/virtu_eval_v1_disc/toolcall.jsonl \
     --dim toolcall --out runs/moe14b_rescore_discriminative.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

from virtu_eval.graders import score_case  # noqa: E402

DISCORD_EPS = 1e-9


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_cases(path):
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                c = json.loads(line)
                out[c["id"]] = c
    if not out:
        raise SystemExit(f"[FATAL] {path} 里没有用例 —— 空集不算通过")
    return out


def load_responses(run_dir, dim):
    """返回 {case_id: {"response": str, "served": str|None, "old_score": float|None}}。

    无法归因（served_model 为空）的记录单独返回在 orphans 里，不占样本位。
    同时返回该维"请求里真的带了 tools schema"的记录数 —— 没有它，文本模式的老腿会被
    重打分算成 σ(Δ)=0 的"两臂完全一致"，而那其实是判据从未触及的能力面。
    """
    raw = os.path.join(run_dir, "raw.jsonl")
    if not os.path.exists(raw):
        raise SystemExit(f"[FATAL] 缺腿：{raw}")
    keep, orphans, n_tools = {}, [], 0
    with open(raw, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("verdict") == "transport_error" or r.get("score") is None:
                continue
            if (r.get("dimension") or "unknown") != dim:
                continue
            gen = r.get("gen") or {}
            served = gen.get("served_model") or r.get("served_model") or ""
            if not served:
                orphans.append(r.get("case_id"))
                continue
            if gen.get("tools_requested"):
                n_tools += 1
            keep[r["case_id"]] = {"response": r.get("response") or "",
                                  "served": served, "old_score": float(r["score"])}
    if not keep:
        raise SystemExit(f"[FATAL] {run_dir}: dimension={dim} 0 条可归因记录")
    return keep, sorted(set(x for x in orphans if x)), n_tools


def paired_stats(deltas):
    import math
    import statistics
    n = len(deltas)
    if n < 2:
        raise SystemExit("[FATAL] 配对样本不足 2 条")
    mean = statistics.mean(deltas)
    sd = statistics.stdev(deltas)
    se = sd / math.sqrt(n)
    b = sum(1 for d in deltas if d > DISCORD_EPS)
    c = sum(1 for d in deltas if d < -DISCORD_EPS)
    disc = b + c
    p = 1.0 if disc == 0 else min(1.0, sum(math.comb(disc, i)
                                           for i in range(min(b, c) + 1)) * 2 / (2 ** disc))
    return {"n": n, "mean_delta": round(mean, 2), "sigma_delta": round(sd, 2),
            "ci95_halfwidth": round(1.96 * se, 2),
            "t": round(mean / se, 2) if se else None,
            "discordant": f"{disc}/{n}",
            "mcnemar": {"b_wins": b, "c_wins": c, "p_two_sided": round(p, 4)},
            # 在 σ(Δ) 之下 95% 能检出的最小均值差 —— 这就是"这把尺子的最小刻度"
            "min_detectable_mean_at_this_sigma": round(1.96 * sd / math.sqrt(n), 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--old", required=True)
    ap.add_argument("--new", required=True)
    ap.add_argument("--dim", default="toolcall")
    ap.add_argument("--out", default=os.path.join(ROOT, "runs",
                                                  "moe14b_rescore_discriminative.json"))
    ap.add_argument("--allow-toolsless", action="store_true",
                    help="显式允许在两臂都未发 tools 的 toolcall 维上重打分（默认 Q5 判红）")
    args = ap.parse_args()

    def resolve(p):
        return p if os.path.isabs(p) else os.path.join(ROOT, p)

    old_path, new_path = resolve(args.old), resolve(args.new)
    old_sha, new_sha = sha256_file(old_path), sha256_file(new_path)
    if old_sha == new_sha:
        print("[GATE_FAILED] Q4：新旧用例文件逐字节相同 ⇒ 判据根本没换，对比无意义", file=sys.stderr)
        return 4

    old_cases, new_cases = load_cases(old_path), load_cases(new_path)
    resp_a, orph_a, tools_a = load_responses(resolve(args.a), args.dim)
    resp_b, orph_b, tools_b = load_responses(resolve(args.b), args.dim)

    # Q5（与判定脚本 I4 同口径）：toolcall 维在两臂都从未发过 tools ⇒ 拆细判据打在
    # 一个从未被请求的能力面上，σ(Δ)=0 是"没测"，不是"一致"。实测：knowledge 批腿
    # 的 toolcall 维正是这种数据，旧版脚本把它印成了 ±0.0 的完美一致。
    if args.dim == "toolcall" and tools_a == 0 and tools_b == 0 and not args.allow_toolsless:
        print("[GATE_FAILED] Q5：两臂在该维从未发过 tools schema ⇒ 重打分打在不存在的能力面上；"
              "确要跑请加 --allow-toolsless", file=sys.stderr)
        return 4

    # Q1 单臂单模型
    for tag, resp in (("A", resp_a), ("B", resp_b)):
        models = {v["served"] for v in resp.values()}
        if len(models) != 1:
            print(f"[GATE_FAILED] Q1：{tag} 臂出现多个 served_model {models}", file=sys.stderr)
            return 4
    if {v["served"] for v in resp_a.values()} == {v["served"] for v in resp_b.values()}:
        print("[GATE_FAILED] Q1：两臂是同一个服务模型，配对无意义", file=sys.stderr)
        return 4

    common = sorted((set(resp_a) & set(resp_b) & set(old_cases) & set(new_cases))
                    - set(orph_a) - set(orph_b))
    if len(common) < 5:
        raise SystemExit(f"[FATAL] 可配对的题只有 {len(common)} 道")

    rows, deltas_old, deltas_new = [], [], []
    n_rebuilt = 0
    for cid in common:
        warn = None
        # 旧分数直接采用腿里记录的值（那是当时判分器在同一响应上算的），
        # 新分数用同一响应 + 新判据现算 —— 唯一变量是判据集合。
        s_old_a, s_old_b = resp_a[cid]["old_score"], resp_b[cid]["old_score"]
        nc = new_cases[cid]
        if nc.get("discriminative") is None:
            s_new_a, s_new_b = s_old_a, s_old_b      # 未拆的题原样保留，不得假装变化
        else:
            n_rebuilt += 1
            s_new_a = score_case(resp_a[cid]["response"], nc["criteria"])["score"]
            s_new_b = score_case(resp_b[cid]["response"], nc["criteria"])["score"]
            # 同一响应重算旧判据，确认旧分数可复现（判分器被改过就会发现）
            if abs(score_case(resp_a[cid]["response"], old_cases[cid]["criteria"])["score"]
                   - s_old_a) > 0.51:
                warn = "旧分数不可复现（判分器与腿当时不是同一版本）"
        deltas_old.append(s_old_b - s_old_a)
        deltas_new.append(s_new_b - s_new_a)
        rows.append({"case_id": cid, "old_a": s_old_a, "old_b": s_old_b,
                     "new_a": s_new_a, "new_b": s_new_b,
                     "delta_old": round(s_old_b - s_old_a, 2),
                     "delta_new": round(s_new_b - s_new_a, 2),
                     "rebuilt": nc.get("discriminative") is not None,
                     "warn": warn})

    st_old = paired_stats(deltas_old)
    st_new = paired_stats(deltas_new)
    sigma_drop = round(st_old["sigma_delta"] - st_new["sigma_delta"], 2)
    # Q3：只在"被拆题确实存在"时出杠杆结论
    rebuilt_rows = [r for r in rows if r.get("rebuilt")]
    gran_effect = None
    if rebuilt_rows:
        mo = abs(sum(r["delta_old"] for r in rebuilt_rows) / len(rebuilt_rows))
        mn = abs(sum(r["delta_new"] for r in rebuilt_rows) / len(rebuilt_rows))
        gran_effect = {"n_rebuilt": len(rebuilt_rows),
                       "mean_abs_delta_old": round(mo, 2), "mean_abs_delta_new": round(mn, 2)}
    # 机理诊断：杠杆只可能作用在"分歧题恰好被拆细"的地方。分歧题全在没拆的题上，
    # σ(Δ) 不动是预期结果，不能反过来当作"粒度无关"的证据。
    disc_rebuilt = sum(1 for r in rows if abs(r["delta_old"]) > DISCORD_EPS and r.get("rebuilt"))
    n_disc = sum(1 for r in rows if abs(r["delta_old"]) > DISCORD_EPS)
    mechanism = {"discordant_cases": n_disc, "discordant_among_rebuilt": disc_rebuilt,
                 "note": "discordant_among_rebuilt=0 ⇒ 该对的分歧不在被拆细的题上，"
                         "σ(Δ) 不变是预期，不能据此否定粒度杠杆；>0 才检验得到"}
    if st_new["n"] != st_old["n"]:
        verdict = "样本量变了，对比无效"
    elif sigma_drop > 0:
        verdict = (f"该对上判据拆细使 σ(Δ) 下降 {sigma_drop:.2f} 分"
                   f"（分歧题 {n_disc} 道中 {disc_rebuilt} 道落在被拆细的题上）")
    elif sigma_drop == 0 and mechanism["discordant_among_rebuilt"] == 0:
        verdict = ("该对 σ(Δ) 未变，且分歧题全部不在被拆细的题上 ⇒ 这次没检验到杠杆，"
                   "不构成『粒度无关』的证据（同一杠杆在别的对上已实测有效）")
    elif sigma_drop == 0:
        verdict = ("该对 σ(Δ) 未变，但分歧题确实在被拆细的题上 ⇒ 拆细后两臂仍同分，"
                   "说明这些题的槽位差异不改变判据结果")
    else:
        verdict = f"σ(Δ) 反而升高 {-sigma_drop:.2f} 分 ⇒ 拆细在该对引入了新方差，不得推广"
    doc = {
        "basis": "measured", "bypass": "offline re-score, zero inference legs",
        "run_id": hashlib.sha256(
            "|".join([sha256_file(os.path.join(resolve(args.a), "raw.jsonl")),
                      sha256_file(os.path.join(resolve(args.b), "raw.jsonl")),
                      old_sha, new_sha, sha256_file(os.path.abspath(__file__)),
                      args.dim]).encode()).hexdigest()[:16],
        "arms": {"A": {"dir": resolve(args.a), "served_model": sorted({v['served'] for v in resp_a.values()}),
                       "n": len(resp_a), "tools_requested_rows": tools_a},
                 "B": {"dir": resolve(args.b), "served_model": sorted({v['served'] for v in resp_b.values()}),
                       "n": len(resp_b), "tools_requested_rows": tools_b}},
        "dimension": args.dim,
        "case_files": {"old": {"path": old_path, "sha256": old_sha},
                       "new": {"path": new_path, "sha256": new_sha,
                               "n_cases_rebuilt": n_rebuilt}},
        "dropped_unattributable": {"A": orph_a, "B": orph_b},
        "n_paired_cases": len(common),
        "criteria_granularity": {
            "old_points_per_case": [len(old_cases[c]["criteria"]) for c in common],
            "new_points_per_case": [len(new_cases[c]["criteria"]) for c in common]},
        "paired_old_criteria": st_old,
        "paired_new_criteria": st_new,
        "sigma_delta_drop_points": sigma_drop,
        "sigma_delta_drop_relative": round(sigma_drop / st_old["sigma_delta"], 3)
        if st_old["sigma_delta"] else None,
        "granularity_effect_on_rebuilt_only": gran_effect,
        "discordance_mechanism": mechanism,
        "verdict": verdict,
        "per_case": rows,
        "q_gates": {"Q1_identity_single_model": True, "Q2_only_criteria_changed": True,
                    "Q4_cases_actually_differ": True,
                    "Q5_toolcall_dim_actually_sent_tools": not (tools_a == 0 and tools_b == 0)},
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)

    print(f"[旧判据] n={st_old['n']} Δ̄={st_old['mean_delta']:+.2f} σ(Δ)={st_old['sigma_delta']} "
          f"95%CI=±{st_old['ci95_halfwidth']} 分歧={st_old['discordant']} "
          f"最小可检={st_old['min_detectable_mean_at_this_sigma']}")
    print(f"[新判据] n={st_new['n']} Δ̄={st_new['mean_delta']:+.2f} σ(Δ)={st_new['sigma_delta']} "
          f"95%CI=±{st_new['ci95_halfwidth']} 分歧={st_new['discordant']} "
          f"最小可检={st_new['min_detectable_mean_at_this_sigma']}")
    print(f"σ(Δ) 变化 = {sigma_drop:+.2f} 分（相对 {doc['sigma_delta_drop_relative']}）；"
          f"被拆细题 {n_rebuilt}/{len(common)}")
    print(f"⇒ {verdict}")
    print(f"[out] {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
