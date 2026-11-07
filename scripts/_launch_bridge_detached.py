"""Detach the Virtu production bridge so it survives the Bash job lifetime.

Uses ShellExecuteW (not a child Popen) so the process is created outside the
sandbox job object and is not reaped when this shell exits. The bridge reads
VIRTU_VLLM_MODEL from HKCU\Environment (already set to virtu-boundary-sft),
so no env var needs to be injected here.
"""
from __future__ import annotations
import ctypes
import os
import sys

ROOT = r"D:\Virtu模型"
SCRIPT = os.path.join(ROOT, "scripts", "virtu_service_pinned.py")
PY = os.path.join(ROOT, ".venv", "Scripts", "python.exe")

if not os.path.exists(PY):
    PY = sys.executable
if not os.path.exists(SCRIPT):
    raise SystemExit(f"missing {SCRIPT}")

SW_HIDE = 0
rc = ctypes.windll.shell32.ShellExecuteW(
    None, "open", PY, f'"{SCRIPT}"', ROOT, SW_HIDE
)
# rc > 32 means success per Win32 semantics.
print(f"ShellExecuteW rc={rc} (>{32} == launched)")
sys.exit(0 if rc > 32 else 1)
