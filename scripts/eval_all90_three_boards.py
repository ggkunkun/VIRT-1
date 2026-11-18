#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/eval_all90_three_boards.py — All-90 三榜单联动验收器 (system >= 90 / raw_model >= 75 / engineering >= 90)

遵循《测量宪法》与《All-90 计划》：
  1. 三榜单均需真实响应证据文件 (或实调 Ollama) + RunIdentity + Metric 归因，严禁无证据写实测；
  2. 硬性计算 Wilson 95% 置信下界 (n=200/软件 达成 90% 时下界 >= 0.85)；
  3. 强制核验 system_prompt_bytes <= 702B，超出则 system/All-90 榜单判红；
  4. engineering 榜结合真实工具调用合法性与 scripts/wm_verifier.recompute 物理/几何真值重算。
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from build_six_holdout_200 import wilson_lower_bound
from gate_all90_dataset import (
    SIX_SOFTWARES,
    SYSTEM_PROMPT_MAX_BYTES,
    _extract_tool_invocations,
    load_known_tool_names,
    sha256_file,
)
from virtu_eval.provenance import Metric, RunIdentity
from wm_verifier import recompute as wm_recompute

THRESHOLDS = {
    "raw_model": 0.75,
    "system": 0.90,
    "engineering": 0.90,
}


def _close_match(actual: Any, expected: Any) -> bool:
    if isinstance(expected, (bool, str)):
        return actual == expected
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return math.isclose(float(actual), float(expected), rel_tol=0.02, abs_tol=1e-3)
    return actual == expected


def _parse_json_candidate(raw: Any) -> Optional[Dict[str, Any]]:
    if isinstance(raw, dict):
        return raw
    txt = str(raw or "").strip()
    if txt.startswith("{") and txt.endswith("}"):
        try:
            obj = json.loads(txt)
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None
    l = txt.find("{")
    r = txt.rfind("}")
    if l != -1 and r > l:
        try:
            obj = json.loads(txt[l:r + 1])
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None
    return None


