# -*- coding: utf-8 -*-
with open("scripts/workbuddy_virtu_bridge.py", "r", encoding="utf-8") as f:
    text = f.read()

target1 = """                if "tool_calls" in m:
                    entry["tool_calls"] = m["tool_calls"]"""

replacement1 = """                if "tool_calls" in m:
                    sanitized_calls = []
                    for c in m["tool_calls"]:
                        fn = c.get("function", {}) if isinstance(c, dict) else {}
                        a = fn.get("arguments", {})
                        if isinstance(a, str):
                            try:
                                a = json.loads(a)
                            except Exception:
                                pass
                        sanitized_calls.append({
                            "id": c.get("id", ""),
                            "type": "function",
                            "function": {"name": fn.get("name", ""), "arguments": a}
                        })
                    entry["tool_calls"] = sanitized_calls"""

target2 = """                    conv.append({
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [nc]
                    })"""

replacement2 = """                    ollama_call = {
                        "id": nc["id"],
                        "type": "function",
                        "function": {
                            "name": fn_name,
                            "arguments": args_dict,
                        }
                    }
                    conv.append({
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [ollama_call]
                    })"""

assert target1 in text, "target1 not found"
assert target2 in text, "target2 not found"
text = text.replace(target1, replacement1, 1)
text = text.replace(target2, replacement2, 1)

with open("scripts/workbuddy_virtu_bridge.py", "w", encoding="utf-8") as f:
    f.write(text)
print("SUCCESS: updated sanitized calls")
