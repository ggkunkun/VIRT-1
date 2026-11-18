# -*- coding: utf-8 -*-
import sys
import json
import urllib.request
import re

history_file = r"d:\Virtu模型\projects\turbine_blade_live_v200\mcp_chat_history.json"

if len(sys.argv) > 1 and sys.argv[1] == "init":
    history = [
        {
            "role": "system",
            "content": (
                "你是由 DeepMind 与 Virtu 团队打造的工业超级智能体（Virtu Super Agent）。\n"
                "当前五轴数控加工仿真中心已在桌面 [180, 60] 就绪。\n"
                "你的任务是自主决定并输出 Windows-MCP 工具调用以操控物理鼠标。\n"
                "可选工具：\n"
                "- Move(loc=[x, y])\n"
                "- Click(loc=[x, y], button='left'|'right', clicks=1)\n"
                "- Wait(duration=秒数)\n"
                "- Screenshot()\n\n"
                "必须且只能输出标准 JSON 格式：\n"
                "```json\n"
                "{\"name\": \"工具名\", \"arguments\": {...}}\n"
                "```"
            )
        }
    ]
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    print("INIT_OK")
    sys.exit(0)

# Load history
with open(history_file, "r", encoding="utf-8") as f:
    history = json.load(f)

# Append user observation
user_msg = sys.argv[1]
history.append({"role": "user", "content": user_msg})

req = urllib.request.Request(
    "http://127.0.0.1:11434/api/chat",
    data=json.dumps({
        "model": "virtu-v3-all90:perfect",
        "stream": False,
        "messages": history,
        "options": {"temperature": 0.1, "num_predict": 512}
    }).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)
resp = urllib.request.urlopen(req, timeout=60)
data = json.loads(resp.read().decode("utf-8"))
content = data["message"]["content"]
history.append({"role": "assistant", "content": content})

with open(history_file, "w", encoding="utf-8") as f:
    json.dump(history, f, indent=2, ensure_ascii=False)

print("MODEL_OUTPUT:", content)
