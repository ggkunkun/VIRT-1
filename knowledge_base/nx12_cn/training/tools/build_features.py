#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""专属特性库生成器：快捷键体系 / 中文术语对照 / 版本差异 / 报错代码 / 性能调优。

真实性原则：
  - 快捷键、术语对照：全部来自介质目录（measured），逐条可溯源；
  - 版本差异：仅列出可从介质证明的事实（介质版本=12.0.2.9、VERSION 121 菜单、含YX/KASA外挂等），
    其余与其它版本的对比项列为"待官方资料/实测确认"的核对清单，不臆造差异；
  - 报错代码：NX 的数字错误码需官方文档或实际触发取证，这里给出取证方法与开放式登记表，
    不编造"代码→解法"对照（那是误导）。
"""
from __future__ import annotations

import json, sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CAT = ROOT / "catalog" / "nx12_cn_full_catalog.json"
OUT = ROOT / "features"
VER = "NX12.0-CN"


def main() -> int:
    data = json.loads(CAT.read_text(encoding="utf-8"))
    cmds = data["commands"]
    OUT.mkdir(parents=True, exist_ok=True)

    # 1) 快捷键体系
    accels = [(v.get("accelerator", ""), cid, v["zh"], (v.get("menu_paths") or [[""]])[0])
              for cid, v in cmds.items() if v.get("accelerator")]
    accels.sort()
    L = ["# NX 12.0 中文版 快捷键体系", "",
         f"> 版本：**{VER}**　|　快捷键条目：{len(accels)}",
         "> 来源：介质 `definitions_*.btn` 中的 `ACCELERATOR` 字段（measured），非记忆。",
         "> 自定义规则见末节；修改前建议导出当前角色（Role）配置备份。", ""]
    L += ["## 一、完整快捷键表（介质实测）", "",
          "| 快捷键 | 命令 ID | 中文名称 | 菜单路径 |", "|---|---|---|---|"]
    for a, cid, zh, path in accels:
        L.append(f"| `{a}` | `{cid}` | {zh} | {' › '.join(path)} |")
    L += ["", "## 二、分类速查", ""]
    groups = defaultdict(list)
    for a, cid, zh, path in accels:
        key = path[0] if path else "其它"
        groups[key].append((a, zh))
    for k in sorted(groups, key=lambda x: -len(groups[x])):
        L.append(f"### {k}（{len(groups[k])}）")
        L.append("")
        for a, zh in groups[k]:
            L.append(f"- `{a}` — {zh}")
        L.append("")
    L += ["## 三、自定义快捷键规则（首选项/定制）", "",
          f"[{VER}] 以下入口来自介质菜单定义，可据此在 GUI 中定制：", ""]
    for cid, v in cmds.items():
        if any(k in cid for k in ("CUSTOMIZE", "KEYBOARD", "ROLE", "GEOMETRY")) and v.get("zh"):
            L.append(f"- `{cid}` — {v['zh']}" + (f"（菜单：{' › '.join((v.get('menu_paths') or [['']])[0])}）" if v.get("menu_paths") else ""))
    L += ["", "- 操作路径（骨架）：`工具(T) › 定制(Z)` → 切换到「键盘」页 → 选中命令 → 在「按新快捷键」框输入组合 → 指定 → 应用到角色 → 保存角色。",
          "- [待实测] 不同角色（Role）下可修改的快捷键范围、冲突提示的具体文案需在中文界面截图确认。",
          "- 注意：`Ctrl+1` 为定制、`F4` 为重复上一命令等系统级绑定，覆盖前确认不与本表冲突。", ""]
    (OUT / "01_快捷键体系.md").write_text("\n".join(L), encoding="utf-8")
    print("[OK] 01_快捷键体系.md", len(accels))

    # 2) 中文术语对照
    terms = defaultdict(list)
    for cid, v in cmds.items():
        if v.get("zh") or v.get("en"):
            terms[(v.get("zh", ""), v.get("en", ""))].append((cid, v.get("evidence", "")))
    T = ["# NX 12.0 中文版 术语对照（中文 ↔ 英文 ↔ 命令 ID）", "",
         f"> 版本：**{VER}**　|　术语条目：{len(terms)}",
         "> 中文名来自 `simpl_chinese` 官方翻译表，英文名来自 `.btn` 的 LABEL 字段；均为 measured。",
         "> 助记符 `&` 已去除；菜单显示名带括号快捷键（如 `文件(F)`）为界面原文。", "",
         "| 中文（官方译法） | English (LABEL) | 代表命令 ID | 证据 |", "|---|---|---|---|"]
    for (zh, en), refs in sorted(terms.items(), key=lambda x: x[0][0]):
        cid, ev = refs[0]
        T.append(f"| {zh} | {en} | `{cid}` | {ev} |")
    (OUT / "02_中文术语对照.md").write_text("\n".join(T), encoding="utf-8")
    print("[OK] 02_中文术语对照.md", len(terms))

    # 3) 版本差异对照库（只写介质可证事实 + 待核对清单）
    D = ["# 版本差异对照库（严格边界）", "",
         f"> 本训练体系唯一适配：**{VER}**（介质版本字符串见下）。",
         "> 原则：凡未能从本机介质或其它版本官方介质直接取证的差异，一律列入「待核对」，不臆造。", "",
         "## 一、本版本可证事实（measured）", "",
         f"- 介质版本标识：`{data['nx_version']}`", f"- UI 语言：`{data['ui_language']}`",
         "- 菜单文件头版本号：`VERSION 121`（见 `MACH/application/ug_cam.men` 等）",
         "- 主程序：`NXBIN/ugraf.exe`（SHA256 见 catalog key_sources_sha256）",
         "- 介质内含第三方外挂目录：`YANGJEE`（YSUG/QuickCAM/TKLTOOLS）、`KASA`、`MS_NXTOOLS`、`NX_CHINA_PACKAGE` 等；"
         "这些外挂命令 **不是 Siemens 官方功能**，已归入「15_其他与第三方外挂」，训练时禁止与官方命令混用。",
         "- 菜单中同时存在「原/原有」标记的旧命令（如「基本曲线（原有）」「边倒圆」旧版），说明本版本保留向后兼容命令。",
         "", "## 二、与其它版本的差异核对清单（待取证，不预填结论）", "",
         "| 对比对象 | 需核对的差异维度 | 取证方式 | 状态 |", "|---|---|---|---|"]
    for other in ["NX 10.0", "NX 1847 系列", "NX 1903/1907/1911 等 19xx", "NX 2000 系列及更新", "NX 中文版 vs 英文版同一版本"]:
        for dim in ["菜单层级与命令 ID 是否一致", "对话框控件名与参数默认值", "快捷键绑定", "文件格式/兼容性（part 版本）", "JIT/Flex 授权与许可管理"]:
            D.append(f"| {other} | {dim} | 对照该版本官方介质 + GUI 截图 | 待核对 |")
    D += ["", "## 三、使用纪律", "",
          "- 输出任何操作前，先确认用户环境确为 NX 12.0；若用户提到其它版本，明确声明本知识不适用并转人工核对。",
          "- 命令 ID 以本目录为准；不以其它版本的记忆替代。", ""]
    (OUT / "03_版本差异对照库.md").write_text("\n".join(D), encoding="utf-8")
    print("[OK] 03_版本差异对照库.md")

    # 4) 报错代码库（开放式登记 + 取证方法，不编造）
    E = ["# 高频报错代码与解决方案（登记表）", "",
         f"> 版本：**{VER}**　|　原则：NX 错误码必须来自实际触发日志或官方帮助，本表初始为空条目模板。",
         "> 严禁凭 ID 编造“代码→解法”——那会给出错误指导。下列为标准化取证与登记流程。", "",
         "## 一、 erro 取证方法（可立即执行）", "",
         "1. 复现报错时开启 NX 日志文件：`首选项(P) › 用户界面(I)` 中确认日志级别，或用 `帮助(H) › 日志` 定位日志文件。",
         "2. 记录完整错误原文、错误码、触发命令 ID、当时操作步骤、NX 版本与许可证状态。",
         "3. 在 `ugslmd.log`（路径：`C:\\Program Files\\Siemens\\PLMLicenseServer\\`）核对是否许可/超时类问题。",
         "4. 将证据填入下表，经实测确认解法后再标记为已验证。",
         "", "## 二、登记表", "",
         "| 错误码 | 中文报错原文 | 触发命令/场景 | 实测解法 | 证据(截图/日志路径) | 验证状态 |", "|---|---|---|---|---|---|",
         "| （待登记） | | | | | 待实测 |",
         "", "## 三、已可从介质确认的诊断类命令（可用于自查）", ""]
    for cid, v in cmds.items():
        if any(k in cid for k in ("CHECK", "DIAG", "VALIDAT", "VERIFY", "INFO_")) and v.get("zh"):
            E.append(f"- `{cid}` — {v['zh']}" + (f"（{' › '.join((v.get('menu_paths') or [['']])[0])}）" if v.get("menu_paths") else ""))
    E += ["", "> 以上命令来自介质目录（measured），可作为排障入口；其具体判读规则需在 GUI 中实测补充。", ""]
    (OUT / "04_报错代码库.md").write_text("\n".join(E), encoding="utf-8")
    print("[OK] 04_报错代码库.md")

    # 5) 性能优化与配置调优
    P = ["# 性能优化与配置调优", "",
         f"> 版本：**{VER}**　|　下列首选项/命令入口来自介质目录（measured），调优参数值需在目标机型实测。", "",
         "## 一、介质中与性能/显示/可视化相关的官方入口", ""]
    for cid, v in cmds.items():
        if any(k in cid for k in ("PERFORMANCE", "VISUALIZATION", "GRAPHICS", "MEMORY", "PREFERENCE")) and v.get("zh"):
            P.append(f"- `{cid}` — {v['zh']}" + (f"（{' › '.join((v.get('menu_paths') or [['']])[0])}）" if v.get("menu_paths") else ""))
    P += ["", "## 二、调优核对清单（分场景，参数值待实测填入）", "",
          "| 场景 | 调整项 | 官方入口 | 建议值/依据 | 状态 |", "|---|---|---|---|---|",
          "| 大装配卡顿 | 可视化性能、小平面显示、延迟更新 | `UG_PREFERENCES_PERFORMANCE` | 待实测 | 待验证 |",
          "| 图形显示异常 | 可视化首选项、渲染样式 | `UG_PREFERENCES_VISUALIZATION` | 待实测 | 待验证 |",
          "| 内存占用高 | 关闭未用部件、引用集、卸载部件 | 见装配模块对应命令 | 待实测 | 待验证 |",
          "| 许可证断连 | 检查 ugslmd 服务与 lic 文件 | 本机：`C:\\Program Files\\Siemens\\PLMLicenseServer\\ugslmd.exe` | 服务需运行 | 可参考 |",
          "", "## 三、本机实测环境记录（2026-11-18）", "",
          "- 许可证服务 `ugslmd.exe` 进程在运行，`splm_ugslmd.log` 有 `ugraf.exe` 的 IN USE 记录。",
          "- 介质使用 Mesa 软件渲染（`temp/mesa*`），无独立 GPU 时的显示性能需单独评估。", ""]
    (OUT / "05_性能优化配置.md").write_text("\n".join(P), encoding="utf-8")
    print("[OK] 05_性能优化配置.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
