"""Reachability: which training candidates are orphaned from any live anchor?

Anchor = a non-candidate file (tests/, package code, README, docs) that mentions the script.
A candidate is LIVE if an anchor mentions it, or a LIVE candidate mentions it.
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rows = json.load(open(os.path.join(ROOT, "scratch", "_trainscan_result.json"), encoding="utf-8"))
cands = {r["path"]: r for r in rows}

LIVE_DOC_FLOOR = "2026-11-03"  # docs/plans at or after this date count as live anchors
def mtime(p):
    import time
    return time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(os.path.join(ROOT, p))))

anchor_of = {}
for path, r in cands.items():
    a = []
    for ref in r["refs"]:
        if ref in cands:
            continue  # candidate-to-candidate, resolved by reachability
        is_anchor = (ref.startswith(("tests/", "virtu_omni/", "virtu_eval/", "virtu_code/",
                                     "virtu_edge/", "bridges/", ".github/"))
                     or ref in ("README.md", "AGENTS.md", "APPLY_VIRTU_FIXES.bat")
                     or (ref.endswith(".md") and mtime(ref) >= LIVE_DOC_FLOOR)
                     or (ref.endswith((".py", ".sh")) and mtime(ref) >= LIVE_DOC_FLOOR
                         and not ref.startswith("scripts/")))
        # scripts/*.py and *.sh are themselves candidates or remote drivers: treat
        # a mention from a non-candidate script only if that script is anchored
        if is_anchor:
            a.append(ref)
    anchor_of[path] = a

live = {p for p, a in anchor_of.items() if a}
changed = True
while changed:
    changed = False
    for p, r in cands.items():
        if p in live:
            continue
        if any(q in live and q != p for q in r["refs"]):
            live.add(p)
            changed = True

print("LIVE (anchored or reachable from an anchor):", len(live), " ORPHAN:", len(cands) - len(live))
print("\n=== ORPHANS ===")
for p in sorted(cands):
    if p in live:
        continue
    r = cands[p]
    print(f"{r['mtime']} refs={r['nrefs']:<2} {'tracked' if r['tracked'] else 'untracked':<9} {p}")
    for q in r["refs"]:
        mark = "L" if q in live else "o"
        print(f"        [{mark}] {q}")
print("\n=== LIVE ===")
for p in sorted(live):
    r = cands[p]
    print(f"{r['mtime']} refs={r['nrefs']:<2} {p}  anchor={anchor_of[p][:3]}")
