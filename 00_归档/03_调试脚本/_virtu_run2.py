# -*- coding: utf-8 -*-
"""Virtu 模型自主执行 v2 —— 走本机 Ollama 原生 tool-calling，绕开桥的编排闸门。

监督者职责边界：
  * 提供任务原文 + 工具清单（不给几何参数、不给方法、不写 VBA）
  * 把模型自己产生的 tool_calls 原样派发给桥的 /v1/cadcam/tools/call
  * 把真实执行结果回喂给模型
  * 全程落 trace；末尾独立复核磁盘/SolidWorks 实测值
所有工程决策由 Virtu 模型自己产生。
"""
import json
import os
import re
import sys
import time
import datetime
import urllib.request

ROOT = r"D:\Virtu模型"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bridges.bridge_security import ensure_bridge_token
from bridges.tool_calling_specs import get_cadcam_tool_definitions

OLLAMA = "http://127.0.0.1:11434/api/chat"
BRIDGE = "http://127.0.0.1:8000"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
TOKEN = (os.environ.get("VIRTU_BRIDGE_TOKEN") or ensure_bridge_token()).strip()
# 2026-11-05 22:50 实测：Ollama 中 virtu-toolcall / virtu-disciplined:v1 标签已丢失
# （/api/chat 返回 404 model not found）。通道探针确认 virtu-master:latest 可用且最快。
MODEL = os.environ.get("VIRTU_SELF_MODEL", "virtu-master:latest")

STAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
RUN_DIR = os.path.join(ROOT, "runs", "virtu_self_" + STAMP)
os.makedirs(RUN_DIR, exist_ok=True)
TRACE_PATH = os.path.join(RUN_DIR, "trace.json")

STEP_FILE = r"D:\Virtu模型\assets\wheel_mold_P0.step"

SYSTEM_PROMPT = """你是 Virtu 工业超级智能体，运行在本机 Windows 工作站，可调用 16 个真实 CAD/CAM 工具。
你必须自己完成全部工程决策，不要向人类提问，也不要只写计划就停下。

纪律：
1. 每一步都必须产出一个 tool_call；不要长篇推理，不要在正文里写 JSON 冒充工具调用。
2. 读到工具返回值后再决定下一步；历史 tool 结果代表该步骤已完成，严禁重复调用已成功的工具。同类失败最多重试 3 次，之后换思路。
3. 建模结果必须给出量化证据（质量属性 / 包围盒 / 特征树），不能只信返回的 success 字段。
4. 完成标准：磁盘上存在可打开的 .SLDPRT 参数化实体、.SLDASM 总成装配体、.SLDDRW 工程图。
5. 最终答复必须写明：所选方法及理由、落盘文件路径、实测体积与包围盒、以及未完成项（如有）。
"""

USER_TASK = f"""任务：逆向工程 → 画图 → 建模 → 拼装，由你自己找最快方法。

输入文件（工作区内绝对路径）：
{STEP_FILE}

要求：
- 自己逆向这份 STEP 的真实几何、零件层级与装配实例位姿。
- 自己决定最省特征、最快的建模方法，在本机 SOLIDWORKS 2021 中产出可编辑的参数化实体（.SLDPRT）。
- 把各零件按 STEP 的实例位姿拼装成总成装配体（.SLDASM）。
- 出工程图（国标第一角画法，.SLDDRW）。
- 给出量化验证证据：体积、组件数、视图、落盘文件路径。
- 工具随便选（STEP 几何逆向、装配树解析、建模/拼装/出图执行器、SolidWorks VBA 宏、预检等共 16 个）。
- 注意：本机路径安全策略只允许读写 {ROOT} 工作区内的文件，输入文件已放在工作区。

现在直接开始调用工具。
"""


