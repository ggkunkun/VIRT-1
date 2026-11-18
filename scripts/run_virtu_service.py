"""Fixed production entry point for the Virtu bridge.

The launcher defaults are edited by other tooling in this workspace, so the
service pins its model routing explicitly here. It also ensures the bridge token
and WorkBuddy endpoint stay in sync before binding port 8000.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Deployment gate (benchmarks/VIRTU_DEPLOY_ARTIFACT_GATE_2026-11-01.md):
# auto paths must use trained artifacts; never silently serve the untrained base.
os.environ["VIRTU_BACKEND"] = "vllm_http"
os.environ["VIRTU_VLLM_URL"] = "http://127.0.0.1:11434/v1"
os.environ["VIRTU_VLLM_MODEL"] = os.getenv("VIRTU_VLLM_MODEL", "virtu-ties-v1:latest")
os.environ["VIRTU_TOOL_MODEL"] = os.getenv("VIRTU_TOOL_MODEL", "virtu-ties-v1:latest")
os.environ.setdefault("VIRTU_MAX_TOKENS", "1024")
os.environ.setdefault("VIRTU_TEMPERATURE", "0.3")

from bridges.bridge_security import ensure_bridge_token, sync_workbuddy_token  # noqa: E402

token = ensure_bridge_token()
os.environ["VIRTU_BRIDGE_TOKEN"] = token
try:
    sync_workbuddy_token(token)
except Exception as exc:  # noqa: BLE001
    print(f"[service] WorkBuddy token sync failed: {type(exc).__name__}: {exc}", flush=True)

from scripts.workbuddy_virtu_bridge import run_server  # noqa: E402

if __name__ == "__main__":
    run_server()
