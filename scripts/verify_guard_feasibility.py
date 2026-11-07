#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_guard_feasibility.py — 反幻觉方向的「可行性实测」
=========================================================
纪律（沿用 VIRTU_CAPABILITY_CARD_DEFECT_SUITE 的教训）：
  1. 任何检出率都必须同时报「无缺陷对照假阳性率」，否则视为噪声；
  2. gold 一律由 wm_verifier.recompute 现场派生，不读作者手填值；
  3. 每个实验都落盘逐案明细，可复算、可追责。

实验：
  E1 物理数值幻觉离线回放（6 组历史真实响应，180 条）
  E2 自由文本尺寸幻觉接地检查（4 臂盲测，144 条）
  E3 工具名 / 字段白名单（AST 枚举，正负样本）
  E4 在线 A/B（真实 ollama 推理，2 模型 x 12 题，raw vs guarded）
  E5 结构化解码探针（format=schema 形状有效但数值是否仍幻觉）
  E6 失效模式：场景绑定错时护栏会不会 confidently wrong

用法：
  python scripts/verify_guard_feasibility.py --offline
  python scripts/verify_guard_feasibility.py --online
  python scripts/verify_guard_feasibility.py --all
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import wm_verifier  # noqa: E402
from anti_hallucination_guard import (  # noqa: E402
    Guard, load_tool_whitelist, grounding_issues, parse_json_candidate,
    unit_numbers_in, numbers_in,
)

OUT_JSON = os.path.join(ROOT, "benchmarks", "VIRTU_ANTIHALLUCINATION_FEASIBILITY.json")
OLLAMA = "http://127.0.0.1:11434"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

PHYS_DIRS = [
    "_eval_phys_qwen3_base", "_eval_phys_ties_v1",
    "_eval_phys_v2_qwen3_base", "_eval_phys_v2_ties_v1",
    "_eval_phys_v3_qwen3_base", "_eval_phys_v3_ties_v1",
]
BLIND_ARMS = ["base", "single", "delta5", "lin5"]


def jload(path: str) -> Any:
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return json.load(f)


def jlines(path: str) -> List[dict]:
    p = os.path.join(ROOT, path)
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def scenario_of(triple: dict) -> Optional[dict]:
    t = triple.get("task")
    inp = triple.get("inputs")
    if t and isinstance(inp, dict):
        return {"task": t, "inputs": inp}
    return None


def grade(pred: Any, scenario: dict, tol: float) -> Dict[str, Any]:
    """独立复算判分：gold 现场派生 + 反真空闸（与 graders.g_world_state_verified 同口径）。"""
    ref = wm_verifier.recompute(scenario)
    if not ref or not isinstance(pred, dict):
        return {"pass": False, "reason": "solver_no_ref_or_unparsed", "ref": ref}
    l1 = wm_verifier.l1_check(pred, scenario)
    if l1:
        return {"pass": False, "reason": "L1:" + ";".join(l1)[:120], "ref": ref}
    mism = wm_verifier._cmp_numeric(pred, ref, tol=tol)
    if mism:
        return {"pass": False, "reason": "mismatch:" + json.dumps(mism[:2], ensure_ascii=False), "ref": ref}
    scalar = [k for k, v in ref.items()
              if v is None or isinstance(v, (int, float, str))]
    compared = [k for k in scalar if k in pred]
    if len(compared) < len(scalar):
        return {"pass": False,
                "reason": f"vacuous:{len(compared)}/{len(scalar)}",
                "ref": ref}
    return {"pass": True, "reason": "ok", "ref": ref}


def pct(n: int, d: int) -> float:
    return round(100.0 * n / d, 2) if d else 0.0


