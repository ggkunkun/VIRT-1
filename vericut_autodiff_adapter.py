# -*- coding: utf-8 -*-
"""VERICUT Auto-Diff 载荷适配层：把真实偏差图/视觉巡检 JSON 转成审计门证据。

背景：`product_integrity_gate.AutoDiffEvidence` 需要红/蓝/绿比例，但此前 SWARM 的
audit worker 根本没接 Auto-Diff（`swarm_orchestrator` 里 0 处 autodiff），等于这道门
在 Swarm 里被跳过。本模块负责把**真实**载荷接上：

- 复用 `skills/vericut-autodiff-triage/scripts/triage_autodiff.py` 的 `normalize`/`audit`
  （不重写一套口径，避免两套判定打架）；
- 支持两种历史载荷形态：
  1. 旧版扁平 `{red_pixels, blue_pixels, gouge_ratio, verdict, ...}`
  2. 现行嵌套 `{metrics: {gouge_pixels, excess_pixels, in_tolerance_percentage}, safety_verdict}`
- **证据不足不判合格**：空白/未渲染截图（有效像素 0）判 `INSUFFICIENT_EVIDENCE`，
  绝不因为"绿色比例高"就通过。

判定口径（与 AGENTS.md §2E 一致）：红=过切 Fatal ⇒ 一律不通过；蓝=残料 ⇒ 需补半精加工，
同样不通过；绿=在公差内 ⇒ 通过。
"""

from __future__ import annotations

import importlib.util
import json
import os
from typing import Any, Dict, Optional, Tuple

_ROOT = os.path.dirname(os.path.abspath(__file__))
_TRIAGE_PATH = os.path.join(
    _ROOT, "skills", "vericut-autodiff-triage", "scripts", "triage_autodiff.py")

#: 结论 -> 是否允许判定"成品已按此规范加工成形"
ACCEPTED_VERDICTS = frozenset({"AUTODIFF_ACCEPTED"})
#: 这些结论必须停机整改（含证据不足）
BLOCKING_VERDICTS = frozenset({
    "INSUFFICIENT_EVIDENCE",  # 证据不足：不得宣称通过
    "STOP_AND_FIX",           # 过切/口径冲突/日志与图像矛盾
    "REVIEW_GOUGE",           # 存在过切像素
    "ADD_SEMI_FINISHING",     # 残料超限
})

_triage_mod = None


def _load_triage_module():
    """加载既有 triage 脚本（幂等）。缺失时返回 None，由调用方如实降级。"""
    global _triage_mod
    if _triage_mod is not None:
        return _triage_mod
    if not os.path.isfile(_TRIAGE_PATH):
        return None
    spec = importlib.util.spec_from_file_location("_virtu_triage_autodiff", _TRIAGE_PATH)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _triage_mod = mod
    return mod


