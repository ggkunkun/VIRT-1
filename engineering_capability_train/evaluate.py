#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""evaluate.py — 统一量化评测、门控与报告生成。

指标口径全部来自 configs/metrics.json，并与工作区 virtu_eval/report.py 保持一致：
  * transport_error / dry_run / recorded_replay 不计入能力分母，单独记为覆盖损失
  * transport_error > 5% 判本轮无效，必须重跑
  * empty_response / truncated 计入分母（真实产品失败）
  * 每次评测写入全新 run 目录，避免 runner 按 case_id 续跑造成"假刷新"

四类能力评分：
  vision_decision       -> selected 是否等于 argmin(cost) 的可行解；reason 字段接地率
  engineering_semantics -> 配合/尺寸链/参数化策略的数值与物理守恒
  toolchain             -> 工具名白名单 + schema 合法 + 与期望工具一致
  gui_trajectory        -> 由 gui_task_runner.py 的真实执行记录折算

用法：
  python evaluate.py --self-test                       # 合成数据验指标逻辑，不连模型
  python evaluate.py --predictions runs/pred.jsonl --fresh
  python evaluate.py --endpoint http://127.0.0.1:8000/v1 --model virtu-ect --fresh
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from ect_common import (atomic_write_json, atomic_write_jsonl, iter_jsonl,
                        load_config, log, now_iso, resolve, sha256_file)
from physics_gate import (best_candidate, candidate_cost, check_parametric_model,
                          gate_decision)
from _ect_rowcheck import check_tool_calls, tool_spec_index

EXCLUDED_VERDICTS = {"transport_error", "dry_run", "recorded_replay",
                     "not_evaluated_non_real_backend"}


# ---------------------------------------------------------------------------
# 模型响应获取
# ---------------------------------------------------------------------------
def load_predictions(path: Optional[str]) -> Dict[str, str]:
    if not path:
        return {}
    out: Dict[str, str] = {}
    for r in iter_jsonl(resolve(path)):
        tid = str(r.get("task_id") or r.get("case_id") or "")
        if tid:
            out[tid] = str(r.get("response") or r.get("text") or "")
    return out


def call_model(endpoint: str, model: str, prompt: str, timeout: int = 120,
               reasoning_effort: str | None = "none",
               max_tokens: int = 1024) -> Dict[str, Any]:
    """OpenAI-compatible /v1/chat/completions；仅标准库。

    实测（2026-11-04, Ollama 0.35.x + qwen3:8b）：
      * 顶层 `think:false` 在 /v1 端点**不生效**，思考 token 会吃光 max_tokens，
        返回空正文 + finish_reason=length，单题耗时 18s
      * `reasoning_effort:"none"` 生效，1.09s 返回正常 JSON、finish_reason=stop
    因此默认带 reasoning_effort=none；对不需要该字段的后端可传空字符串关闭。
    """
    url = endpoint.rstrip("/") + "/chat/completions"
    payload: Dict[str, Any] = {
        "model": model, "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0, "max_tokens": max_tokens,
    }
    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = data["choices"][0]["message"]["content"]
        return {"text": text or "", "elapsed_s": round(time.perf_counter() - t0, 4),
                "error": None, "finish_reason": data["choices"][0].get("finish_reason")}
    except (urllib.error.URLError, KeyError, IndexError, json.JSONDecodeError,
            TimeoutError, OSError) as exc:
        return {"text": "", "elapsed_s": round(time.perf_counter() - t0, 4),
                "error": f"{type(exc).__name__}: {exc}", "transport_error": True}


def _json_from(text: str) -> Optional[Any]:
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
        t = t.strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}|\[.*\]", t, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
    return None


# ---------------------------------------------------------------------------
# 单任务评分
# ---------------------------------------------------------------------------
def grounding_score(text: str, fields: Sequence[str], condition: Dict[str, Any]) -> float:
    """语义接地：决策理由必须显式引用工况字段或其取值，防套模板瞎猜。"""
    if not fields:
        return 1.0
    hit = 0
    for f in fields:
        val = condition.get(f)
        tokens = [f]
        if val is not None and not isinstance(val, (list, dict)):
            tokens.append(str(val))
            if isinstance(val, float) and val.is_integer():
                tokens.append(f"{val:.0f}")
        if any(t and t in text for t in tokens):
            hit += 1
    return hit / len(fields)


