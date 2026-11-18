# -*- coding: utf-8 -*-
"""通道能力探针：补工具后，模型能否自己找到并调用 cadcam_step_reverse。"""
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
print("TOOLS", len(tools), "SCHEMA_CHARS", len(json.dumps(tools, ensure_ascii=False)), flush=True)

for model in ("virtu-toolcall", "virtu-ties-v1"):
    msgs = [
        {"role": "system", "content": vr.SYSTEM_PROMPT},
        {"role": "user", "content":
            "工作区里有一份 STEP：D:\\Virtu模型\\assets\\wheel_mold_P0.step。"
            "请先取得它的真实几何尺寸，再决定建模方法。现在调用第一个工具。"},
    ]
    payload = {"model": model, "messages": msgs, "tools": tools, "stream": False,
               "options": {"temperature": 0.2, "num_predict": 600}}
    t0 = time.time()
    try:
        d = vr.http_post(vr.OLLAMA, payload, timeout=180)
        m = d.get("message", {})
        calls = vr.extract_calls(m)
        print("%-20s %5.1fs  calls=%s  think=%s  content=%s" % (
            model, time.time() - t0, [c["name"] for c in calls],
            (m.get("thinking") or "")[:180].replace("\n", " "),
            (m.get("content") or "")[:180].replace("\n", " ")), flush=True)
        for c in calls:
            print("    ARGS", json.dumps(c["arguments"], ensure_ascii=False)[:260], flush=True)
    except Exception as e:
        print(model, "ERR", type(e).__name__, str(e)[:160], flush=True)
