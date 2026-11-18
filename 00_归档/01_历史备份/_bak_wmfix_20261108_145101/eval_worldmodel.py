#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval_worldmodel.py — 世界模型评测器（训练+注册后运行）
===================================================
方法：复用 build_worldmodel_sft 的生成器产出"已知真值"的评测用例
（user 提示 + 期望 world_state JSON），调用 ollama 模型，解析其输出的
JSON，逐字段比对数值精度，输出各 family 的通过率与总体精度。

评测维度（可回灌验证的物理量）：
  - removal/mrr：材料去除量、MRR、余下质量、ΔV<0
  - roughness：Ra（μm）
  - fea_fos：FOS、FOS≥1.5 闸门
  - collision：碰撞/过切风险、Auto-Diff 颜色
  - tolerance：极值/RSS 半宽、配合等级
  - geom_delta：ΔV 守恒
  - invalid：应拒绝的非法输入（world_state=null）

用法：
  python scripts/eval_worldmodel.py --model virtu-wm-all90 --n 120 --out _eval_wm.json
"""
import os
import sys
import json
import argparse
import subprocess
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import build_worldmodel_sft as W
import wm_contract as C
from guard_hooks import apply_guard  # 推理时护栏：生成即校验，替换旧的只判分用法

GEN_BY_FAMILY = {
    "removal": W.gen_removal_mrr,
    "roughness": W.gen_roughness,
    "fea_fos": W.gen_fea_fos,
    "collision": W.gen_collision_gcode,
    "tolerance": W.gen_tolerance,
    "geom_delta": W.gen_geometric_delta,
    "mass_props": W.gen_mass_props,
    "invalid": W.gen_invalid,
}

# v2 四族补齐：旧版 GEN_BY_FAMILY 只有 v1 八族，design/process/adapt_machine/
# adapt_material 虽然在契约、验算器、护栏里全部落地，却从未进过评测器 →
# 新族"有没有通过率"这件事一直无数据，属评测链路真实缺口。
try:
    import build_worldmodel_v2 as V2

    def _fam_filter(gen, fam, tries=200):
        """gen_unfamiliar_adaptation 随机返回 adapt_machine / adapt_material 之一，
        评测需要单族样本，故按 rec['scenario']['task'] 重采样直到命中目标族。"""
        def g(rng):
            for _ in range(tries):
                r = gen(rng)
                if r and (r.get("scenario") or {}).get("task") == fam:
                    return r
            return None
        return g

    GEN_BY_FAMILY.update({
        "design": V2.gen_design_from_requirement,
        "process": V2.gen_machining_process_plan,
        "adapt_machine": _fam_filter(V2.gen_unfamiliar_adaptation, "adapt_machine"),
        "adapt_material": _fam_filter(V2.gen_unfamiliar_adaptation, "adapt_material"),
    })
except Exception as _e:  # v2 语料构建器缺失时不影响 v1 八族评测
    print(f"[warn] v2 族评测不可用: {_e}", file=sys.stderr)
REL_TOL = 0.08  # 8% 相对容差

# P0 修复：判分词表改为从契约单一真源导入，禁止在本文件另立一份。
# 历史缺陷是本文件持有唯一 NUM_KEYS，而该词表从未下发给模型。
NUM_KEYS = {fam: spec["numeric"] for fam, spec in C.KEY_SCHEMA.items()}
GATES = {fam: list(spec["gates"].keys()) for fam, spec in C.KEY_SCHEMA.items()}


REQ_TIMEOUT = 180.0


def call_ollama(model, prompt, system, think=False, max_tokens=1024, force_json=True,
                timeout_sec=None):
    # 关掉 Qwen3 等模型的默认思考模式（否则输出被 <think> 包裹、world_state JSON
    # 无法解析，且思考 token 会吃光 num_predict）。非思考模型会忽略 think 字段；
    # temperature=0 保持可复现。
    # force_json=True 走 llama.cpp grammar 约束：这是把解析失败率从 16%~79% 压下去
    # 的结构性手段（参数调优治不了自回归发散）。
    body = {"model": model, "prompt": prompt,
            "system": system, "stream": False, "think": think,
            "options": {"temperature": 0, "num_predict": max_tokens}}
    if force_json:
        body["format"] = "json"
    payload = json.dumps(body)
    # 坑：Windows 下 subprocess(text=True) 默认按 locale(GBK) 解码，而 ollama
    # 返回 UTF-8 中文会抛 UnicodeDecodeError → stdout=None → 整题被误记为解析
    # 失败。必须显式指定 utf-8 + errors=replace。
    p = subprocess.run(["curl", "-s", "http://127.0.0.1:11434/api/generate", "-d", payload],
                       capture_output=True, text=True,
                       timeout=(timeout_sec or REQ_TIMEOUT),
                       encoding="utf-8", errors="replace")
    raw = (p.stdout or "").strip()
    try:
        return json.loads(raw)["response"]
    except Exception as e:
        return f"<parse-fail:{e}|raw={raw[:200]}>"


def _ws(obj):
    """统一提取 world_state 内容，兼容三种返回形态：
      ① 完整对象 {"world_state": {...}, ...}
      ② guard 已剥好的内层 {...}
      ③ 裸平铺字段
    历史缺陷：apply_guard 的 final_world_state 是**内层**，而判分器仍按
    pred.get("world_state") 取，导致 raw 完全正确的样本被 100% 判失败。
    """
    if not isinstance(obj, dict):
        return {}
    inner = obj.get("world_state")
    if isinstance(inner, dict):
        return inner
    if "world_state" in obj and inner is None:
        return {}
    return obj


def _flatten(d):
    """展平一层嵌套子对象（tolerance / mass_props / design 等）。

    契约条目 C 原文写"几何质量属性放 world_state 的 mass_props"，模型据此输出
    world_state.mass_props.volume_mm3，而训练数据是 world_state.volume_mm3 平铺。
    两种形态语义等价，判分必须兼容，否则系统性假失败。
    """
    out = {}
    for k, v in (d or {}).items():
        if isinstance(v, dict):
            for k2, v2 in v.items():
                out.setdefault(k2, v2)
        else:
            out[k] = v
    return out


def _wrap(gws):
    """把 guard 的 final_world_state 归一成完整对象。

    guard 有两种返回形态：① accept 分支回原对象（含 world_state/invalid）
    ② derivation_solver 分支回内层 world_state 字典。必须兼容，否则
    invalid 族（world_state=null）会被包成 {"world_state":{...}} 判成格式失败。
    """
    if not isinstance(gws, dict):
        return None
    if "world_state" in gws or "invalid" in gws:
        return gws
    return {"world_state": gws}


def judge(fam, exp, full):
    """判单条：full 为完整对象（含 world_state 顶层）。返回 (ok, fmt_ok, miss)。"""
    if not isinstance(full, dict):
        return False, False, ["<unparsable>"]
    if fam == "invalid":
        fmt = full.get("invalid") is True
        return (fmt and full.get("world_state") is None), fmt, []
    if not isinstance(full.get("world_state"), dict):
        return False, False, ["<no_world_state>"]
    ews = _flatten(exp.get("world_state") or {})
    pws = _flatten(full["world_state"])
    ok = True
    miss = []
    for k in NUM_KEYS[fam]:
        if k not in ews or k not in pws:
            ok = False
            miss.append(f"{k}(missing)")
            continue
        try:
            ev, pv = float(ews[k]), float(pws[k])
        except (TypeError, ValueError):
            ok = False
            miss.append(f"{k}(type)")
            continue
        if abs(ev) < 1e-9:
            if abs(pv) > 1e-6:
                ok = False
                miss.append(f"{k}(!=0)")
        elif abs(pv - ev) / abs(ev) > REL_TOL:
            ok = False
            miss.append(f"{k}({pv:g}!={ev:g})")
    for gate in ("fos_gate", "volume_conservation", "autodiff", "tolerance_pass"):
        if gate in ews and gate in pws:
            if C.normalize_gate(gate, ews[gate]) != C.normalize_gate(gate, pws[gate]):
                ok = False
                miss.append(f"{gate}({pws[gate]}!={ews[gate]})")
    return ok, True, miss


def _brace_match(s, start):
    """从 s[start]（应为 '{'）起做括号配对，返回匹配右括号下标；失败返回 -1。"""
    depth = 0
    i = start
    n = len(s)
    while i < n:
        c = s[i]
        if c == '"':  # 跳过字符串（含转义）
            i += 1
            while i < n:
                if s[i] == "\\":
                    i += 2
                    continue
                if s[i] == '"':
                    i += 1
                    break
                i += 1
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def extract_json(text):
    """稳健提取首个完整 JSON 对象：剥离 ```json 围栏，括号配对优先；
    再回退到整段 / 首个 {~最后 } 启发式；任一能解析即返回。"""
    if not text:
        return None
    candidates = []
    # 1) 去 ```json ... ``` 围栏
    stripped = text.strip()
    if stripped.startswith("```"):
        end = stripped.find("```", 3)
        if end != -1:
            stripped = stripped[3:end].strip()
            if stripped.startswith("json"):
                stripped = stripped[4:].strip()
        candidates.append(stripped)
    else:
        candidates.append(stripped)
    candidates.append(text)
    # 2) 括号配对：从每个 { 找匹配的 }
    pool = list(candidates)
    # 同时尝试整段
    for cand in candidates:
        if cand.startswith("{"):
            e = _brace_match(cand, 0)
            if e != -1:
                pool.append(cand[:e + 1])
    # 3) 启发式兜底：首个 { ~ 最后一个 }
    for cand in candidates:
        s = cand.find("{")
        e = cand.rfind("}")
        if s != -1 and e != -1:
            pool.append(cand[s:e + 1])
    for cand in pool:
        try:
            return json.loads(cand)
        except Exception:
            continue
    return None


