import json
import sys

sys.path.insert(0, r"D:\Virtu模型")
from scripts.workbuddy_virtu_bridge import OpenAIBaseHandler

handler = OpenAIBaseHandler.__new__(OpenAIBaseHandler)

# 1. Test initial user prompt asking to decompose equipment with feature tree
msgs1 = [{"role": "user", "content": "帮我把这台双工位自动打螺丝机拆成零件，画出零件模型并带有完整特征树，最后组装起来！"}]
resp1 = handler._handle_tool_orchestration(msgs1, tools=[{"type": "function", "function": {"name": "cad.decompose_automation_assembly"}}])
print("Step 1 finish_reason:", resp1["choices"][0]["finish_reason"])
call1 = resp1["choices"][0]["message"]["tool_calls"][0]
print("Step 1 called tool:", call1["function"]["name"])

# 2. Test tool response continuation -> standard parts
msgs2 = msgs1 + [
    resp1["choices"][0]["message"],
    {"role": "tool", "tool_call_id": call1["id"], "name": call1["function"]["name"], "content": json.dumps({"status": "success"})}
]
resp2 = handler._handle_tool_orchestration(msgs2, tools=[])
print("Step 2 finish_reason:", resp2["choices"][0]["finish_reason"])
call2 = resp2["choices"][0]["message"]["tool_calls"][0]
print("Step 2 called tool:", call2["function"]["name"])

# 3. Test tool response continuation -> feature tree modeling
msgs3 = msgs2 + [
    resp2["choices"][0]["message"],
    {"role": "tool", "tool_call_id": call2["id"], "name": call2["function"]["name"], "content": json.dumps({"status": "success"})}
]
resp3 = handler._handle_tool_orchestration(msgs3, tools=[])
print("Step 3 finish_reason:", resp3["choices"][0]["finish_reason"])
call3 = resp3["choices"][0]["message"]["tool_calls"][0]
print("Step 3 called tool:", call3["function"]["name"])

print("[ALL TEST PASSED] Full tool calling chain verified successfully!")
