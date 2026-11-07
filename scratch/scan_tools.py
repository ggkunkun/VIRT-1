import os
import re

pattern = re.compile(r'"(?:name|function_name|tool_name|tool)":\s*"([a-zA-Z0-9_\.]+)"')
all_tools = {}

for root, dirs, files in os.walk('data'):
    for f in files:
        if f.endswith(('.json', '.jsonl')):
            path = os.path.join(root, f)
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as fp:
                    content = fp.read()
                    matches = pattern.findall(content)
                    for m in matches:
                        all_tools[m] = all_tools.get(m, 0) + 1
            except Exception:
                pass

print("=== Found tool names in data/ ===")
for k in sorted(all_tools.keys()):
    if '.' in k or 'cadcam' in k:
        print(f"{k}: {all_tools[k]}")
