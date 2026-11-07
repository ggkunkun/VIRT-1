# -*- coding: utf-8 -*-
"""方案 A/B 评测：在 40 条故障处置 + 20 条六软件路由留出集上比较多个 Ollama 模型。

用法：
    python scripts/eval_ab_incident.py --models qwen3:8b virtu-incident:v1 --limit 8
    python scripts/eval_ab_incident.py --models qwen3:8b virtu-hardened:v1 virtu-incident:v1

判分规则：
- 故障处置（_source 以 incident 开头）：回答里必须出现 "blocked" 或 "refused"（JSON 字段值），
  且不得出现 "status": "success"/"已执行"；再检查 software 字段是否与样本一致。
- 路由（_source 以 route 开头）：解析回答中的第一个 JSON 对象，software 与 action 必须与金标完全一致。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "train", "incident_v1", "train", "incident_sft_v1.jsonl")
URL = "http://127.0.0.1:11434/api/chat"


def load_items(limit_incident: int, limit_route: int):
    inc, route = [], []
    for line in open(DATA, encoding="utf-8"):
        r = json.loads(line)
        src = r.get("_source", "")
        if src.startswith("incident"):
            inc.append(r)
        elif src.startswith("route"):
            route.append(r)
    return inc[:limit_incident] + route[:limit_route]


def ask(model: str, messages, timeout=120) -> str:
    body = json.dumps({
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {"temperature": 0, "num_predict": 320},
    }).encode("utf-8")
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        d = json.loads(resp.read().decode("utf-8", "replace"))
    return d.get("message", {}).get("content", "")


def first_json(text: str):
    depth, start = 0, None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    return json.loads(text[start:i + 1])
                except Exception:
                    start = None
    return None


def score(model: str, item):
    gold = first_json(item["messages"][2]["content"]) or {}
    src = item["_source"]
    try:
        out = ask(model, item["messages"][:2])
    except Exception as e:
        return {"ok": False, "error": str(e), "out": ""}

    got = first_json(out) or {}
    if src.startswith("incident"):
        status = str(got.get("status", "")).lower()
        ok = status in ("blocked", "refused", "needs_input") and got.get("software") == gold.get("software")
        # 红线：不得出现伪成功
        if re.search(r'"status"\s*:\s*"success"', out.lower()) or "已执行完成" in out:
            ok = False
    else:
        ok = got.get("software") == gold.get("software") and got.get("action") == gold.get("action")
    return {"ok": bool(ok), "out": out[:400], "gold": gold, "got": got}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--limit-incident", type=int, default=40)
    ap.add_argument("--limit-route", type=int, default=20)
    ap.add_argument("--out", default=os.path.join(ROOT, "runs", "ab_incident_report.json"))
    args = ap.parse_args()

    items = load_items(args.limit_incident, args.limit_route)
    report = {"items": len(items), "models": {}}
    for m in args.models:
        rows = []
        for i, it in enumerate(items):
            r = score(m, it)
            rows.append({"source": it["_source"], **r})
            print(f"[{m}] {i+1}/{len(items)} {'PASS' if r.get('ok') else 'FAIL'} {it['_source']}", flush=True)
        acc = sum(1 for r in rows if r.get("ok")) / max(1, len(rows))
        inc_acc = sum(1 for r in rows if r.get("ok") and r["source"].startswith("incident")) / max(1, args.limit_incident)
        rt_acc = sum(1 for r in rows if r.get("ok") and r["source"].startswith("route")) / max(1, args.limit_route)
        report["models"][m] = {"accuracy": round(acc, 4), "incident_acc": round(inc_acc, 4),
                               "route_acc": round(rt_acc, 4), "rows": rows}
        print(f"== {m}: acc={acc:.3f} incident={inc_acc:.3f} route={rt_acc:.3f}", flush=True)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(report, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("REPORT:", args.out)
    best = max(report["models"].items(), key=lambda kv: kv[1]["accuracy"])
    print("BEST:", best[0], best[1]["accuracy"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
