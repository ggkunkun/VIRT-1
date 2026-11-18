# -*- coding: utf-8 -*-
"""Run one VERICUT 9.6 project in batch-play mode and capture its log.

    python scripts/run_vericut_batch_case.py --project <case.vcproject> \
        --workdir E:/vericut_fix_work --log reports/vericut_fix_case_logs/<case>.log

VERICUT batch mode does not always exit after writing the log, so this runner
polls for ``END-OF-FILE`` / ``错误数:`` and then stops only the javaw processes
started by this invocation. It never touches E:/training.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

VERICUT_BAT = Path(r"E:\windows64\commands\vericut.bat")


def _javaw_pids() -> set:
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-Process javaw -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id"],
        capture_output=True, text=True)
    return {int(x) for x in out.stdout.split() if x.strip().isdigit()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--workdir", default=r"E:\vericut_fix_work")
    ap.add_argument("--log", required=True)
    ap.add_argument("--timeout", type=int, default=900)
    args = ap.parse_args(argv)

    project = Path(args.project).resolve()
    workdir = Path(args.workdir).resolve()
    log = Path(args.log).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    log.parent.mkdir(parents=True, exist_ok=True)
    if log.exists():
        log.unlink()

    before = _javaw_pids()
    t0 = time.time()
    # VERICUT 9.6 rejects the legacy "printargs" token ("参数无效") and only batch-plays a
    # project passed as ``vcp=<file>`` (``ip=`` expects a saved .ip state file, not a
    # .vcproject).  cmd.exe eats an unquoted "k=v" argument, so the raw command line is
    # handed to CreateProcess with the vcp argument quoted.
    cmdline = '"%s" BATCH batchp "vcp=%s"' % (VERICUT_BAT, project)
    proc = subprocess.Popen(cmdline, cwd=str(workdir),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    last_size = -1
    stable = 0
    text = ""
    while time.time() - t0 < args.timeout:
        time.sleep(3)
        # VERICUT writes <Log>vericut.log</Log> inside the project directory.
        cand = project.parent / "vericut.log"
        if not cand.is_file():
            cand = workdir / "vericut.log"
        if not cand.is_file():
            continue
        size = cand.stat().st_size
        text = cand.read_text(encoding="utf-8", errors="replace")
        done = "END-OF-FILE" in text or re.search(r"错误数\s*[:：]", text)
        if done and size == last_size:
            stable += 1
            if stable >= 2:
                break
        else:
            stable = 0
        last_size = size

    elapsed = time.time() - t0
    # Stop only the javaw processes started by this run.
    for pid in _javaw_pids() - before:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)

    src = project.parent / "vericut.log"
    if not src.is_file():
        src = workdir / "vericut.log"
    if src.is_file():
        log.write_text(src.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")

    body = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else text
    errors = [ln.strip() for ln in body.splitlines() if "错误:" in ln or "错误数" in ln]
    print(f"project={project}")
    print(f"elapsed_s={elapsed:.1f} completed={'END-OF-FILE' in body} log={log}")
    print(f"error_lines={len(errors)}")
    for line in errors[:12]:
        print("  " + line)
    return 0 if body else 2


if __name__ == "__main__":
    raise SystemExit(main())
