#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze_variants2.py — 权威变体计量（修正 tr2 / schema 两个关键点）

上一版结论修正：
  - tool_response#1 只有 ~181 字符（parse_wish_intent 的 JSON spec），很短
  - tool_response#2 才是长文（markdown 手册），平均 ~1636 字符，占全库 16.29M token (27%)
  - call#2 的参数 67.7% 来自 tool_response#1（短），所以 tr1 不能截，tr2 可以丢

变体：
  V0  原样
  V2b 丢 tr2 + 最终总结（保留 2 轮 tool_call）      <- 主推
  V3  schema 瘦身（去掉参数的 description，保留 name/type/enum/required）
  V4  V2b + V3 组合
  V5  V2b + 保留 20% 完整长样本（混合策略，保住"最终总结"能力）
"""
from __future__ import annotations

import json
import os
import sys
import hashlib
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from virtu_tokenize import render_full, find_assistant_spans  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(HERE, "checkpoints", "_base_qwen3_8b")
DATA = os.path.join(HERE, "damodel_cad_cam_tuning", "dataset",
                    "virtu_toolcall_train_unified.jsonl")
OUT = os.path.join(HERE, "data", "validation", "variant_analysis_v2.json")
STRIDE = int(os.environ.get("VAR_STRIDE", "4"))


def norm(msgs):
    out = []
    for m in msgs:
        d = {"r": m.get("role")}
        if m.get("content"):
            d["c"] = " ".join(str(m.get("content").split())) if False else " ".join(str(m.get("content") or "").split())
        if m.get("tool_calls"):
            d["t"] = json.dumps(m.get("tool_calls"), sort_keys=True, ensure_ascii=False)
        if m.get("name"):
            d["n"] = m.get("name")
        out.append(json.dumps(d, sort_keys=True, ensure_ascii=False))
    return "\n".join(out)


def strip_param_desc(tools):
    """去掉 parameters 里每个属性的 description，保留 name/type/enum/required。"""
    out = []
    for t in tools or []:
        t = json.loads(json.dumps(t, ensure_ascii=False))
        params = (t.get("function") or {}).get("parameters") or {}
        props = params.get("properties") or {}
        for k, v in props.items():
            if isinstance(v, dict):
                v.pop("description", None)
        out.append(t)
    return out


def build_drop_tr2(msgs):
    """保留 system/user/assistant#1/tool#1/assistant#2，丢弃 tool#2 与最终总结。"""
    out = []
    nc = 0
    for m in msgs:
        rr = m.get("role")
        if rr == "assistant":
            if m.get("tool_calls"):
                nc += 1
                if nc > 2:
                    break
                out.append(m)
            else:
                break
        elif rr == "tool":
            if nc >= 2:
                break          # tr2 丢弃
            out.append(m)
        else:
            out.append(m)
    return out


