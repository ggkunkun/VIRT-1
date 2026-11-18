#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/derive_trajectories.py — All-90 受控轨迹泛化派生脚本 (<=3x 表层改写)

核心原则：
  1. 仅允许对 user query 做受控表层改写（语序/工程场景表述微调），默认上限 <=3 条/源轨迹；
  2. 硬性锁定不变量：所有工具调用名、工具参数 JSON、以及 assistant 回复中的所有数字保持 100% 一致；
  3. 完整继承源轨迹 source_run_id 与 evidence_sha256；
  4. 自动过 gate_all90_dataset 全部 8 道硬门禁并生成 SHA256 ledger。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from gate_all90_dataset import (
    _extract_tool_invocations,
    run_all_gates,
    sha256_file,
)

SURFACE_TEMPLATES = (
    "{orig}",
    "请按工业标准工程规范执行以下任务：{orig}",
    "[工程工单] {orig}（请结合工具调用与定量校核给出准确结论）",
)

_NUMBER_RE = re.compile(r"(?<![A-Za-z0-9_])[-+]?\d+(?:\.\d+)?")


def _assistant_invariants(rec: Dict[str, Any]) -> Tuple[List[str], List[Tuple[str, Any]]]:
    nums: List[str] = []
    for m in rec.get("messages") or []:
        if isinstance(m, dict) and m.get("role") == "assistant":
            nums.extend(_NUMBER_RE.findall(str(m.get("content") or "")))
    tools = _extract_tool_invocations(rec)
    return nums, tools


def derive_from_trajectories(
    src_jsonl: str | Path,
    out_jsonl: str | Path,
    *,
    factor: int = 3,
    run_gates: bool = True,
) -> Dict[str, Any]:
    if factor < 1 or factor > 3:
        raise ValueError(f"[FATAL] 派生倍数受 All-90 宪法上限约束必须在 [1, 3]，当前 factor={factor}")

    src_p = Path(src_jsonl)
    if not src_p.exists():
        raise FileNotFoundError(f"source trajectories not found: {src_jsonl}")

    out_rows: List[Dict[str, Any]] = []
    source_count = 0

    with open(src_p, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            s = line.strip()
            if not s:
                continue
            rec = json.loads(s)
            source_count += 1
            base_nums, base_tools = _assistant_invariants(rec)
            src_id = rec.get("source_run_id") or f"traj_{idx}"
            ev_sha = rec.get("evidence_sha256") or sha256_file(src_p)

            user_idx = next(
                (i for i, m in enumerate(rec.get("messages") or []) if m.get("role") == "user"),
                None,
            )
            if user_idx is None:
                continue
            orig_query = str(rec["messages"][user_idx]["content"]).strip()

            for copy_idx in range(factor):
                clone = json.loads(json.dumps(rec))
                clone["source_run_id"] = src_id
                clone["evidence_sha256"] = ev_sha
                clone["derivation_variant"] = copy_idx
                clone["messages"][user_idx]["content"] = SURFACE_TEMPLATES[copy_idx].format(orig=orig_query)

                new_nums, new_tools = _assistant_invariants(clone)
                if new_nums != base_nums or new_tools != base_tools:
                    raise RuntimeError(
                        f"[FATAL] 派生过程破坏数值/工具不变量! src_id={src_id}"
                    )
                out_rows.append(clone)

    out_p = Path(out_jsonl)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    with open(out_p, "w", encoding="utf-8") as wf:
        for r in out_rows:
            wf.write(json.dumps(r, ensure_ascii=False) + "\n")

    gate_report = None
    if run_gates and out_rows:
        gate_report = run_all_gates(
            out_p,
            require_provenance=True,
            max_derive_ratio=3,
        )
        if not gate_report["passed"]:
            raise RuntimeError(f"[FATAL] 派生语料未通过 8 道硬门禁: {gate_report}")

    out_sha = sha256_file(out_p)
    ledger = {
        "source_path": str(src_p),
        "output_path": str(out_p),
        "output_sha256": out_sha,
        "source_rows": source_count,
        "derived_rows": len(out_rows),
        "factor": factor,
        "gates_passed": gate_report["passed"] if gate_report else None,
        "derived_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    Path(str(out_p) + ".ledger.json").write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")
    return ledger


def run_self_test() -> int:
    with tempfile.TemporaryDirectory(prefix="derive_traj_selftest_") as td:
        td_p = Path(td)
        src_f = td_p / "src.jsonl"
        sample = {
            "software": "vericut",
            "source_run_id": "run_vc_01",
            "evidence_sha256": "a" * 64,
            "wm_sample": {"task": "adapt_material", "Sy": 300.0, "sigma": 150.0},
            "messages": [
                {"role": "system", "content": "你是 Virtu VERICUT 仿真校验专家。"},
                {"role": "user", "content": "核验零件材料安全系数并调用仿真检查工具。"},
                {"role": "assistant", "content": '<tool_call>\n{"name": "cadcam_vericut_simulate", "arguments": {"part": "housing"}}\n</tool_call>'},
                {"role": "tool", "content": '{"autodiff": "green"}'},
                {"role": "assistant", "content": json.dumps({"yield_strength_mpa": 300.0, "peak_von_mises_mpa": 150.0, "safety_factor": 2.0, "fos_gate": "pass"})},
            ],
        }
        src_f.write_text(json.dumps(sample, ensure_ascii=False) + "\n", encoding="utf-8")
        out_f = td_p / "derived.jsonl"
        res = derive_from_trajectories(src_f, out_f, factor=3, run_gates=True)
        assert res["derived_rows"] == 3 and res["gates_passed"] is True

        # 负向校验：超出 3x 上限必须拒绝
        try:
            derive_from_trajectories(src_f, out_f, factor=4, run_gates=True)
            raise AssertionError("derive_from_trajectories 未拦截 factor=4")
        except ValueError:
            pass

    print("[SELF-TEST] PASS: derive_trajectories (<=3x cap + invariants + 8 gates)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="All-90 受控轨迹泛化派生")
    parser.add_argument("--src", default=None, help="源轨迹 JSONL")
    parser.add_argument("--out", default=None, help="输出派生 JSONL")
    parser.add_argument("--factor", type=int, default=3, help="派生倍数 (1~3)")
    parser.add_argument("--self-test", "--selftest", dest="self_test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()
    if not args.src or not args.out:
        parser.error("请提供 --src 与 --out，或使用 --self-test")
    res = derive_from_trajectories(args.src, args.out, factor=args.factor, run_gates=True)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
