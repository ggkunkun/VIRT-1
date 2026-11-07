#!/usr/bin/env python
"""Fail loudly when a live Ollama tag drifts from the canonical hardened profile.

The repository used to carry ~40 Modelfile_* variants and a doc section claiming the
`<|im_start|>` stop token was gone while all three live tags still carried it. A doc cannot
detect that. This check can: it reads the parameters the live tag actually serves and compares
them with `modelfiles/*.hardened.Modelfile`, so a rebuild that forgets the hardened profile
fails instead of shipping.

Usage:
    python scripts/check_modelfile_drift.py                # check the default live tags
    python scripts/check_modelfile_drift.py --tag a:latest  # check one tag explicitly
    python scripts/check_modelfile_drift.py --json          # machine-readable report

Exit code 0 = no drift, 1 = drift found, 2 = could not read a tag.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DIR = ROOT / "modelfiles"

# tag -> canonical profile. The hardened profiles are the only sanctioned source of parameters;
# anything not listed here is unmanaged and is not checked.
DEFAULT_TAGS = {
    "virtu-moe-14b:hardened": "virtu-moe-14b.hardened.Modelfile",
    "virtu-13.63b:hardened": "virtu-13.63b.hardened.Modelfile",
}

# Tags that must never be drifted: the ones actually served in production.
PRODUCTION_TAGS = ["virtu-moe-14b:latest", "virtu-moe-14b:fast", "virtu-13.63b:latest"]

FORBIDDEN_STOPS = {"<|im_start|>"}
FORBIDDEN_PARAMETERS = {"num_gpu": None}  # pinned per profile; drift means a different machine


def parse_modelfile(text: str) -> dict:
    """Extract PARAMETER lines (multi-valued keys become sorted lists) and the FROM line."""
    params: dict[str, list[str]] = {}
    source = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("PARAMETER "):
            _, key, value = line.split(" ", 2)
            params.setdefault(key, []).append(value.strip())
        elif line.startswith("FROM "):
            source = line[5:].strip()
    return {"params": {k: sorted(v) for k, v in params.items()}, "from": source}


def read_live(tag: str, timeout: int = 180) -> dict:
    env = dict(os.environ)
    env.setdefault("OLLAMA_MODELS", r"E:\ollama\models")
    proc = subprocess.run(["ollama", "show", "--modelfile", tag], capture_output=True,
                          text=True, timeout=timeout, env=env, encoding="utf-8",
                          errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"ollama show failed for {tag}: {proc.stderr.strip()[:400]}")
    return parse_modelfile(proc.stdout)


def compare(tag: str, canonical_path: Path) -> dict:
    canonical = parse_modelfile(canonical_path.read_text(encoding="utf-8"))
    try:
        live = read_live(tag)
    except Exception as exc:  # noqa: BLE001 - reported, never raised further
        return {"tag": tag, "status": "unreadable", "error": str(exc), "drift": []}

    drift = []
    for key, expected in canonical["params"].items():
        actual = live["params"].get(key)
        if actual != expected:
            drift.append({"parameter": key, "expected": expected, "actual": actual})
    for key, actual in live["params"].items():
        if key not in canonical["params"]:
            drift.append({"parameter": key, "expected": None, "actual": actual})
    for value in live["params"].get("stop", []):
        if value in FORBIDDEN_STOPS:
            drift.append({"parameter": "stop", "expected": "not " + value, "actual": value})
    if canonical["from"] and live["from"] != canonical["from"]:
        drift.append({"parameter": "FROM", "expected": canonical["from"], "actual": live["from"]})

    return {"tag": tag, "status": "drift" if drift else "ok", "drift": drift,
            "from": live["from"], "params": live["params"]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tag", action="append", default=None,
                    help="tag to check (repeatable); defaults to the hardened profiles")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args(argv)

    targets = {t: f for t, f in DEFAULT_TAGS.items()}
    if args.tag:
        unknown = [t for t in args.tag if t not in DEFAULT_TAGS]
        if unknown:
            ap.error(f"no canonical profile for: {', '.join(unknown)}")
        targets = {t: DEFAULT_TAGS[t] for t in args.tag}

    reports = [compare(tag, CANONICAL_DIR / name) for tag, name in targets.items()]

    if args.json:
        print(json.dumps({"reports": reports, "unmanaged_production_tags": PRODUCTION_TAGS},
                         ensure_ascii=False, indent=2))
    else:
        for rep in reports:
            if rep["status"] == "ok":
                print(f"OK       {rep['tag']}")
                continue
            if rep["status"] == "unreadable":
                print(f"ERROR    {rep['tag']}: {rep['error']}")
                continue
            print(f"DRIFT    {rep['tag']}")
            for row in rep["drift"]:
                print(f"           {row['parameter']}: expected {row['expected']} "
                      f"got {row['actual']}")
        if PRODUCTION_TAGS:
            print("\nUnmanaged production tags (no canonical profile, not gated): "
                  + ", ".join(PRODUCTION_TAGS))

    if any(r["status"] == "unreadable" for r in reports):
        return 2
    return 0 if all(r["status"] == "ok" for r in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
