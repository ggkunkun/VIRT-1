# -*- coding: utf-8 -*-
"""VERICUT Auto-Diff 回灌验证：适配层 + SWARM 审计门端到端。

此前缺口：`swarm_orchestrator` 里 0 处 autodiff，意味着 AGENTS.md §2E 的
「红=过切/蓝=残料/绿=合格」这道门在 Swarm 里被完全跳过。

本测试锁死接入后的契约（全部可证伪）：

A. 适配层：扁平载荷 / 嵌套载荷都能归一化；自报 PASS 但有过切像素必须拦截；
   空白/未渲染图（有效像素 0）判"证据不足"，不得因"绿色 100%"而通过。
B. SWARM + 合格载荷 -> success=True，verdict=AUTODIFF_ACCEPTED，无缺陷。
C. SWARM + 过切载荷 -> success=False，verdict=STOP_AND_FIX，红队判 RED-AUTODIFF-REJECT。
D. SWARM + 空图载荷 -> success=False，verdict=INSUFFICIENT_EVIDENCE（不得判合格）。
E. SWARM 未提供载荷 -> success 仍可为 True，但红队记 major 缺陷 RED-NO-AUTODIFF
   （如实标注"这道门未取证"，而不是假装通过）。
F. require_autodiff=True 且未提供载荷 -> 审计门直接判红。

运行： python tests/test_autodiff_ingestion.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from swarm_test_support import run_pytest_file, swarm_workspace

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vericut_autodiff_adapter import evidence_from_payload  # noqa: E402
from virtu_omni.agent.swarm_orchestrator import SwarmCommander  # noqa: E402

RUN_ROOT = ROOT / "runs" / "autodiff_ingestion_test"
DESIGN_STL = ROOT / "artifacts" / "aero_closed_impeller" / "AE_CLOSED_IMPELLER_NASA1975.stl"

PAYLOADS = {
    "good": {"red_pixels": 0, "blue_pixels": 30, "green_pixels": 1970,
             "gouge_ratio": 0.0, "excess_ratio": 1.5,
             "in_tolerance_ratio": 98.5, "verdict": "PASS"},
    # 自报 PASS，但存在 120 个过切像素 —— 典型"假合格"
    "gouge": {"red_pixels": 120, "blue_pixels": 0, "green_pixels": 1880,
              "gouge_ratio": 6.0, "excess_ratio": 0.0,
              "in_tolerance_ratio": 94.0, "verdict": "PASS"},
    # 空白/未渲染截图：绿色自报 100%，但没有任何有效像素
    "empty": {"red_pixels": 0, "blue_pixels": 0, "green_pixels": 0,
              "verdict": "PASS", "in_tolerance_ratio": 100.0},
    # 现行嵌套形态
    "nested": {"status": "ok", "safety_verdict": "PASS",
               "metrics": {"gouge_pixels": 0, "excess_pixels": 10,
                           "in_tolerance_percentage": 99.5}},
}


def _write(name: str, payload: dict) -> str:
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    path = RUN_ROOT / f"{name}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return str(path)


def _base_params() -> dict:
    return {
        "design_stl": str(DESIGN_STL),
        "spindle_axis": "Z", "part_type": "铝合金闭式叶轮", "material": "AL6061-T6",
        "surface_finish": "Ra1.6", "tolerance": "IT8",
        "tool_radius_mm": 3.0, "allowance_mm": 0.01,
    }


def _run(label: str, extra: dict) -> dict:
    res = SwarmCommander().solve(dict(_base_params(), **extra),
                                 output_dir=str(RUN_ROOT / label))
    return res["verification_report"]


def main() -> int:
    checks = []

    # ---------- A. 适配层 ----------
    _, i_good = evidence_from_payload(PAYLOADS["good"])
    _, i_gouge = evidence_from_payload(PAYLOADS["gouge"])
    _, i_empty = evidence_from_payload(PAYLOADS["empty"])
    _, i_nested = evidence_from_payload(PAYLOADS["nested"])
    print("A good:", i_good["verdict"], "| gouge:", i_gouge["verdict"],
          i_gouge["blocking_codes"], "| empty:", i_empty["verdict"],
          "| nested:", i_nested["verdict"])
    checks.append(("A 扁平合格 -> ACCEPTED", i_good["accepted"] is True))
    checks.append(("A 嵌套合格 -> ACCEPTED", i_nested["accepted"] is True))
    checks.append(("A 自报PASS但过切 -> 拦截",
                   i_gouge["accepted"] is False
                   and "AD-RED-BUT-PASS" in i_gouge["blocking_codes"]))
    checks.append(("A 空白图 -> 证据不足",
                   i_empty["accepted"] is False
                   and i_empty["evidence_sufficient"] is False))

    # ---------- B~F. SWARM 端到端 ----------
    vr_none = _run("none", {})
    vr_good = _run("good", {"autodiff_payload": _write("good", PAYLOADS["good"])})
    vr_gouge = _run("gouge", {"autodiff_payload": _write("gouge", PAYLOADS["gouge"])})
    vr_empty = _run("empty", {"autodiff_payload": _write("empty", PAYLOADS["empty"])})
    vr_required = _run("required", {"require_autodiff": True})

    for name, vr in (("none", vr_none), ("good", vr_good), ("gouge", vr_gouge),
                     ("empty", vr_empty), ("required", vr_required)):
        ad = vr.get("autodiff") or {}
        print(f"SWARM[{name}] success={vr.get('audit_passed')} basis={ad.get('basis')} "
              f"verdict={ad.get('verdict')} red={[d['id'] for d in (vr.get('red_team_findings') or [])]}")

    # 注意 verification_report 里没有 success，用红队门与审计门判断
    checks.append(("B 合格载荷：审计通过 + 判定 ACCEPTED",
                   vr_good.get("audit_passed") is True
                   and (vr_good.get("autodiff") or {}).get("verdict") == "AUTODIFF_ACCEPTED"
                   and not (vr_good.get("red_team_findings") or [])))
    checks.append(("C 过切载荷：审计判红 + 红队拦截",
                   vr_gouge.get("audit_passed") is False
                   and (vr_gouge.get("autodiff") or {}).get("verdict") == "STOP_AND_FIX"
                   and any(d["id"] == "RED-AUTODIFF-REJECT"
                           for d in (vr_gouge.get("red_team_findings") or []))))
    checks.append(("D 空图载荷：不得判合格",
                   vr_empty.get("audit_passed") is False
                   and (vr_empty.get("autodiff") or {}).get("verdict") == "INSUFFICIENT_EVIDENCE"))
    checks.append(("E 无载荷：审计通过但红队记未取证",
                   vr_none.get("audit_passed") is True
                   and (vr_none.get("autodiff") or {}).get("basis") == "not_provided"
                   and any(d["id"] == "RED-NO-AUTODIFF"
                           for d in (vr_none.get("red_team_findings") or []))))
    checks.append(("F require_autodiff 未提供 -> 判红",
                   vr_required.get("audit_passed") is False
                   and vr_required.get("red_team_gate") is False))

    print("\n=== Auto-Diff 回灌测试 ===")
    all_pass = True
    for name, ok in checks:
        print(("  PASS  " if ok else "  FAIL  ") + name)
        all_pass = all_pass and bool(ok)
    print("\n" + ("ALL PASS (%d/%d)" % (sum(1 for _, o in checks if o), len(checks))
                  if all_pass else "HAS FAILURES"))
    return 0 if all_pass else 1


def test_autodiff_ingestion_contracts(swarm_workspace):
    assert main() == 0
    swarm_workspace.assert_runs(expected_count=5)


if __name__ == "__main__":
    raise SystemExit(run_pytest_file(__file__))
