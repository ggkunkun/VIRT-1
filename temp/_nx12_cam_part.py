# -*- coding: utf-8 -*-
import io, os
from pathlib import Path

root = Path(r"D:\BaiduNetdiskDownload\NX 12.0.2.9\NX12.2.9waigua\NX12.2.9\NX\MACH\resource\template_part")
out = io.StringIO()
keywords = ["型腔铣", "平面铣", "深度轮廓", "钻孔", "固定轴", "曲面轮廓", "等高", "面铣", "车削", "线切割"]
files = list(root.rglob("*.prt")) if root.exists() else []
out.write(f"template parts: {len(files)}\n")
for fp in files[:40]:
    data = fp.read_bytes()
    hits = []
    for enc in ("utf-8", "utf-16-le"):
        for kw in keywords:
            try:
                b = kw.encode(enc)
            except Exception:
                continue
            if b in data:
                hits.append(f"{kw}/{enc}")
    if hits:
        out.write(f"{fp.relative_to(root)} | {', '.join(sorted(set(hits)))}\n")
open(r"d:\Virtu模型\temp\nx12_cn_cam_template.txt", "w", encoding="utf-8").write(out.getvalue())
print(out.getvalue()[:3000])
