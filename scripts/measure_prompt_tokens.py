"""实测 16/17 工具面的服务端 prompt_eval_count（本机 Ollama 在线时跑）。

4779 这个数是 2026-11-06 在 16 工具面下由服务端报出的（checkpoints/PROVENANCE.json
→ toolcall_ctx_overflow_defect）。工具面在 2026-11-13 变成 17 项后，那个数不再覆盖新面，
`tests/test_toolcall_plumbing_gates.py` 只能退化成「估算不得低于 4779」。

本脚本补上真实回读：同一模型、同一题、同一 num_ctx，分别发 16 与 17 工具的 /api/chat，
读 prompt_eval_count。注意本机有透明代理会截 localhost，必须显式清空 ProxyHandler。
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = "virtu-moe-14b:latest"
ENDPOINT = "http://127.0.0.1:11434/api/chat"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def load_case():
    with open(ROOT / "data" / "benchmark" / "virtu_eval_v1" / "toolcall.jsonl",
              encoding="utf-8") as f:
        return json.loads(f.readline())


def build_messages(case):
    msgs = []
    if case.get("system"):
        msgs.append({"role": "system", "content": case["system"]})
    for m in case.get("context") or []:
        msgs.append({"role": m["role"], "content": m["content"]})
    msgs.append({"role": "user", "content": case["prompt"]})
    return msgs


def measure(tools, messages, num_ctx=8192):
    body = json.dumps({
        "model": MODEL, "messages": messages, "tools": tools,
        "stream": False, "think": False,
        "options": {"num_ctx": num_ctx, "num_predict": 1, "temperature": 0},
    }, ensure_ascii=False).encode()
    req = urllib.request.Request(ENDPOINT, data=body,
                                 headers={"Content-Type": "application/json"})
    with OPENER.open(req, timeout=600) as r:
        d = json.load(r)
    return {"prompt_eval_count": d.get("prompt_eval_count"),
            "eval_count": d.get("eval_count"),
            "num_ctx": d.get("context_length") or num_ctx}


def main():
    case = load_case()
    msgs = build_messages(case)
    arms = json.loads((ROOT / "virtu_eval" / "arms.json").read_text(encoding="utf-8"))
    tools17 = arms["virtu_moe_14b"]["tools"]
    tools16 = [t for t in tools17 if t["function"]["name"] != "cadcam_feature_ops"]
    assert len(tools16) == 16 and len(tools17) == 17, (len(tools16), len(tools17))

    out = {"model": MODEL, "case": case["id"],
           "endpoint": ENDPOINT, "num_ctx": 8192,
           "measured_at": __import__("datetime").datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}
    out["tools16"] = measure(tools16, msgs)
    out["tools17"] = measure(tools17, msgs)
    out["delta_tokens"] = (out["tools17"]["prompt_eval_count"]
                           - out["tools16"]["prompt_eval_count"])
    print(json.dumps(out, ensure_ascii=False, indent=1))
    dest = ROOT / "reports" / "PROMPT_TOKENS_BY_TOOL_SURFACE_2026-11-13.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("->", dest.name)


if __name__ == "__main__":
    main()
