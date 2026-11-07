"""Start the RSI run only when the measurement chain is genuinely idle (§8.6).

Why this exists
---------------
On 2026-11-05 an RSI run and the ``qwen3:8b`` board leg fought over the same 6 GB card.
``virtu_eval/arms.py`` sends no ``keep_alive``, so every request reset the model's five minute
lease.  With two 8B models trading places the card spent its time reloading: 70 s per call and
one case in five minutes, which would have ended in a ``blocked`` RSI receipt anyway while
starving the board leg.  The run had to be killed by hand.

What this gate does — three things, nothing else
------------------------------------------------
1. Waits for a quiet window.  Quiet means *both* the repo's own foreign-runner judgement is
   empty *and* no measurement file has been written recently.  The second half matters because
   a leg whose command line we cannot recognise still writes ``raw.jsonl``; a gate that only
   reads process tables can declare a host quiet while 60 GPU cases are in flight (that exact
   mistake is documented in ``scripts/eval_disciplined_ab.py``).
2. Pins the model with ``keep_alive`` and refreshes the lease during RSI's CPU-only synthesis
   phases, when the model would otherwise be evicted before the next call.
3. Yields again: terminates RSI if a foreign leg comes back.  §8.6 makes the chain exclusive,
   so politeness is not optional.

It never writes weights, never changes a production route, never edits another run's files and
only appends under ``runs/rsi/`` (via RSI itself) plus its own log and receipt.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Files whose freshness proves a measurement is running.  ``runs/rsi`` is excluded on purpose:
# RSI writes its own receipt/audit there and would otherwise detect itself as foreign activity.
WATCH_GLOBS = ("runs/**/raw.jsonl", "runs/**/summary.json", "runs/**/receipt.json",
               "_eval_disciplined_*/**/*.jsonl", "_eval_disciplined_*/**/*.json")
SELF_PREFIX = ("runs/rsi/", "runs\\rsi\\")

# A command line is a real evaluator only if it drives one.  Probes that merely *mention*
# runner.py must not count, or the gate waits on its own caller forever (measured pitfall,
# see scripts/eval_disciplined_ab.py::foreign_activity).
#
# The markers are deliberately narrow: a bare "virtu_eval" is *wrong*, because our own launch
# line carries ``--case-dir data/benchmark/virtu_eval_phys_v1``.  Matching the substring would
# make the gate treat its own child as a foreign leg and, worse, kill it mid-run.
EVALUATOR_MARKERS = ("virtu_eval.runner", "virtu_eval/runner", "virtu_eval\\runner",
                     "virtu_eval.py", "run_chain", "drift_watch", "eval_disciplined",
                     "rsi.cli")
NON_EVALUATOR_MARKERS = ("get-ciminstance", "select-object", "-x utf8")

DEFAULT_HOLD_S = 150
DEFAULT_POLL_S = 20
DEFAULT_MAX_WAIT_S = 4 * 3600


def _iso(ts: float | None = None) -> str:
    return dt.datetime.fromtimestamp(ts if ts is not None else time.time()).astimezone() \
        .isoformat(timespec="seconds")


def watch_paths(root: Path = ROOT) -> list[Path]:
    """Every measurement artifact we can see.  Empty is a failure, never 'quiet'."""
    out: list[Path] = []
    for pattern in WATCH_GLOBS:
        for path in root.glob(pattern):
            rel = path.relative_to(root).as_posix()
            if rel.startswith("runs/rsi/"):
                continue
            if path.is_file():
                out.append(path)
    return out


def recent_writes(paths: list[Path], now: float, horizon_s: float) -> list[tuple[str, float]]:
    """``[(path, age_s)]`` for every artifact written inside ``horizon_s``."""
    hits: list[tuple[str, float]] = []
    for path in paths:
        try:
            age = now - path.stat().st_mtime
        except OSError:
            # Vanished mid-scan: that is churn, and churn means someone is working.
            hits.append((str(path), 0.0))
            continue
        if age <= horizon_s:
            hits.append((str(path), round(age, 1)))
    return hits


def busy_reasons(proc_lines: list[str], models: list[str], writes: list[tuple[str, float]],
                 own_marker: str, allowed_models: tuple[str, ...] = (),
                 watched: int | None = None) -> list[str]:
    """Every concrete reason the host is *not* ours to use.  Empty means quiet."""
    reasons: list[str] = []
    if watched == 0:
        # §8.4: an empty match set is a red gate, not a pass.
        reasons.append("gate has no measurement artifact to watch")
    for line in proc_lines:
        low = line.lower()
        if own_marker.lower() in low:
            continue
        if any(marker in low for marker in NON_EVALUATOR_MARKERS):
            continue
        if any(marker in low for marker in EVALUATOR_MARKERS):
            reasons.append("foreign runner: " + line[:120])
    foreign_models = [m for m in models if m not in allowed_models]
    if foreign_models:
        reasons.append("ollama holds " + ", ".join(foreign_models))
    if writes:
        path, age = writes[0]
        reasons.append(f"{len(writes)} recent write(s), newest {Path(path).name} {age:.0f}s ago")
    return reasons


def step(quiet_since: float | None, reasons: list[str], now: float,
         hold_s: float) -> tuple[str, float | None]:
    """Decide ``wait`` or ``go`` and carry the quiet-window start across polls."""
    if reasons:
        return "wait", None
    if quiet_since is None:
        return "wait", now
    if now - quiet_since >= hold_s:
        return "go", quiet_since
    return "wait", quiet_since


def proc_lines(exclude_pids: tuple[int, ...] = ()) -> list[str]:
    """Live python command lines, minus ourselves, our shell and any pid we own.

    Our own RSI child is excluded by pid: its command line contains ``rsi.cli``, so pid-blind
    matching would make the gate convict and terminate its own child.
    """
    try:
        import psutil
    except ImportError:  # pragma: no cover - psutil is present in this venv
        return []
    skip = {os.getpid(), os.getppid(), *exclude_pids}
    lines: list[str] = []
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            if proc.info["pid"] in skip:
                continue
            cmdline = proc.info["cmdline"] or []
            if any("python" in (part or "").lower() for part in cmdline[:1]):
                lines.append(" ".join(cmdline))
        except Exception:
            continue
    return lines


def _opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def loaded_models(base_url: str, timeout: float = 10.0) -> list[str]:
    """From ``/api/ps``: a model in VRAM means someone is mid-measurement."""
    try:
        with _opener().open(urllib.request.Request(base_url.rstrip("/") + "/api/ps",
                                                  method="GET"), timeout=timeout) as resp:
            data = json.load(resp)
    except Exception:
        # Cannot see the host ⇒ cannot claim it is quiet.
        return ["<ps unavailable>"]
    return [m.get("name") or m.get("model") or "?" for m in data.get("models", [])]


def warm(model_id: str, base_url: str, keep_alive: str = "45m", timeout: float = 240.0) -> dict:
    """Load the model and set a long lease so it survives RSI's CPU-only phases."""
    body = json.dumps({"model": model_id, "prompt": "ok", "stream": False,
                       "keep_alive": keep_alive,
                       "options": {"num_predict": 1, "num_ctx": 512, "temperature": 0}}
                      ).encode("utf-8")
    request = urllib.request.Request(base_url.rstrip("/") + "/api/generate", data=body,
                                     headers={"Content-Type": "application/json"}, method="POST")
    with _opener().open(request, timeout=timeout) as resp:
        return json.load(resp)


