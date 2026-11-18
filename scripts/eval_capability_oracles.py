# -*- coding: utf-8 -*-
"""scripts/eval_capability_oracles.py — 新增能力 oracle 取证并按测量宪法 §8 落盘。

跑 P1a 套料 / P1b 后处理 / P2 FEA 三个可证伪 oracle + GUI 成功诚实账本，
把结果写入 benchmarks/，每个发布数字带 basis/n/evidence/run_id（内容指纹）。
GUI 任务成功一律 unmeasured（无真实批准运行+任务完成信号）。

用法：.venv/Scripts/python.exe scripts/eval_capability_oracles.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from virtu_omni.eval.capability_oracles import run_all_oracles
from virtu_eval.provenance import RunIdentity, Metric

RULER_FILES = (
    "virtu_omni/eval/capability_oracles.py",
    "virtu_omni/engine/sheetmetal_nesting_engine.py",
    "virtu_omni/engine/cnc_post_processor.py",
    "virtu_omni/engine/universal_cae_engine.py",
)


def main() -> int:
    ts = time.strftime("%Y-%m-%d")
    out_dir = ROOT / "benchmarks"
    out_dir.mkdir(exist_ok=True)
    evidence_path = out_dir / f"NEW_CAPABILITY_ORACLES_{ts}.json"

    results = run_all_oracles()
    identity = RunIdentity.capture(ruler_files=RULER_FILES)

    # 先把证据落盘，Metric.check 要求 evidence 文件真实存在
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "run_id": identity.run_id,
        "ruler_sha256": identity.ruler,
        "oracles": results["oracles"],
        "all_measurable_oracles_passed": results["all_measurable_oracles_passed"],
        "gui_task_success_basis": results["gui_task_success_basis"],
    }
    evidence_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    metrics = []
    for key in ("nesting", "post_dialect", "fea_cross_check"):
        o = results["oracles"][key]
        m = Metric(
            name=f"oracle.{key}.passed",
            value=bool(o["passed"]),
            basis=o.get("basis", "measured"),
            n=1,
            evidence=str(evidence_path),
            run_id=identity.run_id,
            note=o.get("oracle", key),
        )
        m.check()
        metrics.append(m)

    # GUI 任务成功：unmeasured，值为 None 不得作为分数发布 -> 显式写"未测"
    gui = results["oracles"]["gui_success_ledger"]
    gui_metric = Metric(
        name="oracle.gui_task_success",
        value="未测",
        basis="asserted",
        n=gui["total_events"],
        evidence=str(evidence_path),
        run_id=identity.run_id,
        note="输入门 allow/deny 实测；任务成功无批准运行+完成信号，标 unmeasured",
    )

    summary = {
        "evidence": str(evidence_path.relative_to(ROOT)),
        "run_id": identity.run_id,
        "metrics": [m.as_row() for m in metrics],
        "gui_task_success": gui_metric.as_row(),
        "all_measurable_oracles_passed": results["all_measurable_oracles_passed"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if results["all_measurable_oracles_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())