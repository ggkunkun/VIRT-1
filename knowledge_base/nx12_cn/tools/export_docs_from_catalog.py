#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从命令目录生成两份文档：
  00_基座/03_快捷键速查.md      —— 原生快捷键全表（75 条）
  11_命令字典/00_全量命令索引.md —— 按顶层菜单分组的全量命令索引
数据源：catalog/nx12_cn_commands.json（由 extract_nx12_cn_catalog.py 生成）
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CATALOG = ROOT / "catalog" / "nx12_cn_commands.json"


def main() -> int:
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    cmds = cat["commands"]
    stats = cat["stats"]

    # ---------- 快捷键表 ----------
    rows = []
    for c in cmds.values():
        if not c.get("accelerator"):
            continue
        path = " → ".join(c["menu_paths"][0]) if c["menu_paths"] else "（无菜单路径）"
        rows.append((c["accelerator"], c["zh"], c["id"], path))
    rows.sort(key=lambda r: (r[0].split("+")[-1], r[0]))

    lines = [
        "# 00-03 NX 12.0 中文版原生快捷键速查",
        "",
        f"> 数据源：安装介质 `definitions_*.btn` 的 `ACCELERATOR` 字段，共 **{len(rows)}** 条。",
        "> 只用原生长快捷键；本机插件注册的快捷键不在本表。",
        "",
        "## 全表",
        "",
        "| 快捷键 | 中文名 | 命令 ID | 菜单路径 |",
        "| :--- | :--- | :--- | :--- |",
    ]
    for acc, zh, cid, path in rows:
        lines.append(f"| `{acc}` | {zh} | `{cid}` | {path} |")

    lines += [
        "",
        "## 高频组合（建议背下来）",
        "",
        "| 场景 | 快捷键 |",
        "| :--- | :--- |",
        "| 新建 / 打开 / 保存 | `Ctrl+N` / `Ctrl+O` / `Ctrl+S` |",
        "| 撤销 / 重做 | `Ctrl+Z` / `Ctrl+Y` |",
        "| 删除 | `Ctrl+D` |",
        "| 显示和隐藏 | `Ctrl+W`；隐藏 `Ctrl+B`；显示 `Ctrl+Shift+K` |",
        "| 适合窗口 | `Ctrl+F`；刷新 `F5`；重置视图 `Ctrl+F8` |",
        "| 旋转 / 缩放 | `Ctrl+R` / `Ctrl+Shift+Z` |",
        "| 表达式 | `Ctrl+E` |",
        "| 定制（改快捷键） | `Ctrl+1` |",
        "| 用户界面首选项 | `Ctrl+2` |",
        "| 对象信息 | `Ctrl+I` |",
        "| 编辑对象显示 | `Ctrl+J` |",
        "| 移动对象 | `Ctrl+T` |",
        "| 图层设置 | `Ctrl+L` |",
        "| 重复上一命令 | `F4` |",
        "| 选择优先级：特征/面/体/边/组件 | `Shift+F` / `Shift+G` / `Shift+B` / `Shift+E` / `Shift+C` |",
        "| 操作记录：播放 / 编辑 | `Alt+F8` / `Alt+F11` |",
        "| 宏：录制 / 回放 | `Ctrl+Shift+R` / `Ctrl+Shift+P` |",
        "| 上下文帮助 | `F1` |",
        "",
        "## 改键规则",
        "",
        "1. `工具(T)` → `定制(Z)...`（`Ctrl+1`）→ `键盘` 页签。",
        "2. 类别选 `所有命令（按类别）`，搜索中文名。",
        "3. 选中命令 → `按新快捷键` → 按键 → `指派`。",
        "4. 冲突时 NX 会提示“已被占用”；不要覆盖 `Ctrl+S`、`Ctrl+Z` 这类全局键。",
        "5. 改键属于用户设置，不影响安装介质与其他人。",
        "",
        f"> 生成时间：{datetime.now().astimezone().isoformat(timespec='seconds')}；命令总数 {stats['commands']}。",
    ]
    (ROOT / "00_基座" / "03_快捷键速查.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ---------- 全量命令索引 ----------
    groups: dict[str, list[dict]] = defaultdict(list)
    for c in cmds.values():
        if c["menu_paths"]:
            groups[c["menu_paths"][0][0]].append(c)
        else:
            groups["（无菜单路径 / API·批处理）"].append(c)

    idx = [
        "# 11-00 NX 12.0 中文版全量命令索引",
        "",
        f"> 共 **{stats['commands']}** 条命令，其中 **{stats['commands_with_menu_path']}** 条有菜单路径；"
        f"中文名 **{stats['commands_with_zh']}** 条；快捷键 **{stats['commands_with_accel']}** 条。",
        "> 中文名取自 NX 12.0 简体中文语言包；菜单路径由 `.men` 级联关系重建。",
        "> 本索引用于检索；带 `[CMD:...]` 标记的操作步骤见各模块文档。",
        "",
    ]
    for top in sorted(groups, key=lambda k: (-len(groups[k]), k)):
        items = groups[top]
        idx.append(f"## {top}（{len(items)} 条）")
        idx.append("")
        idx.append("| 中文名 | 命令 ID | 菜单路径 |")
        idx.append("| :--- | :--- | :--- |")
        for c in sorted(items, key=lambda x: (x["menu_paths"] and "/".join(x["menu_paths"][0]) or "", x["zh"])):
            path = " → ".join(c["menu_paths"][0]) if c["menu_paths"] else "—"
            idx.append(f"| {c['zh']} | `{c['id']}` | {path} |")
        idx.append("")

    (ROOT / "11_命令字典").mkdir(parents=True, exist_ok=True)
    (ROOT / "11_命令字典" / "00_全量命令索引.md").write_text("\n".join(idx) + "\n", encoding="utf-8")
    print(f"[OK] 快捷键 {len(rows)} 条；命令索引 {len(cmds)} 条，分组 {len(groups)} 个")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
