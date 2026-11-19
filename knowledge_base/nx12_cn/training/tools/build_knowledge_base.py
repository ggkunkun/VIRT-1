#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""六级知识库生成器：模块-子模块-功能点-操作步骤-参数说明-注意事项。

输入: catalog/nx12_cn_full_catalog.json（全量补全目录）
输出: knowledge/<NN_模块>.md —— 每个模块一份，含该模块全部功能点。

真实性约束：
  - 功能点的 ID / 中文名 / 菜单路径 / 快捷键 / 提示消息 100% 来自介质目录，不编造；
  - 操作步骤中的"菜单路径"来自真实 .men 解析，"快捷键"来自 .btn ACCELERATOR；
  - 参数说明引用官方 message_zh；无官方说明者标注 [待实测]，不臆造默认值；
  - 每个节点带版本标签 NX12.0-CN 与证据等级 E1/E2/E3。
"""
from __future__ import annotations

import json, re, sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CAT = ROOT / "catalog" / "nx12_cn_full_catalog.json"
OUT = ROOT / "knowledge"

VER = "NX12.0-CN"


def sub_of(cmd: dict) -> str:
    """由菜单路径倒数第二级或来源菜单文件名推导子模块。"""
    menus = cmd.get("menus") or []
    # 取最有信息量的菜单名
    for m in menus:
        name = m.lower()
        for key, label in [
            ("sketch", "草图环境"), ("draft", "制图/PMI"), ("cam", "加工环境"),
            ("mold", "注塑模向导"), ("assembl", "装配环境"), ("sbsm", "同步建模"),
            ("smd", "钣金环境"), ("styler", "自由形状"), ("subdiv", "细分曲面"),
            ("layer", "图层"), ("preferences", "首选项"), ("utility", "实用工具"),
        ]:
            if key in name:
                return label
    paths = cmd.get("menu_paths") or []
    if paths and len(paths[0]) >= 2:
        return paths[0][-2]
    mp = cmd.get("men_files") or []
    if mp:
        return Path(mp[0]).stem
    return "通用命令"


def steps_for(cmd: dict) -> list[str]:
    """由真实菜单路径 + 快捷键生成可落地步骤骨架（未实测处显式标注）。"""
    s: list[str] = []
    paths = cmd.get("menu_paths") or []
    if paths:
        p = paths[0]
        if len(p) >= 2:
            s.append(f"在中文界面顶部菜单栏依次选择 **{' › '.join(p[:-1])}**。")
        s.append(f"在展开项中选择 **{p[-1]}**（命令 ID：`{cmd['id']}`）。")
    else:
        src = cmd.get("source_btn") or (cmd.get("men_files") or [""])[0]
        s.append(f"本命令定义于 `{src}`；[待实测] 在对应应用模块中通过命令查找器（`帮助(H) › 命令查找器(F)`）搜索「{cmd['zh'] or cmd['id']}」定位。")
    if cmd.get("accelerator"):
        s.append(f"可直接使用快捷键 **{cmd['accelerator']}** 调用（该快捷键来自介质 `.btn` 定义）。")
    if cmd.get("message_zh"):
        s.append(f"按对话框提示操作：{cmd['message_zh'].rstrip('。')}。")
    else:
        s.append("[待实测] 按弹出的中文对话框逐项设置参数后确定；具体控件名称与默认值需 GUI 取证。")
    s.append("单击 **确定** 完成；如结果为特征，检查图形区几何更新是否符合预期。")
    return s


def param_note(cmd: dict) -> str:
    parts = []
    if cmd.get("message_zh"):
        parts.append(f"官方功能说明（介质翻译表原文）：{cmd['message_zh']}")
    if cmd.get("hint"):
        parts.append(f"可用性提示：{cmd['hint']}")
    if cmd.get("synonyms"):
        parts.append(f"检索同义词：{cmd['synonyms']}")
    if not parts:
        parts.append("[待实测] 本命令无随介质分发的中文参数说明，参数项、取值范围与默认值需在 NX 12.0 中文界面取证后填写。")
    return "\n".join(f"    - {p}" for p in parts)


def caution(cmd: dict) -> str:
    ev = cmd["evidence"]
    c = []
    if ev == "E3-UNTR":
        c.append("该命令在介质中未找到官方中文翻译（E3），菜单显示名需在中文界面复核，勿据 ID 直译下结论。")
    elif ev == "E2-MENU":
        c.append("该命令仅见于菜单定义（E2），完整参数对话框需在 GUI 中确认。")
    if cmd.get("id", "").startswith("UG_MODELING_") or "FEATURE" in cmd.get("id", ""):
        c.append("特征类命令注意参数关联性；修改后需重算并检查特征导航器是否报错。")
    c.append("本条目适用版本严格限定 NX 12.0（12.0.2.9 介质）；NX 10 / 1847 / 2000 系列的菜单位置与对话框可能不同，禁止直接套用。")
    return "\n".join(f"    - {x}" for x in c)


def render_module(mod: str, cmds: list[dict], stats: dict) -> str:
    title = mod.split("_", 1)[1] if "_" in mod else mod
    L: list[str] = [
        f"# {title}",
        "",
        f"> 版本适用范围：**{VER}（NX 12.0 / 12.0.2.9 介质，简体中文）**",
        f"> 功能点数量：{len(cmds)}　|　数据基准：`training/catalog/nx12_cn_full_catalog.json`",
        "> 结构：模块 → 子模块 → 功能点 → 操作步骤 → 参数说明 → 注意事项（六级）",
        "> 证据等级：E1=介质.btn/官方翻译直提；E2=仅菜单定义+官方中文；E3=无官方中文，需GUI复核",
        "",
    ]
    subs = defaultdict(list)
    for c in cmds:
        subs[sub_of(c)].append(c)
    for si, (sub, group) in enumerate(sorted(subs.items(), key=lambda x: (-len(x[1]), x[0])), 1):
        L += [f"## {si}. 子模块：{sub}", "", f"本子模块 {len(group)} 个功能点。", ""]
        for ci, c in enumerate(sorted(group, key=lambda x: x["id"]), 1):
            name = c["zh"] or c["zh_menu"] or c["id"]
            L.append(f"### {si}.{ci} 功能点：{name}  `[{VER}] [{c['evidence']}]`")
            L.append("")
            L.append(f"- **命令 ID**：`{c['id']}`")
            paths = c.get("menu_paths") or []
            if paths:
                L.append("- **菜单路径**：" + "；".join(" › ".join(p) for p in paths[:3]))
            if c.get("accelerator"):
                L.append(f"- **快捷键**：`{c['accelerator']}`")
            if c.get("source_btn"):
                L.append(f"- **定义来源**：`{c['source_btn']}`")
            if c.get("men_files"):
                L.append(f"- **出现菜单**：`{c['men_files'][0]}`" + (f" 等 {len(c['men_files'])} 处" if len(c["men_files"]) > 1 else ""))
            L.append("")
            L.append("**操作步骤**（骨架来自真实菜单/快捷键，标注 `[待实测]` 处需 GUI 取证）：")
            L.append("")
            for i, s in enumerate(steps_for(c), 1):
                L.append(f"{i}. {s}")
            L.append("")
            L.append("**参数说明**：")
            L.append("")
            L.append(param_note(c))
            L.append("")
            L.append("**注意事项**：")
            L.append("")
            L.append(caution(c))
            L.append("")
    return "\n".join(L) + "\n"


def merge_v1_menupaths(data: dict) -> None:
    """从 v1 目录（已解析真实菜单层级）合并 menu_paths 到 v2 全量目录。"""
    v1 = ROOT.parent / "catalog" / "nx12_cn_commands.json"
    if not v1.exists():
        return
    old = json.loads(v1.read_text(encoding="utf-8"))
    merged = 0
    for cid, c in data["commands"].items():
        oc = old.get("commands", {}).get(cid)
        if oc and oc.get("menu_paths"):
            c["menu_paths"] = oc["menu_paths"]
            merged += 1
        else:
            c["menu_paths"] = []
    print(f"[OK] 合并真实菜单路径 {merged} 条")


def main() -> int:
    data = json.loads(CAT.read_text(encoding="utf-8"))
    merge_v1_menupaths(data)
    by_mod: dict[str, list] = defaultdict(list)
    for cid, c in data["commands"].items():
        by_mod[c["module"]].append(c)
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for mod in sorted(by_mod):
        fp = OUT / f"{mod}.md"
        fp.write_text(render_module(mod, by_mod[mod], data["stats"]), encoding="utf-8")
        manifest.append({"module": mod, "file": fp.name, "commands": len(by_mod[mod])})
        print(f"[OK] {fp.name}: {len(by_mod[mod])}")
    (OUT / "_manifest.json").write_text(
        json.dumps({"version": VER, "modules": manifest}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print("[OK] total", sum(m["commands"] for m in manifest))
    return 0


if __name__ == "__main__":
    sys.exit(main())