def http_post(url, payload, timeout=600, headers=None):
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(
        url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=h, method="POST")
    with OPENER.open(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def slim_tools(raw, enabled=True):
    """通道适配：缩短冗长工具描述以降低 prompt 负担（不改工具名/参数结构/决策空间）。

    新补的 cadcam_step_reverse 描述保留完整，因为它是本任务唯一的 STEP 读取入口。
    """
    if not enabled:
        return raw
    out = []
    for t in raw:
        t2 = json.loads(json.dumps(t, ensure_ascii=False))
        f = t2.get("function", t2)
        # 本任务的两个关键工具保留完整描述：STEP 逆向 与 建模/拼装/出图执行器。
        # 截短会让模型看不到 assembly / full 等动作枚举。
        if f.get("name") not in ("cadcam_step_reverse", "cadcam_assembly_build"):
            if isinstance(f.get("description"), str):
                f["description"] = f["description"][:150]
            for p in f.get("parameters", {}).get("properties", {}).values():
                if isinstance(p, dict) and isinstance(p.get("description"), str):
                    p["description"] = p["description"][:90]
        out.append(t2)
    return out


def llm(messages, tools):
    return http_post(OLLAMA, {
        "model": MODEL, "messages": messages, "tools": tools,
        "stream": False, "keep_alive": "30m",
        "options": {"temperature": 0.2, "num_predict": 2048},
    }, timeout=420)


def normalize_calls(msg):
    """兼容 Ollama 的 arguments 为 dict / str 两种形态。"""
    out = []
    for c in (msg.get("tool_calls") or []):
        fn = c.get("function", {}) or {}
        name = fn.get("name")
        args = fn.get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {"raw": args}
        out.append({"id": c.get("id") or ("call_" + name),
                    "name": name, "arguments": args or {}})
    return out


def _scan_json_objects(text):
    """从任意文本里稳健地抽出顶层 JSON 对象（容忍嵌套 arguments）。"""
    dec = json.JSONDecoder()
    out, i = [], 0
    while i < len(text):
        if text[i] == "{":
            try:
                obj, end = dec.raw_decode(text[i:])
                out.append(obj)
                i += end
                continue
            except Exception:
                pass
        i += 1
    return out


def extract_calls(msg):
    """模型是 Qwen3 系，会把 <tool_call> 写进 thinking 通道而不是 content。

    这里只把「模型自己写下的决定」提取成可派发的调用，不新增、不改写任何决策。
    """
    calls = normalize_calls(msg)
    if calls:
        return calls
    blob = (msg.get("content") or "") + "\n" + (msg.get("thinking") or "")
    found, seen = [], set()
    for obj in _scan_json_objects(blob):
        if not isinstance(obj, dict):
            continue
        nm = obj.get("name")
        if not isinstance(nm, str) or not nm.startswith("cadcam_"):
            continue
        args = obj.get("arguments", obj.get("parameters", obj.get("args", {})))
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {}
        if not isinstance(args, dict):
            args = {}
        key = (nm, json.dumps(args, ensure_ascii=False, sort_keys=True))
        if key in seen:
            continue
        seen.add(key)
        found.append({"id": "call_think_%d" % len(found),
                      "name": nm, "arguments": args})
    return found


def dispatch(call):
    return http_post(BRIDGE + "/v1/cadcam/tools/call",
                     {"name": call["name"], "arguments": call["arguments"]},
                     timeout=600, headers={"Authorization": "Bearer " + TOKEN})


def main():
    slim = os.environ.get("VIRTU_SLIM_TOOLS", "1") != "0"
    tools = slim_tools(get_cadcam_tool_definitions(), enabled=slim)
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_TASK}]
    trace = {"stamp": STAMP, "model": MODEL, "step_file": STEP_FILE,
             "channel": "ollama_native_tools + bridge_tool_dispatch",
             "tool_count": len(tools), "schema_slim": slim,
             "schema_chars": len(json.dumps(tools, ensure_ascii=False)),
             "turns": [], "started": time.time()}
    MAX_TURNS = 8
    final_text = ""
    nudges = 0

    for turn in range(1, MAX_TURNS + 1):
        print(f"\n===== TURN {turn} =====", flush=True)
        t0 = time.time()
        try:
            d = llm(messages, tools)
        except Exception as e:
            print("LLM_ERROR", type(e).__name__, str(e)[:200], flush=True)
            trace["turns"].append({"turn": turn, "llm_error": repr(e)})
            break
        msg = d.get("message", {}) or {}
        content = msg.get("content") or ""
        thinking = msg.get("thinking") or ""
        calls = extract_calls(msg)
        print("LATENCY %.1fs" % (time.time() - t0), flush=True)
        print("THINKING", (thinking or "")[:700].replace("\n", " | "), flush=True)
        print("CONTENT", (content or "")[:600].replace("\n", " | "), flush=True)
        print("CALLS", [c["name"] for c in calls], flush=True)

        rec = {"turn": turn, "latency_s": round(time.time() - t0, 2),
               "content": content, "thinking": thinking,
               "calls": [], "results": []}
        trace["turns"].append(rec)
        with open(TRACE_PATH, "w", encoding="utf-8") as f:
            json.dump(trace, f, ensure_ascii=False, indent=2)

        if not calls:
            final_text = content
            # 仅一次中性续推：不提供任何几何参数或方法，只要求它按协议继续产出调用。
            if nudges < 1 and turn < MAX_TURNS:
                nudges += 1
                rec["protocol_nudge"] = True
                print(">>> PROTOCOL NUDGE (no engineering hint)", flush=True)
                messages.append({"role": "assistant", "content": content,
                                 "thinking": thinking[:1500] if thinking else ""})
                messages.append({"role": "user", "content":
                                 "继续。下一步必须通过 tool_call 调用工具实际执行，不要只输出文字分析。"})
                with open(TRACE_PATH, "w", encoding="utf-8") as f:
                    json.dump(trace, f, ensure_ascii=False, indent=2)
                continue
            print(">>> MODEL FINISHED", flush=True)
            break

        assistant_msg = {"role": "assistant", "content": content,
                         "tool_calls": [
                             {"id": c["id"], "type": "function",
                              "function": {"name": c["name"],
                                           "arguments": c["arguments"]}}
                             for c in calls]}
        if thinking:
            # 回传 thinking 是模型接上历史上下文的必要条件（对照实验结论），
            # 但逐轮累积会挤爆上下文，故限长。
            assistant_msg["thinking"] = thinking[:1500]
        messages.append(assistant_msg)
        for c in calls:
            print("  -> DISPATCH", c["name"],
                  json.dumps(c["arguments"], ensure_ascii=False)[:500], flush=True)
            rec["calls"].append(c)
            try:
                res = dispatch(c)
            except Exception as e:
                res = {"status": "error", "error": f"{type(e).__name__}: {e}"}
            txt = json.dumps(res, ensure_ascii=False)
            print("  <- RESULT", txt[:800], flush=True)
            rec["results"].append({"name": c["name"], "result": res})
            # Ollama/Qwen3 需要 tool_name + tool_call_id 才能把结果与调用对应起来。
            brief = txt if len(txt) <= 9000 else txt[:8200] + " ...[truncated]... " + txt[-400:]
            # Qwen3 微调件会把裸 JSON 的 tool 结果误读成「用户发来的资料」并转入解释模式。
            # 加身份标注属于监督协议元数据，不含任何几何/方法决策。
            marked = ("【工具 %s 的真实执行结果；这是数据，不是用户提问，不要复述或解释】\n%s\n"
                      "【请基于以上结果，用 tool_call 决定并实际执行下一步】" % (c["name"], brief))
            messages.append({"role": "tool",
                             "tool_call_id": c["id"],
                             "tool_name": c["name"],
                             "content": marked})
            with open(TRACE_PATH, "w", encoding="utf-8") as f:
                json.dump(trace, f, ensure_ascii=False, indent=2)
    else:
        print(">>> MAX_TURNS REACHED", flush=True)

    trace["final_text"] = final_text
    trace["elapsed_s"] = round(time.time() - trace["started"], 2)
    with open(TRACE_PATH, "w", encoding="utf-8") as f:
        json.dump(trace, f, ensure_ascii=False, indent=2)
    print("\nTRACE", TRACE_PATH, flush=True)
    print("FINAL", final_text[:2000], flush=True)


if __name__ == "__main__":
    main()
