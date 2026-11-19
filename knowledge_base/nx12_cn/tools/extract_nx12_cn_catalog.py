#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NX 12.0 简体中文界面命令目录抽取器（唯一命名基准）。

数据源（全部来自本机已安装 NX 12.0 介质，不依赖模型记忆）：
  1. <NX>/UGII/menus/*.men 及其它应用目录下的 *.men —— 菜单层级与级联关系
  2. <NX>/**/definitions_*.btn —— 命令 ID、英文标签、快捷键、同义词
  3. <NX>/LOCALIZATION/translations/simpl_chinese/*_simpl_chinese.txt
     —— 官方中文对照表：("源文件" "字符串ID" "English" "中文" "")

输出：
  catalog/nx12_cn_commands.json   全量命令目录（含中文名、菜单路径、快捷键）
  catalog/extraction_evidence.json 抽取统计与源文件 sha256（测量宪法 §8 可归因）

用法：
  python extract_nx12_cn_catalog.py                # 自动发现 NX 安装并抽取
  python extract_nx12_cn_catalog.py --nx-root <路径>
  python extract_nx12_cn_catalog.py --audit <markdown目录>   # 审计文档中的 [CMD:ID] 引用
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------- NX 自动发现

def discover_nx_root(explicit: str | None = None) -> Path:
    """按 注册表 → 环境变量 → 已知容器目录 动态发现 NX 根目录。"""
    if explicit:
        p = Path(explicit)
        if (p / "NXBIN" / "ugraf.exe").exists():
            return p
        raise SystemExit(f"[FAIL] 指定路径不是 NX 根目录（缺 NXBIN\\ugraf.exe）：{p}")

    candidates: list[Path] = []

    # 1) 注册表（Windows）
    try:
        import winreg  # type: ignore

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Siemens\NX\CurrentVersion") as k:
            base, _ = winreg.QueryValueEx(k, "UGII_BASE_DIR")
            candidates.append(Path(base))
    except Exception:
        pass

    # 2) 环境变量
    for var in ("UGII_BASE_DIR", "UGII_ROOT_DIR"):
        v = os.environ.get(var)
        if v:
            p = Path(v)
            candidates.append(p.parent if var == "UGII_ROOT_DIR" else p)

    # 3) 已知容器目录（仅做一层，避免全盘扫描）
    for root in ("D:/BaiduNetdiskDownload", "E:/BaiduNetdiskDownload",
                 "C:/Program Files/Siemens", "D:/Program Files/Siemens",
                 "E:/Siemens", "D:/Siemens"):
        rp = Path(root)
        if not rp.is_dir():
            continue
        for depth1 in rp.glob("**/ugraf.exe"):
            candidates.append(depth1.parent.parent)

    for c in candidates:
        if (c / "NXBIN" / "ugraf.exe").exists() and (c / "UGII" / "menus").is_dir():
            return c
    raise SystemExit("[FAIL] 未发现 NX 12.0 安装（NXBIN\\ugraf.exe + UGII\\menus）。"
                     "请用 --nx-root 指定。")


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


# ---------------------------------------------------------------- 翻译对照表

def load_translations(loc_dir: Path) -> dict[tuple[str, str], str]:
    """读取官方中文对照表。键 = (源文件小写, 字符串ID)，值 = 中文。

    行格式（字段以空格分隔、字段值用双引号包裹）：
      "ug_main.men" "UG_FILE_NEW_LABEL" "&New..." "新建(&N)..." ""
    """
    table: dict[tuple[str, str], str] = {}
    files = sorted(loc_dir.glob("*_simpl_chinese.txt"))
    parsed = 0
    for fp in files:
        try:
            with fp.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    try:
                        parts = next(csv.reader([line], delimiter=" ", quotechar='"',
                                                skipinitialspace=True, strict=False))
                    except (csv.Error, StopIteration):
                        continue
                    if len(parts) < 4:
                        continue
                    src, sid, _en, zh = parts[0].strip(), parts[1].strip(), parts[2], parts[3]
                    if not src or not sid:
                        continue
                    key = (src.lower(), sid)
                    if key not in table and zh:
                        table[key] = zh
                    parsed += 1
        except OSError:
            continue
    return table


