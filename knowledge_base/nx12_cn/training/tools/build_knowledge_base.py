#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""六级知识库生成器：模块-子模块-功能点-操作步骤-参数说明-注意事项。

输入: catalog/nx12_cn_full_catalog.json（全量补全目录，含 E4-TRANSLATION）
输出: knowledge/<NN_模块>.md —— 每个模块一份，含该模块全部功能点。

真实性约束：
  - 功能点的 ID / 中文名 / 菜单路径 / 快捷键 / 提示消息 100% 来自介质目录或官方翻译表，不编造；
  - 操作步骤中的"菜单路径"来自真实 .men 解析，"快捷键"来自 .btn ACCELERATOR；
  - E4-TRANSLATION 条目仅有官方译文，菜单路径/快捷键/参数对话框需 GUI 复核；
  - 参数说明引用官方 message_zh；无官方说明者标注 [待实测]，不臆造默认值；
  - 每个节点带版本标签 NX12.0-CN 与证据等级 E1/E2/E3/E4。
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
    """由菜单路径/来源提示推导子模块。"""
    hint = (cmd.get("source_hint") or "").lower()
    if hint:
        for key, label in [
            ("sfem", "Simcenter Pre/Post"), ("desfem", "Design Simulation"),
            ("simcenter", "Simcenter 环境"), ("mechanisms", "Motion 机构运动"),
            ("simulation", "仿真/后处理"), ("durability", "耐久性分析"),
            ("kinematics", "运动学"), ("mechatronics", "机电一体化"),
            ("route", "管线布置"), ("routing", "管线布置"), ("teapipe", "管道应用"),
            ("electrical", "电气布线"), ("harness", "线束"), ("cabling", "线缆"),
            ("pipe", "管道"), ("lgcl", "逻辑布线"),
            ("ship", "船舶结构"), ("weld", "焊接"), ("flex_pcb", "PCB 设计"),
            ("inspection", "检测与计量"), ("line_designer", "线体规划"), ("pid", "工艺流程图"),
            ("mfg_view", "制造视图"), ("tool_designer", "工装设计"), ("additive", "增材制造"),
            ("aerosm", "航空应用"), ("aerodesign", "航空设计"), ("automotive", "汽车应用"),
            ("mechdes", "机构设计"), ("layout", "制图布局"), ("title_block", "标题栏"),
            ("draft", "制图/PMI"), ("mold", "注塑模向导"), ("stamping", "冲压模具"),
            ("pdiewizard", "冲压向导"), ("ediewizard", "电极设计"), ("electrode", "电极设计"),
            ("tooling", "工装"), ("animation", "动画/可视化"), ("visual_reporting", "可视化报告"),
            ("dmu", "数字样机"), ("diagramming", "图表"), ("polygon", "多边形建模"),
        ]:
            if key in hint:
                return label
        if hint.endswith(".men") or hint.endswith(".btn"):
            return Path(hint).stem
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
    """由真实菜单路径 + 快捷键/翻译表生成可落地步骤骨架（未实测处显式标注）。"""
    s: list[str] = []
    paths = cmd.get("menu_paths") or []
    if paths:
        p = paths[0]
        if len(p) >= 2:
            s.append(f"在中文界面顶部菜单栏依次选择 **{' › '.join(p[:-1])}**。")
        s.append(f"在展开项中选择 **{p[-1]}**（命令 ID：`{cmd['id']}`）。")
    else:
        src = cmd.get("source_btn") or (cmd.get("men_files") or [""])[0]
        if not src:
            src = cmd.get("source_hint") or ""
        if not src and cmd.get("translation_sources"):
            src = Path(cmd["translation_sources"][0]).name
        if cmd.get("evidence") == "E4-TRANSLATION":
            s.append(f"本命令为 **E4-TRANSLATION**：中文名/功能说明来自官方简体中文翻译表（`{src}`），但 `.men/.btn` 菜单源未随当前介质提供；[待实测] 在对应应用模块中通过 `帮助(H) › 命令查找器(F)` 搜索「{cmd['zh'] or cmd['id']}」定位实际菜单路径。")
        else:
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
    if ev == "E4-TRANSLATION":
        c.append("该命令来自官方简体中文翻译表（E4），中文名/功能说明可信；但菜单路径、快捷键、参数对话框未随介质提供，必须在 NX 12.0 中文界面 GUI 复核后使用。")
    elif ev == "E3-UNTR":
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
        "> 证据等级：E1=介质.btn/官方翻译直提；E2=仅菜单定义+官方中文；E3=无官方中文，需GUI复核；E4=官方翻译表补全，菜单/参数需GUI复核",
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
            if c.get("source_hint"):
                L.append(f"- **来源提示**：`{c['source_hint']}`")
            if c.get("men_files"):
                L.append(f"- **出现菜单**：`{c['men_files'][0]}`" + (f" 等 {len(c['men_files'])} 处" if len(c["men_files"]) > 1 else ""))
            if c.get("translation_sources"):
                L.append(f"- **官方翻译表**：`{c['translation_sources'][0]}`" + (f" 等 {len(c['translation_sources'])} 处" if len(c["translation_sources"]) > 1 else ""))
            L.append("")
            L.append("**操作步骤**（骨架来自真实菜单/快捷键或官方翻译表，标注 `[待实测]` 处需 GUI 取证）：")
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
