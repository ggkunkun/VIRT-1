# -*- coding: utf-8 -*-
import io, re
from pathlib import Path

loc = Path(r"D:\BaiduNetdiskDownload\NX 12.0.2.9\NX12.2.9waigua\NX12.2.9\NX\LOCALIZATION\translations\simpl_chinese")
out = io.StringIO()
pat = re.compile(r"^([\w]+): (.*?): '(.*)' = '(.*)'(?: \(.*\))?\s*$")
entries = []
for fp in sorted(loc.glob("*_nlm.txt")):
    with fp.open("r", encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            m = pat.match(line.strip())
            if m:
                entries.append((fp.name, m.group(3), m.group(4)))
out.write(f"nlm entries: {len(entries)}\n")
keys = ["Cavity Mill", "Planar Mill", "Z-Level", "Zlevel", "Depth", "Drill", "Face Mill", "End Mill",
        "Ball Mill", "Chamfer", "Thread", "Contour", "Rough", "Finish", "Rest", "Adaptive", "Wave",
        "Spot", "Counter", "Tap", "Ream", "Bore"]
seen = set()
for kw in keys:
    out.write(f"\n-- {kw} --\n")
    n = 0
    for src, en, zh in entries:
        if kw.lower() in en.lower() and len(zh) <= 24 and (en, zh) not in seen:
            seen.add((en, zh))
            out.write(f"  {en} = {zh}  [{src}]\n")
            n += 1
            if n >= 15:
                break
open(r"d:\Virtu模型\temp\nx12_cn_nlm_cam.txt", "w", encoding="utf-8").write(out.getvalue())
print("ok", len(entries))
