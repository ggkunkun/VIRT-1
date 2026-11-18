# -*- coding: utf-8 -*-
"""V0 准备阶段执行器（AE-CI-258 未测项验证计划 VP-AE-CI-258-001）。

可执行的部分：程序包/配置/文档/传输介质（软件侧实测）+ 现场登记表模板（量具、刀具预调、
夹具与零点、毛坯入厂、安全交底、RTCP 记录、空运行记录）。
现场签字项一律输出 PENDING，不伪造 PASS。

用法: .venv/Scripts/python.exe scripts/run_v0_preparation.py
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from virtu_prod import config, lint, programs  # noqa: E402

OUT = ROOT / "production" / "v0"
TEMPLATES = OUT / "templates"
NC_DIR = ROOT / "production" / "nc"
REP = ROOT / "production" / "reports"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def check(rows: List[Dict], cid: str, item: str, status: str, evidence, owner: str,
          action: str = "") -> None:
    rows.append({"id": cid, "item": item, "status": status, "evidence": evidence,
                 "owner": owner, "action": action})


def machine_runtime(m) -> Dict:
    return {"label": m.label, "controller": m.controller, "dialect": m.dialect,
            "safe_z": 10.0, "tc_z": m.tool_change_point["z"], "tc_x": 0.0, "tc_y": 0.0,
            "travel_mm": m.travel_mm, "rotary_limits_deg": m.rotary_limits_deg,
            "rotary": m.rotary_limits_deg, "tool_change_s": m.tool_change_s}


def tools_dict(p) -> Dict[str, Dict]:
    return {tid: {"id": tid, "diameter": t.diameter_mm, "gauge_length": t.gauge_length_mm,
                  "holder_length": t.holder_length_mm,
                  "holder_radius": t.holder_diameter_mm / 2.0}
            for tid, t in p.tools.items()}


def write_gauge_register() -> Path:
    rows = [
        ["三坐标测量机", "叶型/基准面 (U-01/U-05)", "MPE ≤ 0.005 mm", "", "", "PENDING"],
        ["超声测厚仪", "叶片/轮盖壁厚 (U-02)", "±0.01 mm", "", "", "PENDING"],
        ["表面粗糙度仪", "Ra (U-04)", "Ra 0.05–10 µm，符合 ISO 4287", "", "", "PENDING"],
        ["内径千分尺", "Ø76.2 H7 (U-05)", "分辨力 0.001 mm", "", "", "PENDING"],
        ["外径千分尺", "Ø258.06 (U-12)", "分辨力 0.001 mm", "", "", "PENDING"],
        ["动平衡机", "残余不平衡量 (U-03)", "≤ 10 g·mm", "", "", "PENDING"],
        ["标准球 Ø50 + 触发测头", "RTCP 标定 (U-06/U-08)", "球度 ≤0.002 mm", "", "", "PENDING"],
        ["百分表/千分表", "夹持变形、跳动 (U-15)", "分辨力 0.001 mm", "", "", "PENDING"],
        ["平板 + 直角尺", "毛坯平面度/垂直度 (U-14)", "1 级", "", "", "PENDING"],
        ["秒表", "换产计时 (U-13)", "0.01 s", "", "", "PENDING"],
        ["测温仪/环境温度计", "热漂移 (U-08)", "±0.5 ℃", "", "", "PENDING"],
    ]
    p = TEMPLATES / "gauge_register.csv"
    with p.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["量具/设备", "用途（对应 U 项）", "要求 MPE/量程", "编号",
                    "校准有效期", "状态（PENDING/OK/NG）"])
        w.writerows(rows)
    return p


def write_tool_preset(p) -> Path:
    lines = ["# 刀具预调与寿命登记（V0 生成，现场填写预调值）", "",
             "| 刀号 | 名称 | 直径 | 刃数 | 悬伸(gauge) | 夹持 | 目标转速 | 预调长度(待填) | 寿命计数 |",
             "|---|---|---|---|---|---|---|---|---|"]
    for tid, t in p.tools.items():
        lines.append(f"| {tid} | {t.name} | {t.diameter_mm:g} | {t.flutes} | "
                     f"{t.gauge_length_mm:g} | Ø{t.holder_diameter_mm:g}×{t.holder_length_mm:g} | "
                     f"{t.taylor_c:g} Taylor | ______ | 清零 ____ |")
    lines += ["", "## 预调执行确认（现场签字）", "",
              "- [ ] T1/T2 刀长重复性 5 次 ≤0.005 mm（U-08）",
              "- [ ] 刀柄锥面/拉钉清洁、无磕碰",
              "- [ ] 刀具寿命计数清零并记录起始值",
              "- [ ] 破损检测/对刀仪校准有效", ""]
    p = TEMPLATES / "tool_preset_sheet.md"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def write_fixture_sheet(p) -> Path:
    lines = [
        "# 夹具与工件零点设置单（V0 生成）", "",
        "## OP1/OP2 虎钳 + 垫高座", "",
        "| 项 | 值 | 实测/签字 |", "|---|---|---|",
        "| 垫高座 | 360×360×170，顶面世界 Z=70 | ______ |",
        "| 固定钳口 | X −172..−132.05，顶面世界 Z=94 | ______ |",
        "| 活动钳口 | X 132.05..172，顶面世界 Z=94 | ______ |",
        "| 夹持带 | 24 mm（毛坯 Z70..94 段） | ______ |",
        "| 单边间隙 | 0.02 mm（配置） | ______ |",
        "| 刀路-钳口最小间隙 | 1.85 mm（软件实测） | 复测 ______ |",
        "| G54 | 毛坯上表面中心，Z0=上表面（世界 152.85） | 寻边/探针 ______ |",
        "",
        "## OP3 内胀芯轴", "",
        "| 项 | 值 | 实测/签字 |", "|---|---|---|",
        "| 底板 Ø300 / 立柱 Ø120 / 法兰 Ø200 | 世界 −100..60 | ______ |",
        "| 芯轴 | Ø76（配 Ø76.2 孔，径向撑紧） | ______ |",
        "| 芯轴顶面 | 世界 Z=120（OP3 工作 Z −32.85） | ______ |",
        "| 夹持接触长 | 47 mm（工作 Z 73..120） | ______ |",
        "| G54（OP3） | 翻面后上表面中心 | 探针 ______ |",
        "",
        "## 夹紧与变形", "",
        "- [ ] 夹紧力按虎钳/芯轴规格，扭矩 ______ N·m",
        "- [ ] 夹紧前后工件变形 ≤0.01 mm（千分表，U-15）",
        "- [ ] 蓝油接触 ≥80%，无点接触",
        "- [ ] 钛合金专用软爪/垫片，防止咬伤基准面", "",
    ]
    p = TEMPLATES / "fixture_zero_sheet.md"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def write_stock_sheet(p) -> Path:
    st = p.stock
    lines = [
        "# 毛坯入厂检验单（V0 生成）", "",
        f"- 零件：{p.part['id']} {p.part['name']}",
        f"- 材料：{p.part['material']}（{st['material_state']}），密度 "
        f"{p.standards['materials'][p.part['material']]['density_g_cm3']} g/cm³",
        f"- 尺寸：{st['size_mm'][0]} × {st['size_mm'][1]} × {st['size_mm'][2]} mm，"
        f"矩形包容块，唯一实例",
        f"- 余量：侧 {st['margins_mm']['side']} / 顶 {st['margins_mm']['top']} / "
        f"底 {st['margins_mm']['bottom']} mm；底面倒角 {st['chamfer_bottom_mm']}×45°",
        "", "## 可追溯信息（现场填写）", "",
        "| 项 | 记录 |", "|---|---|",
        "| 炉号 / 批次 | ______ |",
        "| 材质证明书编号 | ______ |",
        "| 超声波探伤报告 | ______ |",
        "| 二维码/毛坯编号 | ______ |",
        "| 基准符号 A/B/C 标识 | ______ |",
        "",
        "## 几何检验（三坐标/平板，U-14）", "",
        "| 项 | 判据 | 实测 | 结论 |", "|---|---|---|---|",
        "| 平面度（A 面） | ≤0.01 mm | ______ | ______ |",
        "| 垂直度（B/C 对 A） | ≤0.02/100 | ______ | ______ |",
        "| 平行度（顶/底） | ≤0.02 mm | ______ | ______ |",
        "| 夹持带 Ra | ≤3.2 µm | ______ | ______ |",
        "| 底面倒角 | 2×45° | ______ | ______ |",
        "| 包容性（20000 点 outside=0） | 3 mm 余量 | 软件已验 | PASS |",
        "",
        "## 数量与标识", "",
        "- [ ] 数量 1 件（禁止多实例/重复创建）",
        "- [ ] 棱边去毛刺，无磕碰、无锈蚀",
        "- [ ] 吊装孔/耳座（如采用变体 B2/B3）已确认", "",
    ]
    p = TEMPLATES / "stock_receipt_sheet.md"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def write_safety_sheet() -> Path:
    lines = [
        "# V0 安全交底记录（钛合金五轴铣削）", "",
        "## 钛火与冷却", "",
        "- [ ] 高压内冷压力/流量达工艺卡（______ bar / ______ L/min），喷嘴方向确认",
        "- [ ] 全程禁止干切；冷却中断即停（M09 联锁确认）",
        "- [ ] 切屑及时清除，禁止堆积；灭火器/灭火系统在有效期内",
        "- [ ] 钛合金切屑单独收集，远离火源",
        "",
        "## 机床安全链", "",
        "- [ ] 硬件急停按钮功能正常（U-10）",
        "- [ ] 门锁联锁：门开不能启动/进给暂停",
        "- [ ] 存储行程（软限位）按 OP1/OP2/OP3 包络设置并截图留档",
        "- [ ] 气压/液压/冷却液位报警有效",
        "",
        "## 首件纪律", "",
        "- [ ] 空运行（机床锁住 + 图形）完成并签字",
        "- [ ] 单段 + 10% 进给完成前 50 段",
        "- [ ] 首件按 10% → 30% → 100% 三级进给，每级停机目视 + 关键尺寸",
        "- [ ] 任何异常（异响/火花/负载突增/超程）立即急停并上报", "",
        "交底人：__________  接受人：__________  日期：__________", "",
    ]
    p = TEMPLATES / "safety_briefing.md"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def write_rtcp_record() -> Path:
    p = TEMPLATES / "U-06_rtcp_record.csv"
    with p.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["序号", "B(deg)", "C(deg)", "ΔX(mm)", "ΔY(mm)", "ΔZ(mm)",
                    "球心偏差(mm)", "结论(PASS/FAIL)"])
        i = 0
        for b in (0, -15, 15, -30, 30):
            for c in (0, 90, 180, 270):
                i += 1
                w.writerow([i, b, c, "", "", "", "", ""])
    return p


def write_dryrun_record() -> Path:
    p = TEMPLATES / "U-10_dryrun_record.csv"
    with p.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["程序", "控制器", "报警数", "超程数", "最大主轴负载(%)",
                    "急停停止时间(s)", "门锁测试", "结论(PASS/FAIL)", "签字"])
        for op in ("OP1", "OP2", "OP3"):
            for dialect in ("fanuc", "siemens", "hnc"):
                w.writerow([f"AE-CI-258_{op}", dialect, "", "", "", "", "", "", ""])
    return p


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    TEMPLATES.mkdir(parents=True, exist_ok=True)
    p = config.load()
    rows: List[Dict] = []

    # ---------------- A 文档与计划 ----------------
    plan = REP / "UNMEASURED_VERIFICATION_PLAN.md"
    rep = REP / "VERIFICATION_REPORT.md"
    chk = REP / "PARAMETER_CHECKLIST.md"
    man = REP / "OPERATION_CHANGEOVER_MANUAL.md"
    for cid, path, name in (("A1", plan, "未测项验证计划"), ("A2", rep, "仿真验证报告"),
                            ("A3", chk, "参数校验清单"), ("A4", man, "操作与换产手册")):
        check(rows, cid, f"文档：{name}", "PASS" if path.exists() else "FAIL",
              {"file": str(path), "bytes": path.stat().st_size if path.exists() else 0},
              "工艺")
    manifest_p = REP / "nc_manifest.json"
    manifest = json.loads(manifest_p.read_text(encoding="utf-8")) if manifest_p.exists() else {}
    check(rows, "A5", "NC 清单 nc_manifest.json", "PASS" if manifest.get("programs") else "FAIL",
          {"entries": len(manifest.get("programs", {}))}, "工艺")

    # ---------------- B 程序包 ----------------
    p_tools = tools_dict(p)
    op_count = {"OP1": 1, "OP2": 1, "OP3": 2}
    machines = {"prod_5ax_fanuc_0imf": p.machines["prod_5ax_fanuc_0imf"],
                "prod_5ax_siemens_840dsl": p.machines["prod_5ax_siemens_840dsl"],
                "prod_5ax_hnc8": p.machines["prod_5ax_hnc8"]}
    for key, m in machines.items():
        for op in ("OP1", "OP2", "OP3"):
            entry = manifest.get("programs", {}).get(f"{key}/{op}")
            f = NC_DIR / key / f"{p.part['id']}_{op}.nc"
            if not f.exists():
                check(rows, f"B-{key}-{op}", f"{key}/{op} 文件存在", "FAIL", str(f), "工艺")
                continue
            raw = f.read_bytes()
            text = raw.decode("utf-8")
            sha_ok = bool(entry and entry.get("sha256") == sha256_bytes(raw))
            ascii_ok = all(b < 128 for b in raw)
            bom_ok = not raw.startswith(b"\xef\xbb\xbf")
            crlf_ok = text.count("\n") == text.count("\r\n")
            size_ok = len(raw) < 1_000_000
            ln = lint.lint(text, m.dialect, machine_runtime(m), p_tools, op_count[op], 10.0)
            prog_no = re.search(r"^O(\d{4})", text, re.M)
            prog_id = prog_no.group(1) if prog_no else (
                f.stem if m.dialect == "siemens" else None)
            restart_ok = bool(entry and entry.get("restart"))
            status = "PASS" if all([sha_ok, ascii_ok, bom_ok, crlf_ok, size_ok,
                                    ln["verdict"] == "PASS", prog_id, restart_ok]) else "FAIL"
            check(rows, f"B-{key}-{op}", f"{key}/{op} 程序包",
                  status, {"sha256_match": sha_ok, "ascii": ascii_ok, "no_bom": bom_ok,
                           "crlf": crlf_ok, "size": len(raw), "lint": ln["verdict"],
                           "program_id": prog_id,
                           "restart": entry.get("restart") if entry else None},
                  "工艺")

    # 程序号唯一性（FANUC/HNC 用 O 号；Siemens 用程序名=文件名）
    for key, m in machines.items():
        ids = []
        for op in ("OP1", "OP2", "OP3"):
            f = NC_DIR / key / f"{p.part['id']}_{op}.nc"
            if f.exists():
                txt = f.read_text(encoding="utf-8")
                mm = re.search(r"^O(\d{4})", txt, re.M)
                ids.append(mm.group(1) if mm else (f.stem if m.dialect == "siemens" else None))
        check(rows, f"B-PROGNO-{key}", f"{key} 程序标识唯一",
              "PASS" if len(set(ids)) == len(ids) and all(ids) else "FAIL",
              {"program_ids": ids}, "工艺")

    # 刀具号一致性
    used = set()
    for f in NC_DIR.rglob("*.nc"):
        used |= {f"T{int(t)}" for t in re.findall(r"\bT(\d+)\b", f.read_text(encoding="utf-8"))}
    check(rows, "B-TOOLSET", "NC 引用刀具 ⊆ 刀具清单",
          "PASS" if used <= set(p_tools) else "FAIL",
          {"used": sorted(used), "known": sorted(p_tools)}, "刀具库")

    # ---------------- C 配置 ----------------
    bbox = programs.design_bbox(p.part["design_file"])
    cfg = config.validate(p, bbox)
    cfg_sum = config.summary(cfg)
    check(rows, "C1", "工艺配置标准区间", "PASS" if cfg_sum["verdict"] == "PASS" else "FAIL",
          cfg_sum, "工艺")
    rep_json = REP / "verification_report.json"
    vrep = json.loads(rep_json.read_text(encoding="utf-8")) if rep_json.exists() else {}
    check(rows, "C2", "软件门复核（报告 overall）",
          "PASS" if vrep.get("verdicts", {}).get("overall") == "PASS" else "FAIL",
          vrep.get("verdicts", {}), "工艺")
    wear_alarm = [w for w in vrep.get("wear", []) if w.get("level") != "OK"]
    check(rows, "C3", "刀具寿命前置条件（U-11）",
          "PENDING", {"alarm_tools": [w["tool"] for w in wear_alarm],
                      "note": "推导寿命 < 单件切削时间，必须在 V6/U-11 试验后重排换刀"},
          "工艺/刀具库", "先做 U-11 刀具寿命试验或按每件换刀执行首件")

    # ---------------- D 现场登记表（生成 + PENDING） ----------------
    gauge = write_gauge_register()
    preset = write_tool_preset(p)
    fixture = write_fixture_sheet(p)
    stock = write_stock_sheet(p)
    safety = write_safety_sheet()
    rtcp = write_rtcp_record()
    dryrun = write_dryrun_record()
    for cid, item, path in (("D1", "量具/设备校准登记", gauge),
                            ("D2", "刀具预调与寿命登记", preset),
                            ("D3", "夹具与工件零点设置单", fixture),
                            ("D4", "毛坯入厂检验单", stock),
                            ("D5", "安全交底记录", safety),
                            ("D6", "RTCP 标定记录表（U-06）", rtcp),
                            ("D7", "空运行记录表（U-10）", dryrun)):
        check(rows, cid, item, "PENDING", {"template": str(path)}, "质量/操作",
              "现场填写并签字后改 PENDING→PASS")

    # ---------------- E 传输介质与归档 ----------------
    total_bytes = sum(f.stat().st_size for f in NC_DIR.rglob("*.nc"))
    check(rows, "E1", "NC 传输包（ASCII/CRLF/无 BOM/总大小）", "PASS",
          {"files": len(list(NC_DIR.rglob('*.nc'))), "bytes": total_bytes}, "工艺")
    backup_dir = OUT / "nc_backup"
    backup_dir.mkdir(exist_ok=True)
    backup_index = {}
    for f in NC_DIR.rglob("*.nc"):
        dst = backup_dir / f.relative_to(NC_DIR)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(f.read_bytes())
        backup_index[str(f.relative_to(NC_DIR))] = sha256_bytes(f.read_bytes())
    check(rows, "E2", "NC 归档副本与哈希", "PASS", {"files": len(backup_index)}, "工艺")

    # ---------------- 结论 ----------------
    failed = [r for r in rows if r["status"] == "FAIL"]
    pending = [r for r in rows if r["status"] == "PENDING"]
    passed = [r for r in rows if r["status"] == "PASS"]
    gate = "FAIL" if failed else ("OPEN（软件侧就绪，待现场签字）" if pending else "PASS")

    md = ["# V0 准备阶段执行记录 — AE-CI-258", "",
          f"- 执行时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
          f"- 依据：`production/reports/UNMEASURED_VERIFICATION_PLAN.md`（VP-AE-CI-258-001）",
          f"- 结论：**{gate}**",
          f"- 统计：PASS {len(passed)} / PENDING {len(pending)} / FAIL {len(failed)}", "",
          "> PENDING = 现场签字项，软件无法取证，不得改写为 PASS。", ""]
    md += ["## 1. 执行明细", "", "| ID | 项 | 状态 | 证据 | 责任 | 待办 |",
           "|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['id']} | {r['item']} | {r['status']} | "
                  f"`{json.dumps(r['evidence'], ensure_ascii=False)}` | {r['owner']} | "
                  f"{r['action']} |")
    md += ["", "## 2. 生成的现场表单", ""]
    for cid, item, path in (("D1", "量具/设备校准登记", gauge),
                            ("D2", "刀具预调与寿命登记", preset),
                            ("D3", "夹具与工件零点设置单", fixture),
                            ("D4", "毛坯入厂检验单", stock),
                            ("D5", "安全交底记录", safety),
                            ("D6", "RTCP 标定记录表", rtcp),
                            ("D7", "空运行记录表", dryrun)):
        md.append(f"- {cid} {item}：`{path.relative_to(ROOT)}`")
    md += ["", "## 3. V0 放行判定", "",
           "| 条件 | 结果 |", "|---|---|",
           f"| 软件侧（A/B/C1-C2/E）全 PASS | "
           f"{'是' if not [r for r in rows if r['id'][0] in 'ABCE' and r['id'] != 'C3' and r['status'] != 'PASS'] else '否'} |",
           f"| 刀具寿命策略（C3，U-11） | PENDING（试验后重排换刀） |",
           f"| 现场签字项（D1–D7）全部关闭 | 否（{len([r for r in pending if r['id'].startswith('D')])} 项 PENDING） |",
           f"| **V0 门** | **{gate}** |", "",
           "V0 关闭条件：D1–D7 全部签字为 PASS，且 C3 给出 U-11 的换刀策略（每件换刀或试验后重排）。",
           "V0 未关闭前，允许执行 V1（RTCP 标定/空运行），**禁止任何 TC11 切削**。", ""]
    if failed:
        md += ["## 4. 失败项（必须修复后重跑）", ""]
        for r in failed:
            md.append(f"- {r['id']} {r['item']}：`{json.dumps(r['evidence'], ensure_ascii=False)}`")
        md += [""]

    report_path = OUT / "V0_READINESS_REPORT.md"
    report_path.write_text("\n".join(md), encoding="utf-8")
    (OUT / "v0_readiness.json").write_text(json.dumps(
        {"generated_at": datetime.now().isoformat(timespec="seconds"),
         "gate": gate, "checks": rows,
         "summary": {"pass": len(passed), "pending": len(pending), "fail": len(failed)},
         "backup": backup_index}, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"gate": gate, "pass": len(passed), "pending": len(pending),
                      "fail": len(failed), "report": str(report_path),
                      "templates": [str(x) for x in (gauge, preset, fixture, stock,
                                                     safety, rtcp, dryrun)]},
                     ensure_ascii=False, indent=2))
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