def score_board_from_responses(
    holdout_rows: List[Dict[str, Any]],
    responses_path: str | Path,
    board_name: str,
    *,
    run_id: str,
    min_wilson_lb: float = 0.85,
) -> Dict[str, Any]:
    resp_p = Path(responses_path)
    if not resp_p.exists():
        raise FileNotFoundError(f"board {board_name} evidence missing: {responses_path}")

    known_tools = load_known_tool_names()
    by_id: Dict[str, Dict[str, Any]] = {}
    with open(resp_p, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            obj = json.loads(s)
            if obj.get("id"):
                by_id[str(obj["id"])] = obj

    passed_count = 0
    total = len(holdout_rows)
    sys_byte_violations = 0
    per_sw_pass = {sw: 0 for sw in SIX_SOFTWARES}
    per_sw_total = {sw: 0 for sw in SIX_SOFTWARES}

    for case in holdout_rows:
        cid = str(case["id"])
        sw = str(case.get("software", ""))
        if sw in per_sw_total:
            per_sw_total[sw] += 1

        resp = by_id.get(cid)
        if not resp:
            continue

        if resp.get("system_prompt") is not None:
            if len(str(resp["system_prompt"]).encode("utf-8")) > SYSTEM_PROMPT_MAX_BYTES:
                sys_byte_violations += 1
                continue

        # 物理/几何真值对比
        ref = wm_recompute(case["wm_sample"]) if isinstance(case.get("wm_sample"), dict) else (case.get("expected") or {})
        pred_dict = _parse_json_candidate(resp.get("prediction") if resp.get("prediction") is not None else resp.get("content"))

        physics_ok = False
        if pred_dict and ref:
            shared = [k for k in ref.keys() if k in pred_dict]
            if shared and all(_close_match(pred_dict[k], ref[k]) for k in shared):
                physics_ok = True
        elif isinstance(resp.get("passed"), bool):
            physics_ok = resp["passed"]

        if board_name in ("system", "engineering"):
            # System/Engineering 额外要求工具面真实匹配
            exp_tool = case.get("expected_tool")
            tool_calls = resp.get("tool_calls") or []
            called_names = [
                (tc.get("function") or {}).get("name") or tc.get("name")
                for tc in tool_calls if isinstance(tc, dict)
            ]
            if not called_names and resp.get("content"):
                called_names = [n for n, _ in _extract_tool_invocations({"messages": [{"role": "assistant", "content": str(resp["content"])}]})]
            tool_ok = all(n in known_tools for n in called_names) and (not exp_tool or exp_tool in called_names)
            item_ok = bool(physics_ok and tool_ok)
        else:
            item_ok = bool(physics_ok)

        if item_ok:
            passed_count += 1
            if sw in per_sw_pass:
                per_sw_pass[sw] += 1

    acc = (passed_count / total) if total > 0 else 0.0
    lb = wilson_lower_bound(passed_count, total)
    metric = Metric(
        name=f"{board_name}_accuracy",
        value=round(acc, 4),
        basis="measured",
        n=total,
        evidence=str(resp_p),
        run_id=run_id,
        note=f"wilson_lb={lb:.4f}",
        planned=total,
    )
    metric.check()

    threshold = THRESHOLDS[board_name]
    lb_ok = True if board_name == "raw_model" else (lb >= min_wilson_lb)
    sys_ok = (sys_byte_violations == 0)
    board_passed = (acc >= threshold) and lb_ok and sys_ok

    per_sw_report = {}
    for sw in SIX_SOFTWARES:
        n_sw = per_sw_total[sw]
        k_sw = per_sw_pass[sw]
        per_sw_report[sw] = {
            "passed": k_sw,
            "n": n_sw,
            "rate": round(k_sw / n_sw, 4) if n_sw else 0.0,
            "wilson_lb": round(wilson_lower_bound(k_sw, n_sw), 4) if n_sw else 0.0,
        }

    return {
        "board": board_name,
        "basis": "measured",
        "evidence": str(resp_p),
        "evidence_sha256": sha256_file(resp_p),
        "run_id": run_id,
        "passed_count": passed_count,
        "n": total,
        "score": round(acc * 100.0, 2),
        "threshold": round(threshold * 100.0, 2),
        "wilson_95_lb": round(lb, 4),
        "min_wilson_lb": min_wilson_lb if board_name != "raw_model" else None,
        "system_prompt_violations": sys_byte_violations,
        "per_software": per_sw_report,
        "passed": board_passed,
    }


def collect_live_ollama_responses(
    holdout_rows: List[Dict[str, Any]],
    model_tag: str,
    out_jsonl: Path,
    system_prompt: str,
) -> Path:
    if len(system_prompt.encode("utf-8")) > SYSTEM_PROMPT_MAX_BYTES:
        raise ValueError(f"[FATAL] system_prompt {len(system_prompt.encode('utf-8'))}B > {SYSTEM_PROMPT_MAX_BYTES}B")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with open(out_jsonl, "w", encoding="utf-8") as wf:
        for case in holdout_rows:
            payload = {
                "model": model_tag,
                "stream": False,
                "options": {"temperature": 0.0, "num_predict": 512},
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": case["prompt"]},
                ],
            }
            req = urllib.request.Request(
                "http://127.0.0.1:11434/api/chat",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with opener.open(req, timeout=120) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            msg = body.get("message") or {}
            wf.write(json.dumps({
                "id": case["id"],
                "system_prompt": system_prompt,
                "content": msg.get("content", ""),
                "tool_calls": msg.get("tool_calls") or [],
            }, ensure_ascii=False) + "\n")
    return out_jsonl


def evaluate_three_boards(
    holdout_path: str | Path,
    *,
    raw_responses: Optional[str | Path] = None,
    system_responses: Optional[str | Path] = None,
    engineering_responses: Optional[str | Path] = None,
    min_wilson_lb: float = 0.85,
    out_report: Optional[str | Path] = None,
) -> Dict[str, Any]:
    hp = Path(holdout_path)
    if not hp.exists():
        raise FileNotFoundError(f"holdout benchmark not found: {holdout_path}")

    holdout_rows = [
        json.loads(line) for line in hp.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    if not holdout_rows:
        raise ValueError(f"holdout is empty: {holdout_path}")

    ident = RunIdentity.capture(case_dirs=(), extra={"holdout_sha256": sha256_file(hp)})
    boards: Dict[str, Any] = {}
    board_inputs = {
        "raw_model": raw_responses,
        "system": system_responses,
        "engineering": engineering_responses,
    }

    for bname, rpath in board_inputs.items():
        if not rpath:
            boards[bname] = {
                "board": bname,
                "basis": "asserted",
                "status": "UNMEASURED",
                "passed": False,
                "reason": "未提供实测输出文件",
            }
        else:
            boards[bname] = score_board_from_responses(
                holdout_rows,
                rpath,
                bname,
                run_id=ident.run_id,
                min_wilson_lb=min_wilson_lb,
            )

    all90_passed = all(bool(b.get("passed")) for b in boards.values())
    report = {
        "run_id": ident.run_id,
        "holdout_path": str(hp),
        "holdout_sha256": sha256_file(hp),
        "total_cases": len(holdout_rows),
        "all90_passed": all90_passed,
        "boards": boards,
        "evaluated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    if out_report:
        op = Path(out_report)
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def _write_synthetic_responses(
    holdout_rows: List[Dict[str, Any]],
    out_path: Path,
    pass_rate: float,
    include_tool: bool,
    sys_prompt: str = "Virtu concise system prompt <=702B.",
) -> Path:
    total = len(holdout_rows)
    pass_quota = int(round(total * pass_rate))
    with open(out_path, "w", encoding="utf-8") as wf:
        for i, case in enumerate(holdout_rows):
            ref = wm_recompute(case["wm_sample"])
            if i < pass_quota:
                pred = ref
            else:
                pred = {"__wrong__": -999999}
            rec = {
                "id": case["id"],
                "system_prompt": sys_prompt,
                "prediction": pred,
                "tool_calls": [{"function": {"name": case["expected_tool"], "arguments": {}}}] if include_tool else [],
            }
            wf.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return out_path


def run_self_test() -> int:
    from build_six_holdout_200 import build_holdout

    with tempfile.TemporaryDirectory(prefix="eval_three_boards_selftest_") as td:
        td_p = Path(td)
        holdout_f = td_p / "holdout_200.jsonl"
        build_holdout(holdout_f, per_software=50)  # 300 cases; 92% -> wilson_lb ~ 0.884 >= 0.85
        rows = [json.loads(line) for line in holdout_f.read_text(encoding="utf-8").splitlines() if line.strip()]

        raw_f = _write_synthetic_responses(rows, td_p / "raw.jsonl", 0.80, include_tool=False)
        sys_f = _write_synthetic_responses(rows, td_p / "sys.jsonl", 0.92, include_tool=True)
        eng_f = _write_synthetic_responses(rows, td_p / "eng.jsonl", 0.93, include_tool=True)

        rep = evaluate_three_boards(
            holdout_f,
            raw_responses=raw_f,
            system_responses=sys_f,
            engineering_responses=eng_f,
            min_wilson_lb=0.85,
            out_report=td_p / "report.json",
        )
        assert rep["all90_passed"] is True, f"Valid 3-board test failed: {rep}"

        # 负向反证 1：system < 90% (0.86) 必须判红
        bad_sys = _write_synthetic_responses(rows, td_p / "bad_sys.jsonl", 0.86, include_tool=True)
        rep_bad = evaluate_three_boards(holdout_f, raw_responses=raw_f, system_responses=bad_sys, engineering_responses=eng_f)
        assert rep_bad["all90_passed"] is False and not rep_bad["boards"]["system"]["passed"]

        # 负向反证 2：system prompt > 702B 必须判红
        over_sys = _write_synthetic_responses(rows, td_p / "over_sys.jsonl", 0.95, include_tool=True, sys_prompt="A" * 705)
        rep_over = evaluate_three_boards(holdout_f, raw_responses=raw_f, system_responses=over_sys, engineering_responses=eng_f)
        assert rep_over["all90_passed"] is False

        # 负向反证 3：缺少某榜单响应不能伪造通过
        rep_missing = evaluate_three_boards(holdout_f, raw_responses=raw_f, system_responses=sys_f)
        assert rep_missing["all90_passed"] is False and rep_missing["boards"]["engineering"]["status"] == "UNMEASURED"

    print("[SELF-TEST] PASS: eval_all90_three_boards (Wilson LB + 702B system gate + WM recompute + negative probes)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="All-90 三榜单联动评测验收器")
    parser.add_argument("--holdout", default=str(ROOT / "data" / "benchmark" / "six_holdout_200.jsonl"))
    parser.add_argument("--raw-responses", default=None)
    parser.add_argument("--system-responses", default=None)
    parser.add_argument("--engineering-responses", default=None)
    parser.add_argument("--min-wilson-lb", type=float, default=0.85)
    parser.add_argument("--out", default=str(ROOT / "runs" / "all90_three_boards_report.json"))
    parser.add_argument("--self-test", "--selftest", dest="self_test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()
    rep = evaluate_three_boards(
        args.holdout,
        raw_responses=args.raw_responses,
        system_responses=args.system_responses,
        engineering_responses=args.engineering_responses,
        min_wilson_lb=args.min_wilson_lb,
        out_report=args.out,
    )
    print(json.dumps({"all90_passed": rep["all90_passed"], "boards": {
        k: {"score": v.get("score"), "wilson_lb": v.get("wilson_95_lb"), "passed": v.get("passed")}
        for k, v in rep["boards"].items()
    }}, indent=2, ensure_ascii=False))
    return 0 if rep["all90_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
