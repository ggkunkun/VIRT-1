# -*- coding: utf-8 -*-
"""通道探针：在本轮 16 工具 schema 下，挑选能正确产出工具调用的本地模型。"""
import importlib.util
import json
import sys
import time

sys.path.insert(0, r"D:\Virtu模型")
from bridges.tool_calling_specs import get_cadcam_tool_definitions

spec = importlib.util.spec_from_file_location("vr", r"D:\Virtu模型\_virtu_run2.py")
vr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vr)
tools = vr.slim_tools(get_cadcam_tool_definitions(), True)
print("TOOLS", len(tools), "SCHEMA", len(json.dumps(tools, ensure_ascii=False)), flush=True)

CANDIDATES = ["virtu-test-tool:latest", "virtu-ties-v1:latest",
              "virtu-master:latest", "qwen3:8b"]
msgs = [
    {"role": "system", "content": vr.SYSTEM_PROMPT},
    {"role": "user", "content":
        "任务：逆向 D:\\Virtu模型\\assets\\wheel_mold_P0.step，自己找最快方法，画图、建模并拼装成总成。现在调用第一个工具。"},
]
for model in CANDIDATES:
    payload = {"model": model, "messages": msgs, "tools": tools, "stream": False,
               "options": {"temperature": 0.2, "num_predict": 500}}
    t0 = time.time()
    try:
        d = vr.http_post(vr.OLLAMA, payload, timeout=200)
        m = d.get("message", {})
        calls = vr.extract_calls(m)
        print("%-28s %5.1fs calls=%s" % (model, time.time() - t0,
              [c["name"] for c in calls]), flush=True)
        for c in calls:
            print("     ARGS", json.dumps(c["arguments"], ensure_ascii=False)[:220], flush=True)
        if not calls:
            print("     THINK", (m.get("thinking") or "")[:160].replace("\n", " "), flush=True)
            print("     CONTENT", (m.get("content") or "")[:160].replace("\n", " "), flush=True)
    except Exception as e:
        print("%-28s ERR %s %s" % (model, type(e).__name__, str(e)[:110]), flush=True)
