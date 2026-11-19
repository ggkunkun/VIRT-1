# -*- coding: utf-8 -*-
import json, io
cat = json.load(open(r"d:\Virtu模型\knowledge_base\nx12_cn\catalog\nx12_cn_commands.json", encoding="utf-8"))
cmds = cat["commands"]
out = io.StringIO()

def dump(prefixes, limit=400):
    n = 0
    for cid, c in cmds.items():
        if any(cid.startswith(p) for p in prefixes):
            p = c["menu_paths"][0] if c["menu_paths"] else []
            out.write(f"{cid} | {c['zh']} | {c['zh_menu']} | {' > '.join(p)}\n")
            n += 1
            if n >= limit:
                out.write("...(truncated)\n")
                return

out.write("== UG_DRAFT_ ==\n"); dump(["UG_DRAFT_"])
out.write("\n== UG_SKETCH / TOOLBOX_SKETCH ==\n"); dump(["UG_SKETCH", "UG_TOOLBOX_SKETCH", "UG_DIRECT_SKETCH"])
out.write("\n== UG_MODELING_ (FEATURE/FF/SMD/SBSM) ==\n"); dump(["UG_MODELING_"])
out.write("\n== UG_ASSY_ ==\n"); dump(["UG_ASSY_"], 160)
out.write("\n== CAM ==\n"); dump(["UG_CAM_", "CAM_"], 160)
out.write("\n== MOLD ==\n"); dump(["MW_", "UGMOLD_"], 200)

out.write("\n== 视图/图纸/公差/间隙 keyword ==\n")
for kw in ["视图", "图纸", "公差", "间隙", "基准", "注释", "焊接", "曲线", "约束", "尺寸", "层", "属性", "测量"]:
    hits = [(cid, c["zh"], c["menu_paths"][0] if c["menu_paths"] else []) for cid, c in cmds.items() if kw in c["zh"]]
    out.write(f"\n-- {kw} ({len(hits)}) --\n")
    for h in hits[:25]:
        out.write(f"  {h[0]} | {h[1]} | {' > '.join(h[2])}\n")

open(r"d:\Virtu模型\temp\nx12_cn_prefix.txt", "w", encoding="utf-8").write(out.getvalue())
print("ok")
