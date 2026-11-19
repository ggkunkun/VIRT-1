# -*- coding: utf-8 -*-
"""
合并官方数据源：
1) 从简中 acad.pgp 提取命令别名（AutoCAD 2026 R25.1 chs 官方）
2) 与 CUIX 提取的命令库合并，生成统一主命令库 master_commands.json
"""
import os, re, json
from collections import defaultdict

OUT = r"D:\Virtu模型\.autocad2026_research\data"
PGP = r"C:\Users\Administrator\AppData\Roaming\Autodesk\AutoCAD 2026\R25.1\chs\Support\acad.pgp"


def extract_aliases():
    aliases = defaultdict(list)  # 真实命令 -> [别名...]
    ext_cmd_alias = {}  # 外部命令别名
    with open(PGP, "r", encoding="utf-8-sig", errors="ignore") as f:
        for line in f:
            raw = line.rstrip("\n")
            if not raw.strip() or raw.lstrip().startswith(";"):
                continue
            # 别名区：ALIAS, *COMMAND
            m = re.match(r"^\s*([^\s,]+)\s*,\s*\*([^\s,]+)", raw)
            if m:
                alias, cmd = m.group(1).strip(), m.group(2).strip().upper()
                aliases[cmd].append(alias)
                continue
            # 外部命令区：ALIAS, CMD, ... （第一段为别名、第二段为程序，无 *）
    return {k: sorted(set(v)) for k, v in aliases.items()}, ext_cmd_alias


def main():
    cuix = json.load(open(os.path.join(OUT, "cuix_extracted.json"), encoding="utf-8"))
    aliases, ext = extract_aliases()

    macros = cuix["macros"]
    accels = cuix["accelerators"]

    # 快捷键：命令 -> [快捷键]
    cmd_accel = defaultdict(list)
    for a in accels:
        if a["command"]:
            cmd_accel[a["command"]].append(a["keys"])

    # 合并
    merged = {}
    for uid, m in macros.items():
        cmd = m.get("command", "")
        if not cmd:
            continue
        rec = dict(m)
        # 别名：从 CLICommand/command _lookup
        rec["aliases"] = aliases.get(cmd, [])
        # 带连字符的 -COMMAND 变体也查一次
        if not rec["aliases"] and cmd.startswith("-"):
            rec["aliases"] = aliases.get(cmd.lstrip("-"), [])
        rec["shortcuts"] = sorted(set(cmd_accel.get(cmd, [])))
        # 命令输入格式：CLICommand 或其命令本体
        rec["input_format"] = m.get("cli_command") or cmd
        merged[uid] = rec

    # 别名表里存在但 CUIX 无对应菜单实体的命令（大量薄命令/命令行专用命令）
    covered = {r["command"] for r in merged.values()}
    alias_only = []
    for cmd, als in aliases.items():
        if cmd not in covered:
            alias_only.append({"command": cmd, "aliases": als,
                               "source": "acad.pgp（官方命令别名表）"})
    # 快捷键表里有但 CUIX 合并没覆盖的
    data = {
        "sources": [
            cuix["source"],
            PGP,
        ],
        "source_notes": [
            "AutoCAD 2026 简体中文正式版随安装官方界面定义 acad.CUIX（R25.1/chs）",
            "AutoCAD 2026 简体中文正式版官方命令别名表 acad.pgp（R25.1/chs）",
        ],
        "version_internal": "R25.1",
        "language": "zh-CN (chs)",
        "cuix_total_commands": cuix["total_with_command"],
        "alias_table_size": len(aliases),
        "merged_entities": len(merged),
        "commands": merged,
        "alias_only_commands": alias_only,
        "aliases_raw": aliases,
    }
    p = os.path.join(OUT, "master_commands.json")
    json.dump(data, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("写出", p)
    print("合并实体", len(merged), "别名表命令", len(aliases),
          "仅别名命令", len(alias_only))
    # 关键命令核验
    want = ["LINE", "CIRCLE", "COPY", "MOVE", "ARC", "DIMLINEAR", "TRIM", "EXTEND"]
    bycmd = {}
    for uid, r in merged.items():
        bycmd.setdefault(r["command"], r)
    for c in want:
        r = bycmd.get(c, {})
        print(f"{c:12} zh={r.get('name_zh',''):8} alias={r.get('aliases',[])} "
              f"shortcut={r.get('shortcuts',[])} input={r.get('input_format','')}")
    print("\nalias-only 样例:", alias_only[:8])


if __name__ == "__main__":
    main()
