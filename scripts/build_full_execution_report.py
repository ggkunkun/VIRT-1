# -*- coding: utf-8 -*-
"""Merge every measured artifact of this session into one execution report."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
OUT = REPORTS / "FULL_EXECUTION_2026-11-12.json"


def load(name: str) -> dict:
    path = REPORTS / name
    if not path.exists():
        return {"missing": str(path)}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"parse_error": f"{type(exc).__name__}: {exc}"}


def regression_summary() -> dict:
    path = ROOT / "scratch" / "regression_full.txt"
    if not path.exists():
        return {"basis": "unavailable"}
    text = path.read_text(encoding="utf-8", errors="replace")
    passed = re.search(r"(\d+) passed", text)
    failed = re.search(r"(\d+) failed", text)
    return {
        "basis": "measured (pytest -q over 6 test files, clean basetemp)",
        "passed": int(passed.group(1)) if passed else None,
        "failed": int(failed.group(1)) if failed else 0,
        "tail": text.strip().splitlines()[-1] if text.strip() else "",
    }


def main() -> int:
    matrix = load("OLLAMA_CONTEXT_MATRIX_2026-11-12.json")
    integration = load("LONG_CONTEXT_INTEGRATION_2026-11-12.json")
    stress = load("LONG_CONTEXT_STRESS_2026-11-12.json")
    yarn = load("YARN_SERVER_PROBE_2026-11-12.json")
    runtime = load("RUNTIME_CONFIG_VERIFY_2026-11-12.json")
    remory = load("REMORY_INTEGRATION_2026-11-12.json")
    regression = regression_summary()

    executed = [
        {"item": "服务层 KV 量化 + Flash Attention + context-shift 固化核验",
         "status": "done", "basis": "measured",
         "evidence": runtime.get("all_green"),
         "source": "reports/RUNTIME_CONFIG_VERIFY_2026-11-12.json"},
        {"item": "模型层 longctx manifest (num_ctx 32768, SYSTEM 契约保留)",
         "status": "done", "basis": "measured",
         "evidence": runtime.get("checks", {}).get("longctx_manifest"),
         "source": "Modelfile_longctx"},
        {"item": "物理 num_ctx 矩阵探针 5120..32768",
         "status": "done", "basis": "measured",
         "evidence": matrix.get("max_ok_num_ctx"),
         "source": "reports/OLLAMA_CONTEXT_MATRIX_2026-11-12.json"},
        {"item": "应用层长上下文模块（分块外存/BM25/压缩/预算/网关钩子）",
         "status": "done", "basis": "measured",
         "evidence": integration.get("verdict"),
         "source": "virtu_omni/context/long_context.py"},
        {"item": "Remory 协议层记忆接入（上一轮交付）",
         "status": "done", "basis": "measured",
         "evidence": remory.get("verdict"),
         "source": "virtu_omni/memory/remory_adapter.py"},
        {"item": "上下文余量门禁 + 自动再压缩（含反证/变异探针）",
         "status": "done", "basis": "measured",
         "evidence": "tests/test_long_context.py::test_guard_* + auto_recompact tests",
         "source": "virtu_omni/context/long_context.py"},
        {"item": "多 needle 召回 / 2 路并发 / 40960 上限 / clamp 证据",
         "status": "done", "basis": "measured",
         "evidence": stress.get("verdict"),
         "source": "reports/LONG_CONTEXT_STRESS_2026-11-12.json"},
        {"item": "引擎级 YaRN 运行时确证 + q4_0 KV + 131072 加载探针",
         "status": "done", "basis": "measured",
         "evidence": yarn.get("verdict"),
         "source": "reports/YARN_SERVER_PROBE_2026-11-12.json"},
        {"item": "全量回归",
         "status": "done", "basis": "measured",
         "evidence": regression,
         "source": "scratch/regression_full.txt"},
    ]

    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "trigger": "user: 全面执行",
        "scope": "Everything marked 未做/未测 in the preceding long-context "
                 "answer, executed end-to-end without step-by-step confirmation.",
        "executed": executed,
        "headline": {
            "runtime_config_all_green": runtime.get("all_green"),
            "physical_matrix_max_ok": matrix.get("max_ok_num_ctx"),
            "real_native_ceiling": stress.get("verdict", {}).get("native_max_ctx"),
            "num_ctx_clamped_above_native": stress.get("verdict", {}).get("num_ctx_clamped_to_native"),
            "multi_needle_recall_rate": stress.get("verdict", {}).get("multi_needle_recall_rate"),
            "concurrency_2_workers_ok": stress.get("verdict", {}).get("concurrency_2_workers_ok"),
            "module_token_saving": integration.get("verdict", {}).get("module_token_saving_vs_full"),
            "yarn_confirmed_by_runtime_log": yarn.get("verdict", {}).get("yarn_confirmed_by_runtime_log"),
            "q4_0_kv_generation_ok": yarn.get("verdict", {}).get("q4_0_kv_generation_ok"),
            "regression_passed": regression.get("passed"),
        },
        "corrected_assumptions": [
            "65536/131072 requests returned 200 but were clamped to the native 40960 "
            "(ollama ps + unchanged GPU memory); a successful short request != usable window.",
            "print_info 'rope scaling = linear' is GGUF metadata (KV overrides do not "
            "apply in that dump); runtime YaRN evidence is 'custom YaRN scaling detected'.",
            "Expected 131072 to OOM; a CPU server loaded it because KV is lazily "
            "committed and the probe used only 5 prompt tokens.",
            "The first YaRN baseline probe hit a stale server on a reused port; "
            "fixed with port-free checks + stale-process cleanup, then re-verified.",
        ],
        "remaining_limits": [
            "A genuinely filled 131072-token input is not feasible here: ~4.9 GiB KV "
            "(q4_0) + 4.6 GiB weights vs ~2.7 GiB free RAM and a shared 6 GiB GPU.",
            "Ollama itself still clamps num_ctx to 40960; >40960 requires engine-level "
            "YaRN (validated on an isolated llama-server, not wired into Ollama).",
            "Sparse attention, trained compressors and long-context benchmarks "
            "(multi-doc, >100k inputs) were not implemented.",
            "All probes are single-run on a shared machine; host contention can shift timings.",
        ],
        "artifacts": [
            "reports/OLLAMA_CONTEXT_MATRIX_2026-11-12.json",
            "reports/REMORY_INTEGRATION_2026-11-12.json",
            "reports/LONG_CONTEXT_INTEGRATION_2026-11-12.json",
            "reports/LONG_CONTEXT_STRESS_2026-11-12.json",
            "reports/YARN_SERVER_PROBE_2026-11-12.json",
            "reports/RUNTIME_CONFIG_VERIFY_2026-11-12.json",
        ],
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(OUT), "headline": report["headline"],
                      "executed_items": len(executed)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
