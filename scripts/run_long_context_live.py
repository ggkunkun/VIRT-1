# -*- coding: utf-8 -*-
"""End-to-end long-context verification on the real Virtu main model.

Four real Ollama generations compare brute-force context expansion with the
GitHub-grounded retrieval/compression module (needle-in-a-haystack).

    .venv/Scripts/python.exe scripts/run_long_context_live.py
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from virtu_omni.context import long_context as LC  # noqa: E402

ENDPOINT = os.getenv("VIRTU_OLLAMA_URL", "http://127.0.0.1:11434")
REPORT = ROOT / "reports" / "LONG_CONTEXT_INTEGRATION_2026-11-12.json"
NEEDLE = "167.3"
SEGMENTS = 45
QUERY = (
    "Return a world_state JSON containing the FINAL CONFIRMED flange outer "
    "diameter in mm (field outer_dia_mm), using the notes above. "
    "Draft values are not final. Output JSON only."
)
RETRIEVAL_QUERY = "最终确认 法兰外径 外径 FOS 安全系数"


def build_corpus() -> str:
    parts = []
    for i in range(SEGMENTS):
        parts.append(
            f"第 {i+1} 轮工艺评审纪要。草案外径 = {150+i} mm，孔径 = {40+i} mm，"
            f"主轴转速 = {1100+i} rpm，进给量 = {0.10+0.01*i:.2f} mm/r。"
            "与会人员讨论了刀具磨损、装夹刚性、冷却液配比与热处理变形等常规事项，"
            "会议记录已归档，后续按流程复核。上述数值均为阶段草案，未作为最终执行依据。"
        )
    needle = (
        "最终确认：法兰外径 = 167.3 mm，安全系数 FOS = 2.37，材料 45 钢，"
        "输出文件 flange_final.step，sha256=7d1f8c2e，rc=0。"
        "本条为最终执行依据，覆盖此前所有草案数值。"
    )
    parts.insert(SEGMENTS // 2, needle)
    return "\n\n".join(parts)


def _gpu():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            text=True, timeout=10,
        )
        return int(out.strip().splitlines()[0])
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc}"


def _git_head(path: str) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(ROOT / path), "rev-parse", "HEAD"],
                                       text=True, timeout=10).strip()
    except Exception as exc:  # noqa: BLE001
        return f"unavailable: {exc}"


def _server_flags() -> dict:
    log = Path(os.getenv("LOCALAPPDATA", "")) / "Ollama" / "server.log"
    try:
        text = log.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}
    cmds = re.findall(r"starting llama-server.*?cmd=\"([^\"]+)\"", text)
    kv = next((c for c in reversed(cmds) if "cache-type-k" in c), "")
    return {
        "basis": "measured from Ollama server.log",
        "latest_llama_server_cmd": kv[:600],
        "q8_0_kv": "cache-type-k q8_0" in kv and "cache-type-v q8_0" in kv,
        "flash_attention": "--flash-attn on" in kv,
        "context_shift": "--context-shift" in kv,
        "n_ctx_train": next((m.group(1) for m in re.finditer(r"n_ctx_train\s*=\s*(\d+)", text)), None),
    }


def _manifest() -> dict:
    try:
        out = subprocess.check_output(
            ["ollama", "show", LC.DEFAULT_MODEL, "--modelfile"], text=True, timeout=30
        )
        return {
            "basis": "measured from ollama show --modelfile",
            "model": LC.DEFAULT_MODEL,
            "num_ctx": next((int(m.group(1)) for m in re.finditer(r"PARAMETER num_ctx (\d+)", out)), None),
            "num_gpu": next((int(m.group(1)) for m in re.finditer(r"PARAMETER num_gpu (\d+)", out)), None),
            "system_contract_preserved": 'SYSTEM """你是 Virtu 制造世界模型' in out,
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}


def _parse(text: str):
    try:
        value = json.loads(text.strip())
        return True, (list(value.keys())[0] if isinstance(value, dict) and value else None)
    except Exception:  # noqa: BLE001
        return False, None


