#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Queue one statistically-powered RSI run behind whatever is holding the box.

Why queue instead of start: a measurement chain on this host is an exclusive resource
(``agents.md`` §8.6) and Ollama thrashes models between jobs (measured: swapping a model
costs ~20-90 s and silently kills in-flight requests). As of 2026-11-05 13:55 the box
already has ``run_chain4.py``, ``run_chain2.py`` and a queued ``eval_disciplined_ab.py``
smoke arm waiting on its own silence gate. This launcher therefore waits for the same
quiet condition, then runs one bounded RSI experiment against the new solver-verified pool
so the gate can finally be *satisfiable* (validation >= min_validation).

It does not approve anything, does not train, and does not touch production.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "runs" / "rsi" / "queued_run.log"

FOREIGN = ("virtu_eval" + os.sep + "runner.py", "virtu_eval/runner.py", "runner.py",
           "run_chain", "eval_disciplined_ab",
           "model_drives_solidworks", "run_screening")
OWN_MARKERS = ("queue_rsi_pool_run", "virtu_omni" + os.sep + "rsi" + os.sep + "cli.py",
               "virtu_omni/rsi/cli.py")


def running_python_commands() -> list:
    """Process table with command lines (Get-CimInstance; tasklist truncates them).

    Built with string interpolation instead of ``??`` so it also runs under Windows
    PowerShell 5.1, which has no null-coalescing operator.
    """
    ps = ('Get-CimInstance Win32_Process -Filter "Name=\'python.exe\' OR Name=\'pythonw.exe\'" '
          ' | ForEach-Object { "$($_.ProcessId)|$($_.CommandLine)" }')
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                             capture_output=True, text=True, timeout=90,
                             encoding="utf-8", errors="replace").stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def contenders(self_pid: int) -> list:
    busy = []
    for line in running_python_commands():
        pid, _, cmd = line.partition("|")
        if not cmd or pid.strip() == str(self_pid):
            continue
        if any(marker in cmd for marker in OWN_MARKERS):
            continue
        if any(marker in cmd for marker in FOREIGN):
            busy.append((pid.strip(), cmd[:160]))
    return busy


def ollama_loaded() -> list:
    import urllib.request

    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/ps", timeout=10) as fh:
            data = json.loads(fh.read().decode("utf-8", "replace"))
    except OSError:
        return []
    return [m.get("name", "?") for m in data.get("models", [])]


def wait_for_quiet(deadline_s: int, hold_s: int, poll_s: int, log) -> bool:
    started = time.time()
    clear_since = None
    while time.time() - started < deadline_s:
        busy = contenders(os.getpid())
        loaded = ollama_loaded()
        if busy or loaded:
            clear_since = None
            note = f"busy={[p for p, _ in busy][:3]} loaded={loaded[:3]}"
        else:
            if clear_since is None:
                clear_since = time.time()
                note = "quiet, holding"
            elif time.time() - clear_since >= hold_s:
                log.write("quiet window acquired\n")
                return True
            note = f"quiet {int(time.time() - clear_since)}s/{hold_s}s"
        log.write(f"{time.strftime('%H:%M:%S')} {note}\n")
        log.flush()
        time.sleep(poll_s)
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case-dir", default="data/benchmark/virtu_rsi_pool_v1")
    ap.add_argument("--dims", default="physics")
    ap.add_argument("--model-id", default="virtu-disciplined:v1")
    ap.add_argument("--limit", type=int, default=84)
    ap.add_argument("--min-validation", type=int, default=24)
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--max-calls", type=int, default=400)
    ap.add_argument("--max-seconds", type=int, default=5400)
    ap.add_argument("--protect-dirs", default=",".join((
        "data/benchmark/virtu_eval_phys_v1", "data/benchmark/virtu_eval_v1",
        "data/benchmark/virtu_eval_cl_v1")))
    ap.add_argument("--quiet-wait", type=int, default=7200, help="max seconds to wait for silence")
    ap.add_argument("--quiet-hold", type=int, default=120, help="seconds of silence required")
    ap.add_argument("--poll", type=int, default=30)
    ap.add_argument("--no-wait", action="store_true")
    args = ap.parse_args()

    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8", newline="\n") as log:
        log.write(f"\n=== queued at {time.strftime('%F %T')} pid={os.getpid()} ===\n")
        log.flush()
        manifest = ROOT / args.case_dir / "POOL_MANIFEST.json"
        if not manifest.is_file():
            log.write("REFUSED: pool manifest missing -> run scripts/build_rsi_case_pool.py first\n")
            return 3
        if not args.no_wait and not wait_for_quiet(args.quiet_wait, args.quiet_hold, args.poll, log):
            log.write("GIVEUP: no quiet window inside the deadline; nothing was measured\n")
            return 4
        cmd = [sys.executable, "-X", "utf8", "-m", "virtu_omni.rsi.cli", "run",
               "--case-dir", args.case_dir, "--dims", args.dims, "--model-id", args.model_id,
               "--limit", str(args.limit), "--min-validation", str(args.min_validation),
               "--rounds", str(args.rounds), "--max-calls", str(args.max_calls),
               "--max-seconds", str(args.max_seconds),
               "--protect-dirs", args.protect_dirs]
        log.write("CMD " + " ".join(cmd) + "\n")
        log.flush()
        proc = subprocess.run(cmd, cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT,
                              encoding="utf-8", errors="replace")
        log.write(f"rc={proc.returncode}\n")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
