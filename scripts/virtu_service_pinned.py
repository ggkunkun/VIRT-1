"""Authoritative production entry point for the Virtu bridge.

This file intentionally pins the serving models. Other tooling in this workspace
edits the generic launcher defaults, so the live service must not depend on them.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ["VIRTU_BACKEND"] = "vllm_http"
os.environ["VIRTU_VLLM_URL"] = "http://127.0.0.1:11434/v1"
# 服务模型的选择顺序：进程环境变量 > HKCU\Environment 持久值 > qwen3:8b（回滚目标）。
# 读注册表是必要的：setx 写入后已运行的 explorer 不会收到 WM_SETTINGCHANGE 广播，
# 新起的进程可能仍继承旧环境变量，此时注册表才是可靠的真相来源。
def _pinned_text_model() -> str:
    default = "virtu-disciplined:v1"
    env_val = os.environ.get("VIRTU_VLLM_MODEL")
    if env_val and env_val != "virtu-boundary-sft":
        return env_val
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            val, _ = winreg.QueryValueEx(k, "VIRTU_VLLM_MODEL")
        if val and val != "virtu-boundary-sft":
            return val
    except (OSError, ImportError):
        pass
    return default


os.environ["VIRTU_VLLM_MODEL"] = _pinned_text_model()
os.environ["VIRTU_TOOL_MODEL"] = "virtu-ties-v1:latest"
os.environ.setdefault("VIRTU_THINKING_MODE", "off")
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
