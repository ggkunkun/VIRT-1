"""Final tiering: delete-candidate vs protected, with the reason each file is protected."""
import json, os, re, glob, time, hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rows = {r["path"]: r for r in json.load(open(os.path.join(ROOT, "scratch", "_trainscan_result.json"), encoding="utf-8"))}

# P2: pinned by any test file
pinned = {}
for t in glob.glob(os.path.join(ROOT, "tests/*.py")) + glob.glob(os.path.join(ROOT, "**/tests/*.py"), recursive=True):
    txt = open(t, encoding="utf-8", errors="replace").read()
    for p, r in rows.items():
        stem = os.path.splitext(os.path.basename(p))[0]
        if re.search(r"(?<!\w)" + re.escape(stem) + r"(?!\w)", txt):
            pinned.setdefault(p, []).append(os.path.relpath(t, ROOT).replace("\\", "/"))

# P3: anchored by ANY non-candidate file in the repo (docs, code, manifests)
candset = set(rows)
anchor = {}
for p, r in rows.items():
    a = [ref for ref in r["refs"] if ref not in candset and not ref.startswith("scratch/")]
    anchor[p] = a

# P4: produced-checkpoint provenance — script name maps to an existing receipt/adapter dir
PROVEN = [d for d in os.listdir(os.path.join(ROOT, "checkpoints"))] + \
         [d for d in os.listdir(os.path.join(ROOT, "cloud_artifacts")) if os.path.isdir(os.path.join(ROOT, "cloud_artifacts", d))]

def provenance(p):
    stem = os.path.splitext(os.path.basename(p))[0].lower()
    toks = [t for t in re.split(r"[_]", stem) if len(t) > 4 and t not in ("train", "script", "setup", "model")]
    hits = [d for d in PROVEN if any(t in d.lower().replace("_", "") or t in d.lower() for t in toks)]
    return sorted(set(hits))[:3]

out = []
for p, r in sorted(rows.items()):
    prot = []
    if r["mtime"] >= "2026-11-03":
        prot.append("ACTIVE-WINDOW")
    if p in pinned:
        prot.append("TEST-PIN:" + ",".join(pinned[p][:2]))
    if anchor[p]:
        prot.append("ANCHOR:" + ",".join(anchor[p][:2]))
    pv = provenance(p)
    if pv and not prot:
        prot.append("PROVENANCE:" + ",".join(pv))
    out.append({"path": p, "mtime": r["mtime"], "tracked": r["tracked"], "size": os.path.getsize(os.path.join(ROOT, p.replace("/", os.sep))),
                "nrefs": r["nrefs"], "refs": r["refs"], "protected": prot})

dele = [o for o in out if not o["protected"]]
kept = [o for o in out if o["protected"]]
print(f"candidates={len(out)}  DELETE-CANDIDATE={len(dele)} ({sum(o['size'] for o in dele)/1024:.0f} KiB)  PROTECTED={len(kept)}\n")
print("=== DELETE CANDIDATES (unreferenced, not active, not pinned, not provenance) ===")
for o in sorted(dele, key=lambda x: x["mtime"]):
    print(f"{o['mtime']} {o['size']/1024:6.1f}K {'git' if o['tracked'] else 'untracked':<9} {o['path']}")
    if o["refs"]:
        print("           mentions only from:", o["refs"])
json.dump(out, open(os.path.join(ROOT, "scratch", "_train_verdict.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
