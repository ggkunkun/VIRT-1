# -*- coding: utf-8 -*-
"""Virtu 模型自主执行驱动器（监督者只做派发与留证，不做任何建模决策）。

流程:
  user task -> Virtu LLM (+14 tools) -> tool_calls -> /v1/cadcam/tools/call
            -> role=tool 回喂 -> 下一轮 ... -> 模型给出最终答复或达到步数上限

所有决策（读不读 STEP、用哪个工具、写什么几何、怎么验证）全部由模型产生。
监督者只在末尾独立复核磁盘产物与 SolidWorks 实测数值。
"""
import json
import os
import sys
import time
import datetime
import urllib.request

ROOT = r"D:\Virtu模型"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bridges.bridge_security import ensure_bridge_token
from bridges.tool_calling_specs import get_cadcam_tool_definitions

BASE = "http://127.0.0.1:8000"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
TOKEN = (os.environ.get("VIRTU_BRIDGE_TOKEN") or ensure_bridge_token()).strip()
STAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
RUN_DIR = os.path.join(ROOT, "runs", "virtu_self_" + STAMP)
os.makedirs(RUN_DIR, exist_ok=True)
TRACE_PATH = os.path.join(RUN_DIR, "trace.json")

STEP_FILE = r"C:\Users\Administrator\Desktop\微型机轮模总成(P0) 6R15-6R12-6R10.step"

SYSTEM_PROMPT = """你是 Virtu 工业超级智能体，运行在本机 Windows 工作站，拥有 14 个真实可执行的 CAD/CAM 工具。
你必须自己做出全部工程决策，不要向人类提问，不要请求确认，直接调用工具把事情做完。

硬性纪律：
1. 先判断环境，再动手；每一步工具调用后都要读返回值，失败就换思路重试，最多 3 次同类尝试。
2. 体积守恒断言：任何建模结果必须用质量属性或包围盒量化验证，不能凭工具返回的 success 字段就宣称成功。
3. 不要输出计划就停下。任务以"磁盘上存在可打开的实体模型文件"为完成标准。
4. 最终答复里必须列出：你选择的方法及理由、实际落盘文件路径、实测体积/包围盒数值、以及尚未完成的部分（如有）。
"""

USER_TASK = f"""任务：逆向工程再建模。

输入文件（本机绝对路径）：
{STEP_FILE}

要求：
- 由你自己逆向这份 STEP，找出其中真实的几何与尺寸，并自己决定最快、最省特征的建模方法。
- 在本机 SolidWorks 2021 里把这个零件建成可编辑的参数化实体，并保存到磁盘（.SLDPRT，路径放在 {ROOT} 下）。
- 必须给出量化验证证据（体积、包围盒或特征树），证明模型与逆向结果一致。
- 你有预检、SolidWorks VBA 宏、极限闭环链、桌面 GUI 控制等 14 个工具，手段完全由你选。

现在开始，直接调用工具，不要只描述你将怎么做。
"""


def post(path, payload, timeout=420):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + TOKEN},
        method="POST",
    )
    with OPENER.open(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def call_tool(name, args, timeout=600):
    """把模型决定的工具调用原样派发给桥。"""
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            args = {"raw": args}
    return post("/v1/cadcam/tools/call",
                {"name": name, "arguments": args}, timeout=timeout)


def main():
    tools = get_cadcam_tool_definitions()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_TASK},
    ]
    trace = {"stamp": STAMP, "step_file": STEP_FILE,
             "model": "virtu-cad-cam-10b", "turns": [], "started": time.time()}
    MAX_TURNS = 10
    final_text = ""

    for turn in range(1, MAX_TURNS + 1):
        t0 = time.time()
        print(f"\n===== TURN {turn} =====", flush=True)
        try:
            resp = post("/v1/chat/completions", {
                "model": "virtu-cad-cam-10b",
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",
                "temperature": 0.2,
                "max_tokens": 1024,
            }, timeout=420)
        except Exception as e:
            print("LLM_ERROR", type(e).__name__, str(e)[:200], flush=True)
            trace["turns"].append({"turn": turn, "llm_error": repr(e)})
            break

        msg = (resp.get("choices") or [{}])[0].get("message", {}) or {}
        content = msg.get("content") or ""
        calls = msg.get("tool_calls") or []
        gate = resp.get("virtu_gate", {})
        print("LATENCY", round(time.time() - t0, 1), "s", flush=True)
        print("GATE", json.dumps(gate, ensure_ascii=False)[:300], flush=True)
        print("CONTENT", content[:900].replace("\n", " | "), flush=True)
        print("TOOL_CALLS", len(calls), flush=True)

        rec = {"turn": turn, "latency_s": round(time.time() - t0, 2),
               "content": content, "gate": gate,
               "tool_calls": [], "tool_results": []}
        trace["turns"].append(rec)
        with open(TRACE_PATH, "w", encoding="utf-8") as f:
            json.dump(trace, f, ensure_ascii=False, indent=2)

        if not calls:
            final_text = content
            print(">>> MODEL FINISHED (no tool calls)", flush=True)
            break

        # 让 assistant 消息带着 tool_calls 进入历史
        messages.append({"role": "assistant", "content": content,
                         "tool_calls": calls})
        for c in calls:
            fn = c.get("function", {}) or {}
            name = fn.get("name") or c.get("name")
            args_raw = fn.get("arguments", "{}")
            print("  -> CALL", name, str(args_raw)[:400], flush=True)
            rec["tool_calls"].append({"id": c.get("id"), "name": name,
                                     "arguments": args_raw})
            try:
                res = call_tool(name, args_raw)
            except Exception as e:
                res = {"status": "error", "error": f"{type(e).__name__}: {e}"}
            short = json.dumps(res, ensure_ascii=False)
            print("  <- RESULT", short[:700], flush=True)
            rec["tool_results"].append({"name": name, "result": res})
            messages.append({"role": "tool",
                             "tool_call_id": c.get("id") or name,
                             "content": short[:12000]})
            with open(TRACE_PATH, "w", encoding="utf-8") as f:
                json.dump(trace, f, ensure_ascii=False, indent=2)
    else:
        print(">>> MAX_TURNS REACHED", flush=True)

    trace["final_text"] = final_text
    trace["elapsed_s"] = round(time.time() - trace["started"], 2)
    with open(TRACE_PATH, "w", encoding="utf-8") as f:
        json.dump(trace, f, ensure_ascii=False, indent=2)
    print("\nTRACE", TRACE_PATH, flush=True)
    print("FINAL", final_text[:1500], flush=True)


if __name__ == "__main__":
    main()
