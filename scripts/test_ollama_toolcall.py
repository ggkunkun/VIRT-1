#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""virtu-toolcall 落地冒烟：本机 Ollama /api/chat + tools，看能否吐出结构化 tool_calls。

Windows 上必须绕过透明代理直连 127.0.0.1，否则 requests/urllib 会被本机代理截走。
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://127.0.0.1:11434"


def http_json(path, payload=None, timeout=900):
    """绕过本机代理直连本地服务。"""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    if payload is None:
        req = urllib.request.Request(BASE + path)
    else:
        req = urllib.request.Request(
            BASE + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
    with opener.open(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def load_case(idx=0):
    with open("data/toolcall_optimal.jsonl", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i == idx:
                return json.loads(line)
    raise SystemExit("no sample")


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "virtu-toolcall"
    case = load_case(0)
    tools = case["tools"]
    msgs = [m for m in case["messages"] if m.get("role") != "assistant"]

    user_msg = next(m for m in msgs if m["role"] == "user")
    print("=" * 68)
    print(f"模型: {model}")
    print(f"用户: {user_msg['content'][:90]}...")
    print(f"工具数: {len(tools)}")
    print("=" * 68)

    payload = {
        "model": model,
        "messages": msgs,
        "tools": tools,
        "stream": False,
        "options": {"temperature": 0.2, "num_ctx": 4096},
    }
    t0 = time.time()
    r = http_json("/api/chat", payload)
    el = time.time() - t0
    print(f"\n[{el:.1f}s] 响应:")

    msg = r.get("message", {})
    calls = msg.get("tool_calls") or []
    content = (msg.get("content") or "").strip()

    if calls:
        print(f"  ✅ 产出 {len(calls)} 个 tool_call")
        for c in calls:
            fn = c.get("function", {})
            print(f"     -> {fn.get('name')}")
            args = fn.get("arguments")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    pass
            print(f"        args={json.dumps(args, ensure_ascii=False)[:300]}")
        ok = True
    else:
        print("  ❌ 没有 tool_calls，纯文本输出:")
        print("     " + content[:400])
        ok = False

    print(f"\n  prompt_eval={r.get('prompt_eval_count')} "
          f"eval={r.get('eval_count')} 总耗时={el:.1f}s")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