def load_train_prompts():
    """加载 data/sft 下全部训练 JSONL 的 user prompt，供 --exclude-train 换差集。"""
    d = os.path.join(ROOT, "data", "sft")
    seen = set()
    if not os.path.isdir(d):
        return seen
    for fn in os.listdir(d):
        if not fn.endswith(".jsonl"):
            continue
        try:
            with open(os.path.join(d, fn), encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    for m in (obj.get("messages") or []):
                        if m.get("role") == "user":
                            seen.add(m.get("content", ""))
                            break
        except Exception:
            continue
    return seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="virtu-wm-all90")
    ap.add_argument("--n", type=int, default=120)
    ap.add_argument("--out", default="_eval_wm.json")
    ap.add_argument("--seed", type=int, default=777)
    ap.add_argument("--system-mode", default="data",
                    choices=["data", "contract", "both"],
                    help="data=用数据自带 system（复现基线）; contract=纯世界模型契约; both=契约+原背景")
    ap.add_argument("--no-json-format", action="store_true",
                    help="关闭 grammar 约束（对照实验用；默认开启 format=json）")
    ap.add_argument("--exclude-train", action="store_true",
                    help="排除与 data/sft 训练集 prompt 完全重合的用例（去同源污染）")
    ap.add_argument("--offset", type=int, default=0, help="用例分片起点（分批跑用）")
    ap.add_argument("--limit", type=int, default=0, help="本片用例数（0=不分片）")
    ap.add_argument("--timeout", type=float, default=180.0,
                    help="单次 ollama 请求超时秒（显存被其他模型挤占时调大）")
    args = ap.parse_args()
    global REQ_TIMEOUT
    REQ_TIMEOUT = float(args.timeout)
    force_json = not args.no_json_format

    import random
    rng = random.Random(args.seed)
    train_prompts = load_train_prompts() if args.exclude_train else set()
    cases = []
    per = max(1, args.n // len(GEN_BY_FAMILY))
    skipped = 0
    for fam, g in GEN_BY_FAMILY.items():
        for _ in range(per):
            rec = None
            for _try in range(80):
                rec = g(rng)
                if rec is None:
                    continue
                if rec["messages"][1]["content"] not in train_prompts:
                    break
                skipped += 1
                rec = None
            if rec is None:
                continue
            u = rec["messages"][1]["content"]
            sys_p = rec["messages"][0]["content"]
            exp = json.loads(rec["messages"][2]["content"])
            cases.append((fam, u, sys_p, exp, rec.get("scenario")))
    if args.exclude_train:
        print(f"[dedup] 跳过与训练集重合 {skipped} 例；保留 {len(cases)} 例")
    rng.shuffle(cases)
    cases = cases[:args.n]
    if args.limit > 0:
        cases = cases[args.offset:args.offset + args.limit]
    elif args.offset:
        cases = cases[args.offset:]

    stat = {fam: {"n": 0, "pass": 0, "raw_pass": 0, "parse_fail": 0, "fmt_ok": 0,
                  "guard_checked": 0, "guard_blocked": 0, "l2_hit": 0}
            for fam in GEN_BY_FAMILY}
    records = []
    for fam, u, sys_p, exp, scn in cases:
        resp = call_ollama(args.model, u, C.merge_with_data_system(sys_p, args.system_mode),
                           force_json=force_json)
        raw_obj = extract_json(resp)
        stat[fam]["n"] += 1
        # —— 推理时护栏（生成即校验/纠正）——
        # A-1：评测用例携带生成器的结构化 scenario，使 L2 求解器复算分支真正启用，
        # 评测链路与生产链路（worldmodel_infer.generate_world_state）同源。
        gres = apply_guard(resp, prompt=u, scenario=scn, tol_rel=REL_TOL)
        stat[fam]["guard_checked"] += 1
        layers = gres.get("layers_hit") or []
        if scn is not None and any("L2" in str(x) for x in layers):
            stat[fam]["l2_hit"] += 1
        if gres["action"] in ("rejected", "escalate"):
            stat[fam]["guard_blocked"] += 1
        # guard 的 final_world_state 形态不统一（完整对象 / 内层），统一归一
        guard_obj = _wrap(gres.get("final_world_state"))
        # 双指标：raw=模型原生输出（真实能力）；guard=护栏纠正后（交付形态）
        ok_raw, fmt_raw, miss_raw = judge(fam, exp, raw_obj)
        ok_g, fmt_g, miss_g = (judge(fam, exp, guard_obj) if guard_obj is not None
                               else (False, False, ["<no_guard_obj>"]))
        if raw_obj is None:
            stat[fam]["parse_fail"] += 1
        if fmt_raw:
            stat[fam]["fmt_ok"] += 1
        if ok_raw:
            stat[fam]["raw_pass"] += 1
        if ok_g:
            stat[fam]["pass"] += 1
        records.append({"family": fam, "user": u, "expected": exp,
                        "scenario_present": scn is not None,
                        "guard_layers": layers,
                        "predicted": guard_obj or raw_obj,
                        "pass": ok_g, "raw_pass": ok_raw, "fmt_raw": fmt_raw,
                        "miss": miss_g, "miss_raw": miss_raw,
                        "guard_action": gres["action"], "raw": resp})

    # 汇总
    total_n = sum(s["n"] for s in stat.values())
    total_p = sum(s["pass"] for s in stat.values())
    print(f"\n=== 世界模型评测: {args.model} (n={total_n}, system_mode={args.system_mode}) ===")
    for fam, s in stat.items():
        acc = s["pass"] / s["n"] * 100 if s["n"] else 0
        racc = s["raw_pass"] / s["n"] * 100 if s["n"] else 0
        fmt = s["fmt_ok"] / s["n"] * 100 if s["n"] else 0
        print(f"  {fam:10s} 原生通过 {s['raw_pass']:3d}/{s['n']:3d} {racc:5.1f}%  |  "
              f"护栏后 {s['pass']:3d}/{s['n']:3d} {acc:5.1f}%  |  "
              f"格式合规 {s['fmt_ok']:3d}/{s['n']:3d} {fmt:5.1f}%  |  解析失败 {s['parse_fail']}")
    total_f = sum(s["fmt_ok"] for s in stat.values())
    total_r = sum(s["raw_pass"] for s in stat.values())
    total_gc = sum(s["guard_checked"] for s in stat.values())
    total_gb = sum(s["guard_blocked"] for s in stat.values())
    print(f"  {'OVERALL':10s} 原生通过 {total_r:3d}/{total_n:3d} {total_r/total_n*100:5.1f}%  |  "
          f"护栏后 {total_p:3d}/{total_n:3d} {total_p/total_n*100:5.1f}%  |  "
          f"格式合规 {total_f:3d}/{total_n:3d} {total_f/total_n*100:5.1f}%")
    total_l2 = sum(s["l2_hit"] for s in stat.values())
    scn_n = sum(1 for fam, u, sp, ex, sc in cases if sc is not None)
    print(f"  {'GUARD':10s} 护栏检查 {total_gc:3d}/{total_n:3d}  |  拦截(拒绝/升级) {total_gb:3d}")
    print(f"  {'L2':10s} 携 scenario {scn_n:3d}/{total_n:3d}  |  求解器复算命中 {total_l2:3d}/{total_n:3d}")
    json.dump(records, open(os.path.join(ROOT, args.out), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"[ok] 明细 -> {args.out}")


if __name__ == "__main__":
    main()
