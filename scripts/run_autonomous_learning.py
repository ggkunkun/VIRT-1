# -*- coding: utf-8 -*-
"""scripts/run_autonomous_learning.py — Master Automation CLI for Autonomous Internet Learning.

Commands:
    # 1. Run a single or multi-topic autonomous cycle
    python scripts/run_autonomous_learning.py --mode cycle --topics 2

    # 2. Run as all-weather continuous background daemon
    python scripts/run_autonomous_learning.py --mode daemon --interval 1800

    # 3. On-demand autonomous knowledge acquisition
    python scripts/run_autonomous_learning.py --mode learn --concept "TC4 钛合金铣削转速与进给量计算"

    # 4. View telemetry status and knowledge stats
    python scripts/run_autonomous_learning.py --mode status
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import time
from pathlib import Path

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from virtu_omni.internet import (
    AutonomousLearningEngine,
    get_autonomous_engine,
    get_internet_hub,
    get_learning_pipeline,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("VirtuAutonomousCLI")


PID_FILE = WORKSPACE_DIR / "logs" / "autonomous_daemon.pid"
STDOUT_LOG = WORKSPACE_DIR / "logs" / "autonomous_daemon_stdout.log"
STDERR_LOG = WORKSPACE_DIR / "logs" / "autonomous_daemon_stderr.log"


def is_pid_running(pid: int) -> bool:
    """Check if process with given PID is currently active."""
    if sys.platform == "win32":
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if h:
                ctypes.windll.kernel32.CloseHandle(h)
                return True
            return False
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def handle_start(interval: int):
    """Launch detached background daemon process."""
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text(encoding="utf-8").strip())
            if is_pid_running(old_pid):
                print(f"[INFO] Autonomous Learning Daemon is already running (PID: {old_pid}).")
                return
        except Exception:
            pass

    creationflags = 0
    if sys.platform == "win32":
        creationflags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP

    import subprocess
    out_f = open(STDOUT_LOG, "a", encoding="utf-8")
    err_f = open(STDERR_LOG, "a", encoding="utf-8")

    cmd = [sys.executable, "-u", str(Path(__file__).resolve()), "--mode", "daemon", "--interval", str(interval)]
    proc = subprocess.Popen(
        cmd,
        stdout=out_f,
        stderr=err_f,
        creationflags=creationflags,
        close_fds=(sys.platform != "win32"),
    )
    PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    print(f"[SUCCESS] Autonomous Learning Daemon launched in detached background with PID: {proc.pid}")
    print(f"[INFO] Log file: {STDOUT_LOG}")


def handle_stop():
    """Stop running background daemon process."""
    if not PID_FILE.exists():
        print("[INFO] No running autonomous daemon PID file found.")
        return

    try:
        pid = int(PID_FILE.read_text(encoding="utf-8").strip())
        if is_pid_running(pid):
            import subprocess
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
            else:
                os.kill(pid, signal.SIGTERM)
            print(f"[SUCCESS] Terminated Autonomous Daemon process PID: {pid}.")
        else:
            print(f"[INFO] Process PID {pid} is no longer active.")
    except Exception as e:
        print(f"[WARNING] Could not terminate process: {e}")
    finally:
        if PID_FILE.exists():
            PID_FILE.unlink(missing_ok=True)


def handle_cycle(engine: AutonomousLearningEngine, topics_count: int, sleep: bool):
    logger.info(f"Executing autonomous learning cycle with {topics_count} topic(s)...")
    res = engine.run_autonomous_cycle(max_topics=topics_count, run_sleep_cycle=sleep)
    print("\n" + "=" * 60)
    print(f"Autonomous Learning Cycle Completed (Runtime: {res['runtime_seconds']}s)")
    print(f"Topics Completed: {', '.join(res['completed_topics']) if res['completed_topics'] else 'None'}")
    print(f"Total Vector Knowledge Entries: {res['vector_store_entries_total']}")
    print(f"SFT Training Dataset: {res['sft_dataset_path']}")
    print("=" * 60 + "\n")


def handle_daemon(engine: AutonomousLearningEngine, interval: int, max_cycles: int = None):
    logger.info(f"Starting all-weather autonomous learning daemon (interval={interval}s)...")
    logger.info("Press Ctrl+C to terminate.")

    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")

    def _sig_handler(sig, frame):
        logger.info("Termination signal received. Shutting down daemon...")
        engine.stop_daemon()
        if PID_FILE.exists():
            PID_FILE.unlink(missing_ok=True)
        sys.exit(0)

    signal.signal(signal.SIGINT, _sig_handler)

    try:
        engine.start_daemon(interval_seconds=interval, max_cycles=max_cycles)
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received.")
        engine.stop_daemon()
    finally:
        if PID_FILE.exists():
            PID_FILE.unlink(missing_ok=True)


def handle_learn(engine: AutonomousLearningEngine, concept: str):
    logger.info(f"On-demand learning concept: '{concept}'")
    res = engine.learn_missing_knowledge(concept)
    print("\n" + "=" * 60)
    if res["success"]:
        print(res["grounded_knowledge"])
        print(f"\nIngested {res['ingested_entries']} entries. Total memory store: {res['vector_store_total']}")
    else:
        print(f"Error: {res['error']}")
    print("=" * 60 + "\n")


def handle_status(engine: AutonomousLearningEngine):
    health_file = WORKSPACE_DIR / "reports" / "autonomous_daemon_health.json"
    print("\n" + "=" * 60)
    print("   Virtu Autonomous Internet Learning Engine - Telemetry Status")
    print("=" * 60)

    # Process status
    pid_status = "STOPPED"
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text(encoding="utf-8").strip())
            if is_pid_running(pid):
                pid_status = f"RUNNING (PID: {pid})"
            else:
                pid_status = f"STOPPED (Stale PID: {pid})"
        except Exception:
            pass
    print(f"Service Process:    {pid_status}")

    if health_file.exists():
        with open(health_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"Daemon Status:      {data.get('daemon_status')}")
            print(f"Last Heartbeat:     {data.get('last_heartbeat_human')}")
            q = data.get("queue_stats", {})
            print(f"Queue Stats:        Total={q.get('total_topics')} | Pending={q.get('pending')} | Completed={q.get('completed')} | Rejected={q.get('rejected')}")
            k = data.get("knowledge_stats", {})
            print(f"Knowledge Entries:  {k.get('vector_store_entries')} vectors in RAG store")
            print(f"SFT Dataset Size:   {k.get('sft_file_size_bytes')} bytes")
            lc = data.get("last_cycle", {})
            print(f"Last Cycle Runtime: {lc.get('runtime_seconds')}s ({', '.join(lc.get('completed_topics', []))})")
    else:
        print(f"Queue length: {len(engine._queue)}")
        print(f"Total vector store entries: {len(engine.learning_pipeline.entries)}")
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Virtu Autonomous Learning Engine.")
    parser.add_argument("--mode", choices=["cycle", "daemon", "learn", "status", "start", "stop"], default="cycle", help="Execution mode")
    parser.add_argument("--topics", type=int, default=1, help="Max topics for cycle mode")
    parser.add_argument("--interval", type=int, default=1800, help="Seconds between cycles in daemon mode")
    parser.add_argument("--concept", type=str, default="", help="Concept or question for learn mode")
    parser.add_argument("--no-sleep", action="store_true", help="Skip Google Sleep consolidation in cycle mode")
    args = parser.parse_args()

    engine = get_autonomous_engine()

    if args.mode == "start":
        handle_start(args.interval)
    elif args.mode == "stop":
        handle_stop()
    elif args.mode == "cycle":
        handle_cycle(engine, args.topics, sleep=not args.no_sleep)
    elif args.mode == "daemon":
        handle_daemon(engine, args.interval)
    elif args.mode == "learn":
        if not args.concept:
            print("Error: --concept argument is required for learn mode.")
            sys.exit(1)
        handle_learn(engine, args.concept)
    elif args.mode == "status":
        handle_status(engine)


if __name__ == "__main__":
    main()
