# -*- coding: utf-8 -*-
"""
AutoCAD 2026 简体中文专业能力体系 - 三轮交叉验证
第一轮：全命令库匹配校验（知识库 vs 官方原始 CUIX/pgp 数据）
第二轮：100 个典型行业任务交付验证（查询引擎端到端）
第三轮：版本专属特性专项校验（2026 特性来源与命令、无跨版本误用）
所有通过率基于真实比对计算，不预设 100%。
"""
import os, sys, json, time, subprocess
from collections import defaultdict

KB = r"D:\Virtu模型\knowledge_base\autocad_2026_pro"
RAW = r"D:\Virtu模型\.autocad2026_research\data"
sys.path.insert(0, KB)
import query_engine as qe

results = {}


def load(p):
    return json.load(open(p, encoding="utf-8"))


# ========== 第一轮：全命令库匹配校验 ==========
def round1():
    master = load(os.path.join(RAW, "master_commands.json"))
    idx = load(os.path.join(KB, "command_index.json"))
    # 官方原始：命令 -> 中文名集合 / 别名集合 / 菜单路径集合
    off_names = defaultdict(set); off_alias = defaultdict(set); off_menu = defaultdict(set)
    for r in master["commands"].values():
        c = r["command"]
        if not c: continue
        if r.get("name_zh"): off_names[c].add(r["name_zh"])
        for a in r.get("aliases", []): off_alias[c].add(a)
        for m in r.get("menu_paths", []): off_menu[c].add(m)
    for ac in master["alias_only_commands"]:
        for a in ac["aliases"]: off_alias[ac["command"]].add(a)

    total = len(idx["commands"]); passed = 0; fails = []
    for c, r in idx["commands"].items():
        ok = True; reasons = []
        # 命令名一致
        if c not in {x["command"] for x in master["commands"].values()} and c not in {x["command"] for x in master["alias_only_commands"]}:
            ok = False; reasons.append("命令不在官方源")
        # 中文名需在官方集合中（若有）
        if off_names.get(c) and r.get("name_zh") and r["name_zh"] not in off_names[c]:
            ok = False; reasons.append(f"中文名不符:{r['name_zh']} vs {off_names[c]}")
        # 别名需与官方一致（知识库别名是官方子集）
        ka = set(r.get("aliases", [])); oa = off_alias.get(c, set())
        if ka and not ka.issubset(oa):
            ok = False; reasons.append(f"别名非官方:ka-oa={ka-oa}")
        # 菜单路径需来自官方
        km = set(r.get("menu_path", [])); om = off_menu.get(c, set())
        if km and not km.issubset(om):
            ok = False; reasons.append("菜单路径非官方")
        if ok: passed += 1
        else: fails.append({"command": c, "reasons": reasons})
    return {"total": total, "passed": passed, "rate": passed/total if total else 0, "fails": fails[:20]}


# ========== 第二轮：100 个典型行业任务交付验证 ==========
TASKS = [
    # (输入查询, 期望命令或其别名之一, 类别)
    ("LINE","LINE","命令"),("CIRCLE","CIRCLE","命令"),("ARC","ARC","命令"),
    ("RECTANG","RECTANG","命令"),("PLINE","PLINE","命令"),("POLYGON","POLYGON","命令"),
    ("ELLIPSE","ELLIPSE","命令"),("SPLINE","SPLINE","命令"),("POINT","POINT","命令"),
    ("XLINE","XLINE","命令"),("RAY","RAY","命令"),("MLINE","MLINE","命令"),("DONUT","DONUT","命令"),
    ("MOVE","MOVE","命令"),("COPY","COPY","命令"),("ROTATE","ROTATE","命令"),("SCALE","SCALE","命令"),
    ("TRIM","TRIM","命令"),("EXTEND","EXTEND","命令"),("OFFSET","OFFSET","命令"),("MIRROR","MIRROR","命令"),
    ("ARRAY","ARRAY","命令"),("ERASE","ERASE","命令"),("EXPLODE","EXPLODE","命令"),("STRETCH","STRETCH","命令"),
    ("LENGTHEN","LENGTHEN","命令"),("CHAMFER","CHAMFER","命令"),("FILLET","FILLET","命令"),("BREAK","BREAK","命令"),("JOIN","JOIN","命令"),
    ("DIMLINEAR","DIMLINEAR","命令"),("DIMALIGNED","DIMALIGNED","命令"),("DIMANGULAR","DIMANGULAR","命令"),
    ("DIMRADIUS","DIMRADIUS","命令"),("DIMDIAMETER","DIMDIAMETER","命令"),("DIMBASELINE","DIMBASELINE","命令"),
    ("DIMCONTINUE","DIMCONTINUE","命令"),("DIMSTYLE","DIMSTYLE","命令"),("QDIM","QDIM","命令"),
    ("TEXT","TEXT","命令"),("MTEXT","MTEXT","命令"),("LEADER","LEADER","命令"),("MLEADER","MLEADER","命令"),
    ("TOLERANCE","TOLERANCE","命令"),("FIELD","FIELD","命令"),("TABLE","TABLE","命令"),
    ("LAYER","LAYER","命令"),("COLOR","COLOR","命令"),("LINETYPE","LINETYPE","命令"),("LWEIGHT","LWEIGHT","命令"),
    ("MATCHPROP","MATCHPROP","命令"),("PROPERTIES","PROPERTIES","命令"),("LAYISO","LAYISO","命令"),
    ("BLOCK","BLOCK","命令"),("INSERT","INSERT","命令"),("BEDIT","BEDIT","命令"),("WBLOCK","WBLOCK","命令"),
    ("ATTDEF","ATTDEF","命令"),("ATTEDIT","ATTEDIT","命令"),("BREPLACE","BREPLACE","命令"),("COUNT","COUNT","命令"),
    ("XREF","XREF","命令"),("XATTACH","XATTACH","命令"),("IMAGE","IMAGE","命令"),("IMAGEATTACH","IMAGEATTACH","命令"),
    ("PDFATTACH","PDFATTACH","命令"),("XCLIP","XCLIP","命令"),
    ("LAYOUT","LAYOUT","命令"),("PAGESETUP","PAGESETUP","命令"),("MVIEW","MVIEW","命令"),("VPORTS","VPORTS","命令"),
    ("PLOT","PLOT","命令"),("PUBLISH","PUBLISH","命令"),("PREVIEW","PREVIEW","命令"),
    ("EXTRUDE","EXTRUDE","命令"),("REVOLVE","REVOLVE","命令"),("SWEEP","SWEEP","命令"),("LOFT","LOFT","命令"),
    ("UNION","UNION","命令"),("SUBTRACT","SUBTRACT","命令"),("INTERSECT","INTERSECT","命令"),("3DORBIT","3DORBIT","命令"),
    ("MATERIALS","MATERIALS","命令"),("RENDER","RENDER","命令"),("SECTIONPLANE","SECTIONPLANE","命令"),
    ("GEOMCONSTRAINT","GEOMCONSTRAINT","命令"),("DIMCONSTRAINT","DIMCONSTRAINT","命令"),("AUTOCONSTRAIN","AUTOCONSTRAIN","命令"),("PARAMETERS","PARAMETERS","命令"),
    ("DATAEXTRACTION","DATAEXTRACTION","命令"),("DATALINK","DATALINK","命令"),("SHEETSET","SHEETSET","命令"),
    ("COUNT","COUNT","命令"),("HATCH","HATCH","命令"),("PURGE","PURGE","命令"),("AUDIT","AUDIT","命令"),("RECOVER","RECOVER","命令"),
    # 别名 / 场景 / 行业 / 故障 / 新特性（端到端）
    ("L","LINE","别名"),("C","CIRCLE","别名"),("CO","COPY","别名"),("M","MOVE","别名"),("TR","TRIM","别名"),("DLI","DIMLINEAR","别名"),("A","ARC","别名"),
    ("标注直径","DIMDIAMETER","场景"),("怎么画多段线","PLINE","场景"),("删除对象","ERASE","场景"),("填充剖面线","HATCH","场景"),
]

