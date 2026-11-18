# -*- coding: utf-8 -*-
"""Idempotent verification of the long-context runtime configuration.

Read-only by default. Checks the actual llama-server command lines (truth),
process env, the long-context model manifest, and module deliverables.

    .venv/Scripts/python.exe scripts/verify_long_context_runtime.py
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
REPORT = ROOT / "reports" / "RUNTIME_CONFIG_VERIFY_2026-11-12.json"
SERVER_LOG = Path(os.getenv("LOCALAPPDATA", "")) / "Ollama" / "server.log"


def _server_cmds() -> list:
    try:
        text = SERVER_LOG.read_text(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return []
    return re.findall(r'starting llama-server.*?cmd="([^"]+)"', text)


def _manifest() -> dict:
    try:
        out = subprocess.check_output(
            ["ollama", "show", "virtu-wm-v3:longctx", "--modelfile"],
            text=True, timeout=30)
        return {
            "exists": True,
            "num_ctx": next((int(m.group(1)) for m in
                             re.finditer(r"PARAMETER num_ctx (\d+)", out)), None),
            "num_gpu": next((int(m.group(1)) for m in
                             re.finditer(r"PARAMETER num_gpu (\d+)", out)), None),
            "system_contract_preserved": "SYSTEM \"\"\"你是 Virtu 制造世界模型" in out,
        }
    except Exception as exc:  # noqa: BLE001
        return {"exists": False, "error": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    cmds = _server_cmds()
    active = cmds[-1] if cmds else ""
    checks = {
        "flash_attention_in_active_server": "--flash-attn on" in active,
        "q8_0_kv_in_active_server": ("cache-type-k q8_0" in active
                                     and "cache-type-v q8_0" in active),
        "context_shift_in_active_server": "--context-shift" in active,
        "process_env_flash_attention": os.getenv("OLLAMA_FLASH_ATTENTION", "<unset>"),
        "process_env_kv_cache_type": os.getenv("OLLAMA_KV_CACHE_TYPE", "<unset>"),
        "longctx_manifest": _manifest(),
        "deliverables_present": {
            str(p.relative_to(ROOT)): p.exists()
            for p in [
                ROOT / "virtu_omni/context/long_context.py",
                ROOT / "virtu_omni/memory/remory_adapter.py",
                ROOT / "Modelfile_longctx",
                ROOT / "scripts/run_long_context_live.py",
                ROOT / "scripts/run_long_context_stress.py",
                ROOT / "scripts/probe_yarn_server.py",
                ROOT / "scripts/probe_ollama_context.py",
            ]
        },
        "ollama_context_length_env": os.getenv("OLLAMA_CONTEXT_LENGTH", "<unset>"),
    }
    manifest = checks["longctx_manifest"]
    all_green = (
        checks["flash_attention_in_active_server"]
        and checks["q8_0_kv_in_active_server"]
        and checks["context_shift_in_active_server"]
        and manifest.get("exists") and manifest.get("num_ctx") == 32768
        and manifest.get("system_contract_preserved")
        and all(checks["deliverables_present"].values())
    )
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "basis": "measured (server.log command lines + ollama show + filesystem)",
        "server_log": str(SERVER_LOG),
        "active_llama_server_cmd": active[:800],
        "recent_server_cmd_count": len(cmds),
        "checks": checks,
        "all_green": all_green,
        "recommended_commands_if_missing": [
            "setx OLLAMA_FLASH_ATTENTION 1",
            "setx OLLAMA_KV_CACHE_TYPE q8_0",
            "# restart the Ollama service for the above to take effect",
            "ollama create virtu-wm-v3:longctx -f Modelfile_longctx",
        ],
        "note": "This script is read-only; it does not change environment variables "
                "or restart the service. num_ctx above 40960 requires engine-level YaRN "
                "(see YARN_SERVER_PROBE report).",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(REPORT), "all_green": all_green,
                      "checks": {k: v for k, v in checks.items()
                                 if k != "deliverables_present"}},
                     ensure_ascii=False, indent=2))
    return 0 if all_green else 1


if __name__ == "__main__":
    raise SystemExit(main())
