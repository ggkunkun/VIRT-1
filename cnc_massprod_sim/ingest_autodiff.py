# -*- coding: utf-8 -*-
"""VERICUT Auto-Diff 巡检载荷摄取：把真实偏差图分析结果接入量产验证门。

用法：
  python ingest_autodiff.py --inspection-json <vericut巡检.json> [--sim-log <仿真日志>]
  python ingest_autodiff.py --selftest   # 用坏样本自证门会拦截

复用 vericut_autodiff_adapter + triage_autodiff 的 normalize/audit 口径：
红=过切 Fatal / 蓝=残料超限 / 空白或未渲染图=INSUFFICIENT_EVIDENCE，
任何 BLOCKING 结论都必须停线整改，绝不因"绿色比例高"放行。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_PKG = Path(__file__).resolve()
_ROOT = _PKG.parents[1]  # workspace root (adapter + skills live there)
_SIM = _PKG.parent       # cnc_massprod_sim/
for _p in (str(_ROOT), str(_SIM / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import vericut_autodiff_adapter as adapter  # noqa: E402
import importlib.util  # noqa: E402

_TRIAGE = _ROOT / "skills" / "vericut-autodiff-triage" / "scripts" / "triage_autodiff.py"


def _load_triage():
    spec = importlib.util.spec_from_file_location("triage_autodiff", _TRIAGE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ingest(inspection_json: str, sim_log: str = None) -> dict:
    insp = json.loads(Path(inspection_json).read_text(encoding="utf-8"))
    log_text = Path(sim_log).read_text(encoding="utf-8", errors="replace") if sim_log else None
    triage = _load_triage()
    norm = triage.normalize(insp)
    audit = triage.audit(insp, log_text=log_text)
    verdict = str(insp.get("safety_verdict") or insp.get("verdict") or "").upper()
    blocking = verdict in adapter.BLOCKING_VERDICTS or norm["red"] > 0
    return {
        "basis": "measured_vericut_autodiff",
        "source": inspection_json,
        "normalized": {k: norm[k] for k in ("red", "blue", "green", "machined",
                                            "gouge_ratio", "excess_ratio",
                                            "in_tolerance_ratio", "claimed")},
        "verdict": verdict,
        "audit_checks": audit.get("checks", []),
        "escalations": audit.get("escalations", []),
        "passed": (not blocking) and verdict in adapter.ACCEPTED_VERDICTS
                  and norm["red"] == 0 and norm["machined"] > 0,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inspection-json")
    ap.add_argument("--sim-log", default=None)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    out_dir = _SIM / "reports"
    out_dir.mkdir(exist_ok=True)

    if args.selftest:
        # 坏样本1：自报 PASS 但存在过切像素 -> 必须拦截
        bad = {"safety_verdict": "AUTODIFF_ACCEPTED",
               "metrics": {"gouge_pixels": 152, "excess_pixels": 0,
                           "in_tolerance_percentage": 99.0, "machined_pixels": 10000}}
        # 坏样本2：空白未渲染 -> INSUFFICIENT_EVIDENCE
        blank = {"safety_verdict": "AUTODIFF_ACCEPTED", "metrics": {}}
        tmp = out_dir / "_selftest_bad.json"
        tmp.write_text(json.dumps(bad), encoding="utf-8")
        r1 = ingest(str(tmp))
        tmp.write_text(json.dumps(blank), encoding="utf-8")
        r2 = ingest(str(tmp))
        tmp.unlink()
        ok = (not r1["passed"]) and (not r2["passed"])
        print(f"selftest bad_sample_blocked={not r1['passed']} "
              f"blank_blocked={not r2['passed']} -> {'PASS' if ok else 'FAIL'}")
        return 0 if ok else 1

    if not args.inspection_json:
        ap.error("需要 --inspection-json 或 --selftest")
    r = ingest(args.inspection_json, args.sim_log)
    (out_dir / "autodiff_deviation_report.json").write_text(
        json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# VERICUT Auto-Diff 偏差摄取报告", "",
             f"- basis: {r['basis']}", f"- verdict: {r['verdict']}",
             f"- 过切像素 red={r['normalized']['red']}  残料 blue={r['normalized']['blue']} "
             f" 合格 green={r['normalized']['green']}/{r['normalized']['machined']}",
             f"- 判定: {'PASS' if r['passed'] else 'BLOCK'}",
             ""] + [f"- {e}" for e in r["escalations"]]
    (out_dir / "autodiff_deviation_report.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({k: r[k] for k in ("verdict", "passed")}, ensure_ascii=False))
    return 0 if r["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