def grade_vision(task: Dict[str, Any], text: str) -> Dict[str, Any]:
    obj = _json_from(text)
    cands = task.get("candidates") or []
    expected = task.get("expected_chosen")
    by_id = {str(c.get("id")): c for c in cands}
    out = {"capability": "vision_decision", "parsed": isinstance(obj, dict),
           "decision_optimality": 0.0, "semantic_grounding": 0.0,
           "physics_ok": True, "physics_violations": [], "tool_valid": None,
           "model_valid": None, "errors": []}
    if not isinstance(obj, dict):
        out["errors"].append("unparsable_json")
        out["semantic_grounding"] = grounding_score(
            text, task.get("required_grounding_fields") or [], task.get("condition") or {})
        return out
    sel = str(obj.get("selected"))
    reason = str(obj.get("reason") or "") + " " + str(obj.get("analysis") or "")
    out["semantic_grounding"] = grounding_score(
        reason, task.get("required_grounding_fields") or [], task.get("condition") or {})
    cand = by_id.get(sel)
    # 物理否决：选了不可行候选，或根本不是候选集里的 id
    if cand is None:
        out["physics_ok"] = False
        out["physics_violations"].append(f"selected={sel!r} 不在候选集内")
    elif cand.get("physics_ok") is False:
        out["physics_ok"] = False
        out["physics_violations"].append(
            f"选中物理不可行候选 {sel}: {cand.get('violation', '')}")
    # 最优且最快：必须等于可行集里 cost 的 argmin
    recomputed = best_candidate(cands, {}) if cands else None
    optimal = (expected is not None and sel == expected
               and (recomputed is None or sel == recomputed)
               and cand is not None and math.isfinite(candidate_cost(cand, {})))
    out["decision_optimality"] = 1.0 if optimal else 0.0
    out["selected"] = sel
    out["expected"] = expected
    out["cost_recomputed_best"] = recomputed
    return out


def grade_semantic(task: Dict[str, Any], text: str) -> Dict[str, Any]:
    out = {"capability": "engineering_semantics", "parsed": False,
           "decision_optimality": None, "semantic_grounding": 0.0,
           "physics_ok": True, "physics_violations": [],
           "model_valid": 0.0, "errors": []}
    fields = task.get("required_grounding_fields") or []
    out["semantic_grounding"] = grounding_score(text, fields, task.get("condition") or {})
    obj = _json_from(text)
    spec = task.get("expected_model_spec")
    if isinstance(obj, dict):
        out["parsed"] = True
        ver = obj.get("verification")
        if isinstance(ver, dict) and all(
                k in ver for k in ("before_volume_mm3", "delta_volume_mm3",
                                   "after_volume_mm3")):
            g = check_parametric_model(dict(ver, operation="cut"))
            out["physics_ok"] = g.ok
            out["physics_violations"] = g.violations
            out["model_valid"] = 1.0 if g.ok else 0.0
            return out
    # 非 JSON 答案：要求文本中出现可复算的三个体积数值（含容差格式）
    if spec:
        vals = [spec["before_volume_mm3"], spec["delta_volume_mm3"],
                spec["after_volume_mm3"]]
        hit = 0
        for v in vals:
            forms = {f"{v:.3f}", f"{v:.2f}", f"{v:.1f}", f"{v:.0f}", str(v)}
            if any(f in text for f in forms):
                hit += 1
        out["model_valid"] = 1.0 if hit == 3 else hit / 3.0
        if hit < 3:
            out["errors"].append("体积守恒三项数值不全")
        g = check_parametric_model(spec)
        if not g.ok:
            out["physics_ok"] = False
            out["physics_violations"] = g.violations
    else:
        # 配合/尺寸链题：至少给出 ISO 286 偏差或 Σt 数值
        has_numbers = bool(re.search(r"\d+\.\d+|\d+\s*(μm|um|mm)", text))
        out["model_valid"] = 1.0 if has_numbers else 0.0
    return out


