#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""低配本机（RTX4050 6GB / 16GB 内存）上的轻量 tool-call 验证。

8B Q4_0 在本机基本 GPU 放不下，会溢出到系统内存，速度极慢（实测 8 token / 158s）。
为了让验证能在可接受时间内跑完，这里做三处裁剪：
  1) tools 只保留 2 个候选（原 5~7 个，prompt 从 ~1900 token 压到 ~400）
  2) system 提示词压到最短
  3) num_ctx 1024 / num_predict 200，够放下一轮 tool_call 即可
结论若通过，只证明「模型确实学到了 tool-call 格式」，性能评测必须回到有显存的机器上做。
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
            "description": "解析用户的加工/建模意图，抽取结构化参数",
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
    {
        "type": "function",
        "function": {
            "name": "nx.build_parametric_model",
            "description": "为 Siemens NX 生成参数化建模脚本",
            "parameters": {
                "type": "object",
                "properties": {
                    "wish": {"type": "string"},
                    "material": {"type": "string"},
                },
                "required": ["wish", "material"],
            },
        },
    },
]

PROMPT = "为NX12编写参数化建模脚本，工件AL7075-T6，外径80mm，内径24mm，长85mm。"


def call(payload, timeout=1800):
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(
        BASE + "/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with op.open(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "你是工业智能体，需要调用工具完成任务。"},
            {"role": "user", "content": PROMPT},
        ],
        "tools": TOOLS,
        "stream": False,
        "options": {"num_ctx": 1024, "num_predict": 200, "temperature": 0.0},
    }
    print(f"[{MODEL}] 精简 tool-call 验证 ...", flush=True)
    t0 = time.time()
    r = call(payload)
    el = time.time() - t0
    msg = r.get("message", {})
    calls = msg.get("tool_calls") or []
    print(f"\n耗时 {el:.0f}s | prompt_eval={r.get('prompt_eval_count')} "
          f"eval={r.get('eval_count')}")
    if calls:
        for c in calls:
            fn = c.get("function", {})
            args = fn.get("arguments")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    pass
            print(f"  OK tool_call -> {fn.get('name')}")
            print(f"     args={json.dumps(args, ensure_ascii=False)}")
        sys.exit(0)
    print("  无 tool_calls，纯文本:", (msg.get("content") or "")[:300])
    sys.exit(1)


if __name__ == "__main__":
    main()
