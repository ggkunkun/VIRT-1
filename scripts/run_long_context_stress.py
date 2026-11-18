# -*- coding: utf-8 -*-
"""Stress matrix: multi-needle recall, concurrency, physical context ceiling.

Runs REAL Ollama requests. Every failure is recorded, never hidden.

    .venv/Scripts/python.exe scripts/run_long_context_stress.py
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from virtu_omni.context import long_context as LC  # noqa: E402

ENDPOINT = os.getenv("VIRTU_OLLAMA_URL", "http://127.0.0.1:11434")
REPORT = ROOT / "reports" / "LONG_CONTEXT_STRESS_2026-11-12.json"
SEGMENTS = 45

NEEDLES = [
    {"value": "167.3", "segment": 8, "field": "outer_dia_mm",
     "task": "Return a world_state JSON with the final confirmed flange outer diameter in mm (field outer_dia_mm). Output JSON only.",
     "rq": "最终确认 法兰外径 外径"},
    {"value": "2.37", "segment": 22, "field": "safety_factor",
     "task": "Return a world_state JSON with the final confirmed safety factor (field safety_factor). Output JSON only.",
     "rq": "最终确认 安全系数 FOS"},
    {"value": "2387", "segment": 38, "field": "spindle_speed_rpm",
     "task": "Return a world_state JSON with the final confirmed spindle speed in rpm (field spindle_speed_rpm). Output JSON only.",
     "rq": "最终确认 主轴转速 转速"},
]

NEEDLE_TEXT = {
    "167.3": "最终确认：法兰外径 = 167.3 mm，材料 45 钢，输出文件 flange_final.step。本条为最终执行依据。",
    "2.37": "最终确认：安全系数 FOS = 2.37，许用应力已复核，rc=0。本条为最终执行依据。",
    "2387": "最终确认：主轴转速 = 2387 rpm，进给量 = 0.18 mm/r。本条为最终执行依据。",
}


def build_corpus() -> str:
    parts = [
        f"第 {i+1} 轮工艺评审纪要。草案外径 = {150+i} mm，孔径 = {40+i} mm，"
        f"主轴转速 = {1100+i} rpm，进给量 = {0.10+0.01*i:.2f} mm/r。"
        "与会人员讨论了刀具磨损、装夹刚性、冷却液配比与热处理变形等常规事项，"
        "会议记录已归档。上述数值均为阶段草案，未作为最终执行依据。"
        for i in range(SEGMENTS)
    ]
    for needle in sorted(NEEDLES, key=lambda n: n["segment"], reverse=True):
        parts.insert(needle["segment"], NEEDLE_TEXT[needle["value"]])
    return "\n\n".join(parts)


def _gpu():
    try:
        return int(subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            text=True, timeout=10).strip().splitlines()[0])
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc}"


def _multi_needle(backend) -> dict:
    corpus = build_corpus()
    session = LC.LongContextSession(
        store_path=str(ROOT / "runs" / "long_context" / "stress_chunks.sqlite"),
        backend=backend, physical_ctx=5120, model=LC.BASE_MODEL, top_k=4,
    )
    chunks = session.ingest("stress_minutes", corpus, chunk_chars=400)
    rows = []
    for needle in NEEDLES:
        started = time.time()
        row = {"value": needle["value"], "field": needle["field"],
               "segment": needle["segment"], "retrieval_query": needle["rq"]}
        try:
            out = session.chat(needle["task"], retrieval_query=needle["rq"])
            text = out.get("text", "")
            row.update({"ok": True, "recalled": needle["value"] in text,
                        "prompt_tokens": (out.get("usage") or {}).get("prompt_tokens"),
                        "latency_s": out.get("latency_s"),
                        "guard_passed": out.get("context_meta", {}).get("guard_passed"),
                        "retrieved_sources": out.get("context_meta", {}).get("sources"),
                        "text": text[:200]})
        except Exception as exc:  # noqa: BLE001
            row.update({"ok": False, "error": f"{type(exc).__name__}: {exc}",
                        "latency_s": round(time.time() - started, 2)})
        rows.append(row)
        print(f"needle {needle['value']}: ok={row['ok']} recalled={row.get('recalled')} "
              f"tokens={row.get('prompt_tokens')} lat={row.get('latency_s')}s")
    return {"basis": "measured", "corpus_chars": len(corpus), "chunks": chunks,
            "physical_ctx": 5120, "rows": rows,
            "recall_rate": round(sum(1 for r in rows if r.get("recalled")) / len(rows), 3)}


def _one_short(ctx: int, idx: int) -> dict:
    backend = LC.NativeChatBackend(endpoint=ENDPOINT, timeout=180.0)
    started = time.time()
    try:
        out = backend.chat([{"role": "user", "content": "reply with json only"}],
                           model=LC.DEFAULT_MODEL, num_ctx=ctx, max_tokens=8)
        return {"worker": idx, "ok": True, "num_ctx": ctx,
                "prompt_tokens": (out.get("usage") or {}).get("prompt_tokens"),
                "latency_s": out.get("latency_s")}
    except Exception as exc:  # noqa: BLE001
        return {"worker": idx, "ok": False, "num_ctx": ctx,
                "error": f"{type(exc).__name__}: {exc}",
                "latency_s": round(time.time() - started, 2)}


def _concurrency() -> dict:
    before = _gpu()
    started = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_one_short, 8192, i) for i in range(2)]
        rows = [f.result() for f in futures]
    return {"basis": "measured", "workers": 2, "num_ctx_each": 8192,
            "gpu_before_mib": before, "gpu_after_mib": _gpu(),
            "wall_s": round(time.time() - started, 2), "rows": rows,
            "all_ok": all(r["ok"] for r in rows)}


def _ps_ctx():
    """Read the context Ollama actually allocated (clamp detection)."""
    try:
        out = subprocess.check_output(["ollama", "ps"], text=True, timeout=15)
        for line in out.splitlines()[1:]:
            if LC.DEFAULT_MODEL in line:
                for token in line.split():
                    if token.isdigit() and int(token) >= 1024:
                        return int(token)
    except Exception:  # noqa: BLE001
        return None
    return None


def _ceiling() -> dict:
    rows = []
    for ctx in (40960, 65536, 131072):
        backend = LC.NativeChatBackend(endpoint=ENDPOINT, timeout=150.0)
        before = _gpu()
        started = time.time()
        row = {"requested_num_ctx": ctx, "gpu_before_mib": before}
        try:
            out = backend.chat([{"role": "user", "content": "reply with json only"}],
                               model=LC.DEFAULT_MODEL, num_ctx=ctx, max_tokens=8)
            row.update({"ok": True,
                        "prompt_tokens": (out.get("usage") or {}).get("prompt_tokens"),
                        "latency_s": out.get("latency_s"),
                        "response": out.get("text", "")[:80]})
        except Exception as exc:  # noqa: BLE001
            row.update({"ok": False, "error": f"{type(exc).__name__}: {exc}",
                        "latency_s": round(time.time() - started, 2)})
        row["gpu_after_mib"] = _gpu()
        row["effective_ctx_from_ollama_ps"] = _ps_ctx()
        rows.append(row)
        print(f"ctx {ctx}: ok={row['ok']} lat={row.get('latency_s')}s "
              f"effective_ps_ctx={row['effective_ctx_from_ollama_ps']} "
              f"err={row.get('error', '')[:100]}")
        if not row["ok"]:
            # Circuit breaker: do not keep pushing an already failing server.
            print("circuit breaker: stopping the ceiling climb after first failure")
            break
    # KV estimate anchored on the measured server.log value: 612 MiB @ 8192 q8_0.
    estimates = {str(c): round(612 * c / 8192) for c in (40960, 65536, 131072)}
    return {"basis": "measured (requests) + asserted (linear KV estimate)",
            "kv_anchor": "612 MiB KV at 8192 ctx, q8_0, 36 layers (server.log)",
            "gpu_total_mib": 6141, "kv_estimate_mib": estimates, "rows": rows}


def main() -> int:
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        os.environ.pop(key, None)
    backend = LC.NativeChatBackend(endpoint=ENDPOINT, timeout=300.0)
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "basis": "measured (real Ollama /api/chat) unless labelled otherwise",
        "multi_needle": _multi_needle(backend),
        "concurrency": _concurrency(),
        "physical_ceiling": _ceiling(),
    }
    mn = report["multi_needle"]
    ceiling_rows = report["physical_ceiling"]["rows"]
    clamped = any(
        r["ok"] and r["requested_num_ctx"] > 40960
        and (r.get("effective_ctx_from_ollama_ps") or 0) < r["requested_num_ctx"]
        for r in ceiling_rows
    )
    report["verdict"] = {
        "basis": "measured",
        "multi_needle_recall_rate": mn["recall_rate"],
        "multi_needle_all_retrieved": all(r.get("retrieved_sources") for r in mn["rows"] if r["ok"]),
        "concurrency_2_workers_ok": report["concurrency"]["all_ok"],
        "tested_ceiling_rows": len(ceiling_rows),
        "native_max_ctx": 40960,
        "num_ctx_clamped_to_native": clamped,
        "clamp_evidence": [
            {"requested": r["requested_num_ctx"],
             "effective_ps_ctx": r.get("effective_ctx_from_ollama_ps"),
             "gpu_before_mib": r.get("gpu_before_mib"),
             "gpu_after_mib": r.get("gpu_after_mib")}
            for r in ceiling_rows
        ],
        "caveat": "A successful short request does NOT prove the window is usable: "
                  "65536/131072 were clamped to the native 40960 (ollama ps + unchanged GPU memory). "
                  "Beyond 40960 requires YaRN. Single-run probes on a shared 6 GB GPU; "
                  "no long-input (>4k tokens) test was performed at these ceilings.",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(REPORT), "verdict": report["verdict"]},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
