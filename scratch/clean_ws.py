import re

src = "bridges/tool_calling_specs.py"
with open(src, "r", encoding="utf-8") as f:
    text = f.read()

# Collapse multiple consecutive newlines (more than 2 newlines -> 2 newlines)
cleaned = re.sub(r'\n\s*\n+', '\n\n', text)
# Normalize to unix or windows newlines
cleaned = cleaned.replace('\r\n', '\n').replace('\r', '\n')

with open(src, "w", encoding="utf-8", newline="\n") as f:
    f.write(cleaned)

print("Cleaned up whitespace in tool_calling_specs.py")