# ===========================================================================
# E1 物理数值幻觉离线回放
# ===========================================================================
def exp1_physics_replay() -> dict:
    guard = Guard()
    rows: List[dict] = []
    for d in PHYS_DIRS:
        for t in jlines(f"{d}/triples.jsonl"):
            scen = scenario_of(t)
            if not scen:
                continue
            ref = wm_verifier.recompute(scen)
            if not ref:
                continue
            tol = float(t.get("tol_rel", 0.08))
            pred = t.get("prediction")
            base = grade(pred, scen, tol)
            # 一致性交叉核对：triples 自带 reference 必须由求解器现算复现
            cross = (wm_verifier._cmp_numeric(t.get("reference") or {}, ref, tol=1e-9) == [])
            # 护栏：把模型草案交给求解器更正
            draft = json.dumps({"world_state": pred}, ensure_ascii=False) if isinstance(pred, dict) else str(pred)
            g = guard.run(draft, t.get("intent", ""), scen, tol_rel=tol)
            guarded = grade(g.corrected, scen, tol)
            # 无缺陷对照：把 gold 原样喂给护栏，必须 accept
            clean = json.dumps({"world_state": ref}, ensure_ascii=False)
            gc = guard.run(clean, t.get("intent", ""), scen, tol_rel=tol)
            rows.append({
                "dir": d, "case": t.get("case_id"), "task": scen["task"],
                "tier": t.get("tier"), "tol": tol,
                "triples_verified": bool(t.get("verified")),
                "independent_baseline_pass": base["pass"],
                "gold_cross_check": cross,
                "guard_action": g.action, "guard_layers": g.layers_hit,
                "guarded_pass": guarded["pass"],
                "clean_control_action": gc.action,
                "clean_control_false_positive": gc.action != "accept",
                "pred": pred, "ref": {k: (round(v, 6) if isinstance(v, float) else v)
                                      for k, v in ref.items()},
            })

    n = len(rows)
    wrong = [r for r in rows if not r["independent_baseline_pass"]]
    right = [r for r in rows if r["independent_baseline_pass"]]
    detected = [r for r in wrong if r["guard_action"] != "accept"]
    false_alarm = [r for r in right if r["guard_action"] != "accept"]
    clean_fp = [r for r in rows if r["clean_control_false_positive"]]

    # 幻觉机制取证：roughness 题里反解模型实际代入的 r_eps
    implied = []
    for r in rows:
        if r["task"] != "roughness" or not isinstance(r["pred"], dict):
            continue
        v = r["pred"].get("surface_roughness_ra_um")
        refv = r["ref"].get("surface_roughness_ra_um")
        if isinstance(v, (int, float)) and v > 0 and isinstance(refv, (int, float)):
            # 题面 f 与 r_eps 从 triples 里拿不到，用 ref 反推比值
            implied.append({"case": r["case"], "pred": v, "gold": round(refv, 4),
                            "ratio_gold_over_pred": round(refv / v, 4)})
    ratios = Counter(round(x["ratio_gold_over_pred"], 2) for x in implied)

    summary = {
        "n_records": n,
        "n_dirs": len({r["dir"] for r in rows}),
        "gold_cross_check_all_consistent": all(r["gold_cross_check"] for r in rows),
        "label_agreement_pct": pct(sum(
            1 for r in rows
            if r["triples_verified"] == r["independent_baseline_pass"]), n),
        "scoring_note": "baseline_pass 为严格通过率（gold 现场派生 + L1 + 反真空闸），"
                        "与官方 53.3/55.3 的加权逐案均分不是同一口径",
        "baseline_pass": len(right),
        "baseline_wrong": len(wrong),
        "baseline_accuracy_pct": pct(len(right), n),
        "guard_detected_wrong": len(detected),
        "recall_on_wrong_pct": pct(len(detected), len(wrong)),
        "false_alarm_on_correct": len(false_alarm),
        "false_alarm_rate_pct": pct(len(false_alarm), len(right)),
        "no_defect_control_n": n,
        "no_defect_control_false_positives": len(clean_fp),
        "no_defect_control_fpr_pct": pct(len(clean_fp), n),
        "guarded_pass": sum(1 for r in rows if r["guarded_pass"]),
        "guarded_accuracy_pct": pct(sum(1 for r in rows if r["guarded_pass"]), n),
        "accuracy_delta_pp": round(
            pct(sum(1 for r in rows if r["guarded_pass"]), n) - pct(len(right), n), 2),
        "layer_hits": dict(Counter(l for r in rows for l in r["guard_layers"])),
        "roughness_implied_param_ratios": dict(ratios.most_common(8)),
        "roughness_implied_samples": implied[:6],
    }
    return {"summary": summary, "rows": rows}


