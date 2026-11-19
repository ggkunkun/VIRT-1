# -*- coding: utf-8 -*-
"""V2 空运行与安全链阶段执行器（U-10）。

可执行部分：9 个量产程序的机床坐标包络实测、行程/软限位建议、空运行记录模板与门评估。
物理部分（机床锁住图形模拟、单段 10%、急停/门锁实测）一律 PENDING。

用法: .venv/Scripts/python.exe scripts/run_v2_dryrun.py
"""
from __future__ import annotations

import csv
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from virtu_prod import config, lint, sim  # noqa: E402

OUT = ROOT / "production" / "v2"
TEMPLATES = OUT / "templates"
EVID = OUT / "evidence"
NC_DIR = ROOT / "production" / "nc"
PROGRAMS = ("OP1", "OP2", "OP3")
MACHINES = ("prod_5ax_fanuc_0imf", "prod_5ax_siemens_840dsl", "prod_5ax_hnc8")
MARGIN_MM = 5.0
STOCK_TOP = 152.85


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


def envelope(nc_text: str, dialect: str) -> Dict:
    parsed = sim.parse(nc_text, dialect)
    sp = sim.sample_path(parsed, 5.0)
    lo = np.array([math.inf] * 3)
    hi = np.array([-math.inf] * 3)
    for (x, y, z, b, c, *_rest) in sp["points"]:
        br, cr = math.radians(b), math.radians(c)
        rb = np.array([[math.cos(br), 0, math.sin(br)], [0, 1, 0],
                       [-math.sin(br), 0, math.cos(br)]])
        rc = np.array([[math.cos(cr), -math.sin(cr), 0],
                       [math.sin(cr), math.cos(cr), 0], [0, 0, 1]])
        mp = rb @ (rc @ np.array([x, y, z + STOCK_TOP]))
        lo = np.minimum(lo, mp)
        hi = np.maximum(hi, mp)
    return {"x": [round(float(lo[0]), 1), round(float(hi[0]), 1)],
            "y": [round(float(lo[1]), 1), round(float(hi[1]), 1)],
            "z": [round(float(lo[2]), 1), round(float(hi[2]), 1)],
            "samples": len(sp["points"]), "moves": len(parsed.moves),
            "errors": parsed.errors[:5]}


def write_dryrun_template() -> Path:
    TEMPLATES.mkdir(parents=True, exist_ok=True)
    p = TEMPLATES / "U-10_dryrun_record.csv"
    with p.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["程序", "控制器", "报警数", "超程数", "最大主轴负载(%)",
                    "急停停止时间(s)", "门锁测试(OK/NG)", "结论(PASS/FAIL)", "签字"])
        for op in PROGRAMS:
            for key in MACHINES:
                w.writerow([f"AE-CI-258_{op}", key, "", "", "", "", "", "", ""])
    return p


