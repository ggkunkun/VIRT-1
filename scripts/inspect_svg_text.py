# -*- coding: utf-8 -*-
import os, sys
sys.stdout.reconfigure(encoding='utf-8')
svg_path = r'e:\迅雷下载\工程图(1)\UG\SVG源文件\UG-01_轴承支座.svg'
with open(svg_path, 'r', encoding='utf-8', errors='ignore') as f:
    text = f.read()
print(f"SVG length: {len(text)} chars")
# extract text elements
import re
texts = re.findall(r'<text[^>]*>(.*?)</text>', text)
print(f"Text tags found: {len(texts)}")
for t in texts[:20]:
    clean = re.sub(r'<[^>]+>', '', t).strip()
    if clean:
        print("  ", clean)
