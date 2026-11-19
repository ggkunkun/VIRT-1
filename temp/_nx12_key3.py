# -*- coding: utf-8 -*-
import json, io
cat = json.load(open(r"d:\Virtu模型\knowledge_base\nx12_cn\catalog\nx12_cn_commands.json", encoding="utf-8"))
cmds = cat["commands"]
out = io.StringIO()

for kw in ["直线", "圆弧", "圆", "矩形", "快速修剪", "修剪配方", "偏置曲线", "投影曲线", "相交曲线",
           "移动面", "偏置区域", "调整大小", "拉出面", "同步建模", "删除面", "替换面", "复制面", "剪切面",
           "测量", "导入", "导出", "属性", "图层", "角色", "布局", "视图", "渲染", "材料", "重量",
           "装配间隙", "干涉", "安装", "加载", "用户默认", "草图设置", "自动判断", "相切", "平行", "垂直"]:
    hits = [(cid, c["zh"], c["menu_paths"][0] if c["menu_paths"] else []) for cid, c in cmds.items() if kw in c["zh"]]
    out.write(f"\n-- {kw} ({len(hits)}) --\n")
    for h in hits[:20]:
        out.write(f"  {h[0]} | {h[1]} | {' > '.join(h[2])}\n")

# 当前草图模型中的所有路径以“草图”开头的命令
out.write("\n== sketch environment commands ==\n")
for cid, c in cmds.items():
    for p in c["menu_paths"]:
        if p and p[0].startswith(("草图曲线", "草图约束", "尺寸(D)", "任务(K)")):
            out.write(f"  {cid} | {c['zh']} | {' > '.join(p)}\n")
            break

open(r"d:\Virtu模型\temp\nx12_cn_key3.txt", "w", encoding="utf-8").write(out.getvalue())
print("ok")