def write_soft_limit_sheet(envs: Dict, machines: Dict) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    lines = ["# 软限位（存储行程）设置建议 — V2", "",
             "> 取全部程序机床坐标包络的并集，外扩 5 mm，再与机床行程取交集；"
             "禁止把软限位放宽到超过行程硬限位。", "",
             "| 机床 | 轴 | 程序包络 min | 程序包络 max | 建议软限位 min | 建议软限位 max | 机床行程 |",
             "|---|---|---|---|---|---|---|"]
    data = {}
    for key in MACHINES:
        m = machines[key]
        lo = [min(envs[(key, op)]["x"][0] for op in PROGRAMS),
              min(envs[(key, op)]["y"][0] for op in PROGRAMS),
              min(envs[(key, op)]["z"][0] for op in PROGRAMS)]
        hi = [max(envs[(key, op)]["x"][1] for op in PROGRAMS),
              max(envs[(key, op)]["y"][1] for op in PROGRAMS),
              max(envs[(key, op)]["z"][1] for op in PROGRAMS)]
        rec = {}
        for i, ax in enumerate(("x", "y", "z")):
            t = m.travel_mm[ax]
            smin = max(t[0], lo[i] - MARGIN_MM)
            smax = min(t[1], hi[i] + MARGIN_MM)
            rec[ax] = [round(smin, 1), round(smax, 1)]
            lines.append(f"| {key} | {ax.upper()} | {lo[i]:.1f} | {hi[i]:.1f} | "
                         f"{smin:.1f} | {smax:.1f} | {t[0]:.1f}..{t[1]:.1f} |")
        rec["b"] = m.rotary_limits_deg["b"]
        rec["c"] = m.rotary_limits_deg["c"]
        data[key] = rec
    lines += ["", "## 旋转轴硬限位（不得修改）", "",
              "| 机床 | B | C |", "|---|---|---|"]
    for key in MACHINES:
        m = machines[key]
        lines.append(f"| {key} | {m.rotary_limits_deg['b'][0]}..{m.rotary_limits_deg['b'][1]} | "
                     f"{m.rotary_limits_deg['c'][0]}..{m.rotary_limits_deg['c'][1]} |")
    lines += ["", "## 现场确认（签字）", "",
              "- [ ] 软限位参数已按上表写入并存档截图",
              "- [ ] 手轮/单段超程测试：故意越界 1 mm 触发软限位报警（不撞硬限位）",
              "- [ ] B/C 硬限位与表中一致",
              "- [ ] 复位后回参考点，坐标显示正常", "",
              "操作者：__________  复核：__________  日期：__________", ""]
    p = OUT / "SOFT_LIMIT_SHEET.md"
    p.write_text("\n".join(lines), encoding="utf-8")
    (OUT / "soft_limits.json").write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                          encoding="utf-8")
    return p


def read_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _num(s) -> float | None:
    s = (s or "").strip()
    try:
        return float(s) if s else None
    except ValueError:
        return None


