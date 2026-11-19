# -*- coding: utf-8 -*-
"""
从 AutoCAD 2026 简体中文正式版官方 CUIX 界面定义文件中提取权威命令数据。
数据源：D:\\cad2026\\AutoCAD 2026\\UserDataCache\\zh-cn\\Support\\acad.CUIX
这是随正式版安装的官方简体中文界面定义（非第三方、非旧版本）。
"""
import os, re, json, xml.etree.ElementTree as ET
from collections import defaultdict

BASE = r"D:\Virtu模型\.autocad2026_research\raw\cuix_zh"
OUT = r"D:\Virtu模型\.autocad2026_research\data"
os.makedirs(OUT, exist_ok=True)


def clean(s):
    if not s:
        return ""
    return re.sub(r"\s+", " ", s).strip()


def extract_macros():
    """提取所有 MenuMacro：中文名、命令、CLI命令、帮助说明、类型、提示"""
    tree = ET.parse(os.path.join(BASE, "MenuGroup.cui"))
    root = tree.getroot()
    macros = {}
    for mm in root.findall(".//MenuMacro"):
        uid = mm.get("UID", "")
        macro = mm.find("Macro")
        if macro is None:
            continue
        rec = {"uid": uid, "macro_type": macro.get("type", "")}
        for ch in macro:
            tag = ch.tag
            txt = clean(ch.text)
            if tag == "Name":
                rec["name_zh"] = txt
            elif tag == "Command":
                rec["command_macro"] = txt
            elif tag == "CLICommand":
                rec["cli_command"] = txt
            elif tag == "HelpString":
                rec["help_zh"] = txt
            elif tag == "ToolTip":
                rec["help_topic"] = ch.get("HelpTopic", "")
        # 规范化主命令名：优先 CLICommand，否则从 Command 宏解析
        cmd = rec.get("cli_command", "")
        if not cmd:
            cm = rec.get("command_macro", "")
            # 形如 ^C^C_line  或 _line  或 $M=...
            m = re.match(r"[\^_]*C?C?_?([A-Za-z][A-Za-z0-9]*)", cm)
            if m:
                cmd = m.group(1)
        rec["command"] = cmd.upper().replace("-", "") if cmd else ""
        macros[uid] = rec
    return macros


def extract_accelerators(macros):
    """提取快捷键：CTRL+K 等 -> 命令"""
    tree = ET.parse(os.path.join(BASE, "AcceleratorRoot.cui"))
    root = tree.getroot()
    accels = []
    for ma in root.findall(".//MenuAccelerator"):
        kc = ma.find(".//KeyCombo")
        ref = ma.find(".//MacroRef")
        if kc is None or ref is None:
            continue
        mid = ref.get("MenuMacroID", "")
        keys = kc.get("accKeys", "")
        char = kc.get("AccelChar", "")
        combo = "+".join([x for x in [keys, char] if x])
        m = macros.get(mid, {})
        accels.append({
            "keys": combo,
            "macro_id": mid,
            "name_zh": m.get("name_zh", ""),
            "command": m.get("command", ""),
            "cli_command": m.get("cli_command", ""),
        })
    return accels


def extract_menu_paths():
    """从 PopMenuRoot 提取菜单层级路径，命令ID -> 菜单路径（中文）"""
    tree = ET.parse(os.path.join(BASE, "PopMenuRoot.cui"))
    root = tree.getroot()
    paths = defaultdict(list)

    def walk(node, path):
        name = ""
        # 菜单项的显示名可能在 Name 子元素或 attributes
        for ch in node:
            if ch.tag in ("Name", "MenuItem", "Menu") and ch.text and clean(ch.text):
                name = clean(ch.text)
                break
        nm = clean(node.get("Name", "")) or name
        newpath = path + ([nm] if nm and nm != "*"*len(nm) else [])
        # 找该节点引用的 Macro
        refs = node.findall(".//MacroRef")
        for rf in refs:
            mid = rf.get("MenuMacroID", "")
            if mid and newpath:
                paths[mid].append(" > ".join(newpath))
        for ch in node:
            walk(ch, newpath)

    walk(root, [])
    return {k: sorted(set(v)) for k, v in paths.items()}


def extract_ribbon_paths():
    """从 RibbonRoot 提取功能区路径，命令ID -> 选项卡>面板>按钮（中文）"""
    tree = ET.parse(os.path.join(BASE, "RibbonRoot.cui"))
    root = tree.getroot()
    paths = defaultdict(list)

    def node_label(node):
        # 优先 Name 子元素（选项卡/面板定义名），其次 Text/Name 属性
        for ch in node:
            if ch.tag == "Name" and ch.text and clean(ch.text):
                return clean(ch.text)
        for attr in ("Text", "Name"):
            v = clean(node.get(attr, ""))
            if v:
                return v
        return ""

    def walk(node, path):
        lbl = node_label(node)
        newpath = list(path)
        # 仅把结构性节点纳入层级
        if node.tag in ("RibbonTabSource", "RibbonPanelSource", "RibbonTabSourceReference",
                        "RibbonPanelSourceReference"):
            if lbl:
                newpath.append(lbl)
        # 按钮节点：其 MenuMacroID 即为命令，Text 为按钮中文名
        mid = node.get("MenuMacroID", "")
        if node.tag in ("RibbonCommandButton", "RibbonToggleButton", "RibbonButton",
                        "RibbonSplitButton") and mid:
            btn = clean(node.get("Text", "")) or lbl
            final = newpath + ([btn] if btn else [])
            paths[mid].append(" > ".join(final))
        for ch in node:
            walk(ch, newpath)

    walk(root, [])
    return {k: sorted(set(v))[:6] for k, v in paths.items()}


def main():
    macros = extract_macros()
    accels = extract_accelerators(macros)
    menu_paths = extract_menu_paths()
    ribbon_paths = extract_ribbon_paths()

    # 合并路径
    for uid, m in macros.items():
        m["menu_paths"] = menu_paths.get(uid, [])
        m["ribbon_paths"] = ribbon_paths.get(uid, [])

    # 统计有 CLI 命令的实体
    with_cmd = {k: v for k, v in macros.items() if v["command"]}
    data = {
        "source": r"D:\cad2026\AutoCAD 2026\UserDataCache\zh-cn\Support\acad.CUIX",
        "source_note": "AutoCAD 2026 简体中文正式版随安装官方界面定义文件（一手权威数据）",
        "total_macros": len(macros),
        "total_with_command": len(with_cmd),
        "total_accelerators": len(accels),
        "macros": macros,
        "accelerators": accels,
    }
    p = os.path.join(OUT, "cuix_extracted.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("写出", p)
    print("MenuMacro总数", len(macros), "有命令", len(with_cmd), "快捷键", len(accels))
    print("有菜单路径的命令数", sum(1 for m in macros.values() if m["menu_paths"]))
    print("有功能区路径的命令数", sum(1 for m in macros.values() if m["ribbon_paths"]))
    # 样例
    for uid in ["ID_Line", "ID_Circle", "ID_Copy", "ID_DimLinear", "ID_Move"]:
        if uid in macros:
            print("\n样例", uid, json.dumps(macros[uid], ensure_ascii=False)[:500])


if __name__ == "__main__":
    main()