def strip_mnemonic(text: str) -> str:
    """去掉 Windows 助记符 &，并把中文全角括号内的 &X 规整为 (X)。"""
    return text.replace("&", "").strip()


# ---------------------------------------------------------------- .btn 解析

PROP_KEYS = {
    "LABEL", "TOOLBAR_LABEL", "MESSAGE", "SYNONYMS", "ACCELERATOR",
    "HINT", "ACTIONS", "BITMAP", "HELP", "RIBBON_LABEL", "POPUP_LABEL",
}

def parse_btn(path: Path) -> dict[str, dict]:
    commands: dict[str, dict] = {}
    cur: dict | None = None
    with path.open("r", encoding="ascii", errors="replace") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("!"):
                continue
            m = re.match(r"^(BUTTON|TOGGLE|CASCADE_BUTTON|TOGGLE_BUTTON|APPLICATION_BUTTON|BUTTON/HIDE)\s+([A-Za-z0-9_]+)\s*$", line)
            if m:
                cid = m.group(2)
                cur = commands.setdefault(cid, {"id": cid, "props": {}})
                continue
            m = re.match(r"^([A-Z_]+)\s+(.*)$", line)
            if m and cur is not None and m.group(1) in PROP_KEYS:
                cur["props"].setdefault(m.group(1), m.group(2).strip())
    return commands


# ---------------------------------------------------------------- .men 解析

class MenuModel:
    def __init__(self) -> None:
        self.menus: dict[str, dict] = {}          # menu_id -> {file, items:[(type,id)], labels, msgs}
        self.after: list[tuple[str, str, list[tuple[str, str]]]] = []   # (men_file, anchor, items)
        self.before: list[tuple[str, str, list[tuple[str, str]]]] = []  # (men_file, anchor, items)
        self.edit: list[tuple[str, str, list[tuple[str, str]]]] = []    # (men_file, menu_id, items)
        self.command_paths: dict[str, list[list[str]]] = {}             # 命令 → 菜单路径
        self.command_labels: dict[str, tuple[str, str]] = {}            # 命令 → (中文名, 源文件)

    def touch(self, menu_id: str, men_file: str) -> dict:
        m = self.menus.setdefault(menu_id, {"file": men_file, "items": [], "labels": {}, "msgs": {}})
        if not m.get("file"):
            m["file"] = men_file
        return m

    def parse(self, path: Path) -> None:
        men_file = path.name.lower()
        mode = None          # menu | top | edit | after
        target = None
        items: list[tuple[str, str]] = []
        labels: dict[str, str] = {}
        msgs: dict[str, str] = {}
        last_item: str | None = None

        def flush() -> None:
            nonlocal mode, target, items, labels, msgs, last_item
            if mode in ("menu", "top") and target:
                m = self.touch(target, men_file)
                m["items"].extend(items)
                m["labels"].update(labels)
                m["msgs"].update(msgs)
            elif mode == "edit" and target:
                self.edit.append((men_file, target, list(items)))
            elif mode == "after" and target:
                self.after.append((men_file, target, list(items)))
            elif mode == "before" and target:
                self.before.append((men_file, target, list(items)))
            mode, target, items, labels, msgs, last_item = None, None, [], {}, {}, None

        with path.open("r", encoding="ascii", errors="replace") as f:
            for raw in f:
                line = raw.rstrip("\n")
                s = line.strip()
                if not s or s.startswith("!") or s.startswith("VERSION"):
                    continue
                if s == "TOP_MENU":
                    mode, target = "top", "UG_GATEWAY_MAIN_MENUBAR"
                    continue
                if s.startswith("CREATE ") and "MENUBAR" in s:
                    flush()
                    mode, target = "menu", s.split(None, 1)[1].strip()
                    continue
                if s.startswith("MENU "):
                    flush()
                    mode, target = "menu", s.split(None, 1)[1].strip()
                    continue
                if s.startswith("EDIT "):
                    flush()
                    mode, target = "edit", s.split(None, 1)[1].strip()
                    continue
                if s.startswith("AFTER "):
                    flush()
                    mode, target = "after", s.split(None, 1)[1].strip()
                    continue
                if s.startswith("BEFORE "):
                    flush()
                    mode, target = "before", s.split(None, 1)[1].strip()
                    continue
                if s.startswith(("END_OF_MENU", "END_OF_TOP_MENU", "END_OF_EDIT",
                                 "END_OF_AFTER", "END_OF_BEFORE")):
                    flush()
                    continue
                m = re.match(r"^(BUTTON/HIDE|BUTTON|TOGGLE|TOGGLE_BUTTON|APPLICATION_BUTTON|CASCADE_BUTTON)\s+([A-Za-z0-9_]+)\s*$", s)
                if m:
                    typ = "CASCADE" if m.group(1) == "CASCADE_BUTTON" else "BUTTON"
                    item_id = m.group(2)
                    items.append((typ, item_id))
                    last_item = item_id
                    continue
                m = re.match(r"^LABEL\s+(.*)$", s)
                if m and last_item:
                    labels[last_item] = m.group(1).strip()
                    continue
                m = re.match(r"^MESSAGE\s+(.*)$", s)
                if m and last_item:
                    msgs[last_item] = m.group(1).strip()
                    continue
        flush()


