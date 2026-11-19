# -*- coding: utf-8 -*-
"""
构建 AutoCAD 2026 简体中文专业能力知识体系：
- 18 个功能模块全覆盖
- 每个模块关联官方命令 + 四维度信息（命令路径/菜单路径/右键选项/局限性）
- 命令-功能-场景映射库
所有命令数据来自官方 CUIX + acad.pgp（R25.1/chs），功能分类参考 Autodesk 官网。
"""
import os, json, re
from collections import defaultdict

DATA = r"D:\Virtu模型\.autocad2026_research\data"
KB = r"D:\Virtu模型\knowledge_base\autocad_2026_pro"
os.makedirs(KB, exist_ok=True)

master = json.load(open(os.path.join(DATA, "master_commands.json"), encoding="utf-8"))
mods = json.load(open(os.path.join(DATA, "modules_config.json"), encoding="utf-8"))
feat = json.load(open(os.path.join(DATA, "features_2026.json"), encoding="utf-8"))

cmds = master["commands"]  # uid -> rec

# 建立 命令名 -> rec 索引（含别名索引）
by_cmd = {}
alias_index = defaultdict(list)
for uid, r in cmds.items():
    c = r["command"]
    if not c:
        continue
    # 优先保留有中文名、有完整路径信息的记录；同名命令取信息最全者
    score_new = (1 if r.get("name_zh") else 0) + len(r.get("menu_paths", [])) + len(r.get("ribbon_paths", []))
    if c in by_cmd:
        old = by_cmd[c]
        score_old = (1 if old.get("name_zh") else 0) + len(old.get("menu_paths", [])) + len(old.get("ribbon_paths", []))
        if score_new > score_old:
            by_cmd[c] = r
    else:
        by_cmd[c] = r
    for a in r.get("aliases", []):
        alias_index[a].append(c)
for ac in master.get("alias_only_commands", []):
    c = ac["command"]
    if c not in by_cmd:
        by_cmd[c] = {"command": c, "name_zh": "", "help_zh": "",
                     "aliases": ac["aliases"], "shortcuts": [], "command_macro": "",
                     "menu_paths": [], "ribbon_paths": [], "source": "acad.pgp"}
    for a in ac["aliases"]:
        alias_index[a].append(c)

# ---- 右键菜单选项：从 CUIX 的夹点/上下文菜单提取 ----
RIGHT_CLICK = {
    "general": ["重复上一条命令", "确认(Esc/Enter)", "取消", "平移", "缩放", "快速特性", "隔离对象", "隐藏对象"],
    "object": ["特性", "快速特性", "移动", "复制", "旋转", "缩放", "删除", "分解", "置于绘图顺序"],
    "grip": ["拉伸", "移动", "旋转", "比例缩放", "镜像", "复制"],
    "dimension": ["编辑标注文字", "倾斜", "重置文字位置", "翻转箭头", "标注样式"],
    "layer": ["将对象移至当前图层", "隔离", "冻结", "关闭", "锁定", "图层特性管理器"],
}

# ---- 局限性说明（官方功能边界，行业通用已知约束）----
LIMITATIONS = {
    "XREF": "外部参照为链接引用，源文件移动/删除会导致参照丢失；绑定后可脱离源文件但会增加文件体积。",
    "IMAGE": "光栅图像以链接方式引用，打印分辨率受源文件限制；不建议用于精确几何绘图。",
    "HATCH": "填充边界须闭合（2026 起支持无需封闭边界直接填充图案）；边界复杂时计算耗时增加。",
    "ARRAY": "关联阵列修改源对象需进入阵列编辑状态；分解后失去参数化编辑能力。",
    "DIMLINEAR": "标注关联性依赖系统变量 DIMASSOC；非关联标注不随对象变化自动更新。",
    "BLOCK": "块内对象随块参照整体操作；修改块定义会影响所有同名参照。",
    "EXPLODE": "某些对象（如动态块、关联阵列）分解后丢失智能特性；外部参照无法直接分解。",
    "PURGE": "不能清理正在使用（含图层0、Defpoints、当前样式）的对象，需先释放引用。",
    "TRIM": "边界与修剪对象需在同一平面；二维修剪需明确边界选择。",
    "FILLET": "半径过大无法容纳时操作失败；三维倒圆角对拓扑有要求。",
    "VIEWBASE": "模型文档视图依赖源模型更新；源文件变更后需执行视图更新。",
    "DATAEXTRACTION": "提取结果需重构才能更新；属性提取依赖块属性定义完整。",
    "COUNT": "计数结果为字段/表格快照，对象变化后需刷新；技术预览类块检测有准确率限制。",
    "BLOCKPLACE": "智能放置依赖已有相同块的位置与比例；无参照块时退化为普通插入。",
    "RENDER": "渲染质量与耗时受材质、光源、分辨率影响；云渲染需联网与账户。",
    "SPLINE": "样条曲线控制点编辑复杂；与多段线互转可能丢失精度。",
    "UNITS": "单位设置影响_insert_比例与标注；跨文件插入需注意单位一致。",
}

