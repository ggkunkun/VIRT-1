# -*- coding: utf-8 -*-
import json, io
cat = json.load(open(r"d:\Virtu模型\knowledge_base\nx12_cn\catalog\nx12_cn_commands.json", encoding="utf-8"))
cmds = cat["commands"]
out = io.StringIO()
for kw in ["求和", "求差", "求交", "布尔", "基准平面", "基准轴", "基准坐标系", "加厚", "抽取",
           "阵列特征", "阵列面", "镜像特征", "镜像几何体", "分割面", "修剪体", "修剪片体", "旋转",
           "凸台", "腔", "垫块", "键槽", "筋板", "用户定义", "缝合", "取消缝合", "组合", "实体",
           "片体", "曲面", "偏置曲面", "填充曲面", "直纹", "扫掠", "网格", "桥接", "延伸", "弯边曲面"]:
    hits = [(cid, c["zh"], c["menu_paths"][0] if c["menu_paths"] else []) for cid, c in cmds.items() if kw in c["zh"]]
    out.write(f"\n-- {kw} ({len(hits)}) --\n")
    for h in hits[:18]:
        out.write(f"  {h[0]} | {h[1]} | {' > '.join(h[2])}\n")
open(r"d:\Virtu模型\temp\nx12_cn_model.txt", "w", encoding="utf-8").write(out.getvalue())
print("ok")