# ---------------------------------------------------------------- 目录构建

def build_catalog(nx_root: Path) -> tuple[dict, dict]:
    loc_dir = nx_root / "LOCALIZATION" / "translations" / "simpl_chinese"
    if not loc_dir.is_dir():
        raise SystemExit(f"[FAIL] 缺简体中文语言包目录：{loc_dir}")
    translations = load_translations(loc_dir)

    # .btn：全仓扫描（主定义 + 各应用模块定义）
    btn_files = sorted(set(nx_root.rglob("definitions_*.btn")))
    commands: dict[str, dict] = {}
    for bp in btn_files:
        for cid, cmd in parse_btn(bp).items():
            if cid in commands:
                # 主定义优先：UGII/menus/definitions_main.btn 排在最前
                if "UGII/menus" not in str(bp).replace("\\", "/"):
                    continue
            commands[cid] = {
                "id": cid,
                "props": cmd["props"],
                "btn_file": rel(bp, nx_root),
            }

    # .men：按“应用环境”分别建模，避免任务环境（如草图/制图 TE）把 UG_FILE 重定义成“任务”
    MENU_MODELS: dict[str, list[str]] = {
        "建模": [
            "UGII/menus/ug_main.men", "UGII/menus/ug_modeling.men",
            "UGII/menus/ug_sbsm.men", "UGII/menus/ug_smd.men",
            "UGII/menus/ug_shapestudio.men", "UGII/menus/ug_styler.men",
            "UGII/menus/ug_styler1.men", "UGII/menus/ug_modeling_sketch_tools.men",
            "UGII/menus/ug_synchronous.men", "UGII/menus/ug_direct_sketch.men",
        ],
        "工程图": [
            "UGII/menus/ug_main.men", "DRAFTING/application/ug_drafting.men",
            "DRAFTING/application/ug_drafting_sketch_tools.men",
        ],
        "加工": [
            "UGII/menus/ug_main.men", "MACH/application/ug_cam.men",
        ],
        "注塑模向导": [
            "UGII/menus/ug_main.men", "MOLDWIZARD/startup/nx_moldwizard.men",
        ],
        "草图环境": [
            "UGII/menus/ug_sketcher.men", "UGII/menus/ug_modeling_sketch_tools.men",
        ],
    }
    men_files = [nx_root / p for ps in MENU_MODELS.values() for p in ps if (nx_root / p).is_file()]

    def tr(file_name: str, sid: str) -> str | None:
        return translations.get((file_name.lower(), sid))

    def label_of(item_id: str, typ: str, menu_file: str, literal: str | None,
                 mm: "MenuModel") -> str:
        for suffix in (("_LABEL", "_TOOLBAR_LABEL") if typ == "BUTTON" else ("_LABEL",)):
            v = tr(menu_file, item_id + suffix)
            if v:
                return strip_mnemonic(v)
        # 全局兜底：仅接受含中文的条目，避免回落成英文
        for (_f, sid), v in translations.items():
            if sid in (item_id + "_LABEL", item_id + "_TOOLBAR_LABEL") and re.search(r"[\u4e00-\u9fff]", v):
                return strip_mnemonic(v)
        if literal and not literal.isupper():
            return strip_mnemonic(literal)
        return ""

    def build_model(rel_paths: list[str]) -> "MenuModel":
        mm = MenuModel()
        for rp in rel_paths:
            mp = nx_root / rp
            if mp.is_file():
                try:
                    mm.parse(mp)
                except OSError:
                    continue
        # 合并 EDIT / AFTER / BEFORE
        for _f, menu_id, items in mm.edit:
            mm.touch(menu_id, _f)["items"].extend(items)

        def insert_around(records, offset: int) -> None:
            for _f, anchor, items in records:
                placed = False
                for m in mm.menus.values():
                    ids = [i for _, i in m["items"]]
                    if anchor in ids:
                        pos = ids.index(anchor) + offset
                        m["items"][pos:pos] = items
                        placed = True
                        break
                if not placed:
                    mm.touch("UG_GATEWAY_MAIN_MENUBAR", _f)["items"].extend(items)

        insert_around(mm.after, 1)
        insert_around(mm.before, 0)

        # 去重
        for m in mm.menus.values():
            seen_items: set[tuple[str, str]] = set()
            uniq: list[tuple[str, str]] = []
            for it in m["items"]:
                if it not in seen_items:
                    seen_items.add(it)
                    uniq.append(it)
            m["items"] = uniq

        # 父菜单：BFS 取最近父级
        ROOT = "UG_GATEWAY_MAIN_MENUBAR"
        depth: dict[str, int] = {ROOT: 0}
        parent: dict[str, str] = {}
        frontier = [ROOT]
        while frontier:
            nxt: list[str] = []
            for cur in frontier:
                m = mm.menus.get(cur)
                if not m:
                    continue
                for typ, item_id in m["items"]:
                    if typ == "CASCADE" and item_id in mm.menus and item_id not in depth:
                        depth[item_id] = depth[cur] + 1
                        parent[item_id] = cur
                        nxt.append(item_id)
            frontier = nxt
        for menu_id, m in mm.menus.items():
            for typ, item_id in m["items"]:
                if typ == "CASCADE" and item_id in mm.menus and item_id not in parent:
                    parent[item_id] = menu_id

        def literal_for(item_id: str) -> str | None:
            for m in mm.menus.values():
                if item_id in m["labels"]:
                    return m["labels"][item_id]
            return None

        def menu_path(menu_id: str) -> list[str]:
            chain: list[str] = []
            seen: set[str] = set()
            cur = menu_id
            while cur and cur not in seen:
                seen.add(cur)
                info = mm.menus.get(cur)
                if not info:
                    break
                cascade_label = label_of(cur, "CASCADE", info["file"], literal_for(cur), mm)
                chain.append(cascade_label or cur)
                cur = parent.get(cur, "")
            chain.reverse()
            if chain and chain[0] in ("UG_GATEWAY_MAIN_MENUBAR", "MAIN_MENUBAR"):
                chain = chain[1:]
            return chain

        for menu_id, m in mm.menus.items():
            base = menu_path(menu_id)
            for typ, item_id in m["items"]:
                if typ == "BUTTON":
                    lab = label_of(item_id, "BUTTON", m["file"], None, mm)
                    if lab:
                        p = base + [lab]
                        mm.command_paths.setdefault(item_id, [])
                        mm.command_labels.setdefault(item_id, (lab, m["file"]))
                        if p not in mm.command_paths[item_id]:
                            mm.command_paths[item_id].append(p)
        return mm

    model_objs = {name: build_model(paths) for name, paths in MENU_MODELS.items()}

    # 仅存在于菜单、未在 definitions_*.btn 中登记的命令（如 CAM 创建工序/后处理、制图视图）
    for name, mm in model_objs.items():
        for cid, (lab, src) in mm.command_labels.items():
            if cid not in commands:
                commands[cid] = {"id": cid, "props": {}, "btn_file": src}

    # 命令 → 菜单路径（按模型优先级收集，去重，最多保留 6 条）
    menu_paths: dict[str, list[list[str]]] = {}
    for name, mm in model_objs.items():
        for cid, paths in mm.command_paths.items():
            bucket = menu_paths.setdefault(cid, [])
            for p in paths:
                if p not in bucket and len(bucket) < 6:
                    bucket.append(p)

    # 组装命令条目
    menu_label_fallback: dict[str, str] = {}
    for mm in model_objs.values():
        for cid, (lab, _src) in mm.command_labels.items():
            menu_label_fallback.setdefault(cid, lab)

    out_cmds: dict[str, dict] = {}
    for cid, rec in commands.items():
        props = rec["props"]
        btn_file = Path(rec["btn_file"]).name
        zh_label = (tr(btn_file, cid + "_LABEL") or tr(btn_file, cid + "_TOOLBAR_LABEL")
                    or menu_label_fallback.get(cid, "") or "")
        zh_toolbar = tr(btn_file, cid + "_TOOLBAR_LABEL") or zh_label
        zh_msg = tr(btn_file, cid + "_MESSAGE") or ""
        zh_ribbon = tr(btn_file, cid + "_RIBBON_LABEL") or ""
        en_label = props.get("LABEL", "")
        out_cmds[cid] = {
            "id": cid,
            "zh": strip_mnemonic(zh_toolbar or zh_label),
            "zh_menu": strip_mnemonic(zh_label),
            "zh_ribbon": strip_mnemonic(zh_ribbon),
            "en": en_label,
            "message_zh": zh_msg,
            "accelerator": props.get("ACCELERATOR", ""),
            "synonyms": props.get("SYNONYMS", ""),
            "source": rec["btn_file"],
            "menu_paths": menu_paths.get(cid, []),
        }

    # 功能区选项卡名（NX_RBN_TAB_*），来自官方对照表
    ribbon_tabs: dict[str, str] = {}
    for (_f, sid), zh in translations.items():
        if sid.startswith("NX_RBN_TAB_") and sid.endswith("_LABEL"):
            tab = zh.replace("&", "").strip()
            if tab and tab not in ribbon_tabs.values():
                ribbon_tabs[sid] = tab

    stats = {
        "nx_root": str(nx_root),
        "translation_entries": len(translations),
        "btn_files": len(btn_files),
        "men_files": len(men_files),
        "commands": len(out_cmds),
        "commands_with_zh": sum(1 for v in out_cmds.values() if v["zh"]),
        "commands_with_accel": sum(1 for v in out_cmds.values() if v["accelerator"]),
        "commands_with_menu_path": sum(1 for v in out_cmds.values() if v["menu_paths"]),
        "menus": sum(len(m.menus) for m in model_objs.values()),
        "ribbon_tabs": len(ribbon_tabs),
    }

    evidence = {
        "nx_root": str(nx_root),
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "stats": stats,
        "key_sources": {
            rel(p, nx_root): sha256_of(p)
            for p in [
                nx_root / "NXBIN" / "ugraf.exe",
                nx_root / "UGII" / "menus" / "definitions_main.btn",
                nx_root / "UGII" / "menus" / "ug_main.men",
                nx_root / "UGII" / "menus" / "ug_modeling.men",
                nx_root / "UGII" / "menus" / "ug_sketcher.men",
                nx_root / "UGII" / "menus" / "ug_assemblies.men",
                nx_root / "UGII" / "menus" / "ug_drafting.men",
                nx_root / "LOCALIZATION" / "translations" / "simpl_chinese" /
                "definitions_main_btn_simpl_chinese.txt",
            ] if p.exists()
        },
        "basis": "measured（直接解析本机安装介质；非模型记忆）",
    }

    catalog = {
        "nx_version": "NX 12.0（12.0.2.9 介质）",
        "ui_language": "simpl_chinese（简体中文）",
        "stats": stats,
        "ribbon_tabs": ribbon_tabs,
        "commands": out_cmds,
        "menus": {k: {"file": v["file"], "items": v["items"]}
                  for k, v in model_objs["建模"].menus.items()},
    }
    return catalog, evidence


