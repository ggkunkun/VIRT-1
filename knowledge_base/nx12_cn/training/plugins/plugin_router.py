#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第三方外挂 Agent 路由适配层（可执行）。

给上层 Agent 提供统一接口，把「外挂能力」当作可调用的子 Agent 管理：
    list_plugins()                 -> 能力卡（有哪些外挂/多少命令/风险）
    search(query, plugin=None)     -> 双语/ID 检索，返回带命名空间的候选
    resolve(key)                   -> 精确解析 "plugin:command"
    plan_call(key, params)         -> 生成调用计划（前置检查+执行+回退+风险）
    doctor()                       -> 健康检查（路径/环境变量/版本）

异常以 PluginError(code, message, hint) 抛出，code 为稳定枚举，便于上层分支处理。

设计约束（来自介质实测，见 plugins/plugin_registry.json）：
  - 外挂命令 ID 短且跨外挂重名（271 个），必须用 "plugin:command" 复合键；
  - 外挂菜单 GBK 编码，已由注册表解码，本层不再处理编码；
  - 外挂 ACTIONS 可能是绝对路径/环境变量/模块文件/STANDARD 转发官方；
  - 外挂菜单有 VERSION 130（NX13+）混入，NX12 下不可用。
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REG = ROOT / "plugins" / "plugin_registry.json"
NX = Path(r"D:\BaiduNetdiskDownload\NX 12.0.2.9\NX12.2.9waigua\NX12.2.9\NX")

# ---------------------------------------------------------------- 异常体系
CODES = {
    "PLUGIN_NOT_INSTALLED": "外挂未安装或目录缺失",
    "PLUGIN_VERSION_INCOMPATIBLE": "外挂菜单版本与 NX 12 不匹配",
    "COMMAND_NOT_FOUND": "命令不存在于该外挂",
    "AMBIGUOUS_COMMAND": "命令在多个外挂中重名，需指定 plugin_id",
    "ACTION_PATH_BROKEN": "ACTIONS 指向的绝对路径不存在",
    "ENV_VAR_UNSET": "ACTIONS 依赖的环境变量未设置",
    "OFFICIAL_ALIAS": "该外挂项实为转发官方命令，应走内置通道",
    "PARAM_UNVERIFIED": "该命令参数未经 GUI 实测，不能保证可用",
    "REGISTRY_MISSING": "外挂注册表缺失，请先运行 build_plugin_registry.py",
}


class PluginError(Exception):
    def __init__(self, code: str, message: str, hint: str = ""):
        self.code = code
        self.message = message
        self.hint = hint
        super().__init__(f"[{code}] {message}" + (f" → {hint}" if hint else ""))


def _load() -> dict:
    if not REG.exists():
        raise PluginError("REGISTRY_MISSING", f"未找到 {REG}",
                          "先执行 python tools/build_plugin_registry.py")
    return json.loads(REG.read_text(encoding="utf-8"))


def _index(reg: dict) -> dict[str, dict]:
    idx = {}
    for p in reg["plugins"]:
        for c in p["commands"]:
            idx[c["key"]] = {**c, "plugin_id": p["plugin_id"],
                             "plugin_name": p["display_name"],
                             "vendor": p["vendor"],
                             "risk_level": p["risk"]["level"]}
    return idx


# ---------------------------------------------------------------- 能力卡
def list_plugins() -> list[dict]:
    """返回外挂能力卡（不含逐条命令，供 Agent 决策是否加载）。"""
    reg = _load()
    out = []
    for p in reg["plugins"]:
        out.append({
            "plugin_id": p["plugin_id"],
            "display_name": p["display_name"],
            "vendor": p["vendor"],
            "command_count": p["command_count"],
            "zh_commands": sum(1 for c in p["commands"] if c["label_zh"]),
            "menu_versions": p["menu_versions"],
            "version_ok_for_nx12": all(v in ("", "120") for v in p["menu_versions"]) if p["menu_versions"] else True,
            "risk_level": p["risk"]["level"],
            "risk_summary": {
                "hardcoded_paths": p["risk"]["hardcoded_paths"],
                "env_var_paths": p["risk"]["env_var_paths"],
                "duplicate_ids": p["risk"]["duplicate_id_count"],
                "menu_version_mismatch": len(p["risk"]["menu_version_mismatch"]),
                "excluded_men_files": p["excluded_men_files"],
            },
            "actions_profile": p["actions_profile"],
            "evidence": p["evidence"],
        })
    return out