def load_payload(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8", errors="replace") as fh:
        return json.load(fh)


def audit_payload(payload: Dict[str, Any],
                  log_text: Optional[str] = None) -> Dict[str, Any]:
    """对视觉载荷跑 Auto-Diff 审计，返回 triage 报告（含 verdict/escalations/totals）。

    没有 triage 脚本可用时，返回 `INSUFFICIENT_EVIDENCE`（fail-closed），不假装能判。
    """
    mod = _load_triage_module()
    if mod is None:
        return {
            "verdict": "INSUFFICIENT_EVIDENCE",
            "checks": [],
            "escalations": [{"code": "AD-NO-TRIAGE-MODULE", "block": True,
                             "detail": f"未找到 Auto-Diff 判定脚本: {_TRIAGE_PATH}"}],
            "totals": {"red": 0, "blue": 0, "green": 0, "machined": 0},
        }
    return mod.audit(payload, log_text=log_text)


def ratios_from_report(report: Dict[str, Any]) -> Dict[str, float]:
    """从 triage 报告的像素总数反算比例（比自报百分比更可信）。"""
    t = report.get("totals") or {}
    red = float(t.get("red") or 0)
    blue = float(t.get("blue") or 0)
    green = float(t.get("green") or 0)
    machined = float(t.get("machined") or 0) or (red + blue + green)
    if machined <= 0:
        return {"gouge_ratio": 0.0, "excess_ratio": 0.0,
                "in_tol_ratio": 0.0, "coverage_ratio": 1.0}
    return {
        "gouge_ratio": red / machined,
        "excess_ratio": blue / machined,
        "in_tol_ratio": green / machined,
        "coverage_ratio": 1.0,
    }


def evidence_from_payload(payload: Dict[str, Any],
                          log_text: Optional[str] = None) -> Tuple[Dict[str, float], Dict[str, Any]]:
    """载荷 -> (AutoDiff 比例 dict, 元信息)。

    元信息字段：
      ``verdict``               triage 结论
      ``evidence_sufficient``   是否取得可判证据（INSUFFICIENT_EVIDENCE -> False）
      ``accepted``              是否可判定成品已成形
      ``blocking_codes``        置空/阻断的判定码
      ``ratios``                红/蓝/绿/覆盖比例
    """
    report = audit_payload(payload, log_text=log_text)
    verdict = str(report.get("verdict") or "INSUFFICIENT_EVIDENCE")
    ratios = ratios_from_report(report)
    codes = [e.get("code") for e in (report.get("escalations") or []) if e.get("code")]
    info = {
        "verdict": verdict,
        "evidence_sufficient": verdict not in ("INSUFFICIENT_EVIDENCE",),
        "accepted": verdict in ACCEPTED_VERDICTS,
        "blocking_codes": codes,
        "totals": report.get("totals") or {},
        "ratios": ratios,
    }
    return ratios, info


def evidence_from_file(path: str,
                       log_path: Optional[str] = None) -> Tuple[Dict[str, float], Dict[str, Any]]:
    payload = load_payload(path)
    log_text = None
    if log_path and os.path.isfile(log_path):
        with open(log_path, encoding="utf-8", errors="replace") as fh:
            log_text = fh.read()
    ratios, info = evidence_from_payload(payload, log_text=log_text)
    info["payload_path"] = path
    info["log_path"] = log_path if log_text is not None else None
    return ratios, info


# ---------------------------------------------------------------------------
# 自检： python vericut_autodiff_adapter.py
# ---------------------------------------------------------------------------
def _self_test() -> int:
    cases = []

    good_flat = {"red_pixels": 0, "blue_pixels": 30, "green_pixels": 1970,
                 "gouge_ratio": 0.0, "excess_ratio": 1.5,
                 "in_tolerance_ratio": 98.5, "verdict": "PASS"}
    r, info = evidence_from_payload(good_flat)
    cases.append(("扁平合格载荷 -> AUTODIFF_ACCEPTED",
                  info["accepted"] and info["evidence_sufficient"]
                  and abs(r["in_tol_ratio"] - 0.985) < 0.01,
                  f"{info['verdict']} in_tol={r['in_tol_ratio']:.4f}"))

    good_nested = {"status": "ok", "safety_verdict": "PASS",
                   "metrics": {"gouge_pixels": 0, "excess_pixels": 10,
                               "in_tolerance_percentage": 99.5}}
    r2, info2 = evidence_from_payload(good_nested)
    cases.append(("嵌套合格载荷 -> AUTODIFF_ACCEPTED",
                  info2["accepted"] and r2["gouge_ratio"] == 0.0,
                  f"{info2['verdict']} in_tol={r2['in_tol_ratio']:.4f}"))

    gouge = {"red_pixels": 120, "blue_pixels": 0, "green_pixels": 1880,
             "gouge_ratio": 6.0, "excess_ratio": 0.0,
             "in_tolerance_ratio": 94.0, "verdict": "PASS"}  # 自报合格但有过切
    r3, info3 = evidence_from_payload(gouge)
    cases.append(("有过切像素却自报 PASS -> 必须拦截",
                  (not info3["accepted"]) and "AD-RED-BUT-PASS" in info3["blocking_codes"],
                  f"{info3['verdict']} codes={info3['blocking_codes']}"))

    empty = {"red_pixels": 0, "blue_pixels": 0, "green_pixels": 0,
             "verdict": "PASS", "in_tolerance_ratio": 100.0}
    r4, info4 = evidence_from_payload(empty)
    cases.append(("空白/未渲染截图 -> 证据不足，不得判合格",
                  (not info4["accepted"]) and info4["evidence_sufficient"] is False,
                  f"{info4['verdict']} sufficient={info4['evidence_sufficient']}"))

    print("=== Auto-Diff 适配层自检 ===")
    ok_all = True
    for name, ok, detail in cases:
        print(("  PASS  " if ok else "  FAIL  ") + name + f"  [{detail}]")
        ok_all = ok_all and ok
    print("\n" + ("ALL PASS" if ok_all else "HAS FAILURES"))
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(_self_test())
