# -*- coding: utf-8 -*-
import json, io, csv
from pathlib import Path
cat = json.load(open(r"d:\Virtu模型\knowledge_base\nx12_cn\catalog\nx12_cn_commands.json", encoding="utf-8"))
menus = cat["menus"]
out = io.StringIO()

for target in ["UG_FILE_NEW", "UG_FILE_SAVE_ALL", "UG_MODELING_EXTRUDED_FEATURE"]:
    out.write(f"== {target} ==\n")
    for mid, m in menus.items():
        if any(i == target for _, i in m["items"]):
            out.write(f"  in menu {mid} file={m['file']} label_lookup={cat['commands'].get(target,{}).get('menu_paths')}\n")

out.write("\n== UG_FILE defs ==\n")
for mid in ["UG_FILE", "UG_FILE_NEW", "UG_FILE_SAVE", "UG_GATEWAY_MAIN_MENUBAR"]:
    m = menus.get(mid)
    if m:
        out.write(f"{mid} file={m['file']} n_items={len(m['items'])} items={m['items'][:12]}\n")

out.write("\n== translations for UG_FILE *_LABEL ==\n")
loc = Path(r"D:\BaiduNetdiskDownload\NX 12.0.2.9\NX12.2.9waigua\NX12.2.9\NX\LOCALIZATION\translations\simpl_chinese")
for fp in sorted(loc.glob("*_simpl_chinese.txt")):
    with fp.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
        for line in f:
            if "UG_FILE_LABEL" in line or "UG_FILE_NEW_LABEL" in line:
                out.write(fp.name + " | " + line.strip() + "\n")

open(r"d:\Virtu模型\temp\nx12_cn_diag2.txt", "w", encoding="utf-8").write(out.getvalue())
print("ok")
