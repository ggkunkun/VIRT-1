"""端到端全自动加工程序生成编排器。

串联：
  M1 工艺识别 → 毛坯摆放定位(含可选联网查标) → M2 多目标参数求解 →
  M3 初版程序生成 → M4 机床自动匹配与配置 → M3 目标机床后处理定稿 →
  双重校验(路径+机床兼容) + 可视化报告 → 全套交付件与全链路审计日志落盘。

支持 ``transport='inprocess'`` 与 ``transport='http'``（独立 REST 微服务编排）。
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from cam_autogen.common import DEFAULT_LOG_ROOT, TraceLogger
from cam_autogen.contracts import (
    CustomConstraint, MachineLimits, MachineSetup, NCProgram, ObjectiveWeights, OptimizationRequest,
    PipelineResult, ProcessPlan, RecognitionResult, StockSetup, VerificationReport, WorkpieceSpec,
)


class PipelineRequest(BaseModel):
    workpiece: WorkpieceSpec
    weights: ObjectiveWeights = Field(default_factory=ObjectiveWeights)
    custom_constraints: List[CustomConstraint] = Field(default_factory=list)
    disabled_constraints: List[str] = Field(default_factory=list)
    low_confidence_threshold: float = Field(0.90, gt=0, le=1)
    low_confidence_policy: Literal["halt", "conservative_fallback"] = "halt"
    preferred_machine: Optional[str] = None
    preferred_dialect: str = Field("FANUC", pattern="^(FANUC|SIEMENS|HUAZHONG)$")
    enable_web_lookup: bool = False
    machine_rate_per_h: float = Field(120.0, gt=0)
    time_budget_s: float = Field(25.0, gt=0, le=30.0)
    output_dir: Optional[str] = None
    transport: Literal["inprocess", "http"] = "inprocess"
    service_urls: Dict[str, str] = Field(default_factory=lambda: {
        "m1": "http://127.0.0.1:8101",
        "m2": "http://127.0.0.1:8102",
        "m3": "http://127.0.0.1:8103",
        "m4": "http://127.0.0.1:8104",
        "verify": "http://127.0.0.1:8105",
    })


def _http_post(url: str, payload: Dict[str, Any], timeout_s: float = 35.0) -> Dict[str, Any]:
    import httpx

    resp = httpx.post(url, json=payload, timeout=timeout_s)
    if resp.status_code >= 400:
        raise RuntimeError(f"HTTP {resp.status_code} from {url}: {resp.text[:300]}")
    return resp.json()


def _inprocess_backends(fetcher: Optional[Callable[[str, float], str]] = None) -> Dict[str, Callable[..., Any]]:
    from cam_autogen.machine_config import configure_machine
    from cam_autogen.machine_config.library import DEFAULT_REGISTRY
    from cam_autogen.optimization import optimize
    from cam_autogen.process_recognition import handle_low_confidence, recognize
    from cam_autogen.program_generation import generate
    from cam_autogen.stock_positioning import compute_stock_setup
    from cam_autogen.verification import verify_all

    def m1(wp: WorkpieceSpec, threshold: float, policy: str) -> RecognitionResult:
        res = recognize(wp, threshold)
        if res.low_confidence:
            res = handle_low_confidence(res, policy=policy)
        return res

    def stock(wp: WorkpieceSpec, ptype, enable_web: bool) -> StockSetup:
        return compute_stock_setup(wp, ptype, enable_web_lookup=enable_web, fetcher=fetcher)

    def m2(req: OptimizationRequest) -> ProcessPlan:
        return optimize(req)

    def m3(plan: ProcessPlan, ss: StockSetup, post_profile, dialect: str) -> NCProgram:
        return generate(plan, ss, post_profile=post_profile, dialect=dialect)

    def m4(prog: NCProgram, pref_model: Optional[str], pref_dialect: Optional[str]) -> MachineSetup:
        return configure_machine(prog, preferred_model=pref_model, preferred_dialect=pref_dialect,
                                 registry=DEFAULT_REGISTRY)

    def verify(prog: NCProgram, setup: MachineSetup, plan: ProcessPlan, ss: StockSetup, out_dir: Optional[Path]) -> VerificationReport:
        return verify_all(prog, setup, plan=plan, stock_setup=ss, output_dir=out_dir)

    return {"m1": m1, "stock": stock, "m2": m2, "m3": m3, "m4": m4, "verify": verify}


def _http_backends(urls: Dict[str, str], fetcher: Optional[Callable[[str, float], str]] = None) -> Dict[str, Callable[..., Any]]:
    from cam_autogen.stock_positioning import compute_stock_setup
    from cam_autogen.verification import verify_all

    def m1(wp: WorkpieceSpec, threshold: float, policy: str) -> RecognitionResult:
        raw = _http_post(f"{urls['m1']}/v1/recognize", {
            "workpiece": wp.model_dump(mode="json"),
            "threshold": threshold,
            "low_confidence_policy": policy,
        })
        return RecognitionResult.model_validate(raw)

    def stock(wp: WorkpieceSpec, ptype, enable_web: bool) -> StockSetup:
        return compute_stock_setup(wp, ptype, enable_web_lookup=enable_web, fetcher=fetcher)

    def m2(req: OptimizationRequest) -> ProcessPlan:
        raw = _http_post(f"{urls['m2']}/v1/optimize", req.model_dump(mode="json"))
        return ProcessPlan.model_validate(raw)

    def m3(plan: ProcessPlan, ss: StockSetup, post_profile, dialect: str) -> NCProgram:
        raw = _http_post(f"{urls['m3']}/v1/generate", {
            "plan": plan.model_dump(mode="json"),
            "stock_setup": ss.model_dump(mode="json"),
            "post_profile": post_profile.model_dump(mode="json") if post_profile else None,
            "dialect": dialect,
        })
        return NCProgram.model_validate(raw)

    def m4(prog: NCProgram, pref_model: Optional[str], pref_dialect: Optional[str]) -> MachineSetup:
        raw = _http_post(f"{urls['m4']}/v1/configure", {
            "program": prog.model_dump(mode="json"),
            "preferred_model": pref_model,
            "preferred_dialect": pref_dialect,
        })
        return MachineSetup.model_validate(raw)

    def verify(prog: NCProgram, setup: MachineSetup, plan: ProcessPlan, ss: StockSetup, out_dir: Optional[Path]) -> VerificationReport:
        if "verify" in urls and urls["verify"]:
            raw = _http_post(f"{urls['verify']}/v1/verify", {
                "program": prog.model_dump(mode="json"),
                "machine_setup": setup.model_dump(mode="json"),
                "plan": plan.model_dump(mode="json"),
                "stock_setup": ss.model_dump(mode="json"),
                "output_dir": str(out_dir) if out_dir else None,
            })
            return VerificationReport.model_validate(raw)
        return verify_all(prog, setup, plan=plan, stock_setup=ss, output_dir=out_dir)

    return {"m1": m1, "stock": stock, "m2": m2, "m3": m3, "m4": m4, "verify": verify}


def run_pipeline(
    req: PipelineRequest,
    log_root: Optional[Path] = None,
    fetcher: Optional[Callable[[str, float], str]] = None,
) -> PipelineResult:
    """端到端无人工干预全自动执行加工程序生成。"""
    t0 = time.perf_counter()
    logger = TraceLogger(root=log_root or DEFAULT_LOG_ROOT, persist=True)
    out_dir = Path(req.output_dir) if req.output_dir else (logger.dir / "deliverables")
    out_dir.mkdir(parents=True, exist_ok=True)
    backends = _http_backends(req.service_urls, fetcher=fetcher) if req.transport == "http" else _inprocess_backends(fetcher=fetcher)

    timings: Dict[str, float] = {}
    errors: List[str] = []
    rec: Optional[RecognitionResult] = None
    stock_setup: Optional[StockSetup] = None
    plan: Optional[ProcessPlan] = None
    prog: Optional[NCProgram] = None
    msetup: Optional[MachineSetup] = None
    ver: Optional[VerificationReport] = None

    # Stage 1: M1 工艺识别（含置信度 <90% 异常处理）
    try:
        with logger.stage("M1_process_recognition", inputs={"part_id": req.workpiece.part_id,
                                                            "threshold": req.low_confidence_threshold,
                                                            "policy": req.low_confidence_policy}) as ctx:
            rec = backends["m1"](req.workpiece, req.low_confidence_threshold, req.low_confidence_policy)
            ctx["output"] = rec
        timings["m1_ms"] = round(ctx["elapsed_ms"], 2)
    except Exception as exc:
        errors.append(f"M1 工艺识别异常阻断: {exc}")
        res = PipelineResult(trace_id=logger.trace_id, status="BLOCKED", part_id=req.workpiece.part_id,
                             stage_timings_ms=timings, errors=errors, events=logger.records)
        logger.write_artifact("pipeline_result.json", res.model_dump_json(indent=2))
        return res

    # Stage 2: 毛坯定位与标准查询
    with logger.stage("stock_positioning", inputs={"part_id": req.workpiece.part_id,
                                                   "process_type": rec.process_type.value,
                                                   "enable_web_lookup": req.enable_web_lookup}) as ctx:
        stock_setup = backends["stock"](req.workpiece, rec.process_type, req.enable_web_lookup)
        ctx["output"] = stock_setup
    timings["stock_ms"] = round(ctx["elapsed_ms"], 2)

    # Stage 3: M2 多目标约束优化
    limits = MachineLimits()
    if req.preferred_machine:
        from cam_autogen.machine_config.library import DEFAULT_REGISTRY
        pm = DEFAULT_REGISTRY.get(req.preferred_machine)
        if pm:
            limits = MachineLimits(
                max_rpm=pm.max_rpm,
                max_power_kw=pm.spindle_power_kw,
                max_feed_mm_min=pm.max_feed_mm_min,
                live_tool_max_rpm=pm.live_tool_max_rpm or 4000.0,
                live_tool_power_kw=pm.live_tool_power_kw or 3.7,
            )
    opt_req = OptimizationRequest(
        workpiece=req.workpiece,
        process_type=rec.process_type,
        weights=req.weights,
        machine_limits=limits,
        custom_constraints=req.custom_constraints,
        disabled_constraints=req.disabled_constraints,
        time_budget_s=req.time_budget_s,
        machine_rate_per_h=req.machine_rate_per_h,
    )
    with logger.stage("M2_optimization", inputs=opt_req) as ctx:
        plan = backends["m2"](opt_req)
        ctx["output"] = plan
    timings["m2_ms"] = round(ctx["elapsed_ms"], 2)
    if not plan.feasible:
        errors.extend(plan.infeasible_reasons or ["M2 优化未找到可行解"])
        res = PipelineResult(trace_id=logger.trace_id, status="BLOCKED", part_id=req.workpiece.part_id,
                             recognition=rec, stock_setup=stock_setup, plan=plan,
                             stage_timings_ms=timings, errors=errors, events=logger.records)
        logger.write_artifact("pipeline_result.json", res.model_dump_json(indent=2))
        return res

    # Stage 4: M3 初版程序生成
    with logger.stage("M3_program_generation_draft", inputs={"dialect": req.preferred_dialect, "ops": len(plan.operations)}) as ctx:
        draft_prog = backends["m3"](plan, stock_setup, None, req.preferred_dialect)
        ctx["output"] = {"sha256": draft_prog.sha256, "stats": draft_prog.stats, "tools": draft_prog.tool_table}
    timings["m3_draft_ms"] = round(ctx["elapsed_ms"], 2)

    # Stage 5: M4 机床自动选型与配置
    try:
        with logger.stage("M4_machine_config", inputs={"preferred_model": req.preferred_machine,
                                                       "preferred_dialect": req.preferred_dialect,
                                                       "prog_sha": draft_prog.sha256}) as ctx:
            msetup = backends["m4"](draft_prog, req.preferred_machine, req.preferred_dialect)
            ctx["output"] = msetup
        timings["m4_ms"] = round(ctx["elapsed_ms"], 2)
    except Exception as exc:
        errors.append(f"M4 机床匹配失败: {exc}")
        res = PipelineResult(trace_id=logger.trace_id, status="BLOCKED", part_id=req.workpiece.part_id,
                             recognition=rec, stock_setup=stock_setup, plan=plan, program=draft_prog,
                             stage_timings_ms=timings, errors=errors, events=logger.records)
        logger.write_artifact("pipeline_result.json", res.model_dump_json(indent=2))
        return res

    # Stage 6: M3 按目标机床专用后处理规则定稿
    with logger.stage("M3_program_generation_final", inputs=msetup.post_profile) as ctx:
        prog = backends["m3"](plan, stock_setup, msetup.post_profile, msetup.machine.dialect)
        ctx["output"] = {"sha256": prog.sha256, "dialect": prog.dialect, "line_count": prog.stats.get("line_count")}
    timings["m3_final_ms"] = round(ctx["elapsed_ms"], 2)

    # Stage 7: 双重校验 + 可视化报告
    with logger.stage("dual_verification", inputs={"machine": msetup.machine.model, "prog_sha": prog.sha256}) as ctx:
        ver = backends["verify"](prog, msetup, plan, stock_setup, out_dir)
        ctx["output"] = ver
    timings["verify_ms"] = round(ctx["elapsed_ms"], 2)

    # Stage 8: 交付件落盘
    ext = ".mpf" if prog.dialect == "SIEMENS" else ".nc"
    nc_path = out_dir / f"{req.workpiece.part_id}{ext}"
    ms_path = out_dir / f"{req.workpiece.part_id}.machine_setup.json"
    pl_path = out_dir / f"{req.workpiece.part_id}.process_plan.json"
    ss_path = out_dir / f"{req.workpiece.part_id}.stock_setup.json"
    nc_path.write_text(prog.program_text, encoding="utf-8")
    ms_path.write_text(msetup.model_dump_json(indent=2), encoding="utf-8")
    pl_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    ss_path.write_text(stock_setup.model_dump_json(indent=2), encoding="utf-8")

    output_files = {
        "nc_program": str(nc_path),
        "machine_setup": str(ms_path),
        "process_plan": str(pl_path),
        "stock_setup": str(ss_path),
        "verification_html": ver.html_path or "",
        "verification_json": ver.json_path or "",
        "trace_log": str(logger.path),
    }
    status = "SUCCESS" if ver.passed else "BLOCKED"
    if not ver.passed:
        errors.extend([f"[{r.level}] {r.code}: {r.message}" for r in ver.risks if r.level in ("CRITICAL", "HIGH")])

    timings["total_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    logger.log("pipeline", status, total_ms=timings["total_ms"], output_files=output_files)
    result = PipelineResult(
        trace_id=logger.trace_id,
        status=status,  # type: ignore[arg-type]
        part_id=req.workpiece.part_id,
        recognition=rec,
        plan=plan,
        stock_setup=stock_setup,
        program=prog,
        machine_setup=msetup,
        verification=ver,
        output_files=output_files,
        stage_timings_ms=timings,
        errors=errors,
        events=logger.records,
    )
    res_path = out_dir / f"{req.workpiece.part_id}.pipeline_result.json"
    res_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    output_files["pipeline_result"] = str(res_path)
    return result
