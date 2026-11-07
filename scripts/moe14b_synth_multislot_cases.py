# -*- coding: utf-8 -*-
"""
scripts/moe14b_synth_multislot_cases.py — 合成"多槽 + 值级分歧"的 toolcall 题单

为什么要合成：判别力审计（run_id 0d142b1c35f96fe1）与离线重打分（run_id 8421bf66d5c7c28b）
证明了两件事 ——
  ① σ(Δ) 的旋钮是单题判据粒度：现有 30 题只有 2–3 条判据 ⇒ 跳变 33.3–50 分；
  ② 该旋钮只对"分歧确实落在被拆细的槽位上"的题有效：随机门 vs 正交门那对，
     2 道分歧题全部落在没拆的题里，所以 σ(Δ)=8.46 纹丝不动（run_id fc573cb783aed95d）。
而现有 gold 里 17/30 题只有 2–4 个槽，**拆不出更多判据不是脚本弱，是题面信息量就这么多**。
⇒ 要拿到 ≥5 槽的题面只能新写。本脚本按模型真正看到的 schema 写，并全部离线自证。

关键约束（每条都有对应的机器检查，不靠人工保证）：
  S1 schema 唯一参照：工具清单取自 virtu_eval/arms.json 里该臂实际发送的 tools，
     绝不从 bridges/tool_calling_specs.py 另抄一份（两者已经不一致：目录里有 17 个，
     在役臂只发 16 个，少 cadcam_feature_ops —— 用目录出题会出成"模型看不见的工具"）。
  S2 槽位下限：tool + action + ≥3 个参数 ⇒ 判据 ≥5 条、粒度 ≤20 分。
  S3 公平性：gold 里每个标量值都必须出现在题面里（考点是"意图→工具/动作/参数名的映射"，
     不是猜数值）。缺一个就判红，不许出"只有标准答案知道"的题。
  S4 非送分：完整 gold JSON 不得出现在题面里。
  S5 可判性：gold 必须 100 分；每个单槽扰动必须落在 (0,100)；
     近邻错误调用（同参数、换工具或换动作）必须 <100 且 ≥20 —— 这才叫中间难度带。
  S6 纯种子：值由 random.Random(SEED) 生成，重跑逐字节一致（否则题单 sha 不稳，归因失效）。

用法：
  python scripts/moe14b_synth_multislot_cases.py --arm moe14b_gate_random \
      --out data/benchmark/virtu_eval_v1_disc/toolcall_multi.jsonl \
      --receipt runs/moe14b_synth_multislot_cases.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "disc_builder", os.path.join(ROOT, "scripts", "moe14b_build_discriminative_cases.py"))
builder = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(builder)          # 判据构造只有一份实现（宪法第 5 条）

from virtu_eval.graders import score_case  # noqa: E402

SEED = 20261106
MIN_SLOTS = 5               # S2
MAX_SLOTS = 9
# S5 中间带的上下沿是按"整条路由换掉、参数照抄"这个错误模型定的：
# 误路由在加法判据下仍会捞到参数分，所以带上沿不追求 0 分，只要求"看得出来掉了大半"。
NEIGHBOUR_MIN_SCORE = 20.0
NEIGHBOUR_MAX_SCORE = 65.0
# 权重（design，附理由，见 _fit_and_check）：路由占大头，参数转录占小头。
ROUTING_WEIGHT = 3.0
PARAM_WEIGHT = 0.5

_STR_POOL = ["dfn_cn_m6_40", "hp_605_flange", "b12_x90_cover", "rc_240_shaft",
             "tb_300_plate", "br_120_gusset", "sg_801_housing", "pn_502_stub"]
_PATH_POOL = [r"D:\cad\part_a.step", r"D:\cad\asm_b.nx", r"D:\cam\op_12.nc",
              r"D:\sim\job_7.vcu", r"D:\cad\drw_c.dxf", r"D:\cam\post_3.ptp"]
_NUM_POOL = [42.5, 8.0, 120.0, 3.2, 15.0, 2.5, 64.0, 11.1]


def arm_tools(arm_name):
    p = os.path.join(ROOT, "virtu_eval", "arms.json")
    a = json.load(open(p, encoding="utf-8"))
    if arm_name not in a:
        raise SystemExit(f"[FATAL] arms.json 里没有 {arm_name}")
    spec = a[arm_name]
    tools = spec.get("tools") or []
    if not tools:
        raise SystemExit(f"[FATAL] {arm_name} 没有 tools 清单 ⇒ 无法按模型看到的 schema 出题")
    if "toolcall" not in (spec.get("tools_dimensions") or []):
        raise SystemExit(f"[FATAL] {arm_name} 的 tools_dimensions 不含 toolcall（S1 破）")
    return tools, hashlib.sha256(json.dumps(tools, sort_keys=True).encode()).hexdigest()


def scalar_value(kind, name, rng):
    if kind == "boolean":
        return rng.choice([True, False])
    if kind == "integer":
        return int(rng.choice([2, 4, 6, 8, 12, 24, 36]))
    if kind == "number":
        return rng.choice(_NUM_POOL)
    if "path" in name or name.endswith("_file") or name.endswith("_filename"):
        return rng.choice(_PATH_POOL)
    return rng.choice(_STR_POOL)


def make_case(tool, action, props, rng, idx):
    """返回 (case, 题面里写出的值表)。参数只取标量型，保证每槽都能核对。"""
    scalars = [(k, v) for k, v in props.items()
               if k != "action" and v.get("type") in ("string", "number", "integer", "boolean")]
    if not scalars:
        return None, "该 action 的参数面没有标量槽（拆不出参数级判据）"
    chosen = scalars[:MAX_SLOTS - 2]
    args = {}
    if action:
        args["action"] = action
    for k, v in chosen:
        args[k] = scalar_value(v.get("type"), k, rng)
    if len(args) + 1 < MIN_SLOTS:      # +1 是工具名判据
        return None, f"只有 {len(args) + 1} 个槽（含工具名），不足 {MIN_SLOTS}"
    name_lines = "、".join(f"{k}={v}" if not isinstance(v, bool)
                          else f"{k}={'是' if v else '否'}" for k, v in args.items())
    prompt = (f"要让 {tool} 完成这次操作，参数按下面给：{name_lines}。"
              f"请输出一个 JSON 工具调用，字段为 tool 与 arguments。")
    gold = json.dumps({"tool": tool, "arguments": args}, ensure_ascii=False)
    case = {"id": f"toolcall-d{idx:02d}", "dimension": "toolcall",
            "tier": "medium", "language": "zh", "prompt": prompt,
            "gold": {"answer": gold}, "criteria": []}
    return case, args


def stated_in_prompt(value, prompt):
    if isinstance(value, bool):
        return ("是" if value else "否") in prompt
    s = repr(value) if isinstance(value, float) and not value.is_integer() else str(value)
    return s in prompt or (isinstance(value, float) and value.is_integer()
                           and str(int(value)) in prompt)


def neighbours(tool, action, args, tool_names, max_n=6):
    """错误模型 = 整条路由走偏（换工具并且用那个工具自己的动作），参数值照抄。

    不要只翻 tool 或只翻 action：真实误路由是"它去调另一个工具了"，那时动作也是那个工具的。
    只翻一项会造出"工具是 A、动作是 B 的"这种没有智能体会产出的假答案。
    """
    outs = []
    for t2 in [t for t in tool_names if t != tool][:3]:
        acts2 = _ACTIONS.get(t2) or [None]
        for a2 in acts2[:2]:
            aa = {k: v for k, v in args.items() if k != "action"}
            if a2 is not None:
                aa["action"] = a2
            outs.append((f"误路由→{t2}/{a2}",
                         json.dumps({"tool": t2, "arguments": aa}, ensure_ascii=False)))
            if len(outs) >= max_n:
                return outs
    return outs


_ACTIONS = {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="moe14b_gate_random")
    ap.add_argument("--out", required=True)
    ap.add_argument("--receipt", default=None)
    ap.add_argument("--limit", type=int, default=24)
    args = ap.parse_args()

    tools, tools_sha = arm_tools(args.arm)
    global _ACTIONS
    _ACTIONS = {}
    tool_names = []
    schemas = []
    for t in tools:
        f = t["function"]
        props = f["parameters"]["properties"]
        acts = props.get("action", {}).get("enum", [])
        _ACTIONS[f["name"]] = list(acts)
        tool_names.append(f["name"])
        schemas.append((f["name"], acts, props))

    rng = random.Random(SEED)
    built, rejected = [], []
    idx = 0
    for name, acts, props in schemas:
        for action in (acts or [None]):
            if len(built) >= args.limit:
                break
            idx += 1
            case, info = make_case(name, action, props, rng, idx)
            if case is None:
                rejected.append({"tool": name, "action": action, "why": info})
                continue
            crit, why = _fit_and_check(case, name, action, props, tool_names)
            if crit is None:
                rejected.append({"tool": name, "action": action, "case_id": case["id"], "why": why})
                continue
            case["criteria"] = crit
            tw = sum(float(c.get("weight", 1)) for c in crit)
            rw = sum(float(c.get("weight", 1)) for c in crit if c["key"] in ("工具名", "动作"))
            case["discriminative"] = {"total_weight": tw,
                                      "routing_weight_share": round(rw / tw, 3),
                                      "min_step_points": round(100.0 * PARAM_WEIGHT / tw, 2),
                                      "routing_step_points": round(100.0 * rw / tw, 2),
                                      "perturbation_scores": why["pert"],
                                      "neighbour_scores": why["neigh"],
                                      "built_by": "scripts/moe14b_synth_multislot_cases.py"}
            built.append(case)

    if len(built) < 6:
        print(f"[GATE_FAILED] 只合成 {len(built)} 题，不足 6 题不构成题单", file=sys.stderr)
        print(json.dumps(rejected[:8], ensure_ascii=False, indent=1), file=sys.stderr)
        return 4

    dst = args.out if os.path.isabs(args.out) else os.path.join(ROOT, args.out)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "w", encoding="utf-8") as f:
        for c in built:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    gran = [c["discriminative"]["min_step_points"] for c in built]
    rstep = [c["discriminative"]["routing_step_points"] for c in built]
    neigh = [s for c in built for s in c["discriminative"]["neighbour_scores"].values()]
    # builder.perturbations() 里既有"单个参数改值"也有"换工具名/换动作"，两者代价差一个量级，
    # 混在一个字段里报会被人读成"参数错误只值 45 分"。按类别拆开。
    all_pert = [(k, v) for c in built for k, v in c["discriminative"]["perturbation_scores"].items()]
    pert = [v for k, v in all_pert if k.startswith("arg:") and k != "arg:action改值"]
    routing_flips = [v for k, v in all_pert if not (k.startswith("arg:") and k != "arg:action改值")]
    receipt = {
        "basis": "measured",
        "tool": "scripts/moe14b_synth_multislot_cases.py",
        "arm": args.arm, "arm_tools_sha256": tools_sha, "n_tools_in_surface": len(tool_names),
        "seed": SEED,
        "weights": {"routing": ROUTING_WEIGHT, "param": PARAM_WEIGHT,
                    "routing_share_min_allowed": 0.5},
        "out_file": dst, "out_sha256": _sha(dst), "n_cases": len(built),
        "n_rejected": len(rejected),
        "criteria_per_case": {k: sum(1 for c in built if len(c["criteria"]) == k)
                              for k in sorted({len(c["criteria"]) for c in built})},
        "min_step_points": {"min": min(gran), "max": max(gran),
                            "mean": round(sum(gran) / len(gran), 2)},
        "routing_error_cost_points": {"min": min(rstep), "max": max(rstep),
                                      "mean": round(sum(rstep) / len(rstep), 2)},
        "single_parameter_error_scores": {"n": len(pert), "min": min(pert), "max": max(pert),
                                          "distinct": len(set(pert))},
        "routing_flip_scores_from_perturbations": {"n": len(routing_flips),
                                                   "min": min(routing_flips),
                                                   "max": max(routing_flips)},
        "misroute_neighbour_scores": {"n": len(neigh), "min": min(neigh), "max": max(neigh),
                                      "band": [NEIGHBOUR_MIN_SCORE, NEIGHBOUR_MAX_SCORE],
                                      "all_within_band": bool(all(
                                          NEIGHBOUR_MIN_SCORE <= x <= NEIGHBOUR_MAX_SCORE
                                          for x in neigh))},
        "checks": {"S1_schema_from_the_arm_that_serves_it": True,
                   "S2_min_5_slots": all(len(c["criteria"]) >= MIN_SLOTS for c in built),
                   "S3_every_gold_value_stated_in_prompt": True,
                   "S4_full_gold_not_in_prompt": True,
                   "S5_gold_100_and_perturbations_partial_and_neighbours_midband": True,
                   "S5b_routing_carries_at_least_half_the_weight": True},
        "rejected": rejected,
        "note": "本文件里的数字全部由真实判分器 virtu_eval.graders.score_case 现算，零推理；"
                "σ(Δ) 的实际收益必须等推理腿（提交内存不足时不得假装已验证）",
    }
    rp = args.receipt or (dst + ".receipt.json")
    with open(rp, "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2, ensure_ascii=False)
    print(json.dumps({k: receipt[k] for k in ("n_cases", "n_rejected", "criteria_per_case", "weights",
                                              "min_step_points", "routing_error_cost_points", "single_parameter_error_scores",
                                              "routing_flip_scores_from_perturbations",
                                              "misroute_neighbour_scores", "checks")},
                     ensure_ascii=False, indent=1))
    print(f"[out] {dst}\n[receipt] {rp}")
    return 0


def _fit_and_check(case, tool, action, props, tool_names):
    """把 builder.slot_criteria 装上，并跑 S3/S4/S5。任何一条不过就不收这道题。"""
    args = json.loads(case["gold"]["answer"])["arguments"]
    crit = builder.slot_criteria(tool, args, case["id"])
    # 权重设计（design，附理由）：参数值是题面逐字给出的转录任务，工具名/动作才是被测能力。
    # 均匀权重下"整条路由全错"仍得 83–90 分（实测），等于不惩罚路由 —— 那正是
    # 现有题单没有判别力的原因之一。路由判据权重提到参数的 ROUTING_WEIGHT 倍后，
    # 全路由错误落进 [20,65]，单参数错误仍在 80+ 高分区 ⇒ 分数面单调且路由敏感。
    # 注意：权重只加在本合成族上。原 30 题的拆细族保持均匀权重不改，
    # 否则已发布的 σ(Δ) 测量（run_id 8421bf66d5c7c28b）就不复现了。
    for c in crit:
        if c["key"] in ("工具名", "动作"):
            c["weight"] = ROUTING_WEIGHT
        else:
            c["weight"] = PARAM_WEIGHT
    total_w = sum(float(c.get("weight", 1)) for c in crit)
    routing_share = sum(float(c.get("weight", 1)) for c in crit
                        if c["key"] in ("工具名", "动作")) / total_w
    if routing_share < 0.5:
        return None, f"路由判据权重占比只有 {routing_share:.2f} ⇒ 整条路由错仍得高分，题目不测路由"
    if len(crit) < MIN_SLOTS:
        return None, f"按槽拆完只有 {len(crit)} 条判据，不足 {MIN_SLOTS}"
    gold = case["gold"]["answer"]
    if abs(score_case(gold, crit)["score"] - 100.0) > 1e-6:
        return None, "S5 破：gold 自身不满分"
    if gold in case["prompt"]:
        return None, "S4 破：完整 gold 出现在题面"
    for k, v in args.items():
        if not stated_in_prompt(v, case["prompt"]):
            return None, f"S3 破：参数 {k}={v} 没写进题面 ⇒ 该值靠猜，考点不成立"
    pert = {}
    for name, resp in builder.perturbations(tool, args):
        s = score_case(resp, crit)["score"]
        if not (0.0 < s < 100.0):
            return None, f"S5 破：单槽扰动 {name} 得分 {s} 不在 (0,100)"
        pert[name] = s
    neigh = {}
    for i, (label, resp) in enumerate(neighbours(tool, action, args, tool_names)):
        s = score_case(resp, crit)["score"]
        if not (NEIGHBOUR_MIN_SCORE <= s <= NEIGHBOUR_MAX_SCORE):
            return None, f"S5 破：近邻错误 {label} 得分 {s} 不在中间带 " \
                         f"[{NEIGHBOUR_MIN_SCORE},{NEIGHBOUR_MAX_SCORE}]"
        neigh[f"{label}#{i}"] = s
    return crit, {"pert": pert, "neigh": neigh}


def _sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


if __name__ == "__main__":
    sys.exit(main())
