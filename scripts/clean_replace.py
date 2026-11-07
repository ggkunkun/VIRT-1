# -*- coding: utf-8 -*-
import os

target_path = r"d:\Virtu模型\agent_chain_executor.py"
with open(target_path, "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace('open(path, "w", encoding="utf-8").write("\n".join(lines))', 'open(path, "w", encoding="utf-8").write(chr(10).join(lines))')
content = content.replace('open(path, "w", encoding="utf-8").write("\r\n".join(lines))', 'open(path, "w", encoding="utf-8").write(chr(10).join(lines))')

with open(target_path, "w", encoding="utf-8", newline="\r\n") as f:
    f.write(content)
print("Fixed write join in agent_chain_executor.py.")
