# -*- coding: utf-8 -*-
import json, io, csv
from pathlib import Path
cat = json.load(open(r"d:\Virtu模型\knowledge_base\nx12_cn\catalog\nx12_cn_commands.json", encoding="utf-8"))
cmds = cat["commands"]
out = io.StringIO()

out.write("== IDs containing SKETCH ==\n")
for cid, c in cmds.items():
    if "SKETCH" in cid:
        out.write(f"{cid} | {c['zh']} | {c['menu_paths'][:2]}\n")

out.write("\n== ADM sync commands ==\n")
for cid, c in cmds.items():
    if cid.startswith("UG_ADM_") or cid.startswith("UG_MODELING_DELETE_FACE") or cid.startswith("UG_MODELING_REPLACE_FACE"):
        out.write(f"{cid} | {c['zh']} | {c['menu_paths'][:2]}\n")

out.write("\n== 快速修剪/延伸 translation ==\n")
loc = Path(r"D:\BaiduNetdiskDownload\NX 12.0.2.9\NX12.2.9waigua\NX12.2.9\NX\LOCALIZATION\translations\simpl_chinese")
for fp in sorted(loc.glob("*_simpl_chinese.txt")):
    with fp.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
        for line in f:
            if "快速修剪" in line or "快速延伸" in line or "轮廓曲线" in line:
                out.write(fp.name + " | " + line.strip() + "\n")
                break
open(r"d:\Virtu模型\temp\nx12_cn_sketch.txt", "w", encoding="utf-8").write(out.getvalue())
print("ok")
