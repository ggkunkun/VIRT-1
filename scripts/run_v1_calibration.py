# -*- coding: utf-8 -*-
"""V1 五轴标定阶段执行器（U-06 / U-07 / U-08）。

生成三套标定 NC（FANUC 0i-MF / HNC-8 / SINUMERIK 840D sl）、逐份审查、行程包络校核、
Siemens 方向矢量一致性校核、证据表模板，并对已填证据计算 G1 门。

用法: .venv/Scripts/python.exe scripts/run_v1_calibration.py
"""
from __future__ import annotations

import csv
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from virtu_prod import calibration as cal, config, lint, post  # noqa: E402

OUT = ROOT / "production" / "v1"
NC_DIR = OUT / "nc"
TEMPLATES_DIR = OUT / "templates"
EVID = OUT / "evidence"


def _f(v: float) -> str:
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "", "-") else s


def _f6(v: float) -> str:
    s = f"{v:.6f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "", "-") else s


def gen_fanuc(number: int, tag: str) -> str:
    L: List[str] = ["%", f"O{number} (RTCP BALL TEST - {tag})",
                    "(SPHERE D50 AT G54 ORIGIN / CENTER 150MM ABOVE TABLE)",
                    "(G54 = SPHERE CENTER / INDICATOR OR PROBE IN T1 / SPINDLE OFF)",
                    "(20 ORIENTATIONS: B 0,+/-15,+/-30 / C 0,90,180,270)"]
    n = 0

    def code(text: str) -> None:
        nonlocal n
        n += 10
        L.append(f"N{n} {text}")

    code("G21 G17 G40 G49 G80 G90")
    code("G54")
    code("M01")
    code("G00 G90 G49 Z240.")
    code("G00 B0. C0.")
    code("G00 X0 Y0")
    code("T1 M06")
    code("G43.4 H1 (TCPM ON)")
    code("G00 Z10.")
    code("G01 Z0 F100.")
    for i, (b, c) in enumerate(cal.orientations(), 1):
        L.append(f"(--- {i:02d}  B{b:g} C{c:g} ---)")
        code(f"G01 B{_f(b)} C{_f(c)} F100.")
    code("G49")
    code("G00 Z240.")
    code("M30")
    L.append("%")
    return "\n".join(L) + "\n"


def gen_siemens() -> str:
    L: List[str] = [";RTCP BALL TEST / SINUMERIK 840D sl / TRAORI",
                    ";SPHERE D50 AT G54 ORIGIN / CENTER 150MM ABOVE TABLE",
                    ";G54 = SPHERE CENTER / INDICATOR OR PROBE IN T1 / SPINDLE OFF",
                    "N10 G71 G90 G17 G40 G54", "N20 M01", "N30 G0 Z240", "N40 B0 C0",
                    "N50 G0 X0 Y0", "N60 T1 D1 M6", "N70 TRAORI", "N80 G0 Z10",
                    "N90 G1 Z0 F100"]
    for i, (b, c) in enumerate(cal.orientations(), 1):
        ax, ay, az = post.tool_axis(b, c)
        L.append(f";--- {i:02d}  B{b:g} C{c:g} ---")
        L.append(f"N{100 + i * 10} G1 A3={_f6(ax)} B3={_f6(ay)} "
                 f"C3={_f6(az)} F100")
    L += ["N900 TRAFOOF", "N910 G0 Z240", "N920 M30"]
    return "\n".join(L) + "\n"


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


DATA_COLUMNS = {
    "U-06_rtcp_record.csv": ["ΔX(mm)", "ΔY(mm)", "ΔZ(mm)", "球心偏差(mm)",
                             "结论(PASS/FAIL)"],
    "U-07_siemens_orientation.csv": ["指示表极差(mm)", "结论(PASS/FAIL)"],
    "U-08_repeatability.csv": ["刀长(mm)"],
    "U-08_thermal.csv": ["Z(mm)"],
    "U-08_backlash.csv": ["正向角(deg)", "反向角(deg)"],
    "SESSION_META.csv": ["操作者", "复核人", "日期"],
}


def _has_data(path: Path) -> bool:
    """数据列是否有任何已填内容；用于保护现场已填记录不被模板覆盖。"""
    cols = DATA_COLUMNS.get(path.name, [])
    for r in cal.read_csv(path):
        if any((r.get(c) or "").strip() for c in cols):
            return True
    return False


