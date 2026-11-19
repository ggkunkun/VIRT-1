#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NX 12.0 简体中文命令目录 —— 全量补全提取器（training 命名基准 v2）

与 extract_nx12_cn_catalog.py 的区别：
  - v1 只解析 17 个指定 .men，加工/仿真/布线等模块命令漏采；
  - v2 解析介质内全部 *.men（128 个）+ 全部 definitions_*.btn + 全部 simpl_chinese 翻译表，
    把命令目录补全，并为每条命令记录来源菜单文件与证据等级。

证据等级（写入每条命令 evidence 字段）：
  E1-MEDIA  直接来自本机 NX 12.0.2.9 安装介质的 .btn/.men + 官方中文翻译表（可点名源文件与行）
  E2-MENU   仅出现在菜单定义中、无独立 .btn 定义，但菜单项有官方中文翻译
  E3-UNTR   菜单中出现但无中文翻译（字符串 ID 直出），需 GUI 复核显示名

用法：
  python extract_full_catalog_v2.py [--nx-root PATH] [--out PATH]
"""
from __future__ import annotations

import argparse, csv, hashlib, json, re, sys
from datetime import datetime
from pathlib import Path

DEFAULT_NX = Path(r"D:\BaiduNetdiskDownload\NX 12.0.2.9\NX12.2.9waigua\NX12.2.9\NX")

PROP_KEYS = {
    "LABEL", "TOOLBAR_LABEL", "MESSAGE", "SYNONYMS", "ACCELERATOR",
    "HINT", "ACTIONS", "BITMAP", "HELP", "RIBBON_LABEL", "POPUP_LABEL",
}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def load_translations(loc_dir: Path) -> dict[tuple[str, str], str]:
    """键=(源文件名小写, 字符串ID) → 中文值。仅接受含中文的值。"""
    table: dict[tuple[str, str], str] = {}
    for fp in sorted(loc_dir.glob("*_simpl_chinese.txt")):
        try:
            with fp.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
                for line in f:
                    s = line.strip()
                    if not s or s.startswith("#"):
                        continue
                    try:
                        parts = next(csv.reader([s], delimiter=" ", quotechar='"',
                                                skipinitialspace=True, strict=False))
                    except (csv.Error, StopIteration):
                        continue
                    if len(parts) < 4:
                        continue
                    src, sid, _en, zh = parts[0].strip(), parts[1].strip(), parts[2], parts[3]
                    if not src or not sid or not zh:
                        continue
                    if not re.search(r"[\u4e00-\u9fff]", zh):
                        continue
                    key = (src.lower(), sid)
                    table.setdefault(key, zh)
        except OSError:
            continue
    return table


def strip_mn(text: str) -> str:
    return text.replace("&", "").strip()


def parse_btn(path: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    cur = None
    with path.open("r", encoding="ascii", errors="replace") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("!"):
                continue
            m = re.match(r"^(BUTTON|TOGGLE|CASCADE_BUTTON)\s+([A-Za-z0-9_]+)\s*$", line)
            if m:
                cur = out.setdefault(m.group(2), {"props": {}, "lines": []})
                continue
            m = re.match(r"^([A-Z_]+)\s+(.*)$", line)
            if m and cur is not None and m.group(1) in PROP_KEYS:
                cur["props"].setdefault(m.group(1), m.group(2).strip())
                cur["lines"].append(line)
    return out


def parse_men(path: Path) -> list[tuple[str, str, str]]:
    """返回 [(item_id, item_type, menu_id)]，从 MENU/CREATE/TOP 块中提取。"""
    items: list[tuple[str, str, str]] = []
    cur_menu = "UG_GATEWAY_MAIN_MENUBAR"
    with path.open("r", encoding="ascii", errors="replace") as f:
        for raw in f:
            s = raw.strip()
            if not s or s.startswith("!") or s.startswith("VERSION"):
                continue
            if s == "TOP_MENU" or s.startswith("CREATE ") and "MENUBAR" in s:
                cur_menu = "UG_GATEWAY_MAIN_MENUBAR"
                continue
            if s.startswith("MENU "):
                cur_menu = s.split(None, 1)[1].strip()
                continue
            if s.startswith(("END_OF_",)):
                continue
            m = re.match(r"^(BUTTON/HIDE|BUTTON|TOGGLE|CASCADE_BUTTON)\s+([A-Za-z0-9_]+)\s*$", s)
            if m:
                typ = "CASCADE" if m.group(1) == "CASCADE_BUTTON" else "BUTTON"
                items.append((m.group(2), typ, cur_menu))
    return items


def module_of(cid: str, zh: str, men: str) -> str:
    """按 ID 前缀 + 来源菜单文件映射到用户要求的模块体系。"""
    c, m = cid.upper(), men.lower()
    if c.startswith(("UG_CAM_", "BATCH_PROCESS")) or "mach/" in m or "cam.men" in m:
        return "08_加工制造"
    if c.startswith(("UG_SFEM_", "NX_SIMULATION", "UG_SIMULATION", "UG_MOTION")) or "simcenter" in m or "sfem" in m:
        return "09_仿真分析"
    if c.startswith(("UG_LAYER_", "UG_ARRANGE_", "UG_VIEW_SEE_THRU_STYLE_LAYERS")):
        return "13_图层与显示"
    if c.startswith("UG_PREFERENCES") or c.startswith("UG_TOOLS_CUSTOMIZE") or c.startswith("UI_KRU") or "custom" in m:
        return "14_定制与首选项"
    if c.startswith("UG_SKETCH") or c.startswith("UG_DIRECT_SKETCH") or "sketch" in m:
        return "01_草图绘制"
    if c.startswith(("UG_ADM_", "UG_MODELING_REPLACE", "UG_MODELING_SYNCHRONOUS")):
        return "06_同步建模"
    if ("SMD" in c or "SHEETMTL" in c or "sheetmetal" in m) and not c.startswith("UG_DRAFT"):
        return "05_钣金设计"
    if c.startswith("UG_MODELING_FF_") or "SURFACE" in c or c.startswith(("UG_SUBDIV_", "UG_STYLER_")) or "freeform" in m:
        return "04_曲面设计"
    if c.startswith("UG_MODELING_") or c.startswith(("UG_CURVE_", "UG_ASSOCIATIVE_", "UG_UDF_", "UG_KBE_")):
        return "02_零件建模"
    if c.startswith(("UG_ASSY_", "UG_NXPOS_", "UG_ANT_", "UG_PARTNAV_", "UGMGR_")) or "assembl" in m:
        return "03_装配设计"
    if c.startswith(("UG_DRAFT_", "UG_PMI_", "UG_TABLE_", "UG_TITLE_BLOCK")) or "draft" in m:
        return "07_工程图与PMI"
    if c.startswith(("MW_", "UGMOLD_", "PDW_", "EDW_", "TOOLING_")) or "mold" in m or "stamping" in m:
        return "10_模具设计"
    if c.startswith(("UG_FILE_", "UG_EDIT_", "UG_INFO_", "UG_HELP_", "UG_VIEW_", "UG_SEL_", "UG_WINDOW_", "UG_LAYOUT_", "UG_NXLAYOUT_", "UG_TOOLBOX_", "UG_MACRO_", "UG_JOURNAL_", "UG_EXPRESSION_", "UG_WCS_", "UG_CHECKER_", "UG_DIALOG_")):
        return "12_文件编辑视图信息"
    if "routing" in m or "pipe" in m or "harness" in m or "管线" in zh or "布线" in zh:
        return "11_管线与线路"
    return "15_其他与第三方外挂"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nx-root", default=str(DEFAULT_NX))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    root = Path(args.nx_root)
    if not (root / "NXBIN" / "ugraf.exe").exists():
        print(f"[FAIL] 非 NX 根目录: {root}")
        return 1
    out_dir = Path(args.out) if args.out else Path(__file__).resolve().parent.parent / "catalog"
    out_dir.mkdir(parents=True, exist_ok=True)

    loc = root / "LOCALIZATION" / "translations" / "simpl_chinese"
    trans = load_translations(loc)
    print(f"[OK] 翻译条目 {len(trans)}")

    btn_files = sorted(set(root.rglob("definitions_*.btn")))
    men_files = sorted(set(root.rglob("*.men")))
    print(f"[OK] btn={len(btn_files)}  men={len(men_files)}")

    commands: dict[str, dict] = {}

    # 1) .btn 定义（主定义优先）
    for bp in btn_files:
        rp = rel(bp, root)
        for cid, rec in parse_btn(bp).items():
            if cid in commands and "UGII/menus" in commands[cid]["source"]:
                continue
            commands[cid] = {
                "id": cid,
                "source_btn": rp,
                "props": rec["props"],
                "men_files": [],
                "menus": [],
                "evidence": "E1-MEDIA",
            }

    # 2) .men 菜单（全量）
    for mp in men_files:
        rp = rel(mp, root)
        men_base = mp.name
        try:
            items = parse_men(mp)
        except OSError:
            continue
        for cid, typ, menu_id in items:
            rec = commands.setdefault(cid, {
                "id": cid, "source_btn": "", "props": {},
                "men_files": [], "menus": [], "evidence": "E2-MENU",
            })
            if rp not in rec["men_files"]:
                rec["men_files"].append(rp)
            if typ == "BUTTON" and menu_id not in rec["menus"]:
                rec["menus"].append(menu_id)

    # 3) 官方中文名：优先 btn 文件对应翻译表，其次任一 men 文件翻译表，最后全局同 SID
    global_by_sid: dict[str, str] = {}
    for (_f, sid), zh in trans.items():
        global_by_sid.setdefault(sid, zh)

    out_cmds: dict[str, dict] = {}
    for cid, rec in commands.items():
        props = rec["props"]
        zh, zh_menu, zh_ribbon, zh_msg = "", "", "", ""
        btn_name = Path(rec["source_btn"]).name if rec["source_btn"] else ""
        sources = ([btn_name] if btn_name else []) + [Path(f).name for f in rec["men_files"]]
        for src in sources:
            if not zh:
                zh = trans.get((src.lower(), cid + "_TOOLBAR_LABEL"), "") or trans.get((src.lower(), cid + "_LABEL"), "")
            if not zh_menu:
                zh_menu = trans.get((src.lower(), cid + "_LABEL"), "")
            if not zh_ribbon:
                zh_ribbon = trans.get((src.lower(), cid + "_RIBBON_LABEL"), "")
            if not zh_msg:
                zh_msg = trans.get((src.lower(), cid + "_MESSAGE"), "")
        if not zh:
            zh = global_by_sid.get(cid + "_TOOLBAR_LABEL", "") or global_by_sid.get(cid + "_LABEL", "")
        if not zh_menu:
            zh_menu = global_by_sid.get(cid + "_LABEL", "")
        if not zh_msg:
            zh_msg = global_by_sid.get(cid + "_MESSAGE", "")

        evidence = rec["evidence"]
        if evidence == "E2-MENU" and not zh:
            evidence = "E3-UNTR"

        out_cmds[cid] = {
            "id": cid,
            "zh": strip_mn(zh or zh_menu),
            "zh_menu": strip_mn(zh_menu),
            "zh_ribbon": strip_mn(zh_ribbon),
            "en": strip_mn(props.get("LABEL", "")),
            "message_zh": zh_msg,
            "accelerator": props.get("ACCELERATOR", ""),
            "synonyms": props.get("SYNONYMS", ""),
            "hint": props.get("HINT", ""),
            "source_btn": rec["source_btn"],
            "men_files": rec["men_files"],
            "menus": rec["menus"],
            "module": module_of(cid, zh, rec["men_files"][0] if rec["men_files"] else ""),
            "evidence": evidence,
        }

    stats = {
        "nx_root": str(root),
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "btn_files": len(btn_files),
        "men_files": len(men_files),
        "translation_entries": len(trans),
        "commands": len(out_cmds),
        "commands_with_zh": sum(1 for v in out_cmds.values() if v["zh"]),
        "commands_with_accel": sum(1 for v in out_cmds.values() if v["accelerator"]),
        "commands_e1": sum(1 for v in out_cmds.values() if v["evidence"] == "E1-MEDIA"),
        "commands_e2": sum(1 for v in out_cmds.values() if v["evidence"] == "E2-MENU"),
        "commands_e3": sum(1 for v in out_cmds.values() if v["evidence"] == "E3-UNTR"),
    }
    key_sources = {
        rel(p, root): sha256_of(p) for p in [
            root / "NXBIN" / "ugraf.exe",
            root / "UGII" / "menus" / "definitions_main.btn",
            root / "UGII" / "menus" / "ug_main.men",
            root / "MACH" / "application" / "ug_cam.men",
            root / "LOCALIZATION" / "translations" / "simpl_chinese" /
            "definitions_main_btn_simpl_chinese.txt",
        ] if p.exists()
    }
    catalog = {
        "schema": "nx12-cn-full-catalog-v2",
        "nx_version": "NX 12.0（12.0.2.9 介质，含第三方外挂菜单）",
        "ui_language": "simpl_chinese（简体中文）",
        "basis": "measured（直接解析本机安装介质）",
        "stats": stats,
        "key_sources_sha256": key_sources,
        "commands": out_cmds,
    }
    (out_dir / "nx12_cn_full_catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=1), encoding="utf-8")
    print("[OK]", json.dumps(stats, ensure_ascii=False, indent=1))
    print("[OK] ->", out_dir / "nx12_cn_full_catalog.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