def grade_tool(task: Dict[str, Any], text: str, index: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    errs = check_tool_calls(text, index)
    obj = _json_from(text)
    name = obj.get("tool") if isinstance(obj, dict) else None
    expected = task.get("expected_tool")
    ok = not errs and name == expected
    return {"capability": "toolchain", "parsed": isinstance(obj, dict),
            "tool_valid": 1.0 if not errs else 0.0,
            "criteria_passed": bool(ok), "tool_errors": errs,
            "selected": name, "expected": expected,
            "decision_optimality": None, "semantic_grounding": 1.0 if ok else 0.0,
            "physics_ok": True, "physics_violations": [], "errors": errs}


def grade_gui(task: Dict[str, Any], gui_results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    r = gui_results.get(str(task.get("task_id")))
    if not r:
        return {"capability": "gui_trajectory", "verdict": "missing_execution",
                "evaluation_valid": False, "errors": ["no_gui_execution_record"]}
    total = max(1, int(r.get("actions_total") or 0))
    return {
        "capability": "gui_trajectory",
        "verdict": r.get("verdict"),
        "evaluation_valid": bool(r.get("evaluation_valid")),
        "criteria_passed": bool(r.get("success")),
        "physics_ok": bool(r.get("physics_ok", True)),
        "fatal_error": bool(r.get("fatal_error")),
        "transport_error": bool(r.get("transport_error")),
        "elapsed_s": float(r.get("elapsed_s") or 0.0),
        "retry_count": int(r.get("retry_count") or 0),
        "actions_total": total,
        "actions_valid": int(r.get("actions_valid") or 0),
        "gui_action_valid": (int(r.get("actions_valid") or 0)) / total,
        "errors": r.get("errors") or [],
        "decision_optimality": None,
        "semantic_grounding": None,
    }


# ---------------------------------------------------------------------------
# 指标聚合
# ---------------------------------------------------------------------------
def aggregate(records: List[Dict[str, Any]], mcfg: Dict[str, Any]) -> Dict[str, Any]:
    rules = mcfg["denominator_rules"]
    valid = [r for r in records if r.get("verdict") not in EXCLUDED_VERDICTS
             and not r.get("transport_error")]
    all_n = len(records)
    n = len(valid)
    transport = sum(1 for r in records if r.get("verdict") == "transport_error"
                    or r.get("transport_error"))
    transport_rate = transport / all_n if all_n else 0.0
    latency = [float(r.get("elapsed_s") or 0) for r in valid if r.get("elapsed_s")]
    errs = [r for r in valid if r.get("errors") or r.get("fatal_error")]
    fatal = [r for r in valid if r.get("fatal_error")]
    recovered = sum(1 for r in valid for e in (r.get("errors") or [])
                    if isinstance(e, dict) and e.get("recovered"))
    nonfatal = sum(1 for r in valid for e in (r.get("errors") or [])
                   if isinstance(e, dict) and not e.get("fatal"))

    def mean(xs, default=0.0):
        return sum(xs) / len(xs) if xs else default

    def pct(xs, q):
        if not xs:
            return None
        s = sorted(xs)
        return s[min(len(s) - 1, int(len(s) * q))]

    physics_flags = [bool(r.get("physics_ok", True)) for r in valid]
    opt = [r["decision_optimality"] for r in valid
           if r.get("decision_optimality") is not None]
    ground = [r["semantic_grounding"] for r in valid
              if r.get("semantic_grounding") is not None]
    toolv = [r["tool_valid"] for r in valid if r.get("tool_valid") is not None]
    modelv = [r["model_valid"] for r in valid if r.get("model_valid") is not None]
    guiv = [r["gui_action_valid"] for r in valid if r.get("gui_action_valid") is not None]
    successes = [r for r in valid if r.get("criteria_passed")
                 and r.get("physics_ok", True) and not r.get("fatal_error")]

    # 无样本的能力指标一律置 None（"未测"），绝不显示成 0 分冒充实测；
    # 门控会把 None 判为不通过，强制补齐真实评测后才能验收
    m = {
        "task_success_rate": len(successes) / n if n else 0.0,
        "first_attempt_success_rate": (
            sum(1 for r in successes if int(r.get("retry_count") or 0) == 0) / n if n else 0.0),
        "physics_compliance_rate": (mean([1.0 if x else 0.0 for x in physics_flags])
                                    if valid else 0.0),
        "decision_optimality_rate": mean(opt) if opt else None,
        "semantic_grounding_rate": mean(ground) if ground else None,
        "tool_call_valid_rate": mean(toolv) if toolv else None,
        "parametric_model_valid_rate": mean(modelv) if modelv else None,
        "gui_action_valid_rate": mean(guiv) if guiv else None,
        "error_rate": len(errs) / n if n else 0.0,
        "fatal_error_rate": len(fatal) / n if n else 0.0,
        "transport_error_rate": transport_rate,
        "latency_mean_s": mean(latency) if latency else None,
        "latency_p50_s": pct(latency, 0.50),
        "latency_p95_s": pct(latency, 0.95),
        "recovery_rate": recovered / nonfatal if nonfatal else None,
    }
    # 综合分：只聚合 weight>0 的指标，lower-is-better 做 (1 - v/ceiling) 归一
    comp = mcfg["composite"]
    ceil_map = {"error_rate": comp["error_rate_ceiling"]}
    score, wsum = 0.0, 0.0
    for name, spec in mcfg["metrics"].items():
        w = float(spec.get("weight", 0) or 0)
        if w <= 0 or name not in m or m[name] is None:
            continue
        v = float(m[name])
        norm = max(0.0, 1.0 - v / ceil_map.get(name, 1.0)) if spec["direction"] == "lower" else v
        score += min(1.0, max(0.0, norm)) * w
        wsum += w
    m["engineering_capability_score"] = round(score / wsum, 4) if wsum else 0.0

    gates = mcfg["acceptance_gates"]
    checks = []
    for key, threshold in gates.items():
        if key == "min_valid_tasks":
            checks.append({"gate": key, "value": n, "threshold": threshold,
                           "pass": n >= threshold})
            continue
        if not key.endswith(("_min", "_max")):
            continue
        metric = key.rsplit("_", 1)[0]
        if metric not in m or m[metric] is None:
            checks.append({"gate": key, "value": None, "threshold": threshold,
                           "pass": False, "reason": "metric unavailable"})
            continue
        passed = (m[metric] >= threshold if key.endswith("_min")
                  else m[metric] <= threshold)
        checks.append({"gate": key, "value": round(float(m[metric]), 4),
                       "threshold": threshold, "pass": bool(passed)})
    run_valid = transport_rate <= rules["invalid_run_if_transport_rate_above"]
    veto_ok = m["physics_compliance_rate"] >= gates["physics_compliance_rate_min"]
    return {
        "metrics": m, "gate_checks": checks,
        "n_total_records": all_n, "n_valid_tasks": n,
        "transport_errors": transport, "evaluation_valid": run_valid,
        "physics_veto_passed": veto_ok,
        "accepted": (run_valid and veto_ok and all(c["pass"] for c in checks)
                     and n >= gates["min_valid_tasks"]),
        "verdicts": dict(Counter(r.get("verdict") for r in records)),
        "capability_breakdown": dict(Counter(r.get("capability") for r in valid)),
    }


def _gate_metric_names(m: Dict[str, Any], gates: Dict[str, Any]) -> set:
    return {k.rsplit("_", 1)[0] for k in gates if k.endswith(("_min", "_max"))}


def render_markdown(result: Dict[str, Any], mcfg: Dict[str, Any]) -> str:
    m = result["metrics"]
    lines = [
        "# Virtu 工程能力评测报告", "",
        f"- 生成时间：{now_iso()}",
        f"- 有效任务：{result['n_valid_tasks']} / 总记录 {result['n_total_records']}",
        f"- 本轮有效（transport_error <= 5%）：**{result['evaluation_valid']}**",
        f"- 物理否决项通过：**{result['physics_veto_passed']}**",
        f"- **最终验收：{'PASS' if result['accepted'] else 'FAIL'}**", "",
        "## 量化指标", "", "| 指标 | 数值 | 方向 | 权重 |", "|---|---:|---|---:|",
    ]
    for name, spec in mcfg["metrics"].items():
        if name not in m:
            continue
        v = m[name]
        if isinstance(v, float):
            v = f"{v:.4f}" if ("rate" in name or "score" in name) else f"{v:.2f}"
        lines.append(f"| {name} | {v} | {spec['direction']} | {spec.get('weight', 0)} |")
    lines += ["", f"| engineering_capability_score | {m['engineering_capability_score']:.4f} | higher | — |",
              "", "## 验收门", "", "| 门 | 实测 | 阈值 | 结果 |", "|---|---:|---:|---|"]
    for c in result["gate_checks"]:
        lines.append(f"| {c['gate']} | {c['value']} | {c['threshold']} | "
                     f"{'PASS' if c['pass'] else 'FAIL'} |")
    lines += ["", "## 口径说明", "",
              "- transport_error / recorded_replay / 非 real 的 GUI 回放不计入能力分母，单独记覆盖损失",
              "- 任何物理违规（体积不守恒 / FOS<1.5 / G00 扎刀 / 公差带为负 / 选中不可行候选）判该任务失败",
              "- decision_optimality 要求 chosen 等于可行集里 cost=time*(1+0.5*risk) 的最小者",
              "- 只有 gui_task_runner.py --backend real 的执行结果才计入 GUI 能力指标",
              ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def run(args) -> Dict[str, Any]:
    cfg = load_config("pipeline")
    mcfg = load_config("metrics")
    index = tool_spec_index()
    tasks_p = resolve(args.tasks or (cfg["paths"]["data_dir"] + "/eval_tasks.jsonl"))
    tasks = list(iter_jsonl(tasks_p))
    if args.limit:
        tasks = tasks[:args.limit]
    preds = load_predictions(args.predictions)
    gui_results: Dict[str, Dict[str, Any]] = {}
    if args.gui_results and resolve(args.gui_results).is_file():
        for r in iter_jsonl(resolve(args.gui_results)):
            gui_results[str(r.get("task_id"))] = r

    # 全新 run 目录（禁止复用，避免评测假刷新）
    runs = resolve(cfg["paths"]["runs_dir"])
    run_dir = runs / (f"eval_{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}")
    run_dir.mkdir(parents=True, exist_ok=True)

    records: List[Dict[str, Any]] = []
    for task in tasks:
        tid = str(task.get("task_id"))
        cap = task.get("capability")
        t0 = time.perf_counter()
        gen: Dict[str, Any] = {}
        if cap == "gui_trajectory" and not preds.get(tid):
            g = grade_gui(task, gui_results)
            g.update({"task_id": tid, "elapsed_s": g.get("elapsed_s", 0.0)})
            if not g.get("evaluation_valid"):
                g["verdict"] = "recorded_replay"
                g["criteria_passed"] = False
            records.append(g)
            continue
        if tid in preds:
            gen = {"text": preds[tid], "elapsed_s": 0.0, "error": None}
        elif args.endpoint:
            gen = call_model(args.endpoint, args.model, task["prompt"],
                             timeout=args.timeout,
                             reasoning_effort=(args.reasoning_effort or None),
                             max_tokens=args.max_tokens)
        else:
            gen = {"text": "", "elapsed_s": 0.0, "error": None,
                   "transport_error": True}
        if gen.get("transport_error"):
            records.append({"task_id": tid, "capability": cap,
                            "verdict": "transport_error", "transport_error": True,
                            "elapsed_s": gen.get("elapsed_s", 0.0),
                            "errors": [gen.get("error")]})
            continue
        text = gen["text"]
        if cap == "vision_decision":
            g = grade_vision(task, text)
        elif cap == "engineering_semantics":
            g = grade_semantic(task, text)
        elif cap == "toolchain":
            g = grade_tool(task, text, index)
        else:
            g = grade_gui(task, gui_results)
        # 判定统一：vision 的 optimality / semantic 的 model_valid / tool 的 criteria
        passed = g.get("criteria_passed")
        if passed is None:
            if g.get("decision_optimality") is not None:
                passed = (g["decision_optimality"] >= 1.0
                          and g.get("semantic_grounding", 0) >= 0.8)
            elif g.get("model_valid") is not None:
                passed = g["model_valid"] >= 0.999
            else:
                passed = False
        g.update({"task_id": tid, "elapsed_s": gen.get("elapsed_s", 0.0),
                  "criteria_passed": bool(passed)})
        if not text.strip():
            g["verdict"] = "empty_response"
        elif gen.get("finish_reason") == "length":
            g["verdict"] = "partial_truncated"
        elif g.get("fatal_error"):
            g["verdict"] = "fatal_error"
        elif not g.get("physics_ok", True):
            g["verdict"] = "physics_violation"
        elif passed:
            g["verdict"] = "pass"
        else:
            g["verdict"] = "partial"
        records.append(g)

    result = aggregate(records, mcfg)
    result["run_dir"] = str(run_dir)
    result["eval_config"] = {
        "endpoint": args.endpoint, "model": args.model,
        "predictions": args.predictions, "gui_results": args.gui_results,
        "reasoning_effort": args.reasoning_effort, "max_tokens": args.max_tokens,
        "limit": args.limit, "timeout": args.timeout,
    }
    result["config_sha256"] = {
        "metrics.json": sha256_file(resolve("engineering_capability_train/configs/metrics.json")),
        "eval_tasks.jsonl": sha256_file(tasks_p)}
    result["evaluated_at"] = now_iso()
    atomic_write_jsonl(run_dir / "raw.jsonl", records)
    atomic_write_json(run_dir / "results.json", result)
    (run_dir / "report.md").write_text(render_markdown(result, mcfg), encoding="utf-8")
    log("evaluate", f"run_dir={run_dir} valid={result['n_valid_tasks']} "
                    f"accepted={result['accepted']}")
    return result


def self_test() -> int:
    """合成 12 条记录，验证指标口径（含 transport 排除、物理否决、最优性）。"""
    mcfg = load_config("metrics")
    recs = []
    for i in range(10):
        recs.append({"task_id": f"t{i}", "capability": "vision_decision",
                     "verdict": "pass", "criteria_passed": True, "physics_ok": True,
                     "fatal_error": False, "elapsed_s": 1.0 + i,
                     "decision_optimality": 1.0, "semantic_grounding": 1.0,
                     "tool_valid": 1.0, "model_valid": 1.0,
                     "gui_action_valid": 1.0, "retry_count": 0, "errors": []})
    recs.append({"task_id": "tx", "capability": "toolchain",
                 "verdict": "transport_error", "transport_error": True,
                 "elapsed_s": 0.1, "errors": ["connection refused"]})
    recs.append({"task_id": "ty", "capability": "toolchain",
                 "verdict": "recorded_replay", "evaluation_valid": False,
                 "elapsed_s": 0.1, "errors": []})
    r = aggregate(recs, mcfg)
    ok = (r["n_valid_tasks"] == 10
          and abs(r["metrics"]["task_success_rate"] - 1.0) < 1e-9
          and abs(r["metrics"]["transport_error_rate"] - 1 / 12) < 1e-9
          and r["metrics"]["latency_p95_s"] is not None)
    # 物理否决：一条违规必须让 physics_compliance_rate < 1 且 veto 不通过
    bad = list(recs)
    bad[0] = dict(bad[0], physics_ok=False, verdict="physics_violation")
    r2 = aggregate(bad, mcfg)
    ok &= (r2["metrics"]["physics_compliance_rate"] < 1.0
           and not r2["physics_veto_passed"] and not r2["accepted"])
    print(json.dumps({"self_test": "PASS" if ok else "FAIL",
                      "valid_tasks": r["n_valid_tasks"],
                      "task_success_rate": r["metrics"]["task_success_rate"],
                      "transport_error_rate": r["metrics"]["transport_error_rate"],
                      "physics_veto_after_violation": r2["physics_veto_passed"]},
                     ensure_ascii=False, indent=2))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Virtu 工程能力 - 统一量化评测")
    ap.add_argument("--tasks", default=None)
    ap.add_argument("--predictions", default=None)
    ap.add_argument("--endpoint", default=None)
    ap.add_argument("--model", default=os.environ.get("VIRTU_EVAL_MODEL", "virtu-ect"))
    ap.add_argument("--gui-results", default=None)
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--max-tokens", type=int, default=1024)
    ap.add_argument("--reasoning-effort", default="none",
                    help='传 "none" 关闭 Qwen3 思考（Ollama /v1 实测有效）；空字符串=不传该字段')
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    r = run(args)
    # stdout 输出完整结果快照，便于 CI / 流水线直接消费，无需再读 run_dir 里的文件
    print(json.dumps({"run_dir": r["run_dir"], "accepted": r["accepted"],
                      "evaluation_valid": r["evaluation_valid"],
                      "physics_veto_passed": r["physics_veto_passed"],
                      "n_total_records": r["n_total_records"],
                      "n_valid_tasks": r["n_valid_tasks"],
                      "transport_errors": r["transport_errors"],
                      "verdicts": r["verdicts"],
                      "capability_breakdown": r["capability_breakdown"],
                      "eval_config": r["eval_config"],
                      "metrics": r["metrics"],
                      "gate_checks": r["gate_checks"],
                      "failed_gates": [g for g in r["gate_checks"] if not g["pass"]]},
                     ensure_ascii=False, indent=2))
    return 0 if r["accepted"] else 1


if __name__ == "__main__":
    sys.exit(main())