def write_evidence_templates(target: Path) -> List[Path]:
    """生成 U-06/U-07/U-08 数据记录模板（target 目录内）。"""
    target.mkdir(parents=True, exist_ok=True)
    paths = []

    p = target / "U-06_rtcp_record.csv"
    with p.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["序号", "B(deg)", "C(deg)", "ΔX(mm)", "ΔY(mm)", "ΔZ(mm)",
                    "球心偏差(mm)", "结论(PASS/FAIL)", "备注"])
        for i, (b, c) in enumerate(cal.orientations(), 1):
            w.writerow([i, b, c, "", "", "", "", "", ""])
    paths.append(p)

    p = target / "U-07_siemens_orientation.csv"
    with p.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["序号", "B(deg)", "C(deg)", "A3(期望)", "B3(期望)", "C3(期望)",
                    "指示表极差(mm)", "结论(PASS/FAIL)", "备注"])
        for i, (b, c) in enumerate(cal.orientations(), 1):
            ax, ay, az = post.tool_axis(b, c)
            vals = [0.0 if abs(v) < 1e-12 else round(v, 6) for v in (ax, ay, az)]
            w.writerow([i, b, c, vals[0], vals[1], vals[2], "", "", ""])
    paths.append(p)

    p = target / "U-08_repeatability.csv"
    with p.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["次数", "刀具", "刀长(mm)", "备注"])
        for i in range(1, 6):
            w.writerow([i, "T1", "", ""])
    paths.append(p)

    p = target / "U-08_thermal.csv"
    with p.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["时间(min)", "Z(mm)", "环境温度(℃)", "备注"])
        for t in (0, 10, 20, 30, 40, 50, 60):
            w.writerow([t, "", "", ""])
    paths.append(p)

    p = target / "U-08_backlash.csv"
    with p.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["序号", "轴(B/C)", "正向角(deg)", "反向角(deg)", "备注"])
        for i in range(1, 11):
            w.writerow([i, "B" if i % 2 else "C", "", ""])
    paths.append(p)

    p = target / "SESSION_META.csv"
    with p.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["机床编号", "控制器", "球心机床坐标", "环境温度(℃)", "仪器编号",
                    "校准有效期", "操作者", "复核人", "日期", "备注"])
        w.writerow(["", "", "X100 Y0 Z50", "", "", "", "", "", "", ""])
    paths.append(p)

    paths.append(write_record_guide(target))
    return paths