def main():
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)

    # 先量 schema 本身
    with open(DATA, encoding="utf-8") as f:
        r0 = json.loads(f.readline())
    tools0 = r0.get("tools") or []
    full_schema = json.dumps(tools0, ensure_ascii=False)
    thin_schema = json.dumps(strip_param_desc(tools0), ensure_ascii=False)
    schema_tok_full = len(tok(full_schema, add_special_tokens=False)["input_ids"])
    schema_tok_thin = len(tok(thin_schema, add_special_tokens=False)["input_ids"])

    # 统计 description 占比
    desc_chars = 0
    total_chars = 0
    for t in tools0:
        fn = t.get("function") or {}
        props = (fn.get("parameters") or {}).get("properties") or {}
        for k, v in props.items():
            total_chars += len(json.dumps(v, ensure_ascii=False))
            desc_chars += len(str((v or {}).get("description") or ""))
        desc_chars += len(str(fn.get("description") or ""))

    seen = set()
    i = 0
    sn = 0
    V = Counter(); N = Counter(); SIG = Counter()
    tr2_chars = 0
    tr2_cnt = 0

    with open(DATA, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            msgs = r["messages"]
            tools = r.get("tools") or []
            i += 1

            fp = hashlib.md5(norm(msgs).encode()).hexdigest()
            if fp in seen:
                continue
            seen.add(fp)

            # 统计 tr2 长度
            tmsgs = [m for m in msgs if m.get("role") == "tool"]
            if len(tmsgs) >= 2:
                tr2_chars += len(str(tmsgs[1].get("content") or ""))
                tr2_cnt += 1

            if sn % STRIDE:
                sn += 1
                continue
            sn += 1

            def measure(v_msgs, v_tools):
                t = render_full(tok, v_msgs, v_tools)
                ids = tok(t, add_special_tokens=False, return_offsets_mapping=True)
                offs = ids["offset_mapping"]
                n_all = len(ids["input_ids"])
                spans = find_assistant_spans(t)
                ncalls = sum(1 for m in v_msgs if m.get("tool_calls"))
                n_sig = 0
                for si, (s0, e0) in enumerate(spans):
                    c = sum(1 for a, b in offs if a >= s0 and b <= e0 and b > a)
                    if si < ncalls:
                        n_sig += c
                return n_all, n_sig

            thin = strip_param_desc(tools)
            v2b = build_drop_tr2(msgs)

            t0, s0 = measure(msgs, tools)
            t2b, s2b = measure(v2b, tools)
            t3, s3 = measure(msgs, thin)
            t4, s4 = measure(v2b, thin)

            V["V0"] += t0; N["V0"] += 1; SIG["V0"] += s0
            V["V2b"] += t2b; N["V2b"] += 1; SIG["V2b"] += s2b
            V["V3"] += t3; N["V3"] += 1; SIG["V3"] += s3
            V["V4"] += t4; N["V4"] += 1; SIG["V4"] += s4

            if N["V0"] % 600 == 0:
                print(f"  {N['V0']} ...", flush=True)

    uniq = len(seen)
    scale = uniq / max(1, N["V0"])
    res = {}
    for k in V:
        t = int(V[k] * scale)
        res[k] = {"samples": uniq, "tokens_1ep": t,
                  "avg_per_sample": round(t / uniq, 1),
                  "signal_pct": round(SIG[k] / max(1, V[k]) * 100, 2)}
    base = res["V0"]["tokens_1ep"]

    out = {
        "total_in_file": i, "unique": uniq, "dup_removed": i - uniq,
        "schema": {
            "tokens_full": schema_tok_full,
            "tokens_thin": schema_tok_thin,
            "saving_pct": round(100 * (1 - schema_tok_thin / schema_tok_full), 1),
            "desc_chars": desc_chars,
            "param_total_chars": total_chars,
        },
        "tr2": {"avg_chars": round(tr2_chars / max(1, tr2_cnt), 1), "count": tr2_cnt},
        "variants": res,
        "saving_vs_V0": {k: round(100 * (1 - v["tokens_1ep"] / base), 1) for k, v in res.items()},
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 76)
    print("权威变体计量（去重后 18,330 条口径）")
    print("=" * 76)
    sc = out["schema"]
    print(f"tools schema: 完整 {sc['tokens_full']} tok -> 瘦身后 {sc['tokens_thin']} tok "
          f"(省 {sc['saving_pct']}%)")
    print(f"参数 description 字符占比: {100*sc['desc_chars']/max(1,sc['param_total_chars']):.1f}%")
    print(f"tool_response#2 平均 {out['tr2']['avg_chars']} 字符")
    print()
    print(f"{'变体':<7}{'总token(1ep)':>16}{'条均':>9}{'信号占比':>10}{'较V0省':>9}")
    print("-" * 76)
    desc = {"V0": "原样", "V2b": "丢tr2+总结", "V3": "schema瘦身", "V4": "V2b+V3"}
    for k in ("V0", "V2b", "V3", "V4"):
        v = res[k]
        print(f"{k:<7}{v['tokens_1ep']:>16,}{v['avg_per_sample']:>9}"
              f"{v['signal_pct']:>9}%{out['saving_vs_V0'][k]:>8}%   {desc[k]}")
    print(f"\n报告 -> {OUT}")


if __name__ == "__main__":
    main()
