# -*- coding: utf-8 -*-
"""Measure the REAL physical context ceiling of the Virtu main model.

Sends short requests with increasing ``options.num_ctx`` to Ollama and records
success / latency / GPU memory / the context Ollama actually allocated.
No service restart, no environment-variable changes, no model mutation.

    .venv/Scripts/python.exe scripts/probe_ollama_context.py
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "OLLAMA_CONTEXT_MATRIX_2026-11-12.json"
ENDPOINT = os.getenv("VIRTU_OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.getenv("VIRTU_REMORY_MODEL", "virtu-wm-v3:chatml")
CTXS = [5120, 8192, 12288, 16384, 24576, 32768]
NUM_GPU = 16


def _opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _gpu_mib():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used,memory.free",
             "--format=csv,noheader,nounits"], text=True, timeout=10,
        ).strip().splitlines()[0]
        used, free = [int(x.strip()) for x in out.split(",")]
        return {"used_mib": used, "free_mib": free}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}


def _ollama_ps_context():
    try:
        out = subprocess.check_output(["ollama", "ps"], text=True, timeout=15)
        for line in out.splitlines()[1:]:
            if MODEL in line:
                parts = line.split()
                for token in parts:
                    if token.isdigit() and int(token) >= 1024:
                        return int(token)
    except Exception:  # noqa: BLE001
        return None
    return None


def _probe(ctx: int) -> dict:
    payload = {
        "model": MODEL,
        "prompt": "Reply with a compact JSON object only.",
        "stream": False,
        "options": {
            "num_ctx": ctx,
            "num_gpu": NUM_GPU,
            "num_predict": 16,
            "temperature": 0,
        },
    }
    req = urllib.request.Request(
        ENDPOINT + "/api/generate",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.time()
    row: dict = {"requested_num_ctx": ctx, "num_gpu_layers": NUM_GPU,
                 "gpu_before": _gpu_mib()}
    try:
        with _opener().open(req, timeout=240) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        row.update({
            "ok": True,
            "latency_s": round(time.time() - started, 2),
            "prompt_eval_count": data.get("prompt_eval_count"),
            "eval_count": data.get("eval_count"),
            "total_duration_ms": round((data.get("total_duration") or 0) / 1e6, 1),
            "response_excerpt": (data.get("response") or "")[:120],
        })
    except urllib.error.HTTPError as exc:
        row.update({"ok": False, "error": f"HTTP {exc.code}: {exc.read()[:300].decode('utf-8', 'replace')}",
                    "latency_s": round(time.time() - started, 2)})
    except Exception as exc:  # noqa: BLE001
        row.update({"ok": False, "error": f"{type(exc).__name__}: {exc}",
                    "latency_s": round(time.time() - started, 2)})
    row["gpu_after"] = _gpu_mib()
    row["ollama_ps_context"] = _ollama_ps_context()
    return row


def main() -> int:
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        os.environ.pop(key, None)
    rows = []
    for ctx in CTXS:
        row = _probe(ctx)
        rows.append(row)
        print(f"ctx={ctx:>6} ok={row['ok']} latency={row.get('latency_s')}s "
              f"gpu_after={row.get('gpu_after')} ps_ctx={row.get('ollama_ps_context')} "
              f"err={row.get('error', '')[:100]}")
        # Stop climbing once two consecutive configurations fail: circuit breaker.
        if len(rows) >= 2 and not rows[-1]["ok"] and not rows[-2]["ok"]:
            print("circuit breaker: two consecutive failures, stopping the climb")
            break

    ok_rows = [r for r in rows if r["ok"]]
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "basis": "measured (real Ollama /api/generate requests, f16 KV cache, no service restart)",
        "model": MODEL,
        "endpoint": ENDPOINT,
        "num_gpu_layers": NUM_GPU,
        "runtime_env": {
            "OLLAMA_FLASH_ATTENTION": os.getenv("OLLAMA_FLASH_ATTENTION", "<unset>"),
            "OLLAMA_KV_CACHE_TYPE": os.getenv("OLLAMA_KV_CACHE_TYPE", "<unset: default f16>"),
            "OLLAMA_CONTEXT_LENGTH": os.getenv("OLLAMA_CONTEXT_LENGTH", "<unset>"),
        },
        "rows": rows,
        "max_ok_num_ctx": max((r["requested_num_ctx"] for r in ok_rows), default=None),
        "note": "A short prompt only tests KV allocation, NOT long-context recall quality. "
                "Ollama may silently fall back to CPU KV offload; check latency and GPU memory.",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(REPORT), "max_ok_num_ctx": report["max_ok_num_ctx"],
                      "successes": len(ok_rows), "total": len(rows)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
