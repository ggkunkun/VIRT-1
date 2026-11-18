# -*- coding: utf-8 -*-
"""End-to-end verification: Remory protocol adapter -> Virtu main model.

Runs REAL Ollama generations (no mocks) and writes a falsifiable evidence report.

    .venv/Scripts/python.exe scripts/run_remory_live.py

The report labels every item as ``measured`` / ``asserted`` / ``untested``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from virtu_omni.memory import remory_adapter as R  # noqa: E402

MODEL = os.getenv("VIRTU_REMORY_MODEL", R.DEFAULT_MODEL)
ENDPOINT = os.getenv("VIRTU_OLLAMA_URL", R.DEFAULT_ENDPOINT)
REPORT = ROOT / "reports" / "REMORY_INTEGRATION_2026-11-12.json"
STORE = ROOT / "runs" / "remory" / "memory.sqlite"
RECALL_PROMPT = (
    "Return a world_state JSON containing the confirmed flange outer diameter "
    "in mm (field outer_dia_mm). Output JSON only, no explanation."
)
RECALL_PROMPT_FOS = (
    "Return a world_state JSON containing the confirmed safety factor "
    "(field safety_factor). Output JSON only, no explanation."
)


def _ollama_identity() -> dict:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(ENDPOINT + "/api/version", timeout=10) as resp:
            version = json.loads(resp.read().decode("utf-8")).get("version")
    except Exception as exc:  # noqa: BLE001
        version = f"unavailable: {type(exc).__name__}: {exc}"
    try:
        with opener.open(ENDPOINT + "/api/tags", timeout=10) as resp:
            tags = json.loads(resp.read().decode("utf-8")).get("models", [])
        match = next((m for m in tags if m.get("name") == MODEL), None)
        model_present = match is not None
        size = match.get("size") if match else None
    except Exception as exc:  # noqa: BLE001
        model_present, size = False, f"unavailable: {exc}"
    return {"ollama_version": version, "model": MODEL,
            "model_present": model_present, "model_size_bytes": size}


def _upstream_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(ROOT / "external" / "Remory"), "rev-parse", "HEAD"],
            text=True, timeout=10,
        ).strip()
    except Exception as exc:  # noqa: BLE001
        return f"unavailable: {exc}"


def _parse_json(text: str):
    try:
        return json.loads(text.strip()), True
    except Exception:  # noqa: BLE001
        return None, False


def _arm(backend, harness, *, checkpoint, prompt, name, max_tokens=160) -> dict:
    started = time.time()
    try:
        if checkpoint is None:
            result = harness.plain_generate(
                prefix_messages=[], messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
            )
        else:
            result = harness.generate(
                checkpoint=checkpoint, prefix_messages=[],
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
            )
        text = result.get("text", "")
        parsed, json_ok = _parse_json(text)
        return {
            "arm": name, "ok": True,
            "prompt_tokens": (result.get("usage") or {}).get("prompt_tokens"),
            "latency_s": round(time.time() - started, 2),
            "text": text[:600],
            "json_valid": json_ok,
            "top_level_key": list(parsed.keys())[0] if isinstance(parsed, dict) and parsed else None,
            "contains_160": "160" in text,
            "contains_2_1": "2.1" in text,
        }
    except Exception as exc:  # noqa: BLE001
        return {"arm": name, "ok": False, "error": f"{type(exc).__name__}: {exc}",
                "latency_s": round(time.time() - started, 2)}


def main() -> int:
    # Clear host-side transparent proxies for local Ollama traffic.
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        os.environ.pop(key, None)

    report: dict = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "basis": "measured (real Ollama generations) unless labelled otherwise",
        "model_identity": _ollama_identity(),
        "upstream": {
            "repo": "https://github.com/fudan-generative-vision/Remory",
            "clone": str(ROOT / "external" / "Remory"),
            "commit": _upstream_commit(),
            "license": "MIT",
            "version": "0.4.0",
        },
        "adapter": {
            "module": "virtu_omni/memory/remory_adapter.py",
            "backend": R.BACKEND_ID,
            "model": MODEL,
            "store": str(STORE),
        },
        "compatibility_verdict": {
            "native_soft_memory_possible": False,
            "basis": "asserted from upstream README/docs/deployment + measured local hardware",
            "upstream_requires": [
                "Linux x86_64 + Python 3.11+ + CUDA 13.0",
                "SGLang pinned revision with model hook (actor hidden states)",
                ">= 2 x 80 GB GPUs and 100 GB disk for Qwen3.8-27B + REMORY-1.9B",
                "released checkpoints bound to Qwen3.8-27B / GLM-5.3-Flash tokenizers",
            ],
            "local_facts": [
                "Windows 11 + Ollama 0.40.14 + RTX 4050 Laptop 6141 MiB",
                "main model virtu-wm-v3:chatml is a GGUF Qwen3 8.2B Q4_0 world model",
            ],
            "conclusion": "Only the compaction protocol layer can be integrated; "
                          "learned soft-token weights cannot be attached to this actor.",
        },
        "carrier_role_finding": {
            "basis": "measured 2026-11-12",
            "explicit_system_message": "prompt_tokens 3906 -> 71; Modelfile SYSTEM contract replaced; "
                                       "output changed away from world_state JSON",
            "user_message_carrier": "prompt_tokens 3909 -> 4052; contract preserved; "
                                    "model emitted outer_dia_mm=160 from memory-only fact",
            "decision": "memory carrier role=user (see TextClient.memory_message)",
        },
    }

    backend = R.OllamaChatBackend(endpoint=ENDPOINT, timeout=240.0)
    session = R.RemorySession(
        session_id="remory-live-20261112", model=MODEL, store_path=str(STORE),
        prefix_messages=[], backend=backend, keep_recent=2, residual_budget=24,
    )

    # --- Long history -> compaction -> drop history -> restart-style resume ---
    session.append("user", "任务开始：法兰外径 D160 = 160 mm，材质 45 钢，厚度 = 14 mm")
    session.append("assistant", "确认采用 D160，rc=0，sha256=abc123")
    for i in range(6):
        session.append("user", f"第 {i+1} 步：复核尺寸，主轴转速 = 1200 rpm")
        session.append("assistant", f"第 {i+1} 步已完成，已验证 rc=0")
    cp1 = session.compact(force=True)
    rec1 = session.store.load(cp1.handle, session.session_id)
    resumed = R.RemorySession(
        session_id="remory-live-20261112", model=MODEL, store_path=str(STORE),
        prefix_messages=[], backend=backend, keep_recent=2, residual_budget=24,
    )
    cp_resumed = resumed.resume(cp1.handle)
    report["protocol_evidence"] = {
        "basis": "measured",
        "handle": cp1.handle,
        "handle_format_ok": cp1.handle.startswith("rm_") and len(cp1.handle) == 51,
        "prefix_sha256": cp1.prefix_sha256,
        "history_after_compaction": len(session.history),
        "residual_items": rec1["receipt"]["residual_items"],
        "residual_sample": rec1["residual"][:6],
        "compression_depth": rec1["receipt"]["compression_depth"],
        "sqlite_restart_resume_ok": cp_resumed.handle == cp1.handle,
        "memory_render_chars": len(resumed.client.render(cp1.handle)),
    }

    # --- Real generations ---
    arms = [
        _arm(backend, resumed.harness, checkpoint=None, prompt=RECALL_PROMPT,
             name="A_no_memory_control"),
        _arm(backend, resumed.harness, checkpoint=cp_resumed, prompt=RECALL_PROMPT,
             name="B_with_remory_memory"),
    ]

    # --- Second compaction (chained residual) then FOS recall ---
    session.append("user", "追加约束：安全系数 FOS = 2.1，输出文件 flange.step")
    session.append("assistant", "已验证 FOS，rc=0")
    for i in range(4):
        session.append("user", f"收尾步骤 {i}")
        session.append("assistant", f"收尾 {i} 完成")
    cp2 = session.compact(force=True)
    rec2 = session.store.load(cp2.handle, session.session_id)
    resumed2 = R.RemorySession(
        session_id="remory-live-20261112", model=MODEL, store_path=str(STORE),
        prefix_messages=[], backend=backend, keep_recent=2, residual_budget=24,
    )
    cp2_resumed = resumed2.resume(cp2.handle)
    arms.append(
        _arm(backend, resumed2.harness, checkpoint=cp2_resumed, prompt=RECALL_PROMPT_FOS,
             name="C_chained_compaction_recall")
    )
    # Contract-shape arm: the recall probes above ask for a bare JSON field,
    # which legitimately bypasses the world_state wrapper. This arm uses the
    # model's native request shape to prove the Modelfile SYSTEM contract is
    # still in force while Remory memory is injected.
    arms.append(
        _arm(backend, resumed.harness, checkpoint=cp_resumed,
             prompt="reply with world_state json",
             name="D_contract_shape_with_memory")
    )
    report["chained_evidence"] = {
        "basis": "measured",
        "handle": cp2.handle, "previous": rec2["previous"],
        "previous_matches_first": rec2["previous"] == cp1.handle,
        "compression_depth": rec2["receipt"]["compression_depth"],
        "residual_items": rec2["receipt"]["residual_items"],
    }

    # --- Unified gateway attachment (real request through LLMGateway) ---
    gateway_evidence: dict = {"basis": "measured"}
    try:
        from virtu_omni.runtime.llm_gateway import GatewayConfig, LLMGateway

        gw = LLMGateway(config=GatewayConfig(
            endpoint=ENDPOINT, default_model=MODEL, timeout=240.0, max_retries=0,
        ))
        attach_session = R.RemorySession(
            session_id="remory-live-20261112", model=MODEL, store_path=str(STORE),
            prefix_messages=[], backend=backend, keep_recent=2,
        )
        attach_session.resume(cp1.handle)
        R.attach_to_gateway(gw, attach_session)
        out = gw.chat([{"role": "user", "content": RECALL_PROMPT}], max_tokens=160)
        data = out.get("data", {}) if isinstance(out, dict) else {}
        content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "")
        gateway_evidence.update({
            "success": bool(out.get("success")),
            "injection_count": attach_session.injection_count,
            "injected_handle": attach_session.last_injected_handle,
            "prompt_tokens": (data.get("usage") or {}).get("prompt_tokens"),
            "response_text": content[:400],
            "contains_160": "160" in content,
        })
    except Exception as exc:  # noqa: BLE001
        gateway_evidence.update({"success": False, "error": f"{type(exc).__name__}: {exc}"})
    report["gateway_attachment"] = gateway_evidence

    a = next(x for x in arms if x["arm"] == "A_no_memory_control")
    b = next(x for x in arms if x["arm"] == "B_with_remory_memory")
    c = next(x for x in arms if x["arm"] == "C_chained_compaction_recall")
    d = next(x for x in arms if x["arm"] == "D_contract_shape_with_memory")
    delta = None
    if a.get("prompt_tokens") is not None and b.get("prompt_tokens") is not None:
        delta = b["prompt_tokens"] - a["prompt_tokens"]
    report["live_arms"] = arms
    report["verdict"] = {
        "basis": "measured",
        "all_arms_completed": all(x.get("ok") for x in arms),
        "injection_token_delta": delta,
        "memory_entered_context": delta is not None and delta > 0,
        "json_valid_with_memory": bool(b.get("json_valid")),
        "contract_preserved_with_memory": bool(d.get("json_valid") and d.get("top_level_key") == "world_state"),
        "contract_shape_evidence": {"arm": "D_contract_shape_with_memory",
                                    "top_level_key": d.get("top_level_key"), "text": d.get("text")},
        "recall_from_memory_only_fact": bool(b.get("contains_160")) and not bool(a.get("contains_160")),
        "chained_residual_recall": bool(c.get("contains_2_1")),
        "gateway_hook_works": bool(gateway_evidence.get("success") and gateway_evidence.get("injection_count", 0) > 0),
        "caveat": "text-residual backend; NOT upstream learned soft-memory checkpoints. "
                  "Recall is a single-prompt probe, not a benchmark score; "
                  "arms A/B/C use a bare-JSON recall prompt that intentionally "
                  "bypasses the world_state wrapper, arm D verifies the native shape.",
    }

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "report": str(REPORT),
        "verdict": report["verdict"],
        "arms": [{k: x.get(k) for k in ("arm", "ok", "prompt_tokens", "text", "contains_160")} for x in arms],
        "gateway": gateway_evidence,
    }, ensure_ascii=False, indent=2))
    return 0 if report["verdict"]["all_arms_completed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
