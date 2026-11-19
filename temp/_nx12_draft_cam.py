# -*- coding: utf-8 -*-
import csv, io
from pathlib import Path

loc = Path(r"D:\BaiduNetdiskDownload\NX 12.0.2.9\NX12.2.9waigua\NX12.2.9\NX\LOCALIZATION\translations\simpl_chinese")
out = io.StringIO()

want = {
    "ug_drafting.men": ["基本视图", "投影视图", "剖视图", "局部放大", "图纸页", "标题栏", "标注", "尺寸", "注释"],
    "ug_cam.men": ["工序", "刀具", "几何体", "方法", "程序", "后处理", "刀轨", "机床", "进给", "操作"],
    "ug_main.men": ["基本视图", "图纸页", "标题栏"],
}
rows = {k: [] for k in want}
for fp in sorted(loc.glob("*_simpl_chinese.txt")):
    with fp.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                parts = next(csv.reader([line], delimiter=" ", quotechar='"', skipinitialspace=True))
            except Exception:
                continue
            if len(parts) < 4:
                continue
            src, sid, en, zh = parts[0], parts[1], parts[2], parts[3]
            if src in want and sid.endswith(("_LABEL", "_TOOLBAR_LABEL", "_RIBBON_LABEL")):
                for kw in want[src]:
                    if kw in zh:
                        rows[src].append(f"{sid} | {en} | {zh}")
                        break

for src, lst in rows.items():
    out.write(f"== {src} ({len(lst)}) ==\n")
    seen = set()
    for r in lst:
        if r in seen:
            continue
        seen.add(r)
        out.write("  " + r + "\n")

open(r"d:\Virtu模型\temp\nx12_cn_draft_cam.txt", "w", encoding="utf-8").write(out.getvalue())
print("ok")
