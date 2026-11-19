#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从官方 simpl_chinese 翻译表补全命令目录（E4-TRANSLATION）。

背景：当前 NX 12.0.2.9 介质树中，UGII/menus 与各应用目录只带回一部分 *.men/*.btn；
仿真（SFEM/DESFEM/Motion/Simcenter）、管线布置（Routing/TEAPIPE）、船舶、PCB、机电、
检测、线体规划等应用的菜单/按钮源文件不在安装树中，但 LOCALIZATION/translations/
simpl_chinese 下仍保留其 *_men / definitions_*_btn 官方中文串表。本脚本只做两件事：

1. 从这些官方翻译表还原命令 ID 与中文名/英文名/功能说明；
2. 合并进 nx12_cn_full_catalog.json，证据等级标 E4-TRANSLATION：
   - 中文名/功能说明 = 介质官方译文（measured）；
   - 菜单路径/快捷键/对话框参数 = 未随介质提供，必须 GUI 复核（不臆造）。

用法：
  python augment_catalog_from_translations.py [--catalog PATH] [--nx-root PATH]
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DEFAULT_CAT = ROOT / "catalog" / "nx12_cn_full_catalog.json"
DEFAULT_NX = Path(r"D:\BaiduNetdiskDownload\NX 12.0.2.9\NX12.2.9waigua\NX12.2.9\NX")

# 只补“应用级官方菜单/按钮”翻译表；刻意排除 *_jteditor/*_nxviewer/*_simviewer 之外的
# 纯 UI/调试表，避免把界面字符串误当功能命令。simviewer 属于仿真后处理查看器，保留。
SELECTED_STEMS = {
    # 仿真 / Simcenter / Motion / Durability
    "app_simulation_men", "app_simcenter_men", "definitions_simulation_btn", "definitions_simcenter_btn",
    "ug_sfem_men", "ug_sfem_simcenter_men", "ug_desfem_men", "ug_mechanisms_men",
    "ug_main_simcenter_men", "ug_modeling_simcenter_men", "ug_sketcher_simcenter_men",
    "ug_styler_simcenter_men", "ug_subdiv_simcenter_men", "ug_subset_definition_simcenter_men",
    "ug_true_studio_simcenter_men", "simcenter_layout_te_men", "simcenter_title_block_men",
    "ug_debug_simcenter_men", "ug_gateway_simcenter_men", "ug_nopart_simcenter_men",
    "ug_sequencing_simcenter_men", "ug_sfem_simviewer_men", "ug_view_popup_simviewer_men",
    "ug_main_simviewer_men", "ug_debug_simviewer_men", "kinematics_men", "ug_mechatronics_men",
    "nx_mechatronics_player_men", "app_mechatronics_men", "app_mechatronics_player_men",
    # 管线布置 / Routing / TEAPIPE / 线束 / 电气
    "app_routing_men", "definitions_routing_btn", "ug_route_common_men", "ug_route_elec_men",
    "ug_route_mech_men", "ug_route_lgcl_men", "ug_route_run_nav_men", "nx_mechanical_routing_men",
    "teapipeapplication_men", "UFD_Routing_PipeProdLength_men",
    # 制造规划 / 检测 / 增材 / 线体 / 工装
    "app_mach_men", "nx_additive_manufacturing_men", "app_inspection_men", "ug_inspection_men",
    "pid_men", "app_pid_men", "line_designer_men", "app_line_designer_men", "machining_line_planner_men",
    "mfg_view_maker_men", "tool_designer_men", "app_tool_designer_men", "press_line_simul_men",
    "presslinesim_men", "definitions_pressline_simulation_btn",
    # 船舶 / 结构 / 焊接
    "add_ug_weld_men", "add_weldstructure_shipdetaildesign_men", "ug_ship_men", "ug_ship_basic_men",
    "ug_ship_common_men", "ug_ship_common_design_men", "ug_ship_common_new_men", "ug_ship_detail_men",
    "ug_ship_manufacturing_men", "ug_ship_app_men", "nx_ship_general_arrangement_men",
    "nx_drafting_shipstructure_men", "ug_drafting_shipbuilding_men", "ug_ship_mfg_view_mode_men",
    # 航空 / 汽车 / 机电机构
    "ug_aerosm_men", "nx_aerodesign_men", "app_automotive_men", "definitions_ugautomotive_btn",
    "ug_mechdes_men", "bodydes_men",
    # PCB / 弹性板 / 多边形 / 布局
    "ug_flex_pcb_men", "fpcd_app_men", "nx_polygon_modeling_men", "nx_layout_app_men",
    "nx_layout_te_men", "nx_title_block_men", "nx_visual_reporting_men", "nx_design_tools_men",
    "nx_dmu_men", "app_dmu_men", "diagramming_men", "diagramming_view_men",
    # 模具/冲压/电极/工具（补 translations 中未被 .men 覆盖的部分）
    "diedes_men", "dieeng_men", "nx_ediewizard_men", "nx_electrodedesign_men", "nx_moldwizard_men",
    "app_moldwizard_men", "nx_mtb_men", "nx_pdiewizard_men", "app_stampingtools_men",
    "nx_geodesic_sketch_men", "nx_human_men", "nx_ship_mfg_view_mode_men",
    # 其它官方应用（保守并入“其他官方应用”，不与第三方外挂混淆）
    "nx_animation_designer_men", "nx_pts_men", "nx_pts_view_popup_men",
}

SUFFIXES = [
    "_TOOLBAR_LABEL", "_RIBBON_LABEL", "_POPUP_LABEL", "_LABEL", "_MESSAGE", "_HINT",
]
LABEL_SUFFIXES = {"_LABEL", "_TOOLBAR_LABEL", "_RIBBON_LABEL", "_POPUP_LABEL"}
ID_RE = re.compile(r"[A-Z][A-Z0-9_]*")
ZH_RE = re.compile(r"[\u4e00-\u9fff]")


def parse_translation_file(path: Path):
    """产出 {command_id: {zh,en,message,hint,sources,src_names,suffixes}}。"""
    out: dict[str, dict] = {}
    try:
        lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except OSError:
        return out
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        try:
            parts = next(csv.reader([s], delimiter=" ", quotechar='"', skipinitialspace=True, strict=False))
        except (csv.Error, StopIteration):
            continue
        if len(parts) < 4:
            continue
        src, sid, en, zh = parts[0].strip(), parts[1].strip(), parts[2], parts[3]
        if not zh or not ZH_RE.search(zh):
            continue
        base_id = suffix = None
        for suf in SUFFIXES:
            if sid.endswith(suf):
                base_id, suffix = sid[: -len(suf)], suf
                break
        if not base_id or not ID_RE.fullmatch(base_id):
            continue
        rec = out.setdefault(base_id, {
            "zh": "", "en": "", "message": "", "hint": "",
            "sources": set(), "src_names": set(), "suffixes": set(),
        })
        rec["sources"].add(path.name)
        if src:
            rec["src_names"].add(src)
        rec["suffixes"].add(suffix)
        clean_zh = zh.replace("&", "").strip()
        if suffix in LABEL_SUFFIXES and not rec["zh"]:
            rec["zh"], rec["en"] = clean_zh, en
        elif suffix == "_MESSAGE" and not rec["message"]:
            rec["message"] = zh
        elif suffix == "_HINT" and not rec["hint"]:
            rec["hint"] = zh
    return out


def module_of(cid: str, zh: str, src_names: set[str]) -> str:
    c = cid.upper()
    src = " ".join(sorted(src_names)).lower()
    men = " ".join(sorted(src_names)).lower()

    # CAM/制造仿真优先（nx_manufacturing_simulation_te 属加工仿真，不是 CAE 仿真）
    if c.startswith(("UG_CAM_", "BATCH_PROCESS")) or "manufacturing_simulation" in men or "/mach/" in men or "cam.men" in men:
        return "08_加工制造"
    # 仿真 / Simcenter / Motion / Durability / Mechatronics
    if (c.startswith(("UG_SFEM", "UG_DESFEM", "UG_MECHANISMS", "UG_SIM", "NX_SIM", "CAESIM", "UG_DURABILITY", "UG_FEM", "UG_CAE", "UG_MOTION", "UG_KMP", "UG_KMC", "UG_MDFTNAV"))
            or any(k in men for k in ("sfem", "desfem", "mechanisms", "simcenter", "simulation", "durability", "kinematics", "mechatronics", "motion"))):
        return "09_仿真分析"
    # 管线布置 / Routing / TEAPIPE / 线束 / 电气 / 逻辑布线
    if (c.startswith(("UG_ROUTE", "NX_ROUTE", "UG_MECH_ROUTING", "UG_TEAPIPE", "TEAPIPE_APP", "UFD_ROUTING", "RTE_", "UG_PIPE", "UG_ELEC", "UG_HARNESS", "UG_CABLE", "UG_LGCL", "UG_RUN"))
            or any(k in men for k in ("routing", "route_", "teapipe", "electrical", "harness", "cabling", "pipe", "lgcl"))):
        return "11_管线与线路"
    # 钣金
    if (c.startswith(("UG_SMD", "NXSM", "UG_SHEETMTL")) or "sheet_metal" in men or "smd" in men) and not c.startswith("UG_DRAFT"):
        return "05_钣金设计"
    # 模具/冲压/电极/工装
    if (c.startswith(("MW_", "UGMOLD_", "PDW_", "EDW_", "TOOLING_", "NX_MOLD", "NX_PDI", "NX_EDI", "NX_ELECTRODE", "NX_MTB"))
            or any(k in men for k in ("mold", "stamping", "pdiewizard", "ediewizard", "electrodedesign", "tooling", "dieeng", "diedes"))):
        return "10_模具设计"
    # 草图
    if c.startswith(("UG_SKETCH", "UG_DIRECT_SKETCH", "UG_GEODESIC")) or "sketch" in men:
        return "01_草图绘制"
    # 同步建模
    if c.startswith(("UG_ADM_", "UG_MODELING_REPLACE", "UG_MODELING_SYNCHRONOUS", "UG_SBSM")) or "synchronous" in men or "sbsm" in men:
        return "06_同步建模"
    # 自由曲面/曲面
    if (c.startswith(("UG_MODELING_FF_", "UG_SUBDIV_", "UG_STYLER_", "UG_SHAPESTUDIO", "UG_TRUE_STUDIO", "UG_GEODESIC"))
            or "freeform" in men or "styler" in men or "subdiv" in men or "shapestudio" in men):
        return "04_曲面设计"
    # 工程图/PMI/布局/标题栏/船舶详图
    if (c.startswith(("UG_DRAFT_", "UG_PMI_", "UG_TABLE_", "UG_TITLE_BLOCK", "NX_TITLE_BLOCK", "NX_DRAFTING", "UG_DRAFTING", "UG_ROUTE_BOM"))
            or any(k in men for k in ("draft", "layout", "title_block", "pmi", "shipstructure", "shipbuilding"))):
        return "07_工程图与PMI"
    # 装配/序列/机构位置
    if c.startswith(("UG_ASSY_", "UG_NXPOS_", "UG_ANT_", "UG_PARTNAV_", "UGMGR_", "UG_SEQUENCING", "UG_MSEQ")) or "assembl" in men or "sequencing" in men:
        return "03_装配设计"
    # 零件建模/曲线/表达式/KBE
    if c.startswith(("UG_MODELING_", "UG_CURVE_", "UG_ASSOCIATIVE_", "UG_UDF_", "UG_KBE_", "UG_MECHDES", "BODYDES")):
        return "02_零件建模"
    # 图层/显示/视图样式
    if c.startswith(("UG_LAYER_", "UG_ARRANGE_", "UG_VIEW_SEE_THRU_STYLE_LAYERS", "UG_VISUAL")) or "layer" in men:
        return "13_图层与显示"
    # 定制/首选项/用户界面/角色
    if c.startswith(("UG_PREFERENCES", "UG_TOOLS_CUSTOMIZE", "UI_KRU", "UG_FTK")) or "custom" in men or "preferences" in men:
        return "14_定制与首选项"
    # 文件/编辑/视图/信息/帮助/窗口/表达式/WCS/检查/对话框
    if c.startswith(("UG_FILE_", "UG_EDIT_", "UG_INFO_", "UG_HELP_", "UG_VIEW_", "UG_SEL_", "UG_WINDOW_", "UG_LAYOUT_", "UG_NXLAYOUT_", "UG_TOOLBOX_", "UG_MACRO_", "UG_JOURNAL_", "UG_EXPRESSION_", "UG_WCS_", "UG_CHECKER_", "UG_DIALOG_", "UG_FLEX", "UG_FSM")):
        return "12_文件编辑视图信息"
    # 其它官方应用（船舶/航空/汽车/PCB/机电/检测/线体/可视化/动画等）
    if not c.startswith(("YX_", "MS_", "KASA", "QL_", "CF_", "GY_", "LXH_", "MEILEI", "TCL", "YSUG")):
        return "21_其他官方应用"
    return "15_其他与第三方外挂"


def strip_mn(text: str) -> str:
    return (text or "").replace("&", "").strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default=str(DEFAULT_CAT))
    ap.add_argument("--nx-root", default=str(DEFAULT_NX))
    args = ap.parse_args()

    cat_path = Path(args.catalog)
    loc = Path(args.nx_root) / "LOCALIZATION" / "translations" / "simpl_chinese"
    if not cat_path.exists():
        print(f"[FAIL] catalog not found: {cat_path}")
        return 1
    if not loc.is_dir():
        print(f"[FAIL] translation dir not found: {loc}")
        return 1

    data = json.loads(cat_path.read_text(encoding="utf-8"))
    cmds = data["commands"]

    # 收集候选：stem -> parse file
    candidates: dict[str, dict] = {}
    files_used: list[str] = []
    for stem in sorted(SELECTED_STEMS):
        fp = loc / f"{stem}_simpl_chinese.txt"
        if not fp.exists():
            continue
        files_used.append(fp.name)
        for cid, rec in parse_translation_file(fp).items():
            dst = candidates.setdefault(cid, {
                "zh": "", "en": "", "message": "", "hint": "",
                "sources": set(), "src_names": set(), "suffixes": set(),
            })
            dst["sources"].update(rec["sources"])
            dst["src_names"].update(rec["src_names"])
            dst["suffixes"].update(rec["suffixes"])
            if rec["zh"] and not dst["zh"]:
                dst["zh"], dst["en"] = rec["zh"], rec["en"]
            if rec["message"] and not dst["message"]:
                dst["message"] = rec["message"]
            if rec["hint"] and not dst["hint"]:
                dst["hint"] = rec["hint"]

    added = merged = 0
    module_counts = Counter()
    for cid, rec in candidates.items():
        zh = strip_mn(rec["zh"])
        en = strip_mn(rec["en"])
        msg = rec["message"]
        hint = rec["hint"]
        sources = sorted(f"LOCALIZATION/translations/simpl_chinese/{s}" for s in rec["sources"])
        src_names = sorted(rec["src_names"])
        module = module_of(cid, zh, set(src_names))
        if cid in cmds:
            c = cmds[cid]
            merged += 1
            # 只补空字段，不覆盖既有 .btn/.men 证据
            if not c.get("zh") and zh:
                c["zh"] = zh
            if not c.get("en") and en:
                c["en"] = en
            if not c.get("message_zh") and msg:
                c["message_zh"] = msg
            if not c.get("hint") and hint:
                c["hint"] = hint
            ts = c.setdefault("translation_sources", [])
            for s in sources:
                if s not in ts:
                    ts.append(s)
            if not c.get("source_hint"):
                c["source_hint"] = src_names[0] if src_names else ""
            continue

        cmds[cid] = {
            "id": cid,
            "zh": zh,
            "zh_menu": zh,
            "zh_ribbon": zh,
            "en": en,
            "message_zh": msg,
            "accelerator": "",
            "synonyms": "",
            "hint": hint,
            "source_btn": "",
            "source_hint": src_names[0] if src_names else "",
            "men_files": [],
            "menus": [],
            "menu_paths": [],
            "module": module,
            "evidence": "E4-TRANSLATION",
            "translation_sources": sources,
        }
        added += 1
        module_counts[module] += 1

    # 更新统计
    stats = data.setdefault("stats", {})
    stats["commands"] = len(cmds)
    stats["commands_with_zh"] = sum(1 for v in cmds.values() if v.get("zh"))
    stats["commands_with_accel"] = sum(1 for v in cmds.values() if v.get("accelerator"))
    ev = Counter(v.get("evidence", "") for v in cmds.values())
    stats["commands_e1"] = ev.get("E1-MEDIA", 0)
    stats["commands_e2"] = ev.get("E2-MENU", 0)
    stats["commands_e3"] = ev.get("E3-UNTR", 0)
    stats["commands_e4_translation"] = ev.get("E4-TRANSLATION", 0)
    stats["translation_augmented"] = {
        "translation_files_used": len(files_used),
        "candidate_ids": len(candidates),
        "added_commands": added,
        "merged_existing": merged,
        "added_by_module": dict(module_counts),
    }
    data["nx_version"] = data.get("nx_version", "NX 12.0（12.0.2.9 介质，含第三方外挂菜单）")
    data["ui_language"] = data.get("ui_language", "simpl_chinese（简体中文）")
    data["basis"] = "measured（.btn/.men + LOCALIZATION simpl_chinese 官方翻译表）"

    cat_path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[OK] translation files used: {len(files_used)}")
    print(f"[OK] candidate IDs: {len(candidates)}; added={added}; merged_existing={merged}")
    print(f"[OK] commands total={len(cmds)}; evidence={dict(ev)}")
    print(f"[OK] added_by_module={dict(module_counts)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
