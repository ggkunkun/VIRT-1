#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""云端验收：三轮独立探针 + 连测最差门禁 + G71 语义门（可证伪）。不改判分器。

依赖同目录 `vendor/deploy_trained_adapter.py`（判分器原样拷贝，门禁口径不变）。
用法：
  python verify_gate.py --tag virtu-six-software:v9-repair --rounds 3 \
      --report ./out/VERIFY_REPORT.json [--semantic]

输出：每轮 passed/total、失败项明细、门禁（最差轮）、G71 语义门结果。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--profile", default="auto")
    ap.add_argument("--report", default=str(HERE / "VERIFY_REPORT.json"))
    ap.add_argument("--semantic", action="store_true", help="附加 G71 语义门（需同目录 g71_semantic_check.py）")
    args = ap.parse_args()

    grader_path = HERE / "vendor" / "deploy_trained_adapter.py"
    if not grader_path.exists():
        print(f"[FATAL] 缺少判分器副本: {grader_path}", file=sys.stderr)
        return 2
    grader = _load("deploy_trained_adapter", grader_path)

    sem = None
    if args.semantic:
        sp = HERE / "g71_semantic_check.py"
        if sp.exists():
            sem = _load("g71_semantic_check", sp)
        else:
            print("[WARN] 未找到 g71_semantic_check.py，跳过语义门", file=sys.stderr)

    rounds = []
    for i in range(1, args.rounds + 1):
        t0 = time.time()
        probes = grader.verify_deployed_model(args.tag, probe_profile=args.profile)
        total = len(probes)
        passed = sum(1 for p in probes.values() if p.get("passed"))
        failed = {k: v.get("reason") for k, v in probes.items() if not v.get("passed")}
        rec = {"round": i, "passed": passed, "total": total, "failed": failed,
               "elapsed_s": round(time.time() - t0, 1)}
        if sem is not None:
            g = (probes.get("fanuc_g71_safety_probe") or {}).get("full_response", "") or ""
            r = sem.check_g71_step_shaft(g)
            rec["g71_token_gate"] = bool((probes.get("fanuc_g71_safety_probe") or {}).get("passed"))
            rec["g71_semantic_gate"] = bool(r["passed"])
            rec["g71_violations"] = r["violations"]
        rounds.append(rec)
        print(f"[Verify] round {i}: {passed}/{total} failed={failed}", flush=True)

    worst = min(r["passed"] for r in rounds)
    report = {
        "tag": args.tag,
        "rounds": rounds,
        "gate": {
            "rule": "连测最差值做门禁",
            "worst_passed": worst,
            "worst_total": rounds[0]["total"] if rounds else 0,
            "all_rounds": [r["passed"] for r in rounds],
        },
        "semantic_gate": None if sem is None else {
            "rounds_passed": sum(1 for r in rounds if r.get("g71_semantic_gate")),
            "total": len(rounds),
            "all_pass": all(r.get("g71_semantic_gate") for r in rounds),
        },
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Gate] worst={worst}/{report['gate']['worst_total']} | semantic="
          f"{report['semantic_gate']} | report={args.report}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