def write_record_guide(target: Path) -> Path:
    p = target / "U-06_U-08_RECORD_GUIDE.md"
    lines = [
        "# U-06 / U-07 / U-08 现场标定数据记录指引", "",
        "> 适用：AE-CI-258 五轴标定（V1）。填写前先复制本目录到"
        "`production/v1/evidence/`，**已填写的记录不得被脚本覆盖**。", "",
        "## 0. 会话信息（填 SESSION_META.csv）", "",
        "| 字段 | 要求 |", "|---|---|",
        "| 机床编号 / 控制器 | 与 `production/config/machines.yml` 一致 |",
        "| 球心机床坐标 | 固定为 X100 Y0 Z50（台面上方 150 mm） |",
        "| 环境温度 | 标定开始与结束各记一次 |",
        "| 仪器编号 / 校准有效期 | 千分表、标准球、测头、对刀仪 |",
        "| 操作者 / 复核人 / 日期 | 签字，缺一不可 |", "",
        "## 1. U-06 RTCP 球心偏差（20 行）", "",
        "- 运行 `RTCP_BALL_TEST_FANUC.nc` / `_HNC.nc`；G54 = 球心，T1 = 千分表或测头。",
        "- 每个姿态记录球心相对标称位置的偏差 **ΔX/ΔY/ΔZ（机床坐标，mm，带符号）**。",
        "- 符号约定：机床正方向为正；同一姿态重复测 2 次取平均，超差 0.02 mm 需重测。",
        "- 判据：脚本按 `Δ_i=(R_B(B_i)R_C(C_i)−I)·e` 最小二乘反算枢轴偏置 e，"
        "**残差最大 ≤0.050 mm**。", "",
        "## 2. U-07 Siemens 方向（20 行）", "",
        "- 运行 `RTCP_BALL_TEST_SIEMENS.nc`；T1 = 千分表，测头压在 Ø50 标准块端面。",
        "- 每个姿态让主轴绕端面扫一圈，记录指示表 **极差（max−min，mm）**，不是绝对读数。",
        "- 判据：角偏差 `atan(极差/50) ≤0.050°`。期望 A3/B3/C3 已预填，供现场核对方向符号。", "",
        "## 3. U-08 刀长重复性（5 行）", "",
        "- 同一把 T1 连续换刀 5 次，每次用对刀仪/机内测头测刀长。",
        "- 判据：5 次 **极差 ≤0.005 mm**。", "",
        "## 4. U-08 热漂移（7 行）", "",
        "- 主轴按 OP1 转速（700 rpm）连续运转 60 min；每 10 min 测一次标准球 Z。",
        "- 判据：**漂移 ≤0.020 mm**。", "",
        "## 5. U-08 反向间隙（10 行）", "",
        "- B/C 各往返 10 次，从控制器位置显示读取正向/反向到位角。",
        "- 判据：**|反向−正向| ≤0.010°**。", "",
        "## 6. 合格判据汇总", "",
        "| 项 | 判据 | 失败处置 |", "|---|---|---|",
        "| U-06 RTCP 残差 | ≤0.050 mm | 查枢轴参数/刀长基准，重标；连续 2 次不收敛停线 |",
        "| U-07 刀轴角偏差 | ≤0.050° | 核对 A3/B3/C3 符号与 B/C 映射 |",
        "| U-08 刀长重复性 | ≤0.005 mm | 检查刀柄锥面/拉钉 |",
        "| U-08 热漂移 | ≤0.020 mm | 延长预热或加在线补偿 |",
        "| U-08 反向间隙 | ≤0.010° | 机床参数补偿/检修 |", "",
        "## 7. 签字", "",
        "| 角色 | 姓名 | 日期 | 签字 |", "|---|---|---|---|",
        "| 操作者 |  |  |  |", "| 复核（工艺） |  |  |  |",
        "| 批准（质量） |  |  |  |", "",
        "> 填写完成后运行 `python scripts/run_v1_calibration.py`，G1 门自动判定；"
        "任何 FAIL 禁止进入 V2/切削。", "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    NC_DIR.mkdir(parents=True, exist_ok=True)
    p = config.load()
    m = p.machines["prod_5ax_fanuc_0imf"]
    mach = machine_runtime(m)

    progs = {"fanuc": gen_fanuc(9101, "FANUC 0i-MF"),
             "hnc": gen_fanuc(9102, "HNC-8"),
             "siemens": gen_siemens()}
    checks: List[Dict] = []
    for dialect, text in progs.items():
        path = NC_DIR / f"RTCP_BALL_TEST_{dialect.upper()}.nc"
        path.write_text(text, encoding="utf-8", newline="\r\n")
        res = lint.lint(text, dialect, mach, tools_dict(p), 1, 10.0,
                        require_spindle=False)
        checks.append({"id": f"V1-NC-{dialect}", "item": f"{dialect} 标定程序审查",
                       "status": "PASS" if res["verdict"] == "PASS" else "FAIL",
                       "evidence": {"file": str(path), "failed": res["failed_gates"]}})

    # 行程包络（球心在机床坐标的 20 个姿态）
    pos = cal.sphere_positions()
    xs = [q["machine"][0] for q in pos]
    ys = [q["machine"][1] for q in pos]
    zs = [q["machine"][2] for q in pos]
    tr = m.travel_mm
    in_env = (min(xs) >= tr["x"][0] and max(xs) <= tr["x"][1]
              and min(ys) >= tr["y"][0] and max(ys) <= tr["y"][1]
              and min(zs) >= tr["z"][0] and max(zs) <= tr["z"][1])
    checks.append({"id": "V1-ENVELOPE", "item": "20 姿态球心在机床行程内",
                   "status": "PASS" if in_env else "FAIL",
                   "evidence": {"x": [round(min(xs), 1), round(max(xs), 1)],
                                "y": [round(min(ys), 1), round(max(ys), 1)],
                                "z": [round(min(zs), 1), round(max(zs), 1)],
                                "travel": tr}})

    # Siemens 方向矢量一致性（发射值 vs 解析值，单位长度）
    siemens_text = progs["siemens"]
    mismatch = []
    for i, (b, c) in enumerate(cal.orientations(), 1):
        ax, ay, az = post.tool_axis(b, c)
        line = re.search(rf"N{100 + i * 10} G1 A3=([-\d.]+) B3=([-\d.]+) C3=([-\d.]+)",
                         siemens_text)
        if not line:
            mismatch.append({"i": i, "reason": "line missing"})
            continue
        got = [float(line.group(k)) for k in (1, 2, 3)]
        exp = [round(v, 6) for v in (ax, ay, az)]
        norm = math.sqrt(sum(v * v for v in got))
        if max(abs(g - e) for g, e in zip(got, exp)) > 2e-6 or abs(norm - 1.0) > 1e-5:
            mismatch.append({"i": i, "got": got, "expected": exp, "norm": round(norm, 6)})
    checks.append({"id": "V1-ORIENTATION", "item": "Siemens A3/B3/C3 与 B/C 映射一致",
                   "status": "PASS" if not mismatch else "FAIL",
                   "evidence": {"mismatch": mismatch[:5], "count": len(mismatch),
                                "orientations": 20}})

    templates = write_evidence_templates(TEMPLATES_DIR)
    EVID.mkdir(parents=True, exist_ok=True)
    delivered = []
    for t in templates:
        dst = EVID / t.name
        if (not dst.exists()) or (not _has_data(dst)):
            dst.write_bytes(t.read_bytes())
        delivered.append(dst)
    ev = cal.evaluate_evidence(EVID)
    for key, item in ev["items"].items():
        checks.append({"id": f"V1-{key}", "item": f"证据 {key}", "status": item["status"],
                       "evidence": item})

    failed = [c for c in checks if c["status"] == "FAIL"]
    pending = [c for c in checks if c["status"] == "PENDING"]
    passed = [c for c in checks if c["status"] == "PASS"]
    gate = "FAIL" if failed else ("PASS" if not pending else "OPEN（软件侧就绪，待现场标定）")

    md = ["# V1 五轴标定阶段执行记录 — AE-CI-258", "",
          f"- 执行时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
          "- 依据：`production/reports/UNMEASURED_VERIFICATION_PLAN.md` §U-06/U-07/U-08",
          f"- 结论：**{gate}**",
          f"- 统计：PASS {len(passed)} / PENDING {len(pending)} / FAIL {len(failed)}", "",
          "> 物理标定必须由持证人员在机床上执行；本执行器只负责程序、判据、记录与反算。", ""]
    md += ["## 1. 执行明细", "", "| ID | 项 | 状态 | 证据 |", "|---|---|---|---|"]
    for c in checks:
        md.append(f"| {c['id']} | {c['item']} | {c['status']} | "
                  f"`{json.dumps(c['evidence'], ensure_ascii=False)}` |")
    md += ["", "## 2. 标定程序", "",
           "| 控制器 | 文件 | 说明 |", "|---|---|---|",
           f"| FANUC 0i-MF | `{NC_DIR / 'RTCP_BALL_TEST_FANUC.nc'}` | G43.4 H1，20 姿态 |",
           f"| HNC-8 | `{NC_DIR / 'RTCP_BALL_TEST_HNC.nc'}` | G43.4 H1，20 姿态 |",
           f"| SINUMERIK 840D sl | `{NC_DIR / 'RTCP_BALL_TEST_SIEMENS.nc'}` | TRAORI + A3/B3/C3 |",
           "", "> 球心装在机床坐标 (100, 0, 50)：台面上方 150 mm，偏离 B 轴枢轴，旋转时才会暴露标定误差。",
           "> 程序只把 TCP 定位到球心并旋转 B/C；偏差由千分表/测头读取，填入证据表。", ""]
    md += ["## 3. 证据表（现场填写，不覆盖已填）", "",
           f"空白模板：`{TEMPLATES_DIR.relative_to(ROOT)}`（每次运行重建）；"
           f"填写副本：`{EVID.relative_to(ROOT)}`（已存在则保留）", ""]
    for t in delivered:
        md.append(f"- `{t.relative_to(ROOT)}`")
    md += ["", "## 4. G1 判定逻辑", "",
           "- U-06：Δ_i = (R_B(B_i)R_C(C_i) − I)·e 最小二乘反算枢轴偏置 e；残差最大值 ≤0.050 mm 判 PASS",
           "- U-07：Ø50 端面打表极差 δ → 刀轴角偏差 atan(δ/50) ≤0.050° 判 PASS（矢量映射已由软件校核）",
           "- U-08：刀长重复性 ≤0.005 mm；60 min 热漂移 ≤0.020 mm；B/C 反向间隙 ≤0.010°",
           f"- 现场证据门（U-06/U-07/U-08）：**{ev['gate']}**", ""]
    md += ["## 5. 现场步骤（摘要）", "",
           "1. 机床预热 ≥30 min；工作台清理，拆下虎钳/工件，只保留球座。",
           "2. 标准球装在工作台中心偏置位置（机床 X100/Y0/Z50），千分表找正球座。",
           "3. 设置 G54 = 球心；T1 装千分表/测头并按球心对刀（H1）。",
           "4. 单段运行标定程序，逐姿态记录球心偏差（U-06）或指示表偏差（U-07）。",
           "5. 执行 U-08：5 次换刀测刀长；主轴 60 min 热漂移；B/C 往返 10 次测反向间隙。",
           "6. 填表 → 重跑本脚本 → G1 自动判定。任何 FAIL 禁止进入 V2/切削。", ""]
    report = OUT / "V1_READINESS_REPORT.md"
    report.write_text("\n".join(md), encoding="utf-8")
    (OUT / "v1_readiness.json").write_text(json.dumps(
        {"generated_at": datetime.now().isoformat(timespec="seconds"),
         "gate": gate, "checks": checks,
         "summary": {"pass": len(passed), "pending": len(pending), "fail": len(failed)},
         "sphere_positions": pos}, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"gate": gate, "pass": len(passed), "pending": len(pending),
                      "fail": len(failed), "report": str(report),
                      "nc": [str(x) for x in sorted(NC_DIR.glob('*.nc'))],
                      "templates": [str(t) for t in templates]},
                     ensure_ascii=False, indent=2))
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
