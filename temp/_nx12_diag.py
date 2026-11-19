# -*- coding: utf-8 -*-
import json, io, re, csv
from pathlib import Path

cat = json.load(open(r"d:\Virtu模型\knowledge_base\nx12_cn\catalog\nx12_cn_commands.json", encoding="utf-8"))
menus = cat["menus"]
out = io.StringIO()

out.write("== UG_INSERT items ==\n")
for t, i in menus["UG_INSERT"]["items"]:
    out.write(f"{t} {i}\n")

out.write("\n== menus containing DESIGN ==\n")
for k, v in menus.items():
    if "DESIGN" in k:
        out.write(f"{k}  file={v['file']} items={v['items'][:6]}\n")

out.write("\n== who cascades UG_FILE ==\n")
for k, v in menus.items():
    for t, i in v["items"]:
        if t == "CASCADE" and i in ("UG_FILE", "UG_INSERT", "UG_TOOLBOX", "UG_ASSEMBLIES", "UG_PREFERENCES"):
            out.write(f"{i} <- {k} (file={v['file']})\n")

out.write("\n== root items ==\n")
for t, i in menus.get("UG_GATEWAY_MAIN_MENUBAR", {}).get("items", []):
    out.write(f"{t} {i}\n")

# 直接搜中文对照表
loc = Path(r"D:\BaiduNetdiskDownload\NX 12.0.2.9\NX12.2.9waigua\NX12.2.9\NX\LOCALIZATION\translations\simpl_chinese")
out.write("\n== raw translation search ==\n")
kws = ["型腔铣", "平面铣", "深度轮廓", "基本视图", "投影视图", "图纸页", "装配约束", "分型", "弯边", "展开", "后处理", "刀轨", "工序导航器"]
hits = {k: [] for k in kws}
for fp in sorted(loc.glob("*_simpl_chinese.txt")):
    try:
        with fp.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    parts = next(csv.reader([line.strip()], delimiter=" ", quotechar='"', skipinitialspace=True))
                except Exception:
                    continue
                if len(parts) < 4:
                    continue
                zh = parts[3]
                for k in kws:
                    if k in zh and len(hits[k]) < 6:
                        hits[k].append(f"{parts[0]} | {parts[1]} | {zh}")
    except OSError:
        pass
for k in kws:
    out.write(f"\n-- {k} --\n")
    for h in hits[k]:
        out.write("  " + h + "\n")

open(r"d:\Virtu模型\temp\nx12_cn_diag.txt", "w", encoding="utf-8").write(out.getvalue())
print("ok")
