# -*- coding: utf-8 -*-
"""监督器：只负责唤起 Virtu 模型、派发它自己决定的 tool_call、独立验证产物。
所有建模决策由模型产生，本脚本不预设任何几何参数或操作步骤。
"""
import json
import os
import sys
import time
import urllib.request

ROOT = r"D:\Virtu模型"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bridges.bridge_security import ensure_bridge_token
from bridges.tool_calling_specs import get_cadcam_tool_definitions

BASE = "http://127.0.0.1:8000"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
TOKEN = (os.environ.get("VIRTU_BRIDGE_TOKEN") or ensure_bridge_token()).strip()


def post(path, payload, timeout=300):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + TOKEN},
        method="POST",
    )
    with OPENER.open(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def get(path, timeout=60):
    req = urllib.request.Request(
        BASE + path, headers={"Authorization": "Bearer " + TOKEN})
    with OPENER.open(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def flatten_tools(raw):
    out = []
    for t in raw:
        if t.get("type") == "function" and isinstance(t.get("function"), dict):
            f = t["function"]
            out.append({"name": f.get("name"), "description": f.get("description", ""),
                        "parameters": f.get("parameters", {})})
        else:
            out.append(t)
    return out


if __name__ == "__main__":
    print("TOKEN_LEN", len(TOKEN))
    raw = get_cadcam_tool_definitions()
    tools = flatten_tools(raw)
    print("TOOLS_COUNT", len(tools))
    for t in tools:
        print("  -", t.get("name"), "|", (t.get("description") or "")[:90].replace("\n", " "))

    print("--- PING ---")
    t0 = time.time()
    r = post("/v1/chat/completions", {
        "model": "virtu-cad-cam-10b",
        "messages": [{"role": "user", "content": "只回答两个字：收到"}],
        "temperature": 0.1,
        "max_tokens": 32,
    }, timeout=300)
    print("PING_SECONDS", round(time.time() - t0, 2))
    print(json.dumps(r, ensure_ascii=False)[:1500])