def _run(name: str, backend, messages, *, model: str, num_ctx: int,
         extra_meta: dict | None = None) -> dict:
    started = time.time()
    before = _gpu()
    row: dict = {"arm": name, "model": model, "num_ctx": num_ctx,
                 "gpu_before_mib": before, "extra_meta": extra_meta or {}}
    try:
        result = backend.chat(messages, model=model, num_ctx=num_ctx, max_tokens=128)
        text = result.get("text", "")
        json_ok, top_key = _parse(text)
        row.update({
            "ok": True,
            "prompt_tokens": (result.get("usage") or {}).get("prompt_tokens"),
            "completion_tokens": (result.get("usage") or {}).get("completion_tokens"),
            "latency_s": result.get("latency_s", round(time.time() - started, 2)),
            "total_ms": (result.get("timings") or {}).get("total_ms"),
            "load_ms": (result.get("timings") or {}).get("load_ms"),
            "text": text[:500],
            "json_valid": json_ok,
            "top_level_key": top_key,
            "needle_recalled": NEEDLE in text,
        })
    except Exception as exc:  # noqa: BLE001
        row.update({"ok": False, "error": f"{type(exc).__name__}: {exc}",
                    "latency_s": round(time.time() - started, 2)})
    row["gpu_after_mib"] = _gpu()
    print(f"{name}: ok={row['ok']} tokens={row.get('prompt_tokens')} "
          f"lat={row.get('latency_s')}s needle={row.get('needle_recalled')} "
          f"err={row.get('error', '')[:90]}")
    return row