# ---------------------------------------------------------------- 检索
def search(query: str, plugin: str | None = None, limit: int = 20) -> list[dict]:
    """按中文标签/英文标签/命令ID 检索，返回带复合键的候选。"""
    reg = _load()
    q = query.strip().lower()
    if not q:
        return []
    hits = []
    for p in reg["plugins"]:
        if plugin and p["plugin_id"] != plugin:
            continue
        for c in p["commands"]:
            hay = " ".join([c["label_zh"], c["label_raw"], c["command_id"], c["menu"]]).lower()
            if q in hay:
                hits.append({
                    "key": c["key"], "plugin_id": p["plugin_id"],
                    "plugin_name": p["display_name"],
                    "command_id": c["command_id"], "label": c["label_zh"] or c["label_raw"],
                    "menu": c["menu"], "action_kind": c["action_kind"],
                    "risk_level": p["risk"]["level"],
                })
            if len(hits) >= limit:
                return hits
    return hits


# ---------------------------------------------------------------- 解析
def resolve(key: str) -> dict:
    """精确解析复合键 plugin:command。"""
    reg = _load()
    idx = _index(reg)
    if key in idx:
        return idx[key]
    if ":" not in key:
        owners = sorted({v["plugin_id"] for k, v in idx.items() if v["command_id"] == key})
        if len(owners) > 1:
            raise PluginError("AMBIGUOUS_COMMAND",
                              f"命令 `{key}` 在 {len(owners)} 个外挂中重名：{owners}",
                              f"请用复合键，例如 `{owners[0]}:{key}`")
        if len(owners) == 1:
            cand = f"{owners[0]}:{key}"
            raise PluginError("COMMAND_NOT_FOUND", f"未用复合键：`{key}`",
                              f"该命令属于 {owners[0]}，正确键为 `{cand}`")
    raise PluginError("COMMAND_NOT_FOUND", f"外挂命令不存在：`{key}`",
                      "用 search() 检索，或确认命令 ID 拼写")


