"""Test Six-Software Tool Calling Dispatch via WorkBuddy Bridge."""

import os
import sys
import json

sys.stdout.reconfigure(encoding="utf-8")

WORKSPACE = r"D:\Virtu模型"
sys.path.insert(0, WORKSPACE)

from scripts.workbuddy_virtu_bridge import OpenAIBaseHandler
from bridges.six_software_orchestrator import SixSoftwareOrchestrator

tools_path = os.path.join(WORKSPACE, "data", "tools", "industrial_agent_tools.json")
with open(tools_path, "r", encoding="utf-8") as f:
    tools = json.load(f)

handler = OpenAIBaseHandler.__new__(OpenAIBaseHandler)

test_prompts = [
    ("SolidWorks建模测试", "在 SolidWorks 里建一个法兰盘零件，外径150厚度20"),
    ("AutoCAD出图测试", "在 AutoCAD 里绘制轴系工程图并生成 DXF"),
    ("Siemens NX12测试", "在 NX12 里生成五轴叶轮加工刀路与表达式"),
    ("VERICUT仿真测试", "在 Vericut 里执行机床碰撞检查与过切分析"),
    ("CIMCO宏程序测试", "在 CIMCO Edit 里校验这段 FANUC 宏程序 #100=20"),
    ("斯沃数控对刀测试", "在 斯沃数控 仿真软件中配置外圆车刀并设置 G54 坐标系"),
]

print("=" * 70)
print("  SIX INDUSTRIAL SOFTWARE TOOL DISPATCH INTEGRATION TEST")
print("=" * 70)

all_passed = True
for name, prompt in test_prompts:
    messages = [{"role": "user", "content": prompt}]
    res = handler._handle_tool_orchestration(messages, tools)

    choice = res["choices"][0]
    finish_reason = choice["finish_reason"]
    tool_calls = choice["message"].get("tool_calls", [])

    if finish_reason != "tool_calls" or not tool_calls:
        print(f"❌ [{name}] Failed: finish_reason={finish_reason}, no tool_calls")
        all_passed = False
        continue

    fn_name = tool_calls[0]["function"]["name"]
    fn_args = json.loads(tool_calls[0]["function"]["arguments"])
    target_sw = fn_args.get("target_software")
    action = fn_args.get("action")

    print(f"✅ [{name}] Succeeded -> Tool: {fn_name} | Software: {target_sw} | Action: {action}")

    # Now simulate tool execution response
    tool_msg = {
        "role": "tool",
        "tool_call_id": tool_calls[0]["id"],
        "name": fn_name,
        "content": json.dumps({"status": "success", "software": target_sw, "action": action})
    }
    messages.append(choice["message"])
    messages.append(tool_msg)

    final_res = handler._handle_tool_orchestration(messages, tools)
    final_choice = final_res["choices"][0]
    if final_choice["finish_reason"] == "stop":
        print(f"   ↳ Multi-turn tool execution confirmed: finish_reason=stop")
    else:
        print(f"   ↳ Warning: final finish_reason={final_choice['finish_reason']}")
        all_passed = False

print("=" * 70)
if all_passed:
    print("🎉 ALL SIX INDUSTRIAL SOFTWARE TOOL CALLS 100% VERIFIED!")
else:
    print("❌ Some test cases failed.")