def newest_run_mtime(root: Path) -> float:
    """Freshness of RSI's own output: tells us when the model is idle in a synthesis phase."""
    newest = 0.0
    for path in (root / "runs" / "rsi").glob("*/**/*"):
        try:
            newest = max(newest, path.stat().st_mtime)
        except OSError:
            continue
    return newest


class Recorder:
    """Append-only machine receipt; every decision gets a timestamped line."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: str, detail) -> None:
        line = {"at": _iso(), "event": event, "detail": detail}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")
        print(json.dumps(line, ensure_ascii=False), flush=True)


def rsi_command(args, model_id: str, base_url: str) -> list[str]:
    return [sys.executable, "-m", "virtu_omni.rsi.cli", "run",
            "--model-id", model_id,
            "--case-dir", args.case_dir,
            "--dims", args.dims,
            "--limit", str(args.limit),
            "--min-validation", str(args.min_validation),
            "--rounds", str(args.rounds),
            "--max-calls", str(args.max_calls),
            "--max-seconds", str(args.max_seconds),
            "--base-url", base_url]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Launch RSI inside a verified quiet window")
    parser.add_argument("--model-id", default="virtu-disciplined:v1")
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--case-dir", default="data/benchmark/virtu_eval_phys_v1")
    parser.add_argument("--dims", default="physics,derivation")
    parser.add_argument("--limit", type=int, default=60)
    parser.add_argument("--min-validation", type=int, default=24)
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--max-calls", type=int, default=200)
    parser.add_argument("--max-seconds", type=int, default=3600)
    parser.add_argument("--hold", type=int, default=DEFAULT_HOLD_S)
    parser.add_argument("--poll", type=int, default=DEFAULT_POLL_S)
    parser.add_argument("--max-wait", type=int, default=DEFAULT_MAX_WAIT_S)
    parser.add_argument("--strikes", type=int, default=3,
                        help="consecutive foreign-activity polls before yielding the card")
    parser.add_argument("--log", default="scratch/_rsi_gate.log")
    parser.add_argument("--receipt", default="scratch/_rsi_gate_receipt.jsonl")
    parser.add_argument("--dry-run", action="store_true",
                        help="report the first verdict and exit without launching")
    args = parser.parse_args(argv)

    root = ROOT
    log_path = root / args.log
    log_path.parent.mkdir(parents=True, exist_ok=True)
    rec = Recorder(root / args.receipt)
    own_marker = "rsi_quiet_gate"
    allowed = (args.model_id,)

    # ---- phase 1: wait for a quiet window -------------------------------------------------
    started = time.monotonic()
    quiet_since = None
    rec.emit("gate_start", {"model": args.model_id, "hold_s": args.hold,
                            "max_wait_s": args.max_wait})
    verdict = "timeout"
    while True:
        if time.monotonic() - started > args.max_wait:
            rec.emit("gate_timeout", {"waited_s": round(time.monotonic() - started)})
            verdict = "window_not_found"
            break
        now = time.time()
        paths = watch_paths(root)
        writes = recent_writes(paths, now, args.hold)
        reasons = busy_reasons(proc_lines(), loaded_models(args.base_url), writes,
                               own_marker, watched=len(paths))
        action, quiet_since = step(quiet_since, reasons, now, args.hold)
        if reasons:
            rec.emit("busy", {"reasons": reasons[:3]})
        if action == "go":
            rec.emit("quiet_window", {"held_s": args.hold, "watched_files": len(paths)})
            verdict = "go"
            break
        if args.dry_run:
            rec.emit("dry_run_verdict", {"action": action, "reasons": reasons,
                                         "quiet_since": _iso(quiet_since) if quiet_since else None})
            return 0
        time.sleep(args.poll)

    if verdict != "go":
        (root / "scratch" / "_rsi_gate_last.json").write_text(
            json.dumps({"verdict": verdict, "finished": _iso()}, ensure_ascii=False, indent=2),
            encoding="utf-8")
        return 2

    # ---- phase 2: pin the model, then run -------------------------------------------------
    try:
        warm(args.model_id, args.base_url)
        rec.emit("model_pinned", {"model": args.model_id, "keep_alive": "45m"})
    except Exception as exc:
        rec.emit("pin_failed", {"error": repr(exc)[:200]})

    cmd = rsi_command(args, args.model_id, args.base_url)
    rec.emit("launch", {"cmd": cmd})
    with log_path.open("w", encoding="utf-8") as log:
        proc = subprocess.Popen(cmd, cwd=str(root), stdout=log, stderr=subprocess.STDOUT)

        # ---- phase 3: hold the card, and yield it back if a foreign leg returns ----------
        strikes = 0
        last_warm = time.monotonic()
        last_output = newest_run_mtime(root)
        verdict = "completed"
        while proc.poll() is None:
            time.sleep(args.poll)
            now = time.time()
            fresh = newest_run_mtime(root)
            busy = [line for line in proc_lines(exclude_pids=(proc.pid,))
                    if own_marker not in line.lower()
                    and any(m in line.lower() for m in EVALUATOR_MARKERS)
                    and not any(m in line.lower() for m in NON_EVALUATOR_MARKERS)]
            other_models = [m for m in loaded_models(args.base_url) if m not in allowed]
            if busy or other_models:
                strikes += 1
                rec.emit("foreign_returned", {"strike": strikes, "busy": busy[:1],
                                              "models": other_models})
                if strikes >= args.strikes:
                    proc.terminate()
                    try:
                        proc.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                    rec.emit("yielded", {"reason": "foreign leg reclaimed the card",
                                         "strikes": strikes})
                    verdict = "yielded"
                    break
                continue
            strikes = 0
            # CPU-only synthesis phase: nobody has written for a while, so refresh the lease
            # before ollama evicts a model we are about to need again.
            if fresh == last_output and time.monotonic() - last_warm > 90 and \
                    now - fresh > 100:
                try:
                    warm(args.model_id, args.base_url)
                    last_warm = time.monotonic()
                    rec.emit("lease_refreshed", {"idle_s": round(now - fresh)})
                except Exception as exc:
                    rec.emit("refresh_failed", {"error": repr(exc)[:160]})
            last_output = max(last_output, fresh)

    code = proc.returncode
    rec.emit("gate_end", {"verdict": verdict, "exit_code": code,
                          "elapsed_s": round(time.monotonic() - started)})
    (root / "scratch" / "_rsi_gate_last.json").write_text(
        json.dumps({"verdict": verdict, "exit_code": code, "finished": _iso(),
                    "log": str(log_path)}, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if verdict == "completed" and code == 0 else (3 if verdict == "yielded" else 1)


if __name__ == "__main__":
    raise SystemExit(main())