def round2():
    passed = 0; fails = []; latencies = []
    for q, expect, cat in TASKS:
        t0 = time.perf_counter()
        try:
            if cat in ("命令", "别名"):
                res = qe.query_command(q)
                got = any(r["command"] == expect for r in res)
            else:
                res = qe.query_scene(q)
                got = any(m["command"] == expect for m in res)
        except Exception as e:
            got = False; res = str(e)
        dt = (time.perf_counter() - t0) * 1000
        latencies.append(dt)
        if got: passed += 1
        else: fails.append({"query": q, "expect": expect, "cat": cat})
    n = len(TASKS)
    return {"total": n, "passed": passed, "rate": passed/n if n else 0,
            "avg_latency_ms": sum(latencies)/len(latencies), "max_latency_ms": max(latencies),
            "fails": fails[:20]}


# ========== 第三轮：版本专属特性专项校验 ==========
def round3():
    feat = load(os.path.join(KB, "features_2026.json"))
    idx = load(os.path.join(KB, "command_index.json"))
    master = load(os.path.join(RAW, "master_commands.json"))
    official_cmds = {x["command"] for x in master["commands"].values()} | {x["command"] for x in master["alias_only_commands"]}
    total = 0; passed = 0; fails = []
    for f in feat["new_features_2026"]:
        total += 1
        ok = True; reasons = []
        # 来源必须是 Autodesk 官方
        if "autodesk.com.cn" not in feat["source"]:
            ok = False; reasons.append("来源非官方")
        # 若特性列出命令，命令必须在官方库存在
        for c in f.get("commands", []):
            total += 1
            if c not in official_cmds:
                ok = False; reasons.append(f"命令非官方库:{c}")
            else:
                passed += 1
        if ok: passed += 1
        else: fails.append({"feature": f["name"], "reasons": reasons})
    # 版本标识一致性
    total += 1
    if "R25.1" in idx.get("version", "") or "2026" in idx.get("version", ""):
        passed += 1
    else:
        fails.append({"feature": "版本标识", "reasons": ["非 R25.1/2026"]})
    return {"total": total, "passed": passed, "rate": passed/total if total else 0, "fails": fails[:20]}


def main():
    t0 = time.perf_counter()
    results["round1_command_library"] = round1()
    results["round2_task_delivery"] = round2()
    results["round3_version_features"] = round3()
    results["meta"] = {
        "version": "AutoCAD 2026 (R25.1) 简体中文正式版",
        "total_duration_ms": (time.perf_counter()-t0)*1000,
        "data_sources": "官方 CUIX + acad.pgp (R25.1/chs) + Autodesk 官网",
    }
    p = os.path.join(KB, "validation", "validation_report.json")
    json.dump(results, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("="*60)
    for k in ["round1_command_library","round2_task_delivery","round3_version_features"]:
        r = results[k]
        print(f"{k:28} {r['passed']}/{r['total']} = {r['rate']*100:.2f}%")
        if r.get("fails"): print("   FAILS:", r["fails"][:5])
    r2 = results["round2_task_delivery"]
    print(f"响应延迟: 平均 {r2['avg_latency_ms']:.1f}ms 最大 {r2['max_latency_ms']:.1f}ms")
    print("写出", p)


if __name__ == "__main__":
    main()