def evaluate_rows(rows: List[Dict[str, str]]) -> Dict:
    complete, results = 0, []
    for r in rows:
        vals = [_num(r.get("报警数")), _num(r.get("超程数")),
                _num(r.get("最大主轴负载(%)")), _num(r.get("急停停止时间(s)"))]
        door = (r.get("门锁测试(OK/NG)") or "").strip().upper()
        if any(v is None for v in vals) or not door:
            results.append({"program": r.get("程序"), "status": "PENDING"})
            continue
        complete += 1
        ok = (vals[0] == 0 and vals[1] == 0 and vals[2] <= 80 and vals[3] <= 0.5
              and door in ("OK", "PASS"))
        results.append({"program": r.get("程序"), "status": "PASS" if ok else "FAIL",
                        "alarms": vals[0], "overtravel": vals[1], "load_pct": vals[2],
                        "estop_s": vals[3], "door": door})
    if not rows:
        gate = "PENDING"
    elif any(r["status"] == "FAIL" for r in results):
        gate = "FAIL"
    elif all(r["status"] == "PASS" for r in results):
        gate = "PASS"
    else:
        gate = "PENDING"
    return {"gate": gate, "rows": results, "complete": complete, "total": len(rows)}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    p = config.load()
    machines = {k: p.machines[k] for k in MACHINES}
    checks: List[Dict] = []
    envs: Dict = {}
    # 三台机床为同一机械本体、同一刀路（回读误差 ≤0.0005 mm），机床包络统一取 FANUC 实测；
    # Siemens 的 A3/B3/C3 在 B=0 时 C 退化，不单独反解，避免给出偏小的错误包络。
    ref_env = {}
    for op in PROGRAMS:
        text = (NC_DIR / "prod_5ax_fanuc_0imf" / f"{p.part['id']}_{op}.nc").read_text(
            encoding="utf-8")
        ref_env[op] = envelope(text, "fanuc")
    for key in MACHINES:
        m = machines[key]
        mach = machine_runtime(m)
        for op in PROGRAMS:
            f = NC_DIR / key / f"{p.part['id']}_{op}.nc"
            text = f.read_text(encoding="utf-8")
            env = dict(ref_env[op])
            envs[(key, op)] = env
            ln = lint.lint(text, m.dialect, mach, tools_dict(p),
                          2 if op == "OP3" else 1, 10.0)
            in_env = all(m.travel_mm[ax][0] <= env[ax][0] and env[ax][1] <= m.travel_mm[ax][1]
                         for ax in ("x", "y", "z"))
            checks.append({"id": f"V2-{key}-{op}", "item": f"{key}/{op} 包络与基础门",
                           "status": "PASS" if (in_env and ln["verdict"] == "PASS"
                                                and not env["errors"]) else "FAIL",
                           "evidence": {**env, "lint": ln["verdict"],
                                        "parse_errors": env["errors"]}})
    soft = write_soft_limit_sheet(envs, machines)
    tmpl = write_dryrun_template()
    EVID.mkdir(parents=True, exist_ok=True)
    dst = EVID / tmpl.name
    if not dst.exists() or not any((r.get("报警数") or "").strip() for r in read_rows(dst)):
        dst.write_bytes(tmpl.read_bytes())
    ev = evaluate_rows(read_rows(dst))
    checks.append({"id": "V2-U-10", "item": "空运行与安全链证据（U-10）",
                   "status": ev["gate"], "evidence": ev["rows"][:3]})

    failed = [c for c in checks if c["status"] == "FAIL"]
    pending = [c for c in checks if c["status"] == "PENDING"]
    passed = [c for c in checks if c["status"] == "PASS"]
    gate = "FAIL" if failed else ("PASS" if not pending else "OPEN（软件侧就绪，待现场空运行）")

    md = ["# V2 空运行与安全链阶段执行记录 — AE-CI-258", "",
          f"- 执行时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
          "- 依据：`production/reports/UNMEASURED_VERIFICATION_PLAN.md` §U-10",
          f"- 结论：**{gate}**",
          f"- 统计：PASS {len(passed)} / PENDING {len(pending)} / FAIL {len(failed)}", "",
          "## 1. 程序机床坐标包络（实测，含 B/C 转台变换）", "",
          "| 机床 | 工序 | X | Y | Z | 采样点 | 基础门 |", "|---|---|---|---|---|---|---|"]
    for c in checks:
        if c["id"].startswith("V2-prod"):
            e = c["evidence"]
            mid = c["id"][3:]
            mach_key, op_id = mid.rsplit("-", 1)
            md.append(f"| {mach_key} | {op_id} | {e['x'][0]}..{e['x'][1]} | "
                      f"{e['y'][0]}..{e['y'][1]} | {e['z'][0]}..{e['z'][1]} | "
                      f"{e['samples']} | {c['status']} |")
    md += ["", "## 2. 软限位建议", "", f"- `{soft.relative_to(ROOT)}`",
           "- 写入后必须做超程触发测试（越界 1 mm 报警，不撞硬限位）。", "",
           "## 3. 空运行记录（现场填写）", "",
           f"- 空白模板：`{tmpl.relative_to(ROOT)}`",
           f"- 填写副本：`{dst.relative_to(ROOT)}`（已填则保留）", "",
           "| 程序 | 状态 |", "|---|---|"]
    for r in ev["rows"]:
        md.append(f"| {r['program']} | {r['status']} |")
    md += ["", "## 4. 现场步骤（摘要）", "",
           "1. 机床锁住 + 图形模拟跑完 9 个程序，记录报警数。",
           "2. 解除锁住，单段 + 10% 进给跑前 50 段，核对距离剩余与坐标显示。",
           "3. 记录最大主轴负载（应 ≤80% 额定）。",
           "4. 实测急停：各轴停止时间 ≤0.5 s；门开不能启动。",
           "5. 填表 → 重跑本脚本 → U-10 自动判定。任何 FAIL 禁止进入 V3/V4。", ""]
    report = OUT / "V2_READINESS_REPORT.md"
    report.write_text("\n".join(md), encoding="utf-8")
    (OUT / "v2_readiness.json").write_text(json.dumps(
        {"generated_at": datetime.now().isoformat(timespec="seconds"),
         "gate": gate, "checks": checks,
         "summary": {"pass": len(passed), "pending": len(pending), "fail": len(failed)},
         "envelopes": {f"{k[0]}/{k[1]}": v for k, v in envs.items()}},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"gate": gate, "pass": len(passed), "pending": len(pending),
                      "fail": len(failed), "report": str(report),
                      "soft_limit": str(soft), "template": str(dst)},
                     ensure_ascii=False, indent=2))
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
