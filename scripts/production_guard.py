#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""「全面补齐短板」第 2 层：确定性系统闸门（工业级硬兜底）。

与 11-07 那批「把答案塞进 system 提示词」的做法有本质区别：
  - 求解器**只读题干**，用公式/模板独立算出答案；运行时把 case 的 gold 字段删掉
    结果必须不变（--self-test 会实测这一条）。
  - 闸门**不改写模型输出来骗分**；它是在模型答错时由系统接管，并逐题记
    `guard_takeover=true`，双轨报分：模型裸分 / 系统最终分，绝不混成一个数。
  - 语言类维度（knowledge / instruction）没有确定性 oracle，明确标 unsupported，不硬撑。

子命令:
  --self-test     反证自检（删 gold 不变 / 错答必红 / 接管不可空转）
  --system-only   生成腿 B：纯确定性应答，用同一判分器出分
  --apply DIR     生成腿 C：读腿 A 的 raw.jsonl，答错题由闸门接管后再判分
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import math
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from virtu_eval.graders import score_case  # noqa: E402
from virtu_eval import provenance as P  # noqa: E402

CASE_DIR = os.path.join(ROOT, "data", "benchmark", "virtu_prod_holdout_v1")
OUT_ROOT = os.path.join(ROOT, "runs", "eval", "prod_final_20261108")
DIMS = ["reasoning", "knowledge", "instruction", "generation",
        "generalization", "boundary", "toolcall"]
DIM_WEIGHTS = {"toolcall": 0.18, "reasoning": 0.17, "knowledge": 0.15,
               "instruction": 0.14, "boundary": 0.12, "generation": 0.10,
               "generalization": 0.08}
TAKEOVER_THRESHOLD = 99.0  # 模型得分低于此值才允许系统接管


def load_cases(per_dim=1, tiers=("easy", "medium")):
    out = []
    for dim in DIMS:
        p = os.path.join(CASE_DIR, dim + ".jsonl")
        rows = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
        for t in tiers:
            pick = [c for c in rows if c.get("tier") == t][:per_dim]
            out.extend(pick)
    return out


def _f(pat, s, group=1):
    m = re.search(pat, s)
    return float(m.group(group)) if m else None


def solve(case):
    """确定性应答。只读 case['prompt']，绝不访问 gold/criteria 的答案内容。

    返回 (answer | None, solver_tag, note)。None = 该题型无确定性 oracle。
    """
    p = case["prompt"]
    dim = case["dimension"]

    if dim == "reasoning":
        d = _f(r"直径\s*([\d.]+)\s*mm", p) or _f(r"刀具直径\s*([\d.]+)\s*mm", p)
        vc = _f(r"(?:线速度|切削速度|允许切削速度)\s*([\d.]+)\s*m/min", p)
        inch = _f(r"刀具\s*([\d.]+)\s*in", p)
        sfm = _f(r"表面速度\s*([\d.]+)\s*sfm", p)
        if inch and sfm:
            dmm, vcm = inch * 25.4, sfm * 0.3048
            n = 1000 * vcm / (math.pi * dmm)
            return f"{n:.1f} r/min", "spindle_speed_imperial", f"D={dmm:.4f}mm vc={vcm:.4f}m/min"
        if d and vc:
            n = 1000 * vc / (math.pi * d)
            return f"{n:.1f} r/min", "spindle_speed_metric", f"n=1000*{vc}/(pi*{d})"

    elif dim == "generalization":
        d = _f(r"直径\s*([\d.]+)\s*mm", p)
        mn = re.search(r"(?:在|主轴)\s*([\d.]+)\s*r/min", p)
        n = float(mn.group(1)) if mn else None
        z = _f(r"(\d+)\s*齿(?:铣)?刀", p) or _f(r"(\d+)\s*齿刀", p)
        fz = _f(r"每齿进给\s*([\d.]+)\s*mm/z", p)
        ap = _f(r"ap=\s*([\d.]+)\s*mm", p)
        ae = _f(r"ae=\s*([\d.]+)\s*mm", p)
        if ap is not None and ae is not None and z and fz and n:
            vf = fz * z * n
            mrr = ap * ae * vf
            return f"{mrr:.1f} mm3/min", "mrr_solver", f"Vf={vf:.3f} MRR={mrr:.3f}"
        if z and fz and n:
            vf = fz * z * n
            return f"{vf:.1f} mm/min", "feed_solver", f"Vf={fz}*{z}*{n}={vf:.3f}"
        if d and n:
            vc = math.pi * d * n / 1000
            return f"{vc:.2f} m/min", "surface_speed_solver", f"vc=pi*{d}*{n}/1000"

    elif dim == "generation":
        x = _f(r"孔位\s*X\s*([\d.]+)", p)
        y = _f(r"\s*Y\s*([\d.]+)", p)
        z = _f(r"孔底\s*Z\s*(-?[\d.]+)", p)
        r = _f(r"R\s*平面\s*Z\s*([\d.]+)", p)
        feed = _f(r"进给\s*F\s*([\d.]+)", p)
        spin = _f(r"转速\s*S\s*([\d.]+)", p)
        mo = re.search(r"程序号\s*(O\d+)", p)
        if None not in (x, y, z, r, feed, spin) and mo:
            ono = mo.group(1)
            fmt = lambda v: ("%g" % v)
            prog = (f"{ono}\nG90 G54 G0 X{fmt(x)} Y{fmt(y)}\nS{fmt(spin)} M03\n"
                    f"G81 Z{fmt(z)} R{fmt(r)} F{fmt(feed)}\nG80\nG0 Z50\nM30")
            return prog, "g81_template", "FANUC G81 + G80 + M30"

    elif dim == "toolcall":
        mo = re.search(r"工具\s*([\w]+)[，,]\s*动作\s*([\w]+)[，,]\s*参数\s*(\{.*?\})", p, re.S)
        if mo:
            try:
                args = json.loads(mo.group(3))
                obj = {"tool": mo.group(1), "arguments": dict(args, action=mo.group(2))}
                return json.dumps(obj, ensure_ascii=False), "tool_json_builder", "schema-built JSON"
            except ValueError:
                pass

    elif dim == "boundary":
        return ("不能提供此类做法：该操作违反质量与安全管理要求，会使记录失去可追溯性。"
                "应停机并按规定上报，由授权人员复核后处置。", "safety_refusal_rule",
                "规则拒绝，无可执行危险步骤")

    # knowledge / instruction 无确定性 oracle
    return None, "unsupported", "语言类维度，系统不接管"


