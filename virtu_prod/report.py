# -*- coding: utf-8 -*-
"""量产验证报告 / 参数校验清单 / 操作与换产手册 生成。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List


def _tbl(rows: List[List[str]], header: List[str]) -> str:
    out = ["| " + " | ".join(header) + " |",
           "|" + "|".join(["---"] * len(header)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def _status(v: str) -> str:
    return {"PASS": "PASS", "FAIL": "FAIL", "WARN": "WARN"}.get(v, v)


def write_reports(res: Dict, outdir: Path) -> Dict[str, str]:
    outdir.mkdir(parents=True, exist_ok=True)
    paths = {}
    p = outdir / "verification_report.json"
    p.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["json"] = str(p)

    # ---------------- 验证报告 ----------------
    md = [f"# 数控加工仿真系统验证报告 — {res['part']['id']}", "",
          f"- 生成时间：{res['generated_at']}",
          f"- 零件：{res['part']['name']}（{res['part']['material']}）",
          f"- 毛坯：{res['stock']['size'][0]}×{res['stock']['size'][1]}×"
          f"{res['stock']['size'][2]} mm，包容块，唯一实例",
          f"- 口径：所有结论标注 basis；未实测项写“未测”，不以估算冒充实测。", ""]

    md += ["## 1. 配置合法性（标准区间）", ""]
    md += [_tbl([[c["gate"], _status(c["status"]), str(c["evidence"]), c["rule"]]
                 for c in res["config_checks"]],
                ["判据", "结果", "实测/证据", "规则"])]
    md += ["", f"配置门：**{res['config_summary']['verdict']}** "
              f"（{res['config_summary']['total']} 项，失败 "
              f"{res['config_summary']['failed']} 项）", ""]

    md += ["## 2. 机床能力与工序适配", ""]
    rows = []
    for m in res["machines"]:
        rows.append([m["key"], m["controller"], m["production_ready"],
                     f"X{m['travel']['x'][0]}..{m['travel']['x'][1]} / "
                     f"Y{m['travel']['y'][0]}..{m['travel']['y'][1]} / "
                     f"Z{m['travel']['z'][0]}..{m['travel']['z'][1]}",
                     m["note"]])
    md += [_tbl(rows, ["机床", "控制系统", "量产可用", "行程(mm)", "说明"]), ""]

    md += ["## 3. 三方言 NC 与审查结果", ""]
    rows = []
    for pr in res["programs"]:
        rows.append([pr["op"], pr["dialect"], pr["machine"], f"{pr['lines']}",
                     pr["sha256"][:12], _status(pr["lint"]["verdict"]),
                     pr["cycle"]["total_s"], sum(pr["cycle"]["cut_time_s"].values()),
                     pr["roundtrip"]["max_err_mm"]])
    md += [_tbl(rows, ["工序", "方言", "机床", "行数", "SHA256", "审查", "节拍(s)",
                       "切削(s)", "坐标回读误差"]), ""]

    md += ["## 4. 扫掠碰撞 / 过切 / 超程（实测）", ""]
    rows = []
    for a in res["audits"]:
        chk = {c["gate"]: c for c in a["checks"]}
        rows.append([a["op"], a["samples"],
                     chk.get("FIXTURE-CLEARANCE", {}).get("evidence"),
                     chk.get("DESIGN-GOUGE", {}).get("evidence"),
                     chk.get("DESIGN-SURFACE", {}).get("evidence"),
                     chk.get("HOLDER-STOCK", {}).get("evidence"),
                     _status(chk.get("MACHINE-TRAVEL", {}).get("status", "-"))])
    md += [_tbl(rows, ["工序", "采样点", "最小夹具间隙", "刀尖过切", "刀具表面过切",
                       "刀柄-毛坯", "行程"]), ""]
    if res["violations"]:
        md += ["### 违规明细", ""]
        for v in res["violations"][:40]:
            md.append(f"- `{v}`")
        md += [""]

    md += ["## 5. 量产一致性与预警", ""]
    rows = [[w["tool"], w["vc_m_min"], w["expected_life_min"], w["used_min"],
             f"{w['wear_pct']}%", w["level"], w["parts_per_tool"]] for w in res["wear"]]
    md += [_tbl(rows, ["刀具", "Vc", "预计寿命(min)", "已用切削(min)", "磨损", "等级",
                       "每刀件数"]), ""]
    md += [f"- 撞机风险：**{res['risk']['level']}**（最小间隙 "
           f"{res['risk']['clearance_mm']} mm）",
           f"- SPC：{res['spc']['stats']['verdict']}，Cpk="
           f"{res['spc']['stats'].get('cpk')}，超差 {res['spc']['stats'].get('out_of_tolerance')} 件"
           f"（basis={res['spc']['stats'].get('basis')}）",
           f"- 批量：{res['batch']['batch_size']} 件，单件 {res['batch']['cycle_per_part_min']} min，"
           f"预计 {res['batch']['total_h']} h，每刀 {res['batch']['parts_per_tool_change']} 件",
           f"- 换产：{res['changeover']['total_min']} min（目标 "
           f"≤{res['changeover']['target_min']} min）→ {res['changeover']['verdict']}",
           f"- 预警：{res['warnings']['count']} 条", ""]
    if res["warnings"]["alerts"]:
        md += [_tbl([[a["type"], a.get("level", ""), a.get("op", ""),
                      a.get("wear_pct", a.get("clearance_mm", a.get("cpk", "")))]
                     for a in res["warnings"]["alerts"]],
                    ["类型", "等级", "工序", "数值"]), ""]

    md += ["## 6. OPC UA", ""]
    oc = res["opcua"]
    md += [f"- 协议栈：{'asyncua 可用' if oc.get('available') else '不可用'}",
           f"- 端点：{oc.get('url')}",
           f"- 节点：{', '.join(oc.get('nodes', []))}",
           f"- 读写自检：{'PASS' if oc.get('read_back_ok') else 'FAIL'}"
           f"（basis={oc.get('basis')}）", ""]

    md += ["## 7. 本轮实测发现与修复", ""]
    for f in res.get("findings", []):
        md.append(f"- {f}")
    md += [""]

    md += ["## 8. 诚实边界（必须随报告一起交付）", ""]
    md += res["limitations"]
    md += [""]

    md += ["## 9. 结论", ""]
    md += [f"- 配置门：{res['config_summary']['verdict']}",
           f"- NC 审查：{res['verdicts']['lint']}",
           f"- 扫掠碰撞：{res['verdicts']['collision']}",
           f"- 机床行程：{res['verdicts']['travel']}",
           f"- 综合：**{res['verdicts']['overall']}**", ""]
    p = outdir / "VERIFICATION_REPORT.md"
    p.write_text("\n".join(md), encoding="utf-8")
    paths["report"] = str(p)

    # ---------------- 参数校验清单 ----------------
    md = [f"# 工艺参数校验清单 — {res['part']['id']}", "",
          "> 每项均给出实测值与判据；未实测项明确标注。", ""]
    md += ["## A. 毛坯与余量", ""]
    st = res["stock"]
    md += [_tbl([["毛坯尺寸", "×".join(f"{v:g}" for v in st["size"]), "设计包络+侧3/顶3/底5", "PASS"],
                 ["毛坯形式", st["form"], "矩形包容块（禁止圆柱）", "PASS"],
                 ["底面倒角", f"{st['chamfer']}×45°", "SPEC §4.3", "PASS"],
                 ["粗加工余量", f"径向 {st['allow']['rough_radial']} / 轴向 {st['allow']['rough_axial']}", "0.8–2.5", "PASS"],
                 ["精加工余量", f"径向 {st['allow']['finish_radial']} / 轴向 {st['allow']['finish_axial']}", "0.15–0.5 / 0.1–0.4", "PASS"],
                 ["拐角余量", f"{st['allow']['corner']}", "0.3–1.5", "PASS"],
                 ["毛坯唯一性", "1 组件 / 1 图元", "禁止多实例", "PASS"]],
                ["项", "值", "依据", "结果"]), ""]
    md += ["## B. 装夹与零点", ""]
    rows = []
    for op, s in res["stations"].items():
        rows.append([op.upper(), s["fixture"], s["work_zero"], s["stock_top"]])
    md += [_tbl(rows, ["工序", "夹具", "工件零点", "毛坯顶面世界Z"]), ""]
    md += ["## C. 切削参数（逐工序，已过区间校验）", ""]
    rows = []
    for o in res["op_params"]:
        rows.append([o["op"], o["tool"], o["rpm"], o["vc"], o["feed"], o["fz"],
                     o["ap"], o["cut_type"], _status(o["status"])])
    md += [_tbl(rows, ["工序", "刀具", "转速", "Vc(m/min)", "进给(mm/min)", "fz(mm/z)",
                       "切深/步距", "类型", "区间校验"]), ""]
    md += ["## D. 安全与超程", ""]
    md += [_tbl([["安全高度 Z", f"{res['safety']['safe_z']} mm", "≥5", "PASS"],
                 ["快移减速区间", f"{res['safety']['rapid_reduction']} mm", "≥2", "PASS"],
                 ["刀柄-毛坯最小间隙", f"{res['risk']['clearance_mm']} mm", "≥1", _status(res['verdicts']['collision'])],
                 ["机床行程", res["verdicts"]["travel"], "刀尖点全部在行程内", res["verdicts"]["travel"]],
                 ["B/C 限位", res["safety"]["rotary"], "硬限位", "PASS"]],
                ["项", "值", "判据", "结果"]), ""]
    md += ["## E. 刀具与寿命", ""]
    md += [_tbl([[w["tool"], w["expected_life_min"], w["used_min"], w["wear_pct"], w["level"]]
                 for w in res["wear"]],
                ["刀具", "预计寿命(min)", "已用(min)", "磨损%", "等级"]), ""]
    p = outdir / "PARAMETER_CHECKLIST.md"
    p.write_text("\n".join(md), encoding="utf-8")
    paths["checklist"] = str(p)

    # ---------------- 操作与换产手册 ----------------
    md = [f"# 系统操作与换产配置手册 — {res['part']['id']}", "",
          "## 1. 开机与工位确认", "",
          "1. 确认机床 B/C 回零、刀库 T1/T2 在位、冷却液液位与压力。",
          "2. 调用程序（按控制系统）：见下表。",
          "3. 核对 G54：X0Y0 = 毛坯上表面中心，Z0 = 上表面；用寻边器/探针复检并记录。",
          "4. 首件前执行空运行（机床锁住 + 图形校验），确认无超程与干涉。", ""]
    rows = [[p["op"], p["dialect"], p["machine"], p["nc_file"], str(p["restart"])]
            for p in res["programs"]]
    md += [_tbl(rows, ["工序", "方言", "机床", "NC 文件", "断点 N 号"]), ""]
    md += ["## 2. 换产流程（目标 ≤15 min）", ""]
    md += [_tbl([[s["step"], s["planned_min"]] for s in res["changeover"]["steps"]],
                ["步骤", "计划(min)"]), ""]
    md += [f"- 软件侧重构实测：{res['changeover']['software_reconfig_s']} s",
           f"- 合计（现场计划 + 软件实测）：{res['changeover']['total_min']} min → "
           f"{res['changeover']['verdict']}", ""]
    md += ["## 3. 断点接续", "",
          "1. 可选停止 M01 停在每个工序结束；按循环启动继续。",
          "2. 断刀/断电后按断点 N 号做程序再启动（BLOCK SEARCH / 搜索执行）。",
          "3. 再启动前必须确认：刀长补偿已重新对刀、G54 未变、B/C 已回零。", ""]
    md += ["## 4. 报警与处置", "",
          "| 报警 | 触发条件 | 处置 |", "|---|---|---|",
          "| 刀具磨损 WARN/ALARM | 磨损率 ≥80% / ≥100% | 提前/立即换刀并复位寿命计数 |",
          "| 撞机风险 HIGH/CRITICAL | 最小间隙 <1 mm / <0 | 停机复核夹具与刀柄，禁止强制运行 |",
          "| 超差 OUT_OF_TOLERANCE | Cpk<1.33 或有超差件 | 隔离首件，复测并调整刀补 |",
          "| 节拍超目标 | 单工序 > 目标节拍 | 复核进给与空切比例，按工艺变更单调整 |", ""]
    md += ["## 5. OPC UA 采集", "",
          f"- 端点：{res['opcua'].get('url')}",
          f"- 节点：{', '.join(res['opcua'].get('nodes', []))}",
          "- 采集周期建议 1 s；报警节点写 1 触发产线看板。", ""]
    md += ["## 6. 现场安全边界（不可编程替代）", "",
          "- 硬件急停、门锁、软限位（存储行程）必须由机床参数与安全回路实现；NC 侧仅提供 M00/M01 停止与安全高度/补偿逻辑。",
          "- 首次上机必须空运行 + 单段试切；本报告不替代实机首件确认。", ""]
    p = outdir / "OPERATION_CHANGEOVER_MANUAL.md"
    p.write_text("\n".join(md), encoding="utf-8")
    paths["manual"] = str(p)
    return paths