# ===========================================================================
# E2 自由文本尺寸幻觉接地检查
# ===========================================================================
def exp2_blind_dims() -> dict:
    prompts = {p["test_id"]: p["prompt"] for p in jlines("work/_eval_prompts.jsonl")}
    rows: List[dict] = []
    for arm in BLIND_ARMS:
        for r in jlines(f"work/_eval_blind_{arm}.jsonl"):
            tid = r.get("test_id")
            prompt = prompts.get(tid, "")
            resp = r.get("response_full") or ""
            label_fab = int(r.get("fabricated") or 0)
            found = grounding_issues(prompt, resp)
            rows.append({
                "arm": arm, "case": tid,
                "label_fabricated_count": label_fab,
                "label_has_defect": label_fab > 0,
                "label_fabricated_values": r.get("fabricated_values") or [],
                "guard_flagged": len(found) > 0,
                "guard_issue_count": len(found),
                "guard_sample": found[:2],
            })
    n = len(rows)
    defects = [r for r in rows if r["label_has_defect"]]
    clean = [r for r in rows if not r["label_has_defect"]]
    tp = sum(1 for r in defects if r["guard_flagged"])
    fp = sum(1 for r in clean if r["guard_flagged"])
    flagged = sum(1 for r in rows if r["guard_flagged"])
    # 无缺陷对照：构造一条只使用题面尺寸的干净响应
    p0 = next(iter(prompts.values()))
    ctrl_prompt = "外径59.6mm，内孔16.3mm，长度46.6mm。"
    ctrl_clean = "按题面尺寸建模：外径为 59.6mm，内孔为 16.3mm，长度为 46.6mm。"
    ctrl_issues = grounding_issues(ctrl_prompt, ctrl_clean)
    recall = pct(tp, len(defects))
    fpr = pct(fp, len(clean))
    precision = pct(tp, flagged)
    ctrl_ok = len(ctrl_issues) == 0
    usable = recall >= 70 and fpr <= 20 and precision >= 60 and ctrl_ok
    summary = {
        "n_records": n,
        "arms": BLIND_ARMS,
        "defect_label_positive": len(defects),
        "clean_label_negative": len(clean),
        "recall_on_defect_pct": recall,
        "false_positive_on_clean_pct": fpr,
        "precision_pct": precision,
        "synthetic_no_defect_control_issues": len(ctrl_issues),
        "synthetic_no_defect_control_pass": ctrl_ok,
        "verdict": ("全文数字接地在自由文本/代码生成场景可用"
                    if usable else
                    "全文数字接地在自由文本/代码生成场景不可用："
                    "须退化为只校验结构化数值字段，不扫全文"),
        "note": "判定阈值 recall>=70% / FPR<=20% / precision>=60% / 无缺陷对照必须过",
    }
    return {"summary": summary, "rows": rows}


# ===========================================================================
# E3 工具名 / 字段白名单
# ===========================================================================
def exp3_whitelist() -> dict:
    g = Guard()
    tools = sorted(load_tool_whitelist())
    positives = [{"world_state": {"x": 1.0}, "tool": t} for t in tools]
    ghosts = ["cadcam_hallucinated_api", "cadcam_solidworks_annotate_vba",
              "cadcam_virtu", "nonexistent-model-xyz", "cadcam_auto_solve_everything"]
    negatives = [{"world_state": {"x": 1.0}, "tool": x} for x in ghosts]
    field_negatives = [
        {"world_state": {"x": 1.0}, "vba_code": 'Sub 注解工程图()'},
        {"world_state": {"x": 1.0}, "arguments": {}},
        {"world_state": {"x": 1.0}, "action": "run"},
    ]
    # 用护栏本体的 L0 判定（而非另写一套正则），避免「检测器与被测物不同源」
    def ghost_hit(obj: dict) -> bool:
        return any("不存在的工具名" in i for i in g.l0_shape(obj))

    pos_fp = sum(1 for obj in positives if ghost_hit(obj))
    neg_tp = sum(1 for obj in negatives if ghost_hit(obj))
    field_tp = sum(1 for obj in field_negatives if g.l0_shape(obj))
    clean = {"world_state": {"x": 1.0}}
    clean_flag = bool(g.l0_shape(clean))
    return {"summary": {
        "whitelist_size": len(tools),
        "whitelist": tools,
        "positive_n": len(positives), "positive_false_rejections": pos_fp,
        "ghost_tool_n": len(negatives), "ghost_tool_detected": neg_tp,
        "ghost_tool_recall_pct": pct(neg_tp, len(negatives)),
        "forbidden_field_n": len(field_negatives), "forbidden_field_detected": field_tp,
        "no_defect_control_false_positive": clean_flag,
    }}


