"""Read-only scan: unreferenced / duplicated training entry points. Single pass, one git call."""
import os, re, sys, json, subprocess, time, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIR = {".git", ".venv", "__pycache__", "node_modules", ".pytest_cache", ".ruff_cache",
            ".pytest_temp", ".pytest_tmp_fix", ".screenshots", "external", "build", "dist",
            ".workbuddy", ".qoder", "_cu_test", "runs", "logs"}
SKIP_PREFIX = ["_eval_", "models/", "data/physics_derivation_v1"]
TEXT_EXT = (".py", ".md", ".sh", ".bat", ".ps1", ".json", ".txt", ".yaml", ".yml",
            ".jinja", ".toml", ".cfg", ".Modelfile".lower())
MAX_BYTES = 4_000_000
HARD = 200  # chars of surrounding context we don't need

CAND_RE = re.compile(r"train|finetune|qlora|_sft|lora|_post_|merge_lora|run_evolution|launch_cloud", re.I)
ENTRY_DIRS = ["", "scripts", "cloud_train_pack", "gpu_handoff", "damodel_cad_cam_tuning",
              "engineering_capability_train", "cloud_bugfix_sync_20261102", "cloud_handoff"]
cands = []
for rel_dir in ENTRY_DIRS:
    d = os.path.join(ROOT, rel_dir) if rel_dir else ROOT
    if not os.path.isdir(d):
        continue
    for fn in sorted(os.listdir(d)):
        p = os.path.join(d, fn)
        if not os.path.isfile(p):
            continue
        low = fn.lower()
        if low.endswith(".py") and CAND_RE.search(low):
            cands.append(p)
        elif low.endswith((".sh", ".bat")) and ("train" in low or "deploy" in low):
            cands.append(p)

names = {}
for p in cands:
    b = os.path.basename(p).lower()
    names.setdefault(b, []).append(p)

# single combined regex over basenames (word-boundary on stem)
stems = sorted({os.path.splitext(b)[0] for b in names})
pat = re.compile(r"(?<!\w)(?:%s)(?!\w)" % "|".join(re.escape(s) for s in stems))

def rel(p):
    return os.path.relpath(p, ROOT).replace("\\", "/")

refs = {rel(p): set() for p in cands}
nfiles = 0
for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [x for x in dirnames if x not in SKIP_DIR and not x.startswith("_eval_")]
    rp = rel(dirpath)
    if any(rp.startswith(s) or ("/" + s) in ("/" + rp) for s in ("node_modules", "dist")):
        continue
    for fn in filenames:
        if not fn.lower().endswith(TEXT_EXT):
            continue
        p = os.path.join(dirpath, fn)
        try:
            if os.path.getsize(p) > MAX_BYTES:
                continue
            with open(p, "r", encoding="utf-8", errors="replace") as fh:
                txt = fh.read().lower()
        except Exception:
            continue
        nfiles += 1
        r = rel(p)
        if r not in refs:
            for m in pat.finditer(txt):
                stem = m.group(0)
                for b, plist in names.items():
                    if os.path.splitext(b)[0] == stem:
                        for q in plist:
                            if rel(q) != r:
                                refs[rel(q)].add(r)
        else:
            # candidate file: still credit other candidates it mentions
            for m in pat.finditer(txt):
                stem = m.group(0)
                for b, plist in names.items():
                    if os.path.splitext(b)[0] == stem:
                        for q in plist:
                            if rel(q) != r:
                                refs[rel(q)].add(r)

tracked = set(subprocess.run(["git", "-C", ROOT, "ls-files"], capture_output=True, text=True).stdout.split())
dirty = {}
for line in subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True, text=True).stdout.splitlines():
    dirty[line[3:].strip().replace("\\", "/")] = line[:2].strip()

rows = []
for p in cands:
    r = rel(p)
    ext = sorted(x for x in refs[r] if x != r)
    rows.append({"path": r, "tracked": r in tracked, "git": dirty.get(r, ""),
                 "mtime": time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(p))),
                 "lines": sum(1 for _ in open(p, "rb")), "nrefs": len(ext), "refs": ext})
rows.sort(key=lambda x: (x["nrefs"], x["path"]))
out = os.path.join(ROOT, "scratch", "_trainscan_result.json")
with open(out, "w", encoding="utf-8") as fh:
    json.dump(rows, fh, ensure_ascii=False, indent=1)
print("scanned_files", nfiles, "candidates", len(cands), "->", out)
