#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wm_probe.py — 世界模型能力探针（复用仓库生成器 + 判分口径，轻量快速版）

用途：在任意 ollama 标签上，按 family 抽样生成"求解器派生真值"用例，
      用指定 system 模式 + 采样参数调用，逐字段判定通过率。

用法：
  python wm_probe.py --model virtu-13.63b:latest --per-family 3 --system-mode none \
      --num-gpu 30 --out temp/wm_probe_base.json
"""
from __future__ import annotations
import os, sys, json, time, random, argparse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import build_worldmodel_sft as W  # noqa: E402
import wm_contract as C           # noqa: E402
from guard_hooks import apply_guard  # noqa: E402
from eval_worldmodel import GEN_BY_FAMILY as GEN, judge as _official_judge  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wm_schema as S  # noqa: E402
import wm_gate as G  # noqa: E402
import wm_eval as E  # noqa: E402

REL_TOL = 0.08


def judge(fam, exp, pred):
    # 判分口径唯一真源是 eval_worldmodel.judge（词表/闸门/文本/布尔全部从
    # wm_contract.KEY_SCHEMA 派生）。本文件旧版私持一份 v1 NUM_KEYS + 裸相等
    # 闸门比对：collision 三个 Z 值不判、长短信任字面互判失败、文本/布尔全漏——
    # 与官方判分器系统性偏离，探针分数不可比（2026-11-08 废除第二把尺子）。
    ok, _fmt, miss = _official_judge(fam, exp, pred)
    return ok, ";".join(miss)


def call(model, prompt, system, num_gpu, num_predict, host="127.0.0.1:11434", fmt=None):
    payload = {
        "model": model, "prompt": prompt, "system": system or "",
        "stream": False, "think": False,
        "options": {"temperature": 0, "num_predict": num_predict, "num_gpu": num_gpu, "num_ctx": 4096},
    }
    if fmt is not None:
        payload["format"] = fmt
    req = urllib.request.Request(f"http://{host}/api/generate",
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            d = json.loads(r.read().decode())
        return d.get("response", ""), time.time() - t0, d.get("eval_count", 0)
    except Exception as e:  # noqa: BLE001
        return f"<gen-fail:{e}>", time.time() - t0, 0


def extract_json(text):
    if not text:
        return None
    s = text.strip()
    if s.startswith("```"):
        e = s.find("```", 3)
        if e != -1:
            s = s[3:e].strip()
            if s.lower().startswith("json"):
                s = s[4:].strip()
    cands = [s, text]
    a, b = s.find("{"), s.rfind("}")
    if a != -1 and b != -1:
        cands.append(s[a:b + 1])
    for c in cands:
        try:
            return json.loads(c)
        except Exception:
            continue
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--per-family", type=int, default=3)
    ap.add_argument("--seed", type=int, default=777)
    ap.add_argument("--system-mode", default="none",
                    choices=["none", "data", "contract", "contract-lite", "card", "router"])
    ap.add_argument("--format-schema", default="none", choices=["none", "wide", "family"])
    ap.add_argument("--pipeline", default="raw", choices=["raw", "strengthened"],
                    help="strengthened = 确定性判定层(wm_gate)归一化后再判分")
    ap.add_argument("--num-gpu", type=int, default=30)
    ap.add_argument("--num-predict", type=int, default=320)
    ap.add_argument("--out", default="temp/wm_probe.json")
    ap.add_argument("--only", default="", help="逗号分隔 family，仅跑这些")
    ap.add_argument("--no-think", action="store_true", help="think=false")
    args = ap.parse_args()

    fams = list(GEN) if not args.only else [x.strip() for x in args.only.split(",") if x.strip()]
    rng = random.Random(args.seed)
    cases = []
    for fam in fams:
        got = 0
        tries = 0
        while got < args.per_family and tries < args.per_family * 6:
            tries += 1
            rec = GEN[fam](rng)
            if rec is None:
                continue
            cases.append((fam, rec["messages"][1]["content"], rec["messages"][0]["content"],
                          json.loads(rec["messages"][2]["content"])))
            got += 1

    stat = {f: {"n": 0, "pass": 0, "fmt": 0, "guard_block": 0} for f in fams}
    rows = []
    t_all = time.time()
    for i, (fam, u, sys_p, exp) in enumerate(cases, 1):
        if args.system_mode == "none":
            system = ""
        elif args.system_mode == "data":
            system = sys_p
        elif args.system_mode == "contract":
            system = C.SYSTEM
        elif args.system_mode == "contract-lite":
            system = S.LITE_SYSTEM
        elif args.system_mode == "card":
            system = S.card_system(fam)
        else:
            system = C.ROUTER_SYSTEM
        if args.format_schema == "wide":
            fmt = S.wide_schema()
        elif args.format_schema == "family":
            fmt = S.family_schema(fam)
        else:
            fmt = None
        raw, el, ec = call(args.model, u, system, args.num_gpu, args.num_predict, fmt=fmt, )
        if raw.startswith("<gen-fail") and "500" in raw:   # ollama 偶发 500：重试一次
            time.sleep(3)
            raw, el, ec = call(args.model, u, system, args.num_gpu, args.num_predict, fmt=fmt, )
        pred = extract_json(raw)
        g = None
        try:
            g = apply_guard(raw, prompt=u, scenario=None, tol_rel=REL_TOL)
            if g["action"] in ("rejected", "escalate"):
                stat[fam]["guard_block"] += 1
        except Exception:
            pass
        eval_fixes = []
        if args.pipeline == "strengthened":
            if g and g.get("action") in ("accept", "corrected") and isinstance(g.get("corrected"), dict):
                corr = g["corrected"]
                pred = corr if ("world_state" in corr or "invalid" in corr) else {"world_state": corr}
                pred = G.normalize_pred(pred, u)
            elif pred is not None:
                pred, eval_fixes = E.repair(pred)
                pred = G.normalize_pred(pred, u)
        ok, why = judge(fam, exp, pred)
        stat[fam]["n"] += 1
        stat[fam]["pass"] += int(ok)
        fmt_ok = (pred is not None and (pred.get("invalid") is True or isinstance(pred.get("world_state"), dict)))
        stat[fam]["fmt"] += int(fmt_ok)
        rows.append({"family": fam, "user": u, "expected": exp, "predicted": pred,
                     "raw": raw, "pass": ok, "why": why, "elapsed_s": round(el, 1),
                     "eval_count": ec, "eval_fixes": eval_fixes})
        print(f"[{i}/{len(cases)}] {fam:10s} {'PASS' if ok else 'FAIL':4s} {el:5.1f}s {why[:90]}", flush=True)

    tot_n = sum(s["n"] for s in stat.values())
    tot_p = sum(s["pass"] for s in stat.values())
    tot_f = sum(s["fmt"] for s in stat.values())
    print(f"\n=== {args.model} | system={args.system_mode} | num_gpu={args.num_gpu} ===")
    for f, s in stat.items():
        acc = s["pass"] / s["n"] * 100 if s["n"] else 0
        print(f"  {f:10s} {s['pass']:2d}/{s['n']:2d} {acc:5.1f}%  格式 {s['fmt']}/{s['n']}  护栏拦截 {s['guard_block']}")
    print(f"  {'OVERALL':10s} {tot_p:2d}/{tot_n:2d} {tot_p/tot_n*100:5.1f}%  格式 {tot_f}/{tot_n}  总耗时 {time.time()-t_all:.0f}s")

    out = {"model": args.model, "system_mode": args.system_mode, "num_gpu": args.num_gpu,
           "format_schema": args.format_schema, "pipeline": args.pipeline,
           "per_family": args.per_family, "seed": args.seed,
           "stat": stat, "overall": {"pass": tot_p, "n": tot_n, "fmt": tot_f},
           "elapsed_s": round(time.time() - t_all, 1), "rows": rows}
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[ok] -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