# ---------------------------------------------------------------- 调用计划
def plan_call(key: str, params: dict | None = None) -> dict:
    """生成可执行调用计划，并对已知风险做前置判定（不实际点击 GUI）。"""
    reg = _load()
    cmd = resolve(key)
    plugin = next(p for p in reg["plugins"] if p["plugin_id"] == cmd["plugin_id"])
    pre: list[dict] = []
    blockers: list[dict] = []
    warnings: list[dict] = []

    # 1) 版本兼容
    bad_ver = plugin["risk"]["menu_version_mismatch"]
    if bad_ver:
        blockers.append({
            "check": "menu_version",
            "code": "PLUGIN_VERSION_INCOMPATIBLE",
            "detail": f"该外挂含 VERSION!=120 的菜单（{len(bad_ver)} 个），NX12 下可能不加载",
            "files": bad_ver[:5],
        })
        pre.append({"step": "确认外挂菜单版本为 NX12（VERSION 120）", "required": True})

    # 2) 动作解析
    kind = cmd["action_kind"]
    act = cmd["actions"]
    if kind == "STANDARD_转发官方":
        warnings.append({"check": "alias", "code": "OFFICIAL_ALIAS",
                         "detail": "该外挂项转发 NX 内置命令，优先走官方通道获取参数说明"})
    elif kind == "绝对路径":
        p = Path(act)
        if not p.exists():
            blockers.append({"check": "action_path", "code": "ACTION_PATH_BROKEN",
                             "detail": f"ACTIONS 指向的文件不存在：{act}",
                             "hint": "外挂未按原安装路径部署，需修正路径或重装外挂"})
        else:
            pre.append({"step": f"确认动作文件存在：{act}", "required": True})
    elif kind == "环境变量":
        vars_ = re.findall(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?|%([A-Za-z_][A-Za-z0-9_]*)%", act)
        names = [a or b for a, b in vars_]
        unset = [n for n in names if n and n not in os.environ]
        if unset:
            blockers.append({"check": "env_var", "code": "ENV_VAR_UNSET",
                             "detail": f"未设置环境变量：{unset}", "actions": act,
                             "hint": "在 NX 启动前设置环境变量，或改用绝对路径配置"})
        else:
            pre.append({"step": f"环境变量已就绪：{names}", "required": True})

    # 3) 参数约定
    param_contract = {
        "accepted": params or {},
        "schema": {
            "inputs": "对话框字段的语义键值（需 GUI 实测确认字段名后才可填）",
            "selection": "预选对象（外挂多为交互式 GRIP，选中状态依赖 GUI）",
            "dialog_mode": "gui（默认，外挂基本只支持交互）| batch（若有 .utd/.dlg 支持）",
        },
        "verified": False,
        "note": "外挂 .men 不含参数默认值，参数必须经 NX 12 中文对话框取证后才能承诺可用",
    }
    if params:
        warnings.append({"check": "param", "code": "PARAM_UNVERIFIED",
                         "detail": "传入了参数，但该命令参数未实测，执行结果不可保证"})

    return {
        "key": cmd["key"],
        "plugin_id": plugin["plugin_id"],
        "plugin_name": plugin["display_name"],
        "command_id": cmd["command_id"],
        "label": cmd["label_zh"] or cmd["label_raw"],
        "menus": cmd.get("menus") or ([cmd["menu"]] if cmd.get("menu") else []),
        "menu_path": f"{plugin['display_name']} › " + " / ".join(
            cmd.get("menus") or ([cmd["menu"]] if cmd.get("menu") else ["（无菜单名）"])),
        "men_file": cmd["men_file"],
        "action": act,
        "action_kind": kind,
        "risk_level": plugin["risk"]["level"],
        "preconditions": pre,
        "blockers": blockers,
        "warnings": warnings,
        "param_contract": param_contract,
        "callable": not blockers,
        "execution_channel": "NX GUI 交互（外挂无官方 COM/批处理接口）",
        "rollback": "NX 撤消（Ctrl+Z）；外挂写文件类操作需手动备份目标文件",
        "evidence": "E1-MEDIA（菜单/动作来自介质） + 参数未实测",
    }


# ---------------------------------------------------------------- 健康检查
def doctor() -> dict:
    """扫描全部外挂：路径可用性、环境变量、版本兼容。"""
    reg = _load()
    rows = []
    for p in reg["plugins"]:
        broken, env_missing = [], []
        for c in p["commands"]:
            if c["action_kind"] == "绝对路径":
                if not Path(c["actions"]).exists():
                    broken.append(c["actions"])
            elif c["action_kind"] == "环境变量":
                names = [a or b for a, b in re.findall(
                    r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?|%([A-Za-z_][A-Za-z0-9_]*)%", c["actions"])]
                miss = [n for n in names if n and n not in os.environ]
                if miss:
                    env_missing.append({"command": c["command_id"], "missing": miss})
        rows.append({
            "plugin_id": p["plugin_id"],
            "display_name": p["display_name"],
            "installed": (NX / p["root"]).exists(),
            "version_ok": all(v in ("", "120") for v in p["menu_versions"]) if p["menu_versions"] else True,
            "hardcoded_total": p["risk"]["hardcoded_paths"],
            "hardcoded_broken": len(broken),
            "broken_samples": broken[:3],
            "env_missing_count": len(env_missing),
            "env_missing_samples": env_missing[:3],
            "risk_level": p["risk"]["level"],
        })
    return {
        "nx_root": str(NX),
        "plugins": rows,
        "summary": {
            "total": len(rows),
            "installed": sum(1 for r in rows if r["installed"]),
            "version_ok": sum(1 for r in rows if r["version_ok"]),
            "with_broken_paths": sum(1 for r in rows if r["hardcoded_broken"]),
            "with_missing_env": sum(1 for r in rows if r["env_missing_count"]),
        },
    }


# ---------------------------------------------------------------- CLI
def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 0
    cmd = sys.argv[1]
    try:
        if cmd == "list":
            for p in list_plugins():
                v = "OK" if p["version_ok_for_nx12"] else "VER-MISMATCH"
                print(f"{p['plugin_id']:12s} {p['display_name']:16s} cmd={p['command_count']:4d} "
                      f"zh={p['zh_commands']:4d} risk={p['risk_level']:6s} {v}")
        elif cmd == "search":
            q = sys.argv[2] if len(sys.argv) > 2 else ""
            for h in search(q):
                print(f"{h['key']:28s} {h['label'][:24]:24s} {h['action_kind']:14s} {h['risk_level']}")
        elif cmd == "plan":
            print(json.dumps(plan_call(sys.argv[2]), ensure_ascii=False, indent=1))
        elif cmd == "doctor":
            d = doctor()
            print(json.dumps(d["summary"], ensure_ascii=False, indent=1))
            for r in d["plugins"]:
                print(f"{r['plugin_id']:12s} inst={'Y' if r['installed'] else 'N'} "
                      f"ver={'Y' if r['version_ok'] else 'N'} "
                      f"broken={r['hardcoded_broken']}/{r['hardcoded_total']} "
                      f"env_miss={r['env_missing_count']}")
        else:
            print(f"未知子命令: {cmd}")
            return 2
    except PluginError as e:
        print(f"ERROR {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
