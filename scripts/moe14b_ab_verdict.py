# -*- coding: utf-8 -*-
"""
scripts/moe14b_ab_verdict.py — 用实测噪声底线给 13.63B 的路由/在役价值出判定

预登记判据（写在这里，先于任何数字）：
  R1 σ 只来自 runs/moe14b_noise_probe.json 的配对复测；没有该文件就拒绝出结论。
  R2 每个维度独立用 delta_verdict(Δ, n=该维题数, σ) 判定；|Δ| ≤ 1.96σ√(2/n) ⇒ 记「噪声内」，
     不得转述成「领先/落后 X 分」。
  R3 截断率不对称且偏向结论方向时按「截断混淆」处理（delta_verdict 内置）。
  R4 本脚本不改任何服务配置；只出判定。

用法：
  python scripts/moe14b_ab_verdict.py --pair a.json_dir b.json_dir --label "orth vs random"
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

# 判定语全是中文 + σ/Δ/⇒ 记号：控制台默认 GBK 时 print 会抛 UnicodeEncodeError，
# 让整条腿在"已经算完"之后死掉。放在任何其它 import 之前，导入期崩也报得出来。
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import math
import statistics

from virtu_eval.provenance import delta_verdict, noise_envelope  # noqa: E402

DIM_ORDER = ["knowledge", "toolcall", "reasoning", "instruction", "generation",
             "generalization", "boundary", "multimodal"]


def mcnemar(deltas):
    """配对离散结果的精确 McNemar（符号检验），这才是今晚这种数据的正确检验。

    两臂分数由少数判据组成，逐题 Δ 是离散跳变（±33/±50/±100），t 近似只看均值与散布，
    会把"功效来自几个分歧题"这件事藏起来。McNemar 直接回答：分歧题里 B 赢的比 A 多不多。
    返回 b(B赢)/c(A赢)、双侧精确 p，以及达到 80% 功效还差多少分歧题。
    """
    b = sum(1 for d in deltas if d > 1e-9)
    c = sum(1 for d in deltas if d < -1e-9)
    n = b + c
    if n == 0:
        return {"b_B_wins": 0, "c_A_wins": 0, "n_discordant": 0,
                "p_two_sided": 1.0, "verdict": "两臂在所有题上同分 ⇒ 这条维不含任何判别信息",
                "discordants_needed_for_80pct_power": None}
    k = min(b, c)
    # 双侧精确二项（p=0.5）
    p = sum(math.comb(n, i) for i in range(k + 1)) * 2 / (2 ** n)
    p = min(1.0, p)
    # 80% 功效（双侧 α=0.05）下，若真实优势比 b:c 保持观测值，需要的分歧题数
    ratio = max(b, c) / n
    need = None
    for nn in range(n, 20001):
        lo = nn * 0.5 - 1.96 * math.sqrt(nn) / 2
        # 用正态近似解：需要 nn 使 nn*(2*ratio-1) > 2.8*sqrt(nn)  ⇒ nn > (2.8/(2ratio-1))^2
        if ratio <= 0.5:
            break
        if nn * (2 * ratio - 1) > 2.8 * math.sqrt(nn):
            need = nn
            break
    return {"b_B_wins": b, "c_A_wins": c, "n_discordant": n,
            "p_two_sided": round(p, 4),
            "verdict": ("分歧题显著不对称" if p < 0.05 else "分歧题方向不对称不显著"),
            "observed_edge_ratio": round(ratio, 3),
            "discordants_needed_for_80pct_power": need,
            "note": "功效由分歧题数决定，不由总题数决定；把饱和题（各臂同分）换掉或加难才有用"}


def load_run(run_dir):
    raw = os.path.join(run_dir, "raw.jsonl")
    if not os.path.exists(raw):
        raise SystemExit(f"[FATAL] {raw} 不存在 —— 缺腿不得出判定")
    per_dim, trunc, per_case = {}, {}, {}
    tools_requested = {}
    with open(raw, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("verdict") == "transport_error" or r.get("score") is None:
                continue
            d = r.get("dimension") or "unknown"
            per_dim.setdefault(d, []).append(float(r["score"]))
            per_case.setdefault(d, {})[r["case_id"]] = float(r["score"])
            tools_requested.setdefault(d, {"asked": 0, "total": 0})
            tools_requested[d]["total"] += 1
            gen = r.get("gen") or {}
            if gen.get("tools_requested"):
                tools_requested[d]["asked"] += 1
            ct, mt = gen.get("completion_tokens"), r.get("max_tokens")
            if ct and mt and ct >= mt:
                trunc[d] = trunc.get(d, 0) + 1
    if not per_dim:
        raise SystemExit(f"[FATAL] {run_dir}: 0 条有效记录（全传输错误？）—— 空样本不算通过")
    means = {d: round(sum(v) / len(v), 2) for d, v in per_dim.items()}
    return {"n": {d: len(v) for d, v in per_dim.items()},
            "per_case": {d: dict(v) for d, v in per_case.items()},
            "mean": means, "trunc": trunc,
            "tools_requested_rate": {d: round(v["asked"] / v["total"], 3) if v["total"] else 0.0
                                     for d, v in tools_requested.items()},
            "model_id": os.path.basename(run_dir.rstrip("/\\"))}


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def served_models_of(run_dir):
    """腿的身份只认 raw.jsonl 每条记录里的 served_model，不认臂名/标签名。

    2026-11-06 的事故就是四个标签被不同会话重指到同一 manifest：任何以名字为准的
    A/B 都可能是同一次推理的两个副本。记录级 served_model 是服务方自己回的，改不了。
    返回 (counts, unattributed_case_ids)。
    """
    out, orphan = {}, []
    with open(os.path.join(run_dir, "raw.jsonl"), encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("verdict") == "transport_error" or r.get("score") is None:
                continue     # 传输错误本来就不占样本位，也不算不可归因
            sm = ((r.get("gen") or {}).get("served_model")
                  or r.get("served_model") or "")
            if not sm:
                orphan.append(r.get("case_id"))
                continue
            out[sm] = out.get(sm, 0) + 1
    return out, orphan


def dim_tools_rate(run_dir):
    """每一维里"请求里真的带了 tools schema"的比例 —— toolcall 维没有 tools 就是空转测量。"""
    acc = {}
    with open(os.path.join(run_dir, "raw.jsonl"), encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("verdict") == "transport_error" or r.get("score") is None:
                continue
            d = r.get("dimension") or "unknown"
            gen = r.get("gen") or {}
            a = acc.setdefault(d, [0, 0])
            a[1] += 1
            if gen.get("tools_requested"):
                a[0] += 1
    return {d: round(v[0] / v[1], 3) if v[1] else 0.0 for d, v in acc.items()}


def build_identity(a_dir, b_dir, noise_path, dims, extra_gates, max_unattributed=0):
    """run_id = 两份 raw.jsonl 字节 + 噪声尺子字节 + 本脚本字节 + 维度 的指纹。"""
    self_sha = sha256_of(os.path.abspath(__file__))
    ra_sha, rb_sha = sha256_of(os.path.join(a_dir, "raw.jsonl")), sha256_of(os.path.join(b_dir, "raw.jsonl"))
    nz_sha = sha256_of(noise_path) if os.path.exists(noise_path) else None
    sm_a, orph_a = served_models_of(a_dir)
    sm_b, orph_b = served_models_of(b_dir)
    blob = "|".join([ra_sha, rb_sha, nz_sha or "-", self_sha, ",".join(dims)])
    gates = dict(extra_gates)
    # I1：单臂内 served_model 必须唯一，否则这条腿混了不同模型，逐题配对无意义
    gates["I1_single_served_model_per_arm"] = (len(sm_a) == 1 and len(sm_b) == 1)
    # I2：两臂服务身份必须真的不同 —— 相同 ⇒ 这是同一次推理的两个副本，判定无效
    gates["I2_arms_are_different_models"] = bool(set(sm_a) != set(sm_b))
    # I3：每条计分响应都要能归因。归因不了的题不得当作"模型失败"计入配对。
    gates["I3_every_scored_row_attributable"] = (len(orph_a) + len(orph_b) <= max_unattributed)
    # I4：toolcall 维必须真的发过 tools schema。没发过 ⇒ 判分器在给"从未存在的能力面"打分，
    # 2026-11-06 那批 knowledge 腿的 toolcall 维 σ(Δ)=0 就是这么来的（空转，不是"两臂一致"）。
    tr_a, tr_b = dim_tools_rate(a_dir), dim_tools_rate(b_dir)
    toolsless = sorted({d for d in dims
                        if d == "toolcall"
                        and max(tr_a.get(d, 0.0), tr_b.get(d, 0.0)) < 0.5})
    gates["I4_toolcall_dims_actually_sent_tools"] = not toolsless
    run_id = hashlib.sha256(blob.encode()).hexdigest()[:16]
    return {
        "run_id": run_id,
        "basis": "measured" if gates["I3_every_scored_row_attributable"] and max_unattributed == 0
                 else "measured_degraded",
        "identity_gates": gates,
        # I0–I3 是"这条腿能不能用"，判红即作废；I4 是"这一维能不能算"，只剔维不毁腿。
        "passed": all(v for k, v in gates.items() if not k.startswith("I4")),
        "toolsless_toolcall_dimensions": toolsless,
        "tools_requested_rate": {"A": tr_a, "B": tr_b},
        "max_unattributed_allowed": max_unattributed,
        "unattributable_cases": {"A": sorted(x for x in orph_a if x),
                                 "B": sorted(x for x in orph_b if x)},
        "arm_a": {"dir": os.path.abspath(a_dir), "raw_jsonl_sha256": ra_sha,
                  "served_model_counts": sm_a},
        "arm_b": {"dir": os.path.abspath(b_dir), "raw_jsonl_sha256": rb_sha,
                  "served_model_counts": sm_b},
        "noise_ruler": {"path": os.path.abspath(noise_path), "sha256": nz_sha,
                        "present": bool(nz_sha)},
        "verdict_script_sha256": self_sha,
        "dimensions": list(dims),
        "note": "身份按字节归属：run_id 由两份 raw.jsonl + 噪声尺子 + 判据脚本的 sha256 派生；"
                "served_model 取自每条响应，不取自臂名；空 served_model 的计分题被剔除并单独记账，"
                "不当作能力失败",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True, help="run dir of arm A")
    ap.add_argument("--b", required=True, help="run dir of arm B")
    ap.add_argument("--label", default="A vs B")
    ap.add_argument("--noise", default=os.path.join(ROOT, "runs", "moe14b_noise_probe.json"))
    ap.add_argument("--out", default=os.path.join(ROOT, "runs", "moe14b_ab_verdict.json"))
    ap.add_argument("--max-unattributed", type=int, default=0,
                    help="允许多少条计分题无法归因（默认 0 = 零容忍）。放宽后 basis 记 "
                         "measured_degraded，且这些题从配对里剔除")
    args = ap.parse_args()

    env = noise_envelope(args.noise)
    sigma = env["paired_sigma"]
    ra, rb = load_run(args.a), load_run(args.b)

    dims = [d for d in DIM_ORDER if d in ra["mean"] and d in rb["mean"]]
    if not dims:
        raise SystemExit("[FATAL] 两臂没有共同维度可配")

    ident = build_identity(args.a, args.b, args.noise, dims,
                           {"I0_noise_ruler_present": bool(env.get("n_pairs"))},
                           max_unattributed=args.max_unattributed)
    if not ident["passed"]:
        print("[GATE_FAILED] 腿的身份不成立，判定无效：",
              json.dumps(ident["identity_gates"], ensure_ascii=False), file=sys.stderr)
        print(json.dumps({"served_model": {"A": ident["arm_a"]["served_model_counts"],
                                           "B": ident["arm_b"]["served_model_counts"]},
                          "unattributable_cases": ident["unattributable_cases"]},
                         ensure_ascii=False), file=sys.stderr)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({"basis": "measured", "verdict": "INVALID_IDENTITY",
                       "identity": ident, "label": args.label}, f, indent=2, ensure_ascii=False)
        return 4

    # I4 剔维：从未发过 tools 的 toolcall 维不进判定，但剔完必须还剩东西
    excluded_dims = list(ident["toolsless_toolcall_dimensions"])
    if excluded_dims:
        print(f"[warn] 维度 {excluded_dims} 两臂都没发过 tools schema ⇒ 空转测量，剔出判定"
              f"（不是『两臂一致』）", file=sys.stderr)
        dims = [d for d in dims if d not in excluded_dims]
        if not dims:
            print("[GATE_FAILED] 唯一可配的维度是空转 toolcall ⇒ 无可判内容", file=sys.stderr)
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump({"basis": "measured", "verdict": "NO_EVALUABLE_DIMENSION",
                           "identity": ident, "label": args.label}, f, indent=2, ensure_ascii=False)
            return 4

    # 无法归因的题（空 served_model）两边一起剔除：留着等于把"服务当时没这个模型"
    # 记成"模型答错了这题"，方向性污染配对。剔除本身写进收据，不隐身。
    drop = set(ident["unattributable_cases"]["A"]) | set(ident["unattributable_cases"]["B"])
    if drop:
        for side in (ra, rb):
            for d, per_case in side["per_case"].items():
                removed = drop & set(per_case)
                for cid in removed:
                    per_case.pop(cid)
                if removed:
                    side["n"][d] = max(0, side["n"].get(d, 0) - len(removed))
            side["mean"] = {d: round(sum(v.values()) / len(v), 2)
                            for d, v in side["per_case"].items() if v}
        print(f"[warn] {len(drop)} 题因响应无法归因被剔除出配对："
              f"{sorted(drop)}（basis 降级为 {ident['basis']}）", file=sys.stderr)

    rows, overall = [], []
    for d in dims:
        A = ra["per_case"].get(d, {})
        B = rb["per_case"].get(d, {})
        common = sorted(set(A) & set(B))
        if not common:
            raise SystemExit(f"[FATAL] 维度 {d} 两臂没有共同题 id —— 无法配对，不得出判定")
        deltas = [B[c] - A[c] for c in common]
        n = len(deltas)
        mean = statistics.mean(deltas)
        # 配对均差的分母是"逐题 Δ 的散布"，不是"同臂复测的散布"。
        # 2026-11-06 实测：用复测 σ=8.84 得到的 ±4.47 带把两个其实不可判的差值判成了"净增益"，
        # 而配对 σ(Δ)=26.38 ⇒ SE=4.82 ⇒ 95%CI ±9.44 含 0。二者差两倍多，必须用后者。
        sd = statistics.stdev(deltas) if n > 1 else 0.0
        se = sd / math.sqrt(n) if sd else 0.0
        band_paired = 1.96 * se
        discordant = sum(1 for x in deltas if abs(x) > 1e-9)
        reask_band = 1.96 * sigma * math.sqrt(2.0 / n)
        attributable = abs(mean) > band_paired and abs(mean) > reask_band
        v = delta_verdict(mean, n_cases=n, sigma=sigma,
                          trunc_a=ra["trunc"].get(d, 0), trunc_b=rb["trunc"].get(d, 0))
        v.update({"dimension": d, "sigma_paired_delta": round(sd, 2), "se_paired": round(se, 2),
                  "t_paired": round(mean / se, 2) if se else None,
                  "band_paired": round(band_paired, 2), "band_reask": round(reask_band, 2),
                  "discordant_cases": f"{discordant}/{n}",
                  "attributable": attributable,
                  "verdict": ("可判净增益" if attributable and mean > 0 else
                              "可判净损失" if attributable and mean < 0 else
                              f"不可判（0 在配对 95%CI ±{band_paired:.2f} 内）")})
        # delta_verdict 只说"净正/净负增益"，不说是哪一臂 —— 今天这类歧义就是事故源头。
        # 这里把胜方、方向和幅度写成一句可读的话，结论引用时不允许再省略臂名。
        v["winner"] = (ra["model_id"] if v["attributable"] and mean < 0 else
                       rb["model_id"] if v["attributable"] else None)
        v["statement"] = (f"{v['winner']} 净胜 {abs(mean):.2f} 分（配对 95%CI ±{band_paired:.2f}，"
                          f"复测地板 ±{reask_band:.2f}，t={v['t_paired']}）" if v["attributable"] else
                          f"不可判：Δ̄={mean:+.2f} 落在配对 ±{band_paired:.2f} 内；"
                          + (f"两臂 {v['discordant_cases']} 题分数全同 ⇒ 这条维不含任何判别信息"
                             if discordant == 0 else
                             f"两臂只有 {v['discordant_cases']} 题分数不同，"
                             f"结论由这几题驱动，需按该题型扩样"))
        v["mcnemar"] = mcnemar(deltas)
        # 最终可判性以 McNemar 为准：t 近似只作参考，二者都过才叫增益
        v["attributable"] = bool(v["attributable"] and v["mcnemar"]["p_two_sided"] < 0.05)
        v["verdict"] = ("可判净增益" if v["attributable"] and mean > 0 else
                        "可判净损失" if v["attributable"] else
                        f"不可判（配对 CI ±{band_paired:.2f} 含 0；"
                        f"McNemar p={v['mcnemar']['p_two_sided']}）")
        rows.append(v)
        overall.append((mean, n))

    # 总计也必须用配对统计：把各维共同题的 Δ 汇总，绝不沿用 delta_verdict 的复测带
    pooled = []
    for d in dims:
        A, B = ra["per_case"].get(d, {}), rb["per_case"].get(d, {})
        pooled += [B[c] - A[c] for c in sorted(set(A) & set(B))]
    n_tot = len(pooled)
    mean_tot = statistics.mean(pooled)
    sd_tot = statistics.stdev(pooled) if n_tot > 1 else 0.0
    se_tot = sd_tot / math.sqrt(n_tot) if sd_tot else 0.0
    band_tot = round(1.96 * se_tot, 2)
    disc_tot = sum(1 for x in pooled if abs(x) > 1e-9)
    total = {"delta": round(mean_tot, 2), "band": band_tot, "n": n_tot,
             "sigma_paired_delta": round(sd_tot, 2), "se_paired": round(se_tot, 2),
             "t_paired": round(mean_tot / se_tot, 2) if se_tot else None,
             "band_paired": band_tot, "band_reask": round(1.96 * sigma * math.sqrt(2.0 / n_tot), 2),
             "discordant_cases": f"{disc_tot}/{n_tot}",
             "attributable": bool(abs(mean_tot) > band_tot
                                  and abs(mean_tot) > 1.96 * sigma * math.sqrt(2.0 / n_tot)),
             "trunc_rate_a": round(sum(ra["trunc"].values()) / n_tot, 3),
             "trunc_rate_b": round(sum(rb["trunc"].values()) / n_tot, 3)}
    total["verdict"] = ("可判净增益" if total["attributable"] and mean_tot > 0 else
                        "可判净损失" if total["attributable"] else
                        f"不可判（0 在配对 95%CI ±{band_tot:.2f} 内）")

    band30 = 1.96 * sigma * (2.0 / 30) ** 0.5   # 复测地板，不是判据

    doc = {
        "basis": ident["basis"], "label": args.label,
        "reading_rule": "Δ 一律是 B−A；引用结论必须带臂名与 ±band，禁止裸写『领先 X 分』",
        'A': ra["model_id"], 'B': rb["model_id"],
        "noise_envelope": env, "paired_sigma": sigma,
        "resolution_limit_at_n30": round(band30, 2),
        "arm_a": {k: v for k, v in ra.items()}, "arm_b": {k: v for k, v in rb.items()},
        "ruler_note": "可判性以配对 σ(Δ) 为主、复测 σ 为地板，两者都超才叫增益；"
                      "delta_verdict 的 band 只是复测地板，不能单独当判据",
        "per_dimension": rows, "weighted_overall": total,
        "excluded_dimensions": excluded_dims,
        "rule": "R2: |Δ| ≤ 1.96·σ·√(2/n) 记『噪声内』，不得转述成领先/落后；"
                f"本尺子实测 σ={sigma}，n=30/维时可分辨下限 = {band30:.2f} 分",
        "run_id": ident["run_id"], "identity": ident,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)

    print(f"=== {args.label} ===  复测 σ={sigma} (n_pairs={env['n_pairs']}) ⇒ 复测地板 n=30 为 "
          f"±{band30:.2f}（仅是地板；可判性以配对 σ(Δ) 为准，两者都要越过）")
    for v in rows:
        print(f"  [{v['dimension']:<12}] Δ̄(B−A)={v['delta']:>7.2f}  σ(Δ)={v['sigma_paired_delta']:>6.2f}  "
              f"配对95%CI=±{v['band_paired']:.2f}  t={v['t_paired']}  不同分={v['discordant_cases']}  "
              f"⇒ {v['verdict']}")
        print(f"      ⇒ {v['statement']}")
        m = v["mcnemar"]
        print(f"      McNemar: B赢 {m['b_B_wins']} 题 / A赢 {m['c_A_wins']} 题，"
              f"分歧共 {m['n_discordant']} 题，双侧精确 p={m['p_two_sided']}，"
              f"80% 功效需分歧题 {m['discordants_needed_for_80pct_power']}")
    print(f"  [配对总计] Δ̄={total['delta']:+.2f}  σ(Δ)={total['sigma_paired_delta']}  "
          f"95%CI=±{total['band_paired']}  t={total['t_paired']}  不同分={total['discordant_cases']}  "
          f"n={total['n']}  ⇒ {total['verdict']}")
    print(f"[out] {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