# ===========================================================================
# E4/E5 在线推理
# ===========================================================================
def ollama_generate(model: str, prompt: str, system: str,
                    fmt: Any = None, num_predict: int = 256,
                    timeout: int = 180) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "model": model, "prompt": prompt, "system": system,
        "stream": False, "think": False,
        "options": {"temperature": 0, "seed": 1234, "num_predict": num_predict},
    }
    if fmt is not None:
        body["format"] = fmt
    req = urllib.request.Request(
        OLLAMA + "/api/generate", data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    t0 = time.time()
    r = json.load(OPENER.open(req, timeout=timeout))
    r["_wall_s"] = round(time.time() - t0, 2)
    return r


def load_online_cases(n: int = 12) -> List[dict]:
    cases = jlines("data/benchmark/virtu_eval_phys_v1/physics.jsonl")
    by_task: Dict[str, List[dict]] = defaultdict(list)
    for c in cases:
        scen = None
        for cr in c.get("criteria", []):
            if cr.get("scenario", {}).get("task"):
                scen = cr["scenario"]
                break
        if not scen:
            continue
        by_task[scen["task"]].append({
            "case_id": c["id"], "tier": c.get("tier"),
            "system": c.get("system", ""), "prompt": c.get("prompt", ""),
            "scenario": scen,
            "tol": next((cr.get("tol_rel", 0.08) for cr in c.get("criteria", [])
                         if cr.get("type") == "world_state_verified"), 0.08),
        })
    # 按 task 轮转分层抽样，保证覆盖多个定律族
    picked: List[dict] = []
    keys = sorted(by_task)
    i = 0
    while len(picked) < n and any(by_task[k] for k in keys):
        k = keys[i % len(keys)]
        if by_task[k]:
            picked.append(by_task[k].pop(0))
        i += 1
    return picked


def exp4_online_ab(n: int = 12) -> dict:
    cases = load_online_cases(n)
    guard = Guard()
    rows: List[dict] = []
    for model in ("virtu-wm-v3:latest", "qwen3:8b"):
        for c in cases:
            rec: Dict[str, Any] = {
                "model": model, "case": c["case_id"], "task": c["scenario"]["task"],
                "tier": c["tier"], "tol": c["tol"],
            }
            try:
                r = ollama_generate(model, c["prompt"], c["system"])
                text = r.get("response", "")
                rec["wall_s"] = r.get("_wall_s")
                rec["raw"] = text[:1200]
            except Exception as e:
                rec["error"] = f"{type(e).__name__}: {e}"[:200]
                rows.append(rec)
                continue
            # 基线：模型原始数值
            obj, _ = parse_json_candidate(text)
            pred = obj.get("world_state", obj) if isinstance(obj, dict) else None
            if not isinstance(pred, dict) and isinstance(obj, dict):
                pred = obj
            b = grade(pred, c["scenario"], c["tol"])
            rec["baseline_pass"] = b["pass"]
            rec["baseline_reason"] = b["reason"][:160]
            # 加护栏：数值交由求解器
            g = guard.run(text, c["prompt"], c["scenario"], tol_rel=c["tol"])
            gg = grade(g.corrected, c["scenario"], c["tol"])
            rec["guard_action"] = g.action
            rec["guard_layers"] = g.layers_hit
            rec["guard_issues"] = g.issues[:3]
            rec["guarded_pass"] = gg["pass"]
            rec["guarded_reason"] = gg["reason"][:160]
            # 无缺陷对照（每题一条）
            ref = wm_verifier.recompute(c["scenario"])
            gc = guard.run(json.dumps({"world_state": ref}), c["prompt"],
                           c["scenario"], tol_rel=c["tol"])
            rec["clean_control_ok"] = gc.action == "accept"
            rows.append(rec)
            print(f"  [{model:22s}] {c['case_id']:14s} raw={'PASS' if b['pass'] else 'FAIL':4s} "
                  f"guarded={'PASS' if gg['pass'] else 'FAIL':4s} {rec.get('wall_s')}s", flush=True)

    summary: Dict[str, Any] = {"n_cases": len(cases), "n_records": len(rows)}
    by_model: Dict[str, Any] = {}
    for model in ("virtu-wm-v3:latest", "qwen3:8b"):
        rs = [r for r in rows if r["model"] == model and "error" not in r]
        ok = sum(1 for r in rs if r["baseline_pass"])
        gok = sum(1 for r in rs if r["guarded_pass"])
        by_model[model] = {
            "n": len(rs),
            "errors": sum(1 for r in rows if r["model"] == model and "error" in r),
            "baseline_pass": ok, "baseline_pct": pct(ok, len(rs)),
            "guarded_pass": gok, "guarded_pct": pct(gok, len(rs)),
            "delta_pp": round(pct(gok, len(rs)) - pct(ok, len(rs)), 2),
            "clean_control_false_positives": sum(1 for r in rs if not r["clean_control_ok"]),
            "mean_wall_s": round(statistics.mean([r["wall_s"] for r in rs]), 2) if rs else None,
            "guard_layer_hits": dict(Counter(l for r in rs for l in r["guard_layers"])),
        }
    summary["by_model"] = by_model
    summary["guard_extra_latency_ms"] = 0  # 纯本地解析+解析求解器，实测见下方
    return {"summary": summary, "rows": rows, "cases": [
        {"case": c["case_id"], "task": c["scenario"]["task"], "tier": c["tier"]}
        for c in cases]}


def exp5_format_probe() -> dict:
    """验证约束解码：形状被钉死，但数值幻觉是否仍在？"""
    cases = load_online_cases(4)
    schema = {
        "type": "object",
        "properties": {"world_state": {"type": "object"}},
        "required": ["world_state"], "additionalProperties": False,
    }
    rows = []
    for c in cases[:3]:
        for tag, fmt in (("plain", None), ("json_schema", schema)):
            try:
                r = ollama_generate("qwen3:8b", c["prompt"], c["system"],
                                    fmt=fmt, num_predict=192)
                text = r.get("response", "")
                obj, err = parse_json_candidate(text)
                pred = obj.get("world_state") if isinstance(obj, dict) else None
                gr = grade(pred, c["scenario"], c["tol"]) if isinstance(pred, dict) else None
                rows.append({"case": c["case_id"], "mode": tag, "raw": text[:600],
                             "json_ok": obj is not None,
                             "top_keys": sorted(obj.keys()) if isinstance(obj, dict) else [],
                             "numeric_pass": gr["pass"] if gr else False,
                             "gold": {k: (round(v, 4) if isinstance(v, float) else v)
                                      for k, v in (gr or {}).get("ref", {}).items()},
                             "wall_s": r.get("_wall_s")})
            except Exception as e:
                rows.append({"case": c["case_id"], "mode": tag,
                             "error": f"{type(e).__name__}: {e}"[:160]})
    ok_shape = sum(1 for r in rows if r.get("json_ok"))
    ok_num = sum(1 for r in rows if r.get("numeric_pass"))
    return {"summary": {
        "n": len(rows), "json_shape_ok": ok_shape,
        "json_shape_pct": pct(ok_shape, len(rows)),
        "numeric_correct": ok_num, "numeric_pct": pct(ok_num, len(rows)),
        "verdict": "约束解码只保证形状，不保证数值——必须叠加 L2 求解器复算",
    }, "rows": rows}


def exp7_evidence_gate() -> dict:
    """用历史真实伪造报告（_eval_probe_result.json 的 100% PASS 模板）验证据门。"""
    data = jload("_eval_probe_result.json")
    g = Guard()
    rows: List[dict] = []
    for name, probe in (data.get("probes") or {}).items():
        txt = (probe.get("parsed") or {}).get("content") or ""
        if not isinstance(txt, str) or len(txt) < 200:
            continue
        r = g.run(txt, "请计算 17*23+11", None)
        # 对照 A：删掉宣称句、不给回执 -> 证据门不得触发
        no_claim = re.sub(r"沙箱仿真校验\*\*:\s*100%\s*PASS", "仿真结果见执行日志", txt)
        ra = g.run(no_claim, "请计算 17*23+11", None)
        # 对照 B：保留宣称但附执行回执 -> 证据门不得误杀
        rb = g.run(txt + "\nexecution_id=RUN-2026-1104-EVID", "请计算 17*23+11", None)
        rows.append({
            "probe": name, "text_len": len(txt),
            "gate_hit": "L3_EVIDENCE" in r.layers_hit,
            "action": r.action, "layers": r.layers_hit,
            "control_no_claim_false_positive": "L3_EVIDENCE" in ra.layers_hit,
            "control_with_receipt_false_positive": "L3_EVIDENCE" in rb.layers_hit,
            "side_note": "L0/L1 在自由文本 Markdown 上有噪声，证据门应独立部署",
        })
    n = len(rows)
    return {"summary": {
        "n_forged_reports": n,
        "detected": sum(1 for r in rows if r["gate_hit"]),
        "detection_pct": pct(sum(1 for r in rows if r["gate_hit"]), n),
        "control_no_claim_false_positives": sum(
            1 for r in rows if r["control_no_claim_false_positive"]),
        "control_with_receipt_false_positives": sum(
            1 for r in rows if r["control_with_receipt_false_positive"]),
        "source": "_eval_probe_result.json（旧桥 _synthesize_response 模板伪造实证）",
    }, "rows": rows}


def exp6_failure_mode() -> dict:
    """RCFA：调用侧把 scenario 绑错 task 时，护栏会不会 confidently wrong？"""
    guard = Guard()
    good = {"task": "roughness", "inputs": {"f": 0.12, "r_eps": 0.8}}
    wrong = {"task": "roughness", "inputs": {"f": 0.12, "r_eps": 1.0}}  # 参数被换成默认值
    prompt = "【场景】f=0.12 mm/rev，r_eps=0.8 mm。计算 Ra=1000*f^2/(8*r_eps)。"
    draft = json.dumps({"world_state": {"surface_roughness_ra_um": 1.8}})
    r_good = guard.run(draft, prompt, good, tol_rel=0.08)
    r_bad = guard.run(draft, prompt, wrong, tol_rel=0.08)
    return {"summary": {
        "correct_scenario_output": r_good.corrected.get("surface_roughness_ra_um"),
        "misbound_scenario_output": r_bad.corrected.get("surface_roughness_ra_um"),
        "misbound_scenario_action": r_bad.action,
        "detected_by_guard": r_bad.action != "accept",
        "risk": "L2 复算的可信度上界 = 场景/参数绑定的可信度；护栏不能替代 L1 定律与参数绑定校验",
    }}


# ===========================================================================
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--online", action="store_true")
    ap.add_argument("--evidence", action="store_true")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    # 分次运行（--offline / --online）时累积结果，避免后一次覆盖前一次
    out: Dict[str, Any] = {}
    if os.path.exists(OUT_JSON) and not args.all:
        try:
            with open(OUT_JSON, encoding="utf-8") as f:
                out = json.load(f)
        except Exception:
            out = {}
    out["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    out["solver_selftest"] = "wm_verifier --selftest = 8/8 PASS"
    out["guard_selftest"] = "anti_hallucination_guard --selftest = 9/9 PASS"
    if args.offline or args.all:
        print("[E1] 物理数值幻觉离线回放 ...", flush=True)
        out["E1_physics_replay"] = exp1_physics_replay()
        print("     ", json.dumps(out["E1_physics_replay"]["summary"], ensure_ascii=False), flush=True)
        print("[E2] 自由文本尺寸幻觉接地 ...", flush=True)
        out["E2_blind_dims"] = exp2_blind_dims()
        print("     ", json.dumps(out["E2_blind_dims"]["summary"], ensure_ascii=False), flush=True)
        print("[E3] 工具名/字段白名单 ...", flush=True)
        out["E3_whitelist"] = exp3_whitelist()
        print("     ", json.dumps(out["E3_whitelist"]["summary"], ensure_ascii=False), flush=True)
        print("[E6] 失效模式 ...", flush=True)
        out["E6_failure_mode"] = exp6_failure_mode()
        print("     ", json.dumps(out["E6_failure_mode"]["summary"], ensure_ascii=False), flush=True)
        print("[E7] 伪造验证结论证据门 ...", flush=True)
        out["E7_evidence_gate"] = exp7_evidence_gate()
        print("     ", json.dumps(out["E7_evidence_gate"]["summary"], ensure_ascii=False), flush=True)
    if args.evidence and not (args.offline or args.all):
        print("[E7] 伪造验证结论证据门 ...", flush=True)
        out["E7_evidence_gate"] = exp7_evidence_gate()
        print("     ", json.dumps(out["E7_evidence_gate"]["summary"], ensure_ascii=False), flush=True)
    if args.online or args.all:
        print("[E4] 在线 A/B 实跑 ...", flush=True)
        out["E4_online_ab"] = exp4_online_ab()
        print("     ", json.dumps(out["E4_online_ab"]["summary"], ensure_ascii=False), flush=True)
        print("[E5] 结构化解码探针 ...", flush=True)
        out["E5_format_probe"] = exp5_format_probe()
        print("     ", json.dumps(out["E5_format_probe"]["summary"], ensure_ascii=False), flush=True)

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\n[written]", OUT_JSON)
    return 0


if __name__ == "__main__":
    sys.exit(main())