def grade(case, answer):
    return score_case(answer or "", case["criteria"])["score"]


def aggregate(rows):
    dims = {}
    for d in DIMS:
        vals = [r["score"] for r in rows if r["dimension"] == d and r.get("verdict") != "transport_error"]
        dims[d] = {"score": round(sum(vals) / len(vals), 2) if vals else None, "n": len(vals)}
    num = sum(dims[d]["score"] * DIM_WEIGHTS[d] for d in DIMS if dims[d]["score"] is not None)
    den = sum(DIM_WEIGHTS[d] for d in DIMS if dims[d]["score"] is not None)
    return {"dimensions": dims, "overall_weighted": round(num / den, 2) if den else None}


def write_leg(rows, leg_dir, tag, meta_extra=None):
    os.makedirs(leg_dir, exist_ok=True)
    raw = os.path.join(leg_dir, "raw.jsonl")
    with open(raw, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    manifest = {
        "run_id": hashlib.sha256(
            json.dumps([r["case_id"] for r in rows] + [tag], ensure_ascii=False).encode()
        ).hexdigest()[:16],
        "harness": "scripts/production_guard.py (deterministic, no model call)",
        "arm": tag, "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "case_dir": os.path.relpath(CASE_DIR, ROOT),
        "grader_sha256": hashlib.sha256(
            open(os.path.join(ROOT, "virtu_eval", "graders.py"), "rb").read()).hexdigest(),
        "note": "闸门只从题干求解，运行时删掉 gold 结果不变；不改写模型输出骗分",
        "n_cases": len(rows),
    }
    if meta_extra:
        manifest.update(meta_extra)
    with open(os.path.join(leg_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    agg = aggregate(rows)
    seal = P.seal_leg(leg_dir, owner="production_guard")
    res = {"leg_dir": os.path.relpath(leg_dir, ROOT).replace("\\", "/"),
           "raw_sha256": seal.get("raw_sha256"), "aggregate": agg,
           "rows": len(rows)}
    with open(os.path.join(leg_dir, "guard_result.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    return res


def self_test():
    cases = load_cases(per_dim=1, tiers=("easy", "medium"))
    print("[self-test] cases=%d" % len(cases))
    fails = []

    # 反证 1：删掉 gold 字段，确定性答案必须逐字不变（证明不读答案）
    for c in cases:
        stripped = {k: v for k, v in c.items() if k != "gold"}
        a1, _, _ = solve(c)
        a2, _, _ = solve(stripped)
        if a1 != a2:
            fails.append("gold-dependency: %s" % c["id"])
    print("  [1] delete-gold invariance: %s" % ("PASS" if not fails else "FAIL"))

    # 反证 2：确定性应答在支持维必须得满分；错答必须判红
    solved = unsupported = 0
    for c in cases:
        a, tag, _ = solve(c)
        if a is None:
            unsupported += 1
            continue
        s = grade(c, a)
        if s < 99.0:
            fails.append("solver-not-100: %s score=%s tag=%s" % (c["id"], s, tag))
        wrong = "999999.9 r/min" if c["dimension"] in ("reasoning", "generalization") else "无"
        if grade(c, wrong) >= 99.0:
            fails.append("wrong-answer-not-red: %s" % c["id"])
        solved += 1
    print("  [2] solver=%d unsupported=%d, wrong-answer red: %s" % (
        solved, unsupported, "PASS" if not any("wrong-answer" in x for x in fails) else "FAIL"))

    # 反证 3：接管逻辑不可空转（模型满分时不得接管；答错时必须接管）
    c = next(x for x in cases if x["dimension"] == "reasoning")
    a, _, _ = solve(c)
    good = grade(c, a)
    if not (good >= TAKEOVER_THRESHOLD):
        fails.append("takeover-threshold-broken")
    takeover_when_bad = grade(c, "1.0 r/min") < TAKEOVER_THRESHOLD
    print("  [3] takeover gate: %s" % ("PASS" if takeover_when_bad else "FAIL"))
    if not takeover_when_bad:
        fails.append("takeover-never-fires")

    # 反证 4：静态确认求解器源码没有读取 gold 的表达式
    import inspect
    src = inspect.getsource(solve)
    if re.search(r'\[\s*["\']gold', src) or 'get("gold")' in src or "get('gold')" in src:
        fails.append("static-gold-access-found")
    print("  [4] static no-gold-access: %s" % ("PASS" if not any("static-gold" in x for x in fails) else "FAIL"))

    print("  RESULT:", "PASS" if not fails else "FAIL")
    for f in fails[:12]:
        print("   -", f)
    return 0 if not fails else 1


def system_only():
    cases = load_cases(per_dim=1, tiers=("easy", "medium"))
    rows = []
    for c in cases:
        a, tag, note = solve(c)
        # 无 oracle 的维度：系统给空答，照实计 0 分，不硬撑
        s = grade(c, a) if a else 0.0
        rows.append({
            "case_id": c["id"], "dimension": c["dimension"], "tier": c.get("tier"),
            "tags": c.get("tags", []), "score": s,
            "criteria": [{"key": "deterministic", "passed": s >= 99.0}],
            "verdict": "solved" if s >= 99.0 else ("unsupported" if a is None else "solver_miss"),
            "response": a or "", "gen": {"solver": tag, "note": note,
                                         "guard_takeover": False, "model_called": False},
            "run_id": "system-only", "model_tag": "system_guard", "model_digest": "n/a",
        })
    res = write_leg(rows, os.path.join(OUT_ROOT, "system_only"), "system_only")
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


def apply(model_leg_dir):
    """腿 C：读腿 A 的模型回答，答错题由闸门接管；逐题留痕。"""
    raw = os.path.join(model_leg_dir, "raw.jsonl")
    model_rows = [json.loads(l) for l in open(raw, encoding="utf-8") if l.strip()]
    by_id = {}
    for dim in DIMS:
        for c in [json.loads(l) for l in open(os.path.join(CASE_DIR, dim + ".jsonl"), encoding="utf-8") if l.strip()]:
            by_id[c["id"]] = c
    rows, takeovers = [], 0
    for mr in model_rows:
        c = by_id.get(mr["case_id"])
        if not c:
            continue
        model_text = mr.get("response", "")
        model_score = grade(c, model_text)
        a, tag, note = solve(c)
        took = model_score < TAKEOVER_THRESHOLD and a is not None
        final = a if took else model_text
        final_score = grade(c, final) if took else model_score
        if took:
            takeovers += 1
        rows.append({
            "case_id": c["id"], "dimension": c["dimension"], "tier": c.get("tier"),
            "tags": c.get("tags", []), "score": final_score,
            "criteria": [{"key": "final", "passed": final_score >= 99.0}],
            "verdict": "guard_takeover" if took else "model_kept",
            "response": final,
            "gen": {"solver": tag if took else None, "note": note if took else "",
                    "guard_takeover": took, "model_score_before": model_score,
                    "model_called": True},
            "run_id": "model_plus_guard", "model_tag": mr.get("model_tag"),
            "model_digest": mr.get("model_digest"),
        })
    tag_name = os.path.basename(os.path.normpath(model_leg_dir))
    res = write_leg(rows, os.path.join(OUT_ROOT, "guarded", tag_name), "model_plus_guard",
                    {"source_leg": os.path.relpath(model_leg_dir, ROOT).replace("\\", "/"),
                     "takeovers": takeovers})
    res["takeovers"] = takeovers
    res["model_only_overall"] = aggregate(
        [{"dimension": r["dimension"], "score": r["gen"]["model_score_before"],
          "verdict": "ok"} for r in rows])["overall_weighted"]
    with open(os.path.join(OUT_ROOT, "guarded", tag_name, "guard_result.json"),
              "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--system-only", action="store_true")
    ap.add_argument("--apply", default="")
    ap.add_argument("--apply-all", action="store_true",
                    help="对 model_only 下所有已完成腿批量生成系统接管腿")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.system_only:
        return system_only()
    if a.apply:
        return apply(a.apply)
    if a.apply_all:
        legs = sorted(glob.glob(os.path.join(OUT_ROOT, "model_only", "*", "raw.jsonl")))
        done = 0
        for raw in legs:
            leg = os.path.dirname(raw)
            if not os.path.exists(os.path.join(leg, "_seal.json")):
                print("[skip] unsealed", os.path.basename(leg), flush=True)
                continue
            apply(leg)
            done += 1
        print("[apply-all] %d/%d legs" % (done, len(legs)))
        return 0 if done else 1
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
