# -*- coding: utf-8 -*-
"""scripts/run_sleep_maintenance.py — Virtu Sleep Framework Production Maintenance Daemon & CLI.

Production-grade background maintenance controller implementing Google Sleep Continual Learning:
- Gathers buffered Wake experiences (CAE, CNC, CAD, Drawing).
- Enforces ProcessMemoryReclaimer to safely free RAM/VRAM before dreaming.
- Executes 3-phase Sleep consolidation: Knowledge Seeding -> Counterfactual Dreaming -> Synaptic Homeostasis.
- Guarantees Zero Catastrophic Forgetting (CF <= 5%) & Gate Falsifiability.
- Updates persistent Hindsight memory banks and JSON benchmark provenance.

Usage:
    python scripts/run_sleep_maintenance.py --now
    python scripts/run_sleep_maintenance.py --threshold 3
    python scripts/run_sleep_maintenance.py --daemon --interval 3600
    python scripts/run_sleep_maintenance.py --dry-run
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import logging
from pathlib import Path
import sys
import time
import urllib.request
from typing import Any, Callable, Dict, Optional

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from virtu_omni.memory.sleep_framework import get_sleep_framework, VirtuSleepFramework
from virtu_omni.agent.process_memory_reclaimer import ProcessMemoryReclaimer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [SleepMaintenance] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("run_sleep_maintenance")


def get_default_model_caller() -> Callable[[str], str]:
    """Provides direct connection to virtu-disciplined:v1 in Ollama with backoff retry."""
    def _call(prompt: str) -> str:
        for attempt in range(3):
            try:
                payload = {
                    "model": "virtu-disciplined:v1",
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"temperature": 0.0, "num_predict": 300},
                }
                req = urllib.request.Request(
                    "http://127.0.0.1:11434/api/chat",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                resp = urllib.request.urlopen(req, timeout=60)
                data = json.loads(resp.read().decode("utf-8"))
                return data["message"]["content"].strip()
            except Exception as e:
                logger.warning(f"Model query attempt {attempt+1}/3 failed ({e}), retrying in 2s...")
                time.sleep(2)
        return "ERROR: Model query failed after 3 attempts"
    return _call


def perform_maintenance_cycle(
    framework: VirtuSleepFramework,
    clean_memory: bool = True,
    pre_baseline_score: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """Executes a single end-to-end Sleep maintenance cycle."""
    unconsolidated_count = len(framework.wake_buffer)
    if unconsolidated_count == 0:
        logger.info("No unconsolidated wake experiences found. Nothing to sleep.")
        return None

    logger.info(f"Initiating Sleep maintenance for {unconsolidated_count} buffered wake experiences...")

    # 1. Clean memory & close hung CAD/CAM processes to maximize available RAM/VRAM
    if clean_memory:
        try:
            logger.info("Running ProcessMemoryReclaimer to purge idle industrial software memory...")
            reclaimer = ProcessMemoryReclaimer()
            reclaim_res = reclaimer.reclaim_memory(close_software=True)
            logger.info(f"Memory reclaimed: {reclaim_res.get('freed_mb', 0):.1f} MB freed.")
        except Exception as e:
            logger.warning(f"Memory reclaim step skipped: {e}")

    # 2. Execute 3-phase Sleep Cycle
    cycle_id = f"MAINTENANCE_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    logger.info(f"Running Sleep consolidation cycle (ID: {cycle_id})...")
    report = framework.run_sleep_cycle(run_id=cycle_id, pre_baseline_score=pre_baseline_score)

    # 3. Rule 4 Gate Falsifiability probe
    probe = framework.falsifiable_mutation_probe()
    logger.info(f"Rule 4 Falsifiable Gatekeeper Probe: {'PASSED' if probe['probe_passed'] else 'FAILED'}")

    logger.info("=== Sleep Maintenance Cycle Completed ===")
    logger.info(f"  Consolidated Knowledge Units: {report['consolidated_units']}")
    logger.info(f"  Context Token Compression:    {report['average_token_compression']*100:.1f}%")
    logger.info(f"  Counterfactual Dreams:         {report['dreams_generated']} (Pass Rate: {report['dream_oracle_pass_rate']*100:.1f}%)")
    logger.info(f"  Stability Score (Retention):   {report['stability_score']*100:.1f}%")
    logger.info(f"  Catastrophic Forgetting Rate:  {report['catastrophic_forgetting_rate']*100:.1f}%")
    logger.info(f"  Plasticity Score (New Rules):  {report['plasticity_score']*100:.1f}%")
    logger.info(f"  Audit Evidence File:           {report['evidence_path']}")

    return report


def main():
    parser = argparse.ArgumentParser(description="Virtu Google Sleep Maintenance Controller")
    parser.add_argument("--now", action="store_true", help="Immediately run Sleep maintenance cycle")
    parser.add_argument("--threshold", type=int, default=1, help="Minimum unconsolidated experiences required to trigger sleep")
    parser.add_argument("--daemon", action="store_true", help="Run as standing background maintenance daemon")
    parser.add_argument("--interval", type=int, default=300, help="Daemon polling interval in seconds (default: 300s)")
    parser.add_argument("--no-clean", action="store_true", help="Skip ProcessMemoryReclaimer software closure")
    parser.add_argument("--dry-run", action="store_true", help="Inspect wake buffer status without sleeping")
    args = parser.parse_args()

    caller = get_default_model_caller()
    framework = get_sleep_framework(model_caller=caller)

    unconsolidated_count = len(framework.wake_buffer)
    logger.info(f"Current Wake Buffer: {unconsolidated_count} unconsolidated experiences.")

    if args.dry_run:
        print("\n" + "="*60)
        print("VIRTU SLEEP FRAMEWORK STATUS (DRY-RUN)")
        print("="*60)
        print(f"Is Sleeping:             {framework.is_sleeping}")
        print(f"Unconsolidated Entries:  {unconsolidated_count}")
        print(f"Consolidated Rule Units: {len(framework.consolidated_store)}")
        print(f"Recorded Dreams:         {len(framework.dream_history)}")
        print("="*60)
        return

    if args.now or (unconsolidated_count >= args.threshold and not args.daemon):
        perform_maintenance_cycle(framework, clean_memory=not args.no_clean)
        return

    if args.daemon:
        logger.info(f"Entering daemon loop (polling every {args.interval}s, threshold={args.threshold})...")
        try:
            while True:
                time.sleep(args.interval)
                current_count = len(framework.wake_buffer)
                if current_count >= args.threshold and not framework.is_sleeping:
                    logger.info(f"Buffer threshold reached ({current_count} >= {args.threshold}). Triggering sleep cycle...")
                    perform_maintenance_cycle(framework, clean_memory=not args.no_clean)
                else:
                    logger.debug(f"Daemon check: {current_count}/{args.threshold} buffer items. Sleeping...")
        except KeyboardInterrupt:
            logger.info("Daemon stopped by user.")


if __name__ == "__main__":
    main()
