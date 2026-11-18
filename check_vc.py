import re, os

p = r"d:\Virtu模型\closed_impeller_vericut.vcproject"
with open(p, "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

print("File size:", len(text))
for m in re.findall(r'(\b[A-Za-z0-9_./\\-]+\.(?:mch|ctl|tls|nc|stl|ply|vcproject)\b)', text, re.I):
    print("Referenced file:", m)