# ---------------------------------------------------------------- 文档审计

CMD_REF = re.compile(r"\[CMD:([A-Za-z0-9_]+)\]\s*`?([^\s|｜，,。;；：:`]+)")
PATH_SEG = re.compile(r"`([^`]+)`")
TOP_MENUS = {"文件", "编辑", "视图", "插入", "格式", "工具", "装配", "PMI", "信息",
             "分析", "首选项", "应用模块", "窗口", "帮助", "任务", "草图曲线",
             "草图约束", "尺寸"}


def _norm_name(text: str) -> str:
    """去助记符/括号/省略号/尾部标点，便于中英文混排比对。"""
    s = text.replace("&", "").strip()
    s = re.sub(r"[（(][^）)]*[）)]", "", s)
    s = s.replace("...", "").replace("…", "")
    return s.strip("：: `|")


def audit_docs(catalog: dict, doc_dir: Path) -> int:
    cmds = catalog["commands"]
    problems: list[str] = []
    checked = 0
    path_checked = 0
    for md in sorted(doc_dir.rglob("*.md")):
        text = md.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            for m in CMD_REF.finditer(line):
                cid, claimed = m.group(1), m.group(2)
                checked += 1
                rec = cmds.get(cid)
                if not rec:
                    problems.append(f"{md.name}: 命令 {cid} 不存在于 NX 12.0 中文介质")
                    continue
                allowed = {_norm_name(x) for x in
                           (rec["zh"], rec["zh_menu"], rec["zh_ribbon"])} - {""}
                c = _norm_name(claimed)
                ok = any(c and (a.startswith(c) or c.startswith(a)) for a in allowed)
                if allowed and not ok:
                    problems.append(
                        f"{md.name}: {cid} 名称不符：文档写「{claimed}」，介质为「{rec['zh']}」")
                if not rec["menu_paths"]:
                    problems.append(f"{md.name}: {cid} 无菜单路径证据（可能为仅 API/批处理命令）")
                    continue

                # 路径末级校验：同一行 `插入(S)` → ... → `拉伸(X)...`
                segs = PATH_SEG.findall(line[m.end():])
                if len(segs) >= 2 and _norm_name(segs[0]) in TOP_MENUS:
                    path_checked += 1
                    leaf = _norm_name(segs[-1])
                    leaf_ok = any(leaf and (a.startswith(leaf) or leaf.startswith(a))
                                  for a in allowed)
                    if not leaf_ok:
                        problems.append(
                            f"{md.name}: {cid} 路径末级「{segs[-1]}」与命令中文名「{rec['zh']}」不符")
    print(f"[AUDIT] 名称引用 {checked} 处，路径末级 {path_checked} 处，问题 {len(problems)} 处")
    for p in problems[:80]:
        print("  - " + p)
    return 1 if problems else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nx-root", default=None)
    ap.add_argument("--out", default=None,
                    help="输出目录，默认 <脚本目录>/../catalog")
    ap.add_argument("--audit", default=None, help="审计指定 Markdown 目录")
    args = ap.parse_args()

    here = Path(__file__).resolve().parent
    out_dir = Path(args.out) if args.out else here.parent / "catalog"
    out_dir.mkdir(parents=True, exist_ok=True)

    nx_root = discover_nx_root(args.nx_root)
    print(f"[OK] NX 根目录：{nx_root}")

    catalog, evidence = build_catalog(nx_root)
    (out_dir / "nx12_cn_commands.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "extraction_evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")

    s = catalog["stats"]
    print(f"[OK] 命令 {s['commands']} 条（中文名 {s['commands_with_zh']}，"
          f"快捷键 {s['commands_with_accel']}，有菜单路径 {s['commands_with_menu_path']}）")
    print(f"[OK] 菜单 {s['menus']} 个，功能区选项卡 {s['ribbon_tabs']} 个，"
          f"翻译条目 {s['translation_entries']} 条")
    print(f"[OK] 输出：{out_dir / 'nx12_cn_commands.json'}")

    if args.audit:
        return audit_docs(catalog, Path(args.audit))
    return 0


if __name__ == "__main__":
    sys.exit(main())