def main() -> int:
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        os.environ.pop(key, None)

    corpus = build_corpus()
    backend = LC.NativeChatBackend(endpoint=ENDPOINT, timeout=600.0)
    store_path = str(ROOT / "runs" / "long_context" / "chunks.sqlite")

    # Module sessions: same corpus, different physical windows.
    sess_5120 = LC.LongContextSession(store_path=store_path, backend=backend,
                                      physical_ctx=5120, model=LC.BASE_MODEL, top_k=4)
    sess_32768 = LC.LongContextSession(store_path=store_path, backend=backend,
                                       physical_ctx=32768, model=LC.DEFAULT_MODEL, top_k=4)
    n_chunks = sess_5120.ingest("process_minutes", corpus, chunk_chars=400)
    sess_32768.ingest("process_minutes", corpus, chunk_chars=400)
    msg_mod, meta_mod = sess_5120.compose(QUERY, retrieval_query=RETRIEVAL_QUERY)

    full_prompt = corpus + "\n\n<TASK>\n" + QUERY + "\n</TASK>"
    msg_full = [{"role": "user", "content": full_prompt}]

    arms = [
        _run("A_bruteforce_5120", backend, msg_full, model=LC.BASE_MODEL, num_ctx=5120),
        _run("B_full_32768", backend, msg_full, model=LC.DEFAULT_MODEL, num_ctx=32768),
        _run("C_module_5120", backend, msg_mod, model=LC.BASE_MODEL, num_ctx=5120,
             extra_meta=meta_mod),
        _run("D_module_32768", backend, msg_mod, model=LC.DEFAULT_MODEL, num_ctx=32768,
             extra_meta=meta_mod),
    ]

    # Real unified-gateway hook: proves the module is actually wired into
    # the project's LLMGateway, not just callable from a standalone script.
    gateway_evidence: dict = {"basis": "measured"}
    try:
        from virtu_omni.runtime.llm_gateway import GatewayConfig, LLMGateway

        gw = LLMGateway(config=GatewayConfig(
            endpoint=ENDPOINT, default_model=LC.DEFAULT_MODEL,
            timeout=300.0, max_retries=0,
        ))
        LC.attach_to_gateway(gw, sess_32768)
        out = gw.chat([{"role": "user", "content": QUERY}], max_tokens=128)
        data = out.get("data", {}) if isinstance(out, dict) else {}
        content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "")
        gateway_evidence.update({
            "success": bool(out.get("success")),
            "injection_count": sess_32768.injection_count,
            "prompt_tokens": (data.get("usage") or {}).get("prompt_tokens"),
            "text": content[:300],
            "needle_recalled": NEEDLE in content,
        })
    except Exception as exc:  # noqa: BLE001
        gateway_evidence.update({"success": False, "error": f"{type(exc).__name__}: {exc}"})

    def get(prefix):
        return next(a for a in arms if a["arm"].startswith(prefix))

    a, b, c, d = get("A_"), get("B_"), get("C_"), get("D_")
    matrix_path = ROOT / "reports" / "OLLAMA_CONTEXT_MATRIX_2026-11-12.json"
    matrix_max = None
    if matrix_path.exists():
        try:
            matrix_max = json.loads(matrix_path.read_text(encoding="utf-8")).get("max_ok_num_ctx")
        except Exception:  # noqa: BLE001
            pass

    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "basis": "measured (real Ollama /api/chat generations) unless labelled otherwise",
        "github_sources": [
            {"repo": "https://github.com/ggml-org/llama.cpp",
             "role": "q8_0 KV cache, flash attention, context-shift, YaRN CLI",
             "local_evidence": "Ollama server.log llama-server command line"},
            {"repo": "https://github.com/ollama/ollama",
             "role": "OLLAMA_KV_CACHE_TYPE / OLLAMA_FLASH_ATTENTION / num_ctx options",
             "local_evidence": "ollama serve --help + per-request options"},
            {"repo": "https://github.com/microsoft/LLMLingua",
             "role": "prompt compression with protected structural tokens (concept)",
             "local_path": "external/LLMLingua/README.md", "commit": _git_head("external/LLMLingua")},
            {"repo": "https://github.com/mit-han-lab/streaming-llm",
             "role": "attention sinks / rolling KV (concept; llama.cpp context-shift analogue)",
             "local_path": "external/streaming-llm/README.md", "commit": _git_head("external/streaming-llm")},
        ],
        "runtime_evidence": _server_flags(),
        "model_manifest": _manifest(),
        "physical_matrix": {"basis": "measured", "report": str(matrix_path),
                            "max_ok_num_ctx": matrix_max},
        "corpus": {
            "basis": "measured", "segments": SEGMENTS, "chars": len(corpus),
            "chunks": n_chunks, "needle": NEEDLE,
            "needle_segment_index": SEGMENTS // 2,
            "store_stats": sess_5120.store.stats(),
        },
        "module": {"file": "virtu_omni/context/long_context.py",
                   "backend": LC.BACKEND_ID,
                   "retrieval_query": meta_mod["retrieval_query"],
                   "retrieved_sources": meta_mod["sources"],
                   "estimated_packet_tokens": meta_mod["estimated_packet_tokens"],
                   "input_budget_tokens_5120": meta_mod["input_budget_tokens"],
                   "retrieved_chunks": meta_mod["retrieved_chunks"],
                   "budget_exceeded": meta_mod["budget_exceeded"]},
        "arms": arms,
        "gateway_attachment": gateway_evidence,
        "verdict": {
            "basis": "measured",
            "all_generation_arms_ok": all(x["ok"] for x in arms if not x["arm"].startswith("A_")),
            "negative_control_rejected_as_expected": (
                not a["ok"] and "400" in str(a.get("error", ""))
            ),
            "bruteforce_5120_recalled": bool(a.get("needle_recalled")),
            "full_32768_recalled": bool(b.get("needle_recalled")),
            "module_5120_recalled": bool(c.get("needle_recalled")),
            "module_32768_recalled": bool(d.get("needle_recalled")),
            "module_token_saving_vs_full": (
                b.get("prompt_tokens") - c.get("prompt_tokens")
                if b.get("prompt_tokens") is not None and c.get("prompt_tokens") is not None else None
            ),
            "module_vs_full_same_window_latency_saving_s": (
                round(b["latency_s"] - d["latency_s"], 2)
                if b.get("latency_s") is not None and d.get("latency_s") is not None else None
            ),
            "gateway_hook_live_ok": bool(
                gateway_evidence.get("success") and gateway_evidence.get("needle_recalled")
                and gateway_evidence.get("injection_count", 0) > 0
            ),
            "latency_basis": "B vs D use the same 32768 model (hot); C switches to "
                             "the 5120 model and includes a reload, so B vs C latency "
                             "is not an apples-to-apples comparison.",
        },
        "caveats": [
            "NOT a new attention architecture and NOT LLMLingua's trained compressor: "
            "retrieval is BM25-lite over SQLite chunks and compression is deterministic.",
            "YaRN beyond the model's native 40960 is NOT enabled (Ollama 0.40.14 "
            "does not expose rope scaling; static YaRN degrades short prompts).",
            "Single needle-in-a-haystack probe, not a long-context benchmark. "
            "Concurrency, q4_0 KV, >40960 contexts and multi-needle recall are untested.",
            "First run exposed a real defect: an English-only query retrieved Chinese "
            "draft chunks (model answered 153). Fixed with domain-token expansion plus "
            "an explicit retrieval_query; tests/test_long_context.py covers the regression.",
            "The main model is a strict world-model; recall is judged by whether the "
            "unique value 167.3 appears in its JSON output.",
        ],
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(REPORT), "verdict": report["verdict"]},
                     ensure_ascii=False, indent=2))
    v = report["verdict"]
    return 0 if v["all_generation_arms_ok"] and v["negative_control_rejected_as_expected"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
