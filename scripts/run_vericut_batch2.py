# -*- coding: utf-8 -*-
"""Run VERICUT 9.6 in documented headless batch mode.

Correct syntax (per help.vericut.com/automating_vericut/batch_vericut):
    vericut batch "vcp=<project.vcproject>" [auto-diff=<report.rpt>]

The previous runner used `BATCH batchp printargs <project>`; VERICUT rejected
`printargs` as an invalid user value ("下面的用户输入的数据无效: printargs"),
which is why every prior batch attempt failed.

Headless `batch` loads the project, processes the NC program, then exits.
We set LGFILNAM= to force the log into the ASCII working directory, and poll
that log for END-OF-FILE / error count. If the process does not exit within
`timeout`, we stop only the javaw PIDs this run started.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import time
from pathlib import Path

VERICUT_BAT = Path(r"E:\windows64\commands\vericut.bat")


def javaw_pids() -> set:
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-Process javaw -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id"],
        capture_output=True, text=True)
    return {int(x) for x in out.stdout.split() if x.strip().isdigit()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--workdir", default=r"E:\vc_impeller_run")
    ap.add_argument("--log", required=True)
    ap.add_argument("--autodiff", default="")
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args(argv)

    project = Path(args.project).resolve()
    workdir = Path(args.workdir).resolve()
    log = Path(args.log).resolve()
    log.parent.mkdir(parents=True, exist_ok=True)
    if log.exists():
        log.unlink()

    before = javaw_pids()
    t0 = time.time()

    # VERICUT project-relative log name is set in the .vcproject as <Log>vericut.log</Log>.
    # Force it to our chosen absolute ASCII path via LGFILNAM user variable.
    cmd = [str(VERICUT_BAT), "batch",
           f'vcp={project}',
           f'LGFILNAM={log}']
    if args.autodiff:
        cmd.append(f'auto-diff={args.autodiff}')
    print("CMD:", " ".join(cmd), flush=True)

    env = os.environ.copy()
    # VERICUT otherwise restores the last-opened project (millturn_session_day1)
    # and ignores vcp=; that stale project uses an encrypted control and crashes
    # the native IPC engine. Force a clean load of OUR project.
    env["CGTECH_IGNORE_LAST"] = "TRUE"
    proc = subprocess.Popen(cmd, cwd=str(workdir), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True)

    body = ""
    done = False
    while time.time() - t0 < args.timeout:
        time.sleep(3)
        if log.is_file():
            try:
                body = log.read_text(encoding="utf-8", errors="replace")
            except Exception:
                body = ""
            if ("END-OF-FILE" in body or re.search(r"错误数\s*[:：]", body)
                    or "Error Count" in body):
                # wait for size to stabilize
                s1 = log.stat().st_size
                time.sleep(2)
                if log.stat().st_size == s1:
                    done = True
                    break
        if proc.poll() is not None and not log.is_file():
            break

    elapsed = time.time() - t0
    # Only stop javaw processes started by this run that are still alive.
    for pid in javaw_pids() - before:
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        f"Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue"],
                       capture_output=True)

    try:
        out, _ = proc.communicate(timeout=5)
    except Exception:
        proc.kill()
        out, _ = proc.communicate()

    if log.is_file():
        body = log.read_text(encoding="utf-8", errors="replace")

    tail = out[-1500:] if out else ""
    print(f"project={project}")
    print(f"elapsed_s={elapsed:.1f} log_exists={log.is_file()} done_marker={done} "
          f"proc_rc={proc.poll()}")
    print(f"log_bytes={len(body)} autodiff={args.autodiff or '(none)'}")
    if tail.strip():
        print("--- process stdout tail ---")
        print(tail)
    # Error summary
    errs = [ln.strip() for ln in body.splitlines()
            if re.search(r"错误\s*[:：]|Error\s*:|错误数|Error Count", ln)]
    print(f"error_lines={len(errs)}")
    for e in errs[:15]:
        print("  " + e)
    return 0 if (log.is_file() and len(body) > 0) else 2


if __name__ == "__main__":
    raise SystemExit(main())
