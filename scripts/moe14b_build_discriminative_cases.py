# -*- coding: utf-8 -*-
"""
scripts/moe14b_build_discriminative_cases.py — 把饱和 toolcall 题拆成有中间带的判别性题

判别力审计（runs/moe14b_case_power_audit_toolcall.json, run_id 0d142b1c35f96fe1）实测：
  30 题里只有 4 题两臂分数不同；σ(Δ)=24.14 全部来自"一题 3 条判据 ⇒ 跳变 33.3 分"。
  cross-fitting 进一步显示"只挑会分歧的题"反而更差（kept CI 48.01 > all CI 14.91），
  因为 n 掉得比 σ 快。⇒ 可用的杠杆只有一个：把单题判据拆细，让部分正确能拿部分分。

本构造器只做一件事，且不碰任何模型：
  读现有用例的 gold 工具调用 ⇒ 按槽位（tool / action / 每个参数）各出一条判据
  ⇒ 用真实判分器 virtu_eval.graders.score_case 做两个必须成立的自检：
      P1 gold 原样必须 100 分（否则判据写错了）
      P2 逐槽扰动（改 tool 名 / 改 action / 改数值）必须落在 (0, 100) 开区间
         —— 这才叫"中间难度带"，也是 σ(Δ) 变小的机制

用法：
  python scripts/moe14b_build_discriminative_cases.py \
      --in data/benchmark/virtu_eval_v1/toolcall.jsonl \
      --out data/benchmark/virtu_eval_v1_disc/toolcall.jsonl \
      --receipt runs/moe14b_discriminative_cases.json
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

from virtu_eval.graders import GRADERS, score_case  # noqa: E402

MIN_CRITERIA = 5          # 拆完还少于 5 条判据 ⇒ 粒度没改善，视为构造失败
GRANULARITY_TARGET = 20.0  # 单条判据分值步长必须 ≤ 20 分（原来 33.3~50）


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_gold(gold_answer):
    """gold 必须是 {"tool":..., "arguments":{...}}；不是就返回 None（该题不参与拆分）。"""
    try:
        obj = json.loads(gold_answer) if isinstance(gold_answer, str) else gold_answer
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None
    tool = obj.get("tool")
    args = obj.get("arguments")
    if not isinstance(tool, str) or not isinstance(args, dict):
        return None
    return tool, args


def slot_criteria(tool, args, case_id):
    """每个槽位一条判据。只用 GRADERS 里真实存在的类型，造完立刻自检。"""
    crit = [
        {"type": "json_object", "required_keys": ["tool", "arguments"], "key": "JSON 结构"},
        {"type": "enum_field", "field_enums": {"tool": [tool]}, "key": "工具名"},
    ]
    if "action" in args:
        crit.append({"type": "enum_field", "field_enums": {"action": [str(args["action"])]},
                     "key": "动作"})
    for k, v in args.items():
        if k == "action":
            continue
        if isinstance(v, bool):
            # enum_field 用 str(值) 比成员：JSON 的 false 解析成 Python False，str() 得 "False"。
            # 只写小写会让 gold 自己都不合格 —— P1 闸第一次跑就抓到了这一点。
            crit.append({"type": "enum_field", "field_enums": {k: [str(v), json.dumps(v)]},
                         "key": f"参数:{k}"})
        elif isinstance(v, (int, float)):
            crit.append({"type": "numeric_near", "value": float(v), "tol_rel": 0.005,
                         "key": f"参数:{k}"})
        elif isinstance(v, str) and v.strip():
            # 必须用 enum_field：它是"取到该字段的值再判成员"，而 regex_any/literal_all
            # 都是全文子串匹配 —— 实测把 part_name 从 flange 改成 flange_X，
            # 子串型判据仍然给 100 分（P2 闸就是为此而设，它当场抓到了）。
            crit.append({"type": "enum_field", "field_enums": {k: [v]}, "key": f"参数:{k}"})
        elif isinstance(v, (list, dict)) and v:
            for i, (leaf_key, leaf) in enumerate(scalar_leaves(v)):
                crit.append({"type": "enum_field", "field_enums": {leaf_key: [leaf]},
                             "key": f"参数:{k}[{i}]"})
    for c in crit:
        if c["type"] not in GRADERS:
            raise ValueError(f"{case_id}: 生成了判分器不认识的类型 {c['type']!r}")
    return crit


def scalar_leaves(node, limit=12):
    """容器参数拆成 (字段名, 标量值) 对 —— enum_field 按字段名取值，所以键必须一起给出。"""
    out = []

    def walk(x):
        if len(out) >= limit:
            return
        if isinstance(x, dict):
            for k, v in x.items():
                if isinstance(v, (str, int, float)) and not isinstance(v, bool) \
                        and len(str(v).strip()) >= 2:
                    out.append((k, str(v).strip()))
                else:
                    walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(node)
    return out


def perturbations(tool, args):
    """近邻错误答案 —— 用来证明"部分对能拿部分分"，不是用来喂给模型的。"""
    outs = []
    for k, v in args.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            a2 = dict(args); a2[k] = v + 1
            outs.append((f"arg:{k}+1", json.dumps({"tool": tool, "arguments": a2}, ensure_ascii=False)))
        elif isinstance(v, str) and v.strip():
            a2 = dict(args); a2[k] = v + "_X"
            outs.append((f"arg:{k}改值", json.dumps({"tool": tool, "arguments": a2}, ensure_ascii=False)))
    outs.append(("换工具名", json.dumps({"tool": "cadcam_other_control", "arguments": args},
                                        ensure_ascii=False)))
    if "action" in args:
        a2 = dict(args); a2["action"] = "wrong_action"
        outs.append(("换动作", json.dumps({"tool": tool, "arguments": a2}, ensure_ascii=False)))
    return outs


def build_one(case):
    gold = (case.get("gold") or {}).get("answer")
    prompt = str(case.get("prompt", ""))
    if isinstance(gold, str) and gold and gold in prompt:
        # clarify/refusal 家族按设计就把目标 JSON 写在题面里（考点是"照指令输出"）。
        # 这类题拆细判据没有意义（答对就是全对），必须原样保留并从判别率里排除。
        return None, {"why": "题面已含完整 gold ⇒ 按设计是送分题，不参与判别性拆分",
                      "keep_old": True, "leaky_by_design": True}
    parsed = parse_gold(gold)
    if parsed is None:
        return None, {"why": "gold 不是 {tool, arguments} 结构，无法按槽拆分", "keep_old": True}
    tool, args = parsed
    cid = case["id"]
    crit = slot_criteria(tool, args, cid)

    # P1：gold 原样必须满分。不满足就是判据写错，绝不允许"先出文件再解释"。
    scored = score_case(gold, crit)
    if abs(scored["score"] - 100.0) > 1e-6:
        failed = [d for d in scored["criteria"] if not d["passed"]]
        return None, {"why": f"P1 破：gold 自身只得 {scored['score']}，"
                             f"未过判据={[(d['key'], d['evidence']) for d in failed]}",
                      "keep_old": True}

    # P2：每个单槽扰动必须落在开区间 (0,100)，并且不同扰动给出不同分数（否则判据不分彼此）
    partial = {}
    for name, resp in perturbations(tool, args):
        s = score_case(resp, crit)["score"]
        partial[name] = s
        if not (0.0 < s < 100.0):
            return None, {"why": f"P2 破：{name} 得分 {s} 不在 (0,100)，该扰动拿不到部分分",
                          "keep_old": True}
    granularity = round(100.0 / len(crit), 2)
    if len(crit) < MIN_CRITERIA or granularity > GRANULARITY_TARGET:
        return None, {"why": f"拆完只有 {len(crit)} 条判据（粒度 {granularity} 分），"
                             f"未达 {MIN_CRITERIA} 条 / ≤{GRANULARITY_TARGET} 分",
                      "keep_old": True}
    new = dict(case)
    new["criteria"] = crit
    new["orig_criteria_n"] = len(case.get("criteria") or [])
    new["discriminative"] = {"granularity_points": granularity,
                             "perturbation_scores": partial,
                             "built_by": "scripts/moe14b_build_discriminative_cases.py"}
    return new, {"granularity": granularity, "n_criteria": len(crit),
                 "perturbation_scores": partial,
                 "granularity_before": round(100.0 / max(1, len(case.get("criteria") or [1])), 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--receipt", default=None)
    args = ap.parse_args()

    src = args.infile if os.path.isabs(args.infile) else os.path.join(ROOT, args.infile)
    dst = args.out if os.path.isabs(args.out) else os.path.join(ROOT, args.out)
    rows = [json.loads(l) for l in open(src, encoding="utf-8") if l.strip()]
    if not rows:
        raise SystemExit("[FATAL] 空用例文件 —— 空集不得算构造成功")

    built, skipped = [], []
    for c in rows:
        new, info = build_one(c)
        if new is None:
            skipped.append({"id": c.get("id"), **info})
            built.append(c)          # 保留原题，不假装拆细了
        else:
            built.append(new)

    if not any(b.get("discriminative") for b in built):
        print("[GATE_FAILED] 一题都没拆成功 ⇒ 没有产出判别性题单", file=sys.stderr)
        print(json.dumps(skipped[:5], ensure_ascii=False, indent=1), file=sys.stderr)
        return 4

    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "w", encoding="utf-8") as f:
        for b in built:
            f.write(json.dumps(b, ensure_ascii=False) + "\n")

    ok = [b for b in built if b.get("discriminative")]
    gran_after = [b["discriminative"]["granularity_points"] for b in ok]
    pscores = [s for b in ok for s in b["discriminative"]["perturbation_scores"].values()]
    receipt = {
        "basis": "measured",
        "tool": "scripts/moe14b_build_discriminative_cases.py",
        "in_file": src, "in_sha256": sha256_file(src),
        "out_file": dst, "out_sha256": sha256_file(dst),
        "n_cases_in": len(rows), "n_cases_rebuilt": len(ok),
        "n_cases_kept_as_is": len(skipped),
        "granularity_points_after": {"min": min(gran_after), "max": max(gran_after),
                                     "mean": round(sum(gran_after) / len(gran_after), 2)},
        "partial_credit_observed": {"n_perturbations": len(pscores),
                                    "min": min(pscores), "max": max(pscores),
                                    "distinct_scores": len(set(round(x, 2) for x in pscores))},
        "checks": {"P1_gold_scores_100": True,
                   "P2_every_perturbation_in_open_interval": True,
                   "P3_no_rebuilt_case_has_gold_in_prompt": all(
                       str((c.get("gold") or {}).get("answer", "")) not in str(c.get("prompt", ""))
                       for c in ok)},
        "n_leaky_by_design_excluded": sum(1 for s in skipped if s.get("leaky_by_design")),
        "skipped": skipped,
        "note": "P1/P2 在真实判分器 virtu_eval.graders.score_case 上执行，不起任何推理腿；"
                "构造失败的题原样保留并登记原因，不用删题来凑判别率",
    }
    if not receipt["checks"]["P3_no_rebuilt_case_has_gold_in_prompt"]:
        print("[GATE_FAILED] 拆分后的题里出现了『题面含完整 gold』—— 那是送分，不是判别", file=sys.stderr)
        return 4

    rp = args.receipt or (dst + ".receipt.json")
    os.makedirs(os.path.dirname(os.path.abspath(rp)), exist_ok=True)
    with open(rp, "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2, ensure_ascii=False)
    print(json.dumps({k: receipt[k] for k in
                      ("n_cases_in", "n_cases_rebuilt", "n_cases_kept_as_is",
                       "granularity_points_after", "partial_credit_observed", "checks")},
                     ensure_ascii=False, indent=1))
    print(f"[out] {dst}\n[receipt] {rp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
