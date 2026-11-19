#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试用例集生成器：覆盖全部功能点，每点 3 个场景。

场景维度：
  S1 基础调用与定位    —— 依真实菜单路径/快捷键定位命令（可静态复核）
  S2 对话框参数探查    —— 记录对话框控件/默认值/单位（必须 GUI 取证）
  S3 边界与失误处理    —— 空选择/非法输入/取消/重复执行等（必须 GUI 取证）

可复现性字段：
  STATIC_CHECKABLE —— 依据介质目录可静态核对（命令ID/路径/快捷键存在性）
  PENDING_GUI      —— 需 NX 12.0 中文界面实际执行取证，当前未验证
"""
from __future__ import annotations

import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CAT = ROOT / "catalog" / "nx12_cn_full_catalog.json"
V1 = ROOT.parent / "catalog" / "nx12_cn_commands.json"
OUT = ROOT / "tests"

VER = "NX12.0-CN"


def main() -> int:
    data = json.loads(CAT.read_text(encoding="utf-8"))
    cmds = data["commands"]
    mp: dict[str, list] = {}
    if V1.exists():
        old = json.loads(V1.read_text(encoding="utf-8"))
        mp = {k: v.get("menu_paths", []) for k, v in old.get("commands", {}).items()}
    OUT.mkdir(parents=True, exist_ok=True)

    cases = []
    seq = 0
    for cid, c in cmds.items():
        paths = mp.get(cid, [])
        zh = c["zh"] or c["zh_menu"] or cid
        base = {"version": VER, "command_id": cid, "command_zh": zh,
                "module": c["module"], "evidence": c["evidence"]}
        # S1
        seq += 1
        if paths:
            precond = f"NX 12.0 中文版已启动，处于包含该命令的应用模块；菜单层级：{' › '.join(paths[0])}"
            steps = [f"在菜单栏按 {' › '.join(paths[0][:-1])} 逐层展开。",
                     f"点击「{paths[0][-1]}」（命令 ID `{cid}`）。",
                     "观察是否弹出对应中文对话框/任务环境。"]
            repro = "STATIC_CHECKABLE"
        else:
            precond = "NX 12.0 中文版已启动"
            steps = [f"通过 `帮助(H) › 命令查找器(F)` 搜索「{zh}」或 ID `{cid}`。",
                     "确认命令存在于当前环境并调用。",
                     "[待实测] 记录实际菜单位置。" if c["evidence"] == "E3-UNTR" else "观察弹出的中文对话框。"]
            repro = "PENDING_GUI"
        if c.get("accelerator"):
            steps.append(f"另测快捷键 `{c['accelerator']}` 是否等效触发。")
        cases.append({**base, "case_id": f"TC-{seq:05d}", "scenario": "S1_基础调用与定位",
                      "precondition": precond, "steps": steps,
                      "expected": f"命令「{zh}」被成功调用，界面语言为简体中文，命令 ID 与目录一致。",
                      "reproducibility": repro if not c.get("accelerator") else "STATIC_CHECKABLE"})

        # S2
        seq += 1
        msg = c.get("message_zh") or ""
        cases.append({**base, "case_id": f"TC-{seq:05d}", "scenario": "S2_对话框参数探查",
                      "precondition": f"已按 S1 成功调出「{zh}」对话框；介质说明：{msg or '（无）'}",
                      "steps": [
                          f"逐项记录对话框中的中文控件名、单位、默认值、取值范围（共 __ 项）。",
                          "对每个数值控件输入边界值（最小/最大/非法值）并记录界面反馈。",
                          "取消对话框，确认未产生几何或参数副作用。",
                      ],
                      "expected": "形成该命令的参数快照表；取消后模型状态与调用前一致。",
                      "reproducibility": "PENDING_GUI"})

        # S3
        seq += 1
        cases.append({**base, "case_id": f"TC-{seq:05d}", "scenario": "S3_边界与失误处理",
                      "precondition": "无选择集 / 非法选择 / 重复执行等边界条件" + ("；注意该命令为 E3 未翻译项，先复核显示名" if c["evidence"] == "E3-UNTR" else ""),
                      "steps": [
                          "在空选择状态下调用命令，记录是否给出中文提示或禁用。",
                          "选择不兼容对象后调用，记录报错原文与错误码（若有）。",
                          "连续执行两次，记录是否可重复、是否产生重复特征。",
                          "通过撤消回退，确认可恢复。",
                      ],
                      "expected": "边界行为可解释、可恢复；报错原文与错误码被录入报错代码库。",
                      "reproducibility": "PENDING_GUI"})

    (OUT / "test_cases_all.json").write_text(
        json.dumps({"version": VER, "basis": "介质目录全量功能点",
                    "total_commands": len(cmds), "total_cases": len(cases),
                    "scenarios_per_command": 3, "cases": cases},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[OK] test_cases_all.json: {len(cases)} 用例 / {len(cmds)} 功能点")

    # 人类可读的分模块清单（索引，不重复全字段）
    L = ["# 测试用例集（全量索引）", "",
         f"> 版本：**{VER}**　|　功能点 {len(cmds)} × 场景 3 = 用例 {len(cases)} 条",
         "> 完整用例字段见 `test_cases_all.json`。",
         "> 可复现性：`STATIC_CHECKABLE`=可依介质静态核对；`PENDING_GUI`=需中文界面实测取证。", ""]
    by_mod: dict[str, dict] = {}
    for tc in cases:
        m = by_mod.setdefault(tc["module"], {"n": 0, "cmd": set()})
        m["n"] += 1
        m["cmd"].add(tc["command_id"])
    L += ["| 模块 | 功能点数 | 用例数 |", "|---|---:|---:|"]
    for mod in sorted(by_mod):
        L.append(f"| {mod} | {len(by_mod[mod]['cmd'])} | {by_mod[mod]['n']} |")
    L += ["", "## 验收维度映射", "",
          "- 基础操作维度 → 抽取各模块 S1 用例；合格线 95 分。",
          "- 复杂项目维度 → 组合多模块 S1+S2 的端到端流程；合格线 95 分。",
          "- 故障排查维度 → S3 用例 + 报错代码库；合格线 95 分。",
          "- 版本区分维度 → 版本差异对照库的核对清单；合格线 95 分。", ""]
    (OUT / "README_测试用例集.md").write_text("\n".join(L), encoding="utf-8")
    print("[OK] README_测试用例集.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
