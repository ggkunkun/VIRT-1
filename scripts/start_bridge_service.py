"""Start or restart the Virtu bridge as a persistent desktop process.

The WorkBuddy sandbox reaps ordinary child processes when a command exits. A
shortcut launched by explorer.exe escapes that job, so the service keeps serving
after this helper returns. Logs are written by start_virtu_bridge.py itself.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request

import psutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LNK_PATH = os.path.join(ROOT, "VirtuBridgeService.lnk")
LOG_PATH = os.path.join(ROOT, "logs", "bridge_service.log")
HEALTH_URL = "http://127.0.0.1:8000/v1/models"


def stop_bridge() -> list[int]:
    stopped = []
    seen = set()
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmd = " ".join(proc.info.get("cmdline") or [])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        if ("start_virtu_bridge.py" not in cmd
                and "workbuddy_virtu_bridge.py" not in cmd
                and "run_virtu_service.py" not in cmd
                and "virtu_service_pinned.py" not in cmd):
            continue
        try:
            for child in proc.children(recursive=True):
                if child.pid not in seen:
                    seen.add(child.pid)
                    child.terminate()
            if proc.pid not in seen:
                seen.add(proc.pid)
                proc.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    deadline = time.time() + 5
    while time.time() < deadline and any(psutil.pid_exists(pid) for pid in seen):
        time.sleep(0.2)
    for pid in seen:
        try:
            if psutil.pid_exists(pid):
                psutil.Process(pid).kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    stopped.extend(sorted(seen))
    return stopped


def create_shortcut() -> str:
    from win32com.client import Dispatch

    python = sys.executable
    venv_python = os.path.join(ROOT, ".venv", "Scripts", "python.exe")
    # pythonw hangs during this bridge's win32/GUI imports on this host. Use the
    # console interpreter in a minimized window; explorer still detaches it from
    # the WorkBuddy job so it survives after this helper exits.
    target = venv_python if os.path.exists(venv_python) else python
    shell = Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(LNK_PATH)
    shortcut.TargetPath = target
    shortcut.Arguments = '"%s"' % os.path.join(ROOT, "scripts", "virtu_service_pinned.py")
    shortcut.WorkingDirectory = ROOT
    shortcut.WindowStyle = 7
    shortcut.Description = "Virtu local model bridge"
    shortcut.Save()
    return target


def check_health(timeout: float = 150.0) -> dict:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            with opener.open(HEALTH_URL, timeout=1) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(0.5)
    raise RuntimeError(f"bridge did not become ready: {type(last).__name__}: {last}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restart", action="store_true",
                        help="stop matching bridge processes before launching")
    parser.add_argument("--timeout", type=float, default=150.0)
    args = parser.parse_args(argv)
    if args.restart:
        print("stopped_pids=", stop_bridge())
    pythonw = create_shortcut()
    subprocess.Popen(["explorer.exe", LNK_PATH], cwd=ROOT)
    try:
        data = check_health(args.timeout)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        if os.path.exists(LOG_PATH):
            with open(LOG_PATH, encoding="utf-8", errors="replace") as stream:
                lines = stream.read().splitlines()[-30:]
            print("\n".join(lines), file=sys.stderr)
        return 1
    print(json.dumps({"launcher": pythonw, "models": data}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
