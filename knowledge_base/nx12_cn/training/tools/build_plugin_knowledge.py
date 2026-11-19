#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第三方外挂知识分册生成器：每个外挂一份 Markdown。

输入 plugins/plugin_registry.json（由 build_plugin_registry.py 生成）
输出 knowledge/16_外挂分册/<plugin_id>_<name>.md

真实性：命令/中文名/菜单/ACTIONS 全部来自介质（GBK 解码），参数一律标 [待实测]。
"""
from __future__ import annotations

import json, sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REG = ROOT / "plugins" / "plugin_registry.json"
OUT = ROOT / "knowledge" / "16_外挂分册"
VER = "NX12.0-CN"


def render(p: dict) -> str:
    L = [
        f"# 外挂分册：{p['display_name']}（`{p['plugin_id']}`）",
        "",
        f"> 版本：**{VER}**　|　厂商目录：`{p['root']}`",
        f"> 命令数：{p['command_count']}（中文标签 {sum(1 for c in p['commands'] if c['label_zh'])}）",
        f"> 风险等级：**{p['risk']['level']}**　|　证据：{p['evidence']}",
        "> **非 Siemens 官方功能**，输出时必须向用户明确标注为第三方外挂。",
        "",
        "## 一、能力卡",
        "",
        f"- 菜单文件：{len(p['men_files'])} 个，已排除其它 NX 版本菜单 {p['excluded_men_files']} 个",
        f"- 文件编码：{p['encoding']}",
        f"- 菜单版本：{p['menu_versions'] or '未声明'}（NX12 应为 120）",
        f"- 动作形态：{p['actions_profile']}",
        f"- 硬编码绝对路径：{p['risk']['hardcoded_paths']} 处"
        + (f"，示例：`{p['risk']['hardcoded_examples'][0]}`" if p['risk']['hardcoded_examples'] else ""),
        f"- 环境变量依赖：{p['risk']['env_var_paths']} 处"
        + (f"，示例：`{p['risk']['env_var_examples'][0]}`" if p['risk']['env_var_examples'] else ""),
        f"- 跨外挂重名命令 ID：{p['risk']['duplicate_id_count']} 个（必须用复合键 `{p['plugin_id']}:<ID>`）",
        "",
        "## 二、调用前的硬性检查",
        "",
    ]
    if p["risk"]["menu_version_mismatch"]:
        L += ["- ⛔ **版本不兼容**：以下菜单 `VERSION != 120`，NX12 下可能不加载：", ""]
        for f in p["risk"]["menu_version_mismatch"][:6]:
            L.append(f"  - `{f}`")
        L.append("")
    if p["risk"]["hardcoded_paths"]:
        L += ["- ⚠️ **路径绑定**：ACTIONS 为绝对路径，外挂未装在原路径则调用失败；上线前用 `plugin_router.py doctor` 核对。", ""]
    if p["risk"]["env_var_paths"]:
        L += ["- ⚠️ **环境变量**：ACTIONS 依赖环境变量，NX 启动前必须已设置。", ""]
    L += ["- ✅ 命令键必须用命名空间：`plugin_id:command_id`；裸 ID 会被判为歧义。", "",
          "## 三、命令清单", ""]

    by_act: dict[str, list] = defaultdict(list)
    for c in p["commands"]:
        by_act[c["action_kind"]].append(c)
    for kind in sorted(by_act, key=lambda k: -len(by_act[k])):
        group = by_act[kind]
        L += [f"### 动作类型：{kind}（{len(group)} 条）", "",
              "| 复合键 | 中文名 | 菜单 | ACTIONS | 快捷键 |",
              "|---|---|---|---|---|"]
        for c in sorted(group, key=lambda x: x["command_id"]):
            label = c["label_zh"] or c["label_raw"] or "（无标签）"
            act = (c["actions"] or "—").replace("|", "\\|")
            menus = " / ".join(c.get("menus") or ([c["menu"]] if c.get("menu") else [])) or "—"
            L.append(f"| `{c['key']}` | {label} | {menus} | `{act[:60]}` | {c['accelerator'] or '—'} |")
        L.append("")

    L += ["## 四、标准调用流程（Agent 必须按此执行）", "",
          "1. `list_plugins()` 确认该外挂已注册、`version_ok_for_nx12=true`。",
          "2. `search('<中文名>', plugin='%s')` 定位候选，拿到复合键。" % p["plugin_id"],
          "3. `plan_call(key)` 取调用计划；**`callable=false` 时禁止执行**，按 `blockers` 的 code 处置。",
          "4. 检查 `preconditions` 全部满足；参数按 `param_contract` 组织，未实测字段不得编造。",
          "5. 在 NX GUI 中按 `menu_path` 逐层展开并点击命令；外挂无 COM/批处理，只能交互执行。",
          "6. 结果核验：几何/文件是否按预期变化；失败时先 Ctrl+Z，再按错误码上报。",
          "",
          "## 五、参数说明", "",
          "- 外挂 `.men` 只定义菜单与 ACTIONS，**不含参数默认值/取值范围**。",
          "- 因此本分册所有命令的参数状态为 `[待实测]`；Agent 不得向用户承诺具体参数值。",
          "- 需在 NX 12 中文界面打开该命令对话框后，按 `param_contract.schema` 回填并复跑验证。",
          "",
          "## 六、注意事项", "",
          f"- 该外挂与其它外挂共享 {p['risk']['duplicate_id_count']} 个短 ID，禁止省略命名空间。",
          "- 外挂升级后菜单可能重排，命令键以本注册表（介质实测）为准，升级后需重跑 `build_plugin_registry.py`。",
          "- 外挂写文件、批量改属性等操作可能绕过 NX 撤消栈，执行前必须提示用户备份。",
          "- 回复用户时按此格式标注：`[第三方外挂] {外挂名} › {命令名}`，不得与官方命令混述。",
          ""]
    return "\n".join(L) + "\n"


def main() -> int:
    if not REG.exists():
        print(f"[FAIL] 缺注册表 {REG}")
        return 1
    reg = json.loads(REG.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    idx = []
    for p in reg["plugins"]:
        fp = OUT / f"{p['plugin_id']}_{p['display_name'].split()[0]}.md"
        fp.write_text(render(p), encoding="utf-8")
        idx.append({"plugin_id": p["plugin_id"], "file": fp.name, "commands": p["command_count"]})
        print(f"[OK] {fp.name}: {p['command_count']}")

    # 总索引
    L = ["# 第三方外挂总索引", "",
         f"> 版本：**{VER}**　|　外挂 {len(reg['plugins'])} 个，命令 {reg['totals']['commands']} 条",
         "> 官方中国包（GC Toolkit）不属于外挂，见文末说明。", "",
         "| 外挂 | 插件 ID | 命令数 | 中文标签 | 风险 | NX12 版本兼容 | 分册 |",
         "|---|---|---:|---:|---|---|---|"]
    for p in reg["plugins"]:
        ver_ok = "✅" if all(v in ("", "120") for v in p["menu_versions"]) else "⛔ VERSION≠120"
        f = next(x["file"] for x in idx if x["plugin_id"] == p["plugin_id"])
        L.append(f"| {p['display_name']} | `{p['plugin_id']}` | {p['command_count']} | "
                 f"{sum(1 for c in p['commands'] if c['label_zh'])} | {p['risk']['level']} | {ver_ok} | [{f}]({f}) |")
    L += ["", "## 官方中国包（不计入第三方外挂）", "",
          f"- 路径：`{reg['official_china_package']['path']}`",
          f"- 说明：{reg['official_china_package']['note']}",
          "- 处理方式：按内置能力通道调用，使用官方中文翻译表，不套用外挂的参数未验证规则。",
          "", "## 跨外挂重名（必须用复合键）", "",
          f"- 重名命令 ID：{reg['cross_plugin_duplicate_ids']['count']} 个",
          "", "| 命令 ID | 归属外挂 |", "|---|---|"]
    for s in reg["cross_plugin_duplicate_ids"]["samples"]:
        L.append(f"| `{s['id']}` | {', '.join(s['owners'])} |")
    L += ["", "> 完整重名表见 `plugins/plugin_registry.json` 的 `cross_plugin_duplicate_ids`。", ""]
    (OUT / "_总索引.md").write_text("\n".join(L), encoding="utf-8")
    print("[OK] _总索引.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
