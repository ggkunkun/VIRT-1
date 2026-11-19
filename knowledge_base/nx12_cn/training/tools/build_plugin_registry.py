#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第三方外挂能力注册表生成器（Agent 路由用）。

产出 plugins/plugin_registry.json，供 plugin_router.py 与训练知识库消费。

真实性：全部来自本机 NX 12.0.2.9 介质（measured）。
关键适配事实（均由本脚本实测得出，不是推断）：
  1) 外挂 .men 编码为 GBK（个别 UTF-8），必须嗅探解码，否则中文标签全丢；
  2) 外挂菜单 VERSION 可能为 120(NX12) 或 130(NX13+)，混版会加载失败/不显示；
  3) ACTIONS 存在 绝对路径 / 环境变量 / 模块文件 / STANDARD(转发官方) 四类；
  4) 外挂 BUTTON ID 常为数字或极短串（1/2/FEED/YS），跨外挂重名，必须用复合键。

官方/第三方判定：
  - 官方：UGII、MACH、DRAFTING、MOLDWIZARD、STAMPING_TOOLS、DESIGN_TOOLS、
          LOCALIZATION/prc（Siemens 官方中国包 GC Toolkit，非第三方）
  - 第三方：YANGJEE 合集、MS_NXTOOLS 等
"""
from __future__ import annotations

import json, re, sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                      # training/
NX = Path(r"D:\BaiduNetdiskDownload\NX 12.0.2.9\NX12.2.9waigua\NX12.2.9\NX")
OUT = ROOT / "plugins"

# 厂商 → 目录（按实测结构登记）
VENDORS = [
    ("ysug",         "YANGJEE",      "YSUG 模具外挂",        "YANGJEE/YSUG"),
    ("meilei2",      "YANGJEE",      "美雷工具 MeiLei2",      "YANGJEE/MeiLei2_tool"),
    ("yanxiu",       "YANGJEE",      "燕秀 UG 模具外挂",      "YANGJEE/yanxiu"),
    ("lxh_tool",     "YANGJEE",      "LXH 工具集",            "YANGJEE/LXH_TOOL_12.26"),
    ("ghtools",      "YANGJEE",      "GH 工具",               "YANGJEE/GHTOOLS"),
    ("chaofan",      "YANGJEE",      "超凡工具 ChaoFan",       "YANGJEE/ChaoFan"),
    ("lm_nxplugins", "YANGJEE",      "LM 插件",               "YANGJEE/LM_NXPlugins"),
    ("quickcam",     "YANGJEE",      "QuickCAM 快速编程",      "YANGJEE/QuickCAM"),
    ("tkltools",     "YANGJEE",      "TKL 工具集",            "YANGJEE/TKLTOOLS"),
    ("guyue",        "YANGJEE",      "古月工具 GuYue",         "YANGJEE/GuYue TooL"),
    ("jinyu",        "YANGJEE",      "金雨工具 jinyu",         "YANGJEE/jinyu"),
    ("ms_nxtools",   "MS_NXTOOLS",   "MS 工具箱",             "MS_NXTOOLS"),
    ("kasa",         "YANGJEE",      "KASA 工具",             "YANGJEE/YSUG/Kasa"),
]

OFFICIAL_CN = ("LOCALIZATION/prc", "Siemens 官方中国包 GC Toolkit（齿轮/弹簧/加密/制图工具）")

ENC_ORDER = ("utf-8", "gbk", "latin1")


def decode_best(raw: bytes) -> tuple[str, str]:
    for enc in ENC_ORDER:
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("latin1", errors="replace"), "latin1"


def action_kind(a: str) -> str:
    if not a:
        return "无ACTIONS"
    if a.upper() == "STANDARD":
        return "STANDARD_转发官方"
    if re.match(r"^[A-Za-z]:\\", a):
        return "绝对路径"
    if "$" in a or "%" in a:
        return "环境变量"
    if a.lower().endswith((".grx", ".dll", ".dlx", ".utd", ".dlg")):
        return "模块文件"
    return "其他"


def version_tags(path: Path, root: Path) -> list[str]:
    rel = str(path.relative_to(root)).replace("\\", "/")
    tags = re.findall(r"(NX\s?\d+(?:\.\d+)?|NX\d{4}|3[26]bit|64bit)", rel, re.I)
    return sorted(set(t.replace(" ", "") for t in tags))


def applicable_to_nx12(path: Path, root: Path) -> tuple[bool, str]:
    """判断外挂文件是否适用于 NX 12。

    外挂普遍按 NX 版本分目录（NX4.0/NX6.0/NX10.0/NX11.0/NX12.0/NX1926/NX64...）。
    全量加载会把其它版本的菜单塞进 NX12，导致菜单错乱或加载失败。
    规则：
      - 路径含 NX<主版本> 段且主版本 != 12  -> 不适用
      - 路径含 NX12 / NX12.0                -> 适用
      - NX64/32bit/64bit 视为位数标记，不作版本排除（但仍记录）
      - 无版本段                            -> 适用（通用）
    """
    rel = "/" + str(path.relative_to(root)).replace("\\", "/").lower() + "/"
    # NX 12 为纯 64 位版本：32bit 目录不适用（否则同一外挂会被重复计一遍）
    if "/32bit/" in rel:
        return False, "32bit 目录（NX12 为 64 位版本）"
    marks = re.findall(r"/nx(\d{1,2})(?:\.(\d+))?/", rel)
    if not marks:
        # 兼容 NX10NX11 这类复合写法
        compound = re.findall(r"/nx(\d{1,2})nx(\d{1,2})/", rel)
        if compound:
            return False, "复合版本目录（非 NX12 单版本）"
        return True, "无版本段（通用）"
    for major, _minor in marks:
        if int(major) == 12:
            return True, "NX12 专用目录"
        if int(major) in (64, 32):
            continue
        return False, f"NX{major} 专用目录（与 NX12 不兼容）"
    return True, "位数目录"


def parse_men_gbk(path: Path) -> dict:
    """解析单个 .men：返回菜单、按钮、标签、动作。"""
    txt, enc = decode_best(path.read_bytes())
    menu_ver = ""
    m = re.search(r"^VERSION\s+(\S+)", txt, re.M)
    if m:
        menu_ver = m.group(1)
    cur_menu = ""
    cur_btn = None
    out = {"encoding": enc, "menu_version": menu_ver, "items": []}
    for raw in txt.splitlines():
        s = raw.strip()
        if not s or s.startswith("!"):
            continue
        mm = re.match(r"^MENU\s+([A-Za-z0-9_]+)", s)
        if mm:
            cur_menu = mm.group(1)
            continue
        mm = re.match(r"^(BUTTON|TOGGLE|CASCADE_BUTTON)\s+([A-Za-z0-9_]+)\s*$", s)
        if mm:
            cur_btn = {"type": "CASCADE" if mm.group(1) == "CASCADE_BUTTON" else "BUTTON",
                       "id": mm.group(2), "menu": cur_menu,
                       "label": "", "message": "", "actions": "", "accelerator": ""}
            out["items"].append(cur_btn)
            continue
        if cur_btn is None:
            continue
        if s.startswith("LABEL "):
            cur_btn["label"] = s[6:].strip().replace("&", "")
        elif s.startswith("MESSAGE "):
            cur_btn["message"] = s[8:].strip()
        elif s.startswith("ACTIONS "):
            cur_btn["actions"] = s[8:].strip()
        elif s.startswith("ACCELERATOR "):
            cur_btn["accelerator"] = s[12:].strip()
    return out


def main() -> int:
    if not NX.exists():
        print(f"[FAIL] 介质不存在: {NX}")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)

    # 官方命令 ID 集合（用于冲突检测与 STANDARD 映射）
    official_ids: set[str] = set()
    cat = ROOT / "catalog" / "nx12_cn_full_catalog.json"
    if cat.exists():
        d = json.loads(cat.read_text(encoding="utf-8"))
        official_ids = {k for k, v in d["commands"].items()
                        if v.get("module") != "15_其他与第三方外挂"}

    plugins = []
    global_id_seen: dict[str, list[str]] = defaultdict(list)

    for pid, vendor, disp, relroot in VENDORS:
        d = NX / relroot
        if not d.exists():
            continue
        all_men = sorted(d.rglob("*.men"))
        if not all_men:
            continue
        # 版本适用性过滤：只保留 NX12 可用菜单，其它版本目录整段排除
        men_files, excluded = [], []
        for mp in all_men:
            ok, why = applicable_to_nx12(mp, NX)
            (men_files if ok else excluded).append((mp, why))
        men_files = [mp for mp, _ in men_files]
        if not men_files:
            print(f"[SKIP] {pid}: 无适用 NX12 的菜单（{len(excluded)} 个被排除）")
            continue
        cmds = []
        seen_cmd: dict[str, dict] = {}
        dup_instances = 0
        encs = Counter()
        vers = Counter()
        akinds = Counter()
        vt = set()
        for mp in men_files:
            rec = parse_men_gbk(mp)
            encs[rec["encoding"]] += 1
            if rec["menu_version"]:
                vers[rec["menu_version"]] += 1
            vt |= set(version_tags(mp, NX))
            for it in rec["items"]:
                if it["type"] == "CASCADE":
                    continue
                # 同一外挂内同一命令 ID 可能被多个菜单重复挂载：合并为多入口，不丢信息
                if it["id"] in seen_cmd:
                    dup_instances += 1
                    prev = seen_cmd[it["id"]]
                    if it["menu"] and it["menu"] not in prev["menus"]:
                        prev["menus"].append(it["menu"])
                    continue
                kind = action_kind(it["actions"])
                akinds[kind] += 1
                cmd = {
                    "command_id": it["id"],
                    "key": f"{pid}:{it['id']}",          # 复合键：外挂短ID必须带命名空间
                    "label_zh": it["label"] if re.search(r"[\u4e00-\u9fff]", it["label"]) else "",
                    "label_raw": it["label"],
                    "message": it["message"],
                    "accelerator": it["accelerator"],
                    "menu": it["menu"],
                    "menus": [it["menu"]] if it["menu"] else [],
                    "men_file": str(mp.relative_to(NX)).replace("\\", "/"),
                    "actions": it["actions"],
                    "action_kind": kind,
                }
                cmds.append(cmd)
                seen_cmd[it["id"]] = cmd
                if cmd["key"] not in global_id_seen[it["id"]]:
                    global_id_seen[it["id"]].append(cmd["key"])

        # 风险画像
        dup_ids = sorted({c["command_id"] for c in cmds
                          if len(global_id_seen[c["command_id"]]) > 1})
        hard_paths = [c for c in cmds if c["action_kind"] == "绝对路径"]
        std_alias = [c for c in cmds if c["action_kind"] == "STANDARD_转发官方"]
        env_paths = [c for c in cmds if c["action_kind"] == "环境变量"]
        wrong_ver = [mp for mp in men_files if parse_men_gbk(mp).get("menu_version") not in ("", "120")]
        risk = {
            "level": "HIGH" if (hard_paths or wrong_ver) else ("MEDIUM" if dup_ids or env_paths else "LOW"),
            "hardcoded_paths": len(hard_paths),
            "hardcoded_examples": [c["actions"] for c in hard_paths[:3]],
            # VERSION != 120 表示菜单为其它 NX 版本编写，加载到 NX12 可能不生效
            "menu_version_mismatch": [str(f.relative_to(NX)).replace("\\", "/") for f in wrong_ver],
            "env_var_paths": len(env_paths),
            "env_var_examples": [c["actions"] for c in env_paths[:3]],
            "excluded_by_version": [{"file": str(f.relative_to(NX)).replace("\\", "/"), "reason": why}
                                    for f, why in excluded],
            "duplicate_ids": dup_ids[:10],
            "duplicate_id_count": len(dup_ids),
            "official_aliases": len(std_alias),
            "encoding": dict(encs),
        }
        plugins.append({
            "plugin_id": pid,
            "vendor": vendor,
            "display_name": disp,
            "root": relroot,
            "men_files": [str(f.relative_to(NX)).replace("\\", "/") for f in men_files],
            "excluded_men_files": len(excluded),
            "dedup_skipped": dup_instances,
            "encoding": dict(encs),
            "menu_versions": dict(vers),
            "version_tags": sorted(vt),
            "command_count": len(cmds),
            "actions_profile": dict(akinds),
            "risk": risk,
            "commands": cmds,
            "evidence": "E1-MEDIA（GBK/UTF-8 嗅探解码，直接解析介质 .men；已按 NX12 版本目录过滤）",
        })

    # 跨外挂重名汇总
    cross = {k: v for k, v in global_id_seen.items() if len(v) > 1}
    registry = {
        "schema": "nx12-plugin-registry-v1",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "nx_version": "NX 12.0（12.0.2.9 介质，简体中文）",
        "basis": "measured（直接解析本机介质外挂 .men）",
        "official_china_package": {
            "path": OFFICIAL_CN[0],
            "note": OFFICIAL_CN[1] + "；不属于第三方外挂，走官方翻译表与官方菜单，按内置能力处理。",
            "menus": sorted(str(p.relative_to(NX)).replace("\\", "/")
                            for p in (NX / OFFICIAL_CN[0]).rglob("*.men")),
        },
        "plugins": plugins,
        "cross_plugin_duplicate_ids": {
            "count": len(cross),
            "samples": [{"id": k, "owners": v[:6]} for k, v in list(cross.items())[:15]],
        },
        "totals": {
            "plugins": len(plugins),
            "commands": sum(p["command_count"] for p in plugins),
            "with_zh_label": sum(1 for p in plugins for c in p["commands"] if c["label_zh"]),
        },
    }
    fp = OUT / "plugin_registry.json"
    fp.write_text(json.dumps(registry, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[OK] {fp}")
    print(f"[OK] 外挂 {registry['totals']['plugins']} 个，命令 {registry['totals']['commands']} 条，"
          f"中文标签 {registry['totals']['with_zh_label']} 条")
    for p in plugins:
        print(f"   {p['plugin_id']:12s} {p['display_name']:16s} cmd={p['command_count']:4d} "
              f"risk={p['risk']['level']:6s} enc={list(p['encoding'])} ver={list(p['menu_versions'])}")
    print(f"[OK] 跨外挂重名 ID {len(cross)} 个")
    return 0


if __name__ == "__main__":
    sys.exit(main())
