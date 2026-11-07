"""P0-2 探针：只读地测量 toolrouting 用例在指定 Ollama 标签上的真实输出形态。

不写 runs/，不碰封缄目录。结果落 scratch/_p02_probe_<tag>.jsonl。

用途：定位 v3 toolcall 20/30 失败的根因是不是 JSON 顶层键名（name vs tool），
以及统计空 <think> 块数量。判分复用 virtu_eval.graders.score_case，不另造判据。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from virtu_eval import graders  # noqa: E402


def build_messages(case):
    msgs = []
    if case.get("system"):
        msgs.append({"role": "system", "content": case["system"]})
    for m in case.get("context") or []:
        msgs.append({"role": m["role"], "content": m["content"]})
    msgs.append({"role": "user", "content": case["prompt"]})
    return msgs


def call_chat(base, model, messages, max_tokens, temperature, num_ctx, think,
              response_format=None):
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": bool(think),
        "options": {
            "temperature": float(temperature),
            "top_p": 0.95,
            "num_predict": int(max_tokens),
            "num_ctx": int(num_ctx),
            "seed": 1234,
        },
    }
    if response_format is not None:
        payload["format"] = response_format
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(base.rstrip("/") + "/api/chat", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    t0 = time.perf_counter()
    with opener.open(req, timeout=600) as resp:
        data = json.loads(resp.read().decode("utf-8", "replace"))
    msg = data.get("message") or {}
    content = msg.get("content") or ""
    thinking = msg.get("thinking") or ""
    return {
        "content": content,
        "thinking": thinking,
        "tool_calls": msg.get("tool_calls"),
        "elapsed_s": round(time.perf_counter() - t0, 2),
        "completion_tokens": data.get("eval_count"),
        "done_reason": data.get("done_reason"),
        "raw_len": len(content),
    }


def probe(base, model, cases, limit, max_tokens, temperature, num_ctx, think, out_path,
          response_format=None):
    rows = []
    with open(out_path, "w", encoding="utf-8") as f:
        for case in cases[:limit]:
            # Honour the budget each case declares; a single global cap silently
            # truncates the 704-token cases and would look like a model failure.
            budget = int(case.get("max_tokens") or max_tokens)
            rec = call_chat(base, model, build_messages(case), budget, temperature, num_ctx, think,
                            response_format=response_format)
            rec["max_tokens_used"] = budget
            scored = graders.score_case(rec["content"], case["criteria"])
            shape = next((c for c in scored["criteria"] if c["type"] == "json_object"), None)
            obj, err = graders.parse_json_candidate(rec["content"])
            top_keys = sorted(obj.keys()) if isinstance(obj, dict) else None
            row = {
                "case_id": case["id"],
                "tier": case["tier"],
                "score": scored["score"],
                "shape_passed": bool(shape and shape["passed"]),
                "shape_evidence": shape["evidence"] if shape else None,
                "top_keys": top_keys,
                "has_name_key": bool(top_keys and "name" in top_keys),
                "has_tool_key": bool(top_keys and "tool" in top_keys),
                "empty_think": "<think></think>" in (rec["content"] or "").replace(" ", "").replace("\n", ""),
                "content_len": len(rec["content"] or ""),
                "completion_tokens": rec["completion_tokens"],
                "elapsed_s": rec["elapsed_s"],
                "done_reason": rec["done_reason"],
                "content": rec["content"],
                "criteria": scored["criteria"],
            }
            rows.append(row)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            print(f"[{row['case_id']}] score={row['score']:6.2f} shape={row['shape_passed']} "
                  f"keys={row['top_keys']} tok={row['completion_tokens']} {row['elapsed_s']}s")
    return rows


def summarize(rows, label):
    n = len(rows)
    if not n:
        return
    passed = sum(1 for r in rows if r["score"] >= 99.999)
    mean = sum(r["score"] for r in rows) / n
    name_key = sum(1 for r in rows if r["has_name_key"])
    tool_key = sum(1 for r in rows if r["has_tool_key"])
    shape_ok = sum(1 for r in rows if r["shape_passed"])
    empty_think = sum(1 for r in rows if r["empty_think"])
    tok = [r["completion_tokens"] or 0 for r in rows]
    print("\n==== SUMMARY", label, "====")
    print(f"n={n}  mean={mean:.2f}  all_passed={passed}/{n}")
    print(f"shape(json_object)={shape_ok}/{n}  name_key={name_key}/{n}  tool_key={tool_key}/{n}")
    print(f"empty_think={empty_think}/{n}  completion_tokens_median={sorted(tok)[len(tok)//2]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="virtu-comprehensive:latest")
    ap.add_argument("--base", default="http://127.0.0.1:11434")
    ap.add_argument("--cases", default="data/benchmark/virtu_eval_cl_v1/toolrouting.jsonl")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--max-tokens", type=int, default=512)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--num-ctx", type=int, default=8192)
    ap.add_argument("--think", action="store_true")
    ap.add_argument("--format-file", default=None,
                    help="JSON Schema file for Ollama constrained decoding (format field)")
    ap.add_argument("--tag", default=None)
    args = ap.parse_args()

    case_path = args.cases if os.path.isabs(args.cases) else os.path.join(ROOT, args.cases)
    cases = [json.loads(l) for l in open(case_path, encoding="utf-8") if l.strip()]
    tag = args.tag or args.model.replace(":", "_").replace("/", "_")
    out_path = os.path.join(ROOT, "scratch", f"_p02_probe_{tag}.jsonl")

    fmt = None
    if args.format_file:
        fmt_path = args.format_file if os.path.isabs(args.format_file) else os.path.join(ROOT, args.format_file)
        fmt = json.load(open(fmt_path, encoding="utf-8"))

    rows = probe(args.base, args.model, cases, args.limit, args.max_tokens,
                 args.temperature, args.num_ctx, args.think, out_path, response_format=fmt)
    summarize(rows, args.model)
    print("\nrows ->", out_path)


if __name__ == "__main__":
    main()
