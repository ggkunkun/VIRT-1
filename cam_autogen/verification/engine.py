"""双重校验引擎 + REST API (:8105)。"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from cam_autogen.contracts import MachineSetup, NCProgram, ProcessPlan, RiskItem, StockSetup, VerificationReport
from cam_autogen.verification.compat_check import verify_machine_compatibility
from cam_autogen.verification.path_check import verify_path
from cam_autogen.verification.report import render_html_report

ENGINE_VERSION = "verify-dual-1.0.0"


def verify_all(
    program: NCProgram,
    setup: MachineSetup,
    plan: Optional[ProcessPlan] = None,
    stock_setup: Optional[StockSetup] = None,
    output_dir: Optional[Path] = None,
) -> VerificationReport:
    """执行双重校验：加工路径合理性 + 机床参数兼容性，生成分级告警与可视化报告。"""
    p_res = verify_path(program, plan=plan, stock_setup=stock_setup)
    c_res = verify_machine_compatibility(program, setup, plan=plan)

    risks: List[RiskItem] = list(p_res["risks"]) + list(c_res["risks"])
    if stock_setup and stock_setup.warnings:
        for w in stock_setup.warnings:
            risks.append(RiskItem(level="INFO", check="stock_setup", code="STOCK_NOTICE", message=w))

    summary = {lvl: 0 for lvl in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")}
    for r in risks:
        summary[r.level] = summary.get(r.level, 0) + 1

    passed = bool(p_res["passed"] and c_res["passed"])
    report = VerificationReport(
        part_id=program.part_id,
        passed=passed,
        path_check={k: v for k, v in p_res.items() if k != "risks"},
        compat_check={k: v for k, v in c_res.items() if k != "risks"},
        risks=risks,
        summary=summary,
    )

    if output_dir is not None:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        html_p = out / f"{program.part_id}.verification.html"
        json_p = out / f"{program.part_id}.verification.json"
        html_p.write_text(render_html_report(report, program, setup, stock_setup, plan), encoding="utf-8")
        report = report.model_copy(update={"html_path": str(html_p), "json_path": str(json_p)})
        json_p.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return report
