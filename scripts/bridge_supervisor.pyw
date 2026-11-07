"""Detached supervisor for the Virtu bridge.

Keeps the production bridge (scripts/virtu_service_pinned.py) alive: if it exits
for any reason (crash, OOM, killed), this loop restarts it after a short delay.

Launched via explorer.exe so it is orphaned from the interactive shell/session
and is not reaped when the agent session ends. All diagnostics go to log files
(opened in UTF-8) so the Windows GBK console codepage is never touched.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

PY = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe"
SCRIPT = r"D:\Virtu模型\scripts\virtu_service_pinned.py"
CWD = r"D:\Virtu模型"
SUP_LOG = r"D:\Virtu模型\_bridge_supervisor.log"
BRIDGE_OUT = r"D:\Virtu模型\_bridge_out.log"


def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}\n"
    try:
        with open(SUP_LOG, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def main() -> int:
    log("supervisor started; pinning bridge for the lifetime of this process")
    restarts = 0
    while True:
        try:
            out = open(BRIDGE_OUT, "ab")
        except Exception:
            out = None
        log(f"launching bridge (restart #{restarts})")
        try:
            proc = subprocess.Popen(
                [PY, SCRIPT],
                cwd=CWD,
                stdout=out,
                stderr=subprocess.STDOUT,
                close_fds=True,
            )
        except Exception as exc:  # noqa: BLE001
            log(f"spawn failed: {type(exc).__name__}: {exc}")
            if out is not None:
                out.close()
            time.sleep(3)
            continue
        rc = proc.wait()
        if out is not None:
            out.close()
        restarts += 1
        log(f"bridge exited rc={rc}; restarting in 3s")
        time.sleep(3)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("supervisor interrupted")
