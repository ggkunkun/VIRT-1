"""Pin the benchmark case files and verify nothing was silently rewritten.

Why this exists
---------------
Measured 2026-11-06: `data/benchmark/virtu_eval_cl_v1/toolrouting.jsonl` was
replaced at 23:05, nine hours after two evaluation legs had already run on it.
Eight of thirty prompts and their criteria changed under the same filename.
`RunIdentity.capture()` had *recorded* the case sha in each leg's manifest, but
nothing compared it, so the legs kept quoting scores for a case set that no
longer existed. Recording is not gating.

Usage
-----
    python scripts/check_case_lock.py --write     # accept the current files as the baseline
    python scripts/check_case_lock.py             # verify; non-zero exit on drift
    python scripts/check_case_lock.py --leg runs/eval/<leg>   # also check a leg's manifest

Exit codes: 0 = match, 1 = drift or missing, 2 = no lock file (run --write first).

Changing a case file is still allowed -- it just has to be a deliberate act that
updates the lock, not an edit that quietly invalidates every prior leg.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BENCH = os.path.join(ROOT, "data", "benchmark")
LOCK = os.path.join(BENCH, "CASES.lock")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def scan():
    out = {}
    for dirpath, _dirnames, filenames in os.walk(BENCH):
        for name in sorted(filenames):
            if not name.endswith(".jsonl"):
                continue
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, ROOT).replace("\\", "/")
            st = os.stat(path)
            out[rel] = {"sha256": sha256_file(path), "bytes": st.st_size,
                        "mtime": __import__("datetime").datetime.fromtimestamp(
                            st.st_mtime).strftime("%Y-%m-%dT%H:%M:%S"),
                        "lines": sum(1 for line in open(path, encoding="utf-8") if line.strip())}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="accept current files as the baseline")
    ap.add_argument("--leg", default=None, help="verify a run leg's recorded case hashes too")
    args = ap.parse_args()

    current = scan()

    if args.write:
        doc = {"generated": __import__("datetime").datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
               "note": "sha256 of every benchmark jsonl; verify before starting a leg",
               "files": current}
        with open(LOCK, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
        print(f"wrote {len(current)} case files -> {os.path.relpath(LOCK, ROOT)}")
        return 0

    if not os.path.exists(LOCK):
        print("no CASES.lock; run with --write to create the baseline", file=sys.stderr)
        return 2

    locked = json.load(open(LOCK, encoding="utf-8"))["files"]
    bad = 0
    for rel, meta in sorted(locked.items()):
        now = current.get(rel)
        if now is None:
            print(f"MISSING  {rel}")
            bad += 1
        elif now["sha256"] != meta["sha256"]:
            print(f"DRIFT    {rel}\n         lock {meta['sha256'][:16]} "
                  f"({meta['lines']} lines, {meta['mtime']})\n"
                  f"         now  {now['sha256'][:16]} ({now['lines']} lines, {now['mtime']})")
            bad += 1
    for rel in sorted(set(current) - set(locked)):
        print(f"UNLOCKED {rel}  (new case file not in lock)")
        bad += 1

    if args.leg:
        leg_manifest = os.path.join(ROOT, args.leg, "manifest.json")
        if os.path.exists(leg_manifest):
            m = json.load(open(leg_manifest, encoding="utf-8"))
            print(f"\nleg {args.leg} started {m.get('started')}:")
            by_name = {os.path.basename(r): r for r in locked}
            for fn, recorded in (m.get("case_file_sha256") or {}).items():
                rel = by_name.get(fn)
                if rel is None:
                    print(f"  {fn}: not a locked case file")
                    continue
                ok = locked[rel]["sha256"] == recorded
                print(f"  {fn}: {'OK' if ok else 'LEG RAN ON A DIFFERENT CASE FILE'} "
                      f"(leg {recorded[:12]} / lock {locked[rel]['sha256'][:12]})")
                bad += 0 if ok else 1
        else:
            print(f"\nno manifest at {leg_manifest}", file=sys.stderr)

    print(f"\n{'OK: all case files match the lock' if bad == 0 else f'{bad} problem(s)'}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