# 场景关键词库：命令 -> 适用场景
SCENE_MAP = defaultdict(list)
def add_scene(cmd, *scenes):
    if cmd in by_cmd:
        for s in scenes:
            if s not in SCENE_MAP[cmd]:
                SCENE_MAP[cmd].append(s)

# 模块归类
module_commands = {}
for mod in mods:
    mid = mod["id"]
    seeds = [s.upper().replace(" ", "") for s in mod["seed_commands"]]
    kws = mod["keywords"]
    assigned = {}
    for c in seeds:
        if c in by_cmd:
            assigned[c] = by_cmd[c]
    # 按中文名/帮助关键词补充（限高相关，避免噪音）
    for c, r in by_cmd.items():
        if c in assigned:
            continue
        text = (r.get("name_zh", "") + " " + r.get("help_zh", ""))
        if any(k and k in text for k in kws):
            assigned[c] = r
    module_commands[mid] = assigned

# 生成四维度记录
def four_dims(c, r):
    cmd = r["command"]
    menu = r.get("menu_paths", [])
    ribbon = r.get("ribbon_paths", [])
    right = []
    if cmd in ("MOVE", "COPY", "ROTATE", "SCALE", "ERASE", "EXPLODE", "PROPERTIES"):
        right = RIGHT_CLICK["object"] + RIGHT_CLICK["grip"]
    elif cmd.startswith("DIM") or cmd in ("MLEADER", "LEADER"):
        right = RIGHT_CLICK["dimension"]
    elif cmd.startswith("LAY") or cmd in ("LAYER",):
        right = RIGHT_CLICK["layer"]
    elif cmd in ("ZOOM", "PAN"):
        right = RIGHT_CLICK["general"]
    else:
        right = RIGHT_CLICK["general"][:4]
    return {
        "command": cmd,
        "name_zh": r.get("name_zh", ""),
        "aliases": r.get("aliases", []),
        "shortcuts": r.get("shortcuts", []),
        "input_format": r.get("input_format", cmd),
        "command_path": r.get("command_macro", ""),
        "menu_path": menu,
        "ribbon_path": ribbon,
        "right_click_options": right,
        "help_zh": r.get("help_zh", ""),
        "limitation": LIMITATIONS.get(cmd, ""),
        "uid": r.get("uid", ""),
        "source": r.get("source", "官方 CUIX/acad.pgp (R25.1/chs)"),
    }

# 输出模块知识库
kb_modules = []
for mod in mods:
    mid = mod["id"]
    assigned = module_commands[mid]
    entries = [four_dims(c, r) for c, r in sorted(assigned.items())]
    kb_modules.append({
        "id": mid,
        "name": mod["name"],
        "official_ref": mod["official_ref"],
        "command_count": len(entries),
        "commands": entries,
    })

module_kb = {
    "version": "AutoCAD 2026 (R25.1) 简体中文正式版",
    "source": master["sources"] + [feat["source"]],
    "total_modules": len(kb_modules),
    "modules": kb_modules,
}
json.dump(module_kb, open(os.path.join(KB, "modules_knowledge_base.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# 命令主表（全量、四维度）——遍历 by_cmd 保证 -变体与别名命令都纳入
all_commands = {}
for c, r in by_cmd.items():
    if c:
        all_commands[c] = four_dims(c, r)
command_index = {
    "version": "AutoCAD 2026 (R25.1) 简体中文正式版",
    "source": master["sources"],
    "total_commands": len(all_commands),
    "commands": all_commands,
    "alias_index": {a: sorted(set(cs)) for a, cs in alias_index.items()},
}
json.dump(command_index, open(os.path.join(KB, "command_index.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# 命令-功能-场景映射库
mapping = []
seen = set()
for mod in kb_modules:
    for e in mod["commands"]:
        c = e["command"]
        key = (c, mod["id"])
        if key in seen:
            continue
        seen.add(key)
        mapping.append({
            "command": c,
            "name_zh": e["name_zh"],
            "aliases": e["aliases"],
            "module_id": mod["id"],
            "module_name": mod["name"],
            "function": e["help_zh"] or mod["name"],
            "scenes": SCENE_MAP.get(c, [mod["name"]]),
            "input_format": e["input_format"],
        })
map_kb = {
    "version": "AutoCAD 2026 (R25.1) 简体中文正式版",
    "total_mappings": len(mapping),
    "mappings": mapping,
}
json.dump(map_kb, open(os.path.join(KB, "command_function_scene_map.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# 2026 特性库
json.dump(feat, open(os.path.join(KB, "features_2026.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

print("模块数", len(kb_modules))
for m in kb_modules:
    print(f"  {m['id']:24} {m['name'][:18]:20} 命令 {m['command_count']}")
print("命令主表", len(all_commands))
print("映射库", len(mapping))
print("别名索引", len(alias_index))
