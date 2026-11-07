#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""二分定位 virtu-toolcall 空输出问题。

对照三组：
  A 纯文本问答（无 tools）        —— 验证模型本身能说话
  B tools + 不设任何 stop         —— 验证 stop 是否把输出掐死
  C tools + 只留 <|im_end|>       —— 验证是否是 <|im_start|> stop 的锅
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:11434"
MODEL = sys.argv[1] if len(sys.argv) > 1 else "virtu-toolcall"

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "cad.parse_wish_intent",
            "description": "解析加工/建模意图，抽取结构化参数",
            "parameters": {
                "type": "object",
                "properties": {
                    "wish": {"type": "string"},
                    "material": {"type": "string"},
                    "d_outer": {"type": "number"},
                    "d_inner": {"type": "number"},
                },
                "required": ["wish", "material", "d_outer", "d_inner"],
            },
        },
    },
]


def call(payload, timeout=1800):
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(
        BASE + "/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with op.open(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def run_case(tag, use_tools, stop):
    msgs = [{"role": "user", "content": "为NX12编写参数化建模脚本，工件AL7075-T6，外径80mm，内径24mm。"}]
    payload = {
        "model": MODEL,
        "messages": msgs,
        "stream": False,
        "options": {"num_ctx": 1024, "num_predict": 160, "temperature": 0.0},
    }
    if use_tools:
        payload["tools"] = TOOLS
    if stop is not None:
        payload["options"]["stop"] = stop

    t0 = time.time()
    print(f"\n=== {tag} ===", flush=True)
    try:
        r = call(payload)
    except Exception as e:
        print(f"  FAIL {type(e).__name__}: {str(e)[:120]}")
        return
    msg = r.get("message", {})
    calls = msg.get("tool_calls") or []
    content = (msg.get("content") or "").strip()
    print(f"  {time.time() - t0:.0f}s eval={r.get('eval_count')} "
          f"prompt_eval={r.get('prompt_eval_count')}")
    print(f"  tool_calls={len(calls)}")
    print(f"  content={content[:220]!r}")
    if calls:
        fn = calls[0].get("function", {})
        print(f"  name={fn.get('name')} args={fn.get('arguments')}")


def main():
    run_case("A 纯文本（无 tools）", False, None)
    run_case("B tools + 无 stop", True, [])
    run_case("C tools + 仅 im_end", True, ["<|im_end|>"])


if __name__ == "__main__":
    main()
