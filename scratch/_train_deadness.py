"""Read-only: static deadness check on training candidates (local imports + data paths)."""
import ast, os, re, sys, json, hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rows = json.load(open(os.path.join(ROOT, "scratch", "_trainscan_result.json"), encoding="utf-8"))
LOCAL_PKG = ("virtu_omni", "virtu_eval", "virtu_code", "virtu_edge", "bridges", "scripts",
             "damodel_cad_cam_tuning", "engineering_capability_train", "cloud_train_pack")
DATA_RE = re.compile(r"""["']((?:[A-Za-z]:)?[/\\]?(?:data|cloud_train_pack|damodel_cad_cam_tuning|engineering_capability_train|checkpoints|runs|scratch|artifacts)[/\\][^"'{}\s]*?\.(?:jsonl|json|txt|safetensors|pt|bin|gguf))["']""", re.I)

out = []
for r in rows:
    p = os.path.join(ROOT, r["path"].replace("/", os.sep))
    src = open(p, encoding="utf-8", errors="replace").read()
    rec = {"path": r["path"], "nrefs": r["nrefs"], "md5": hashlib.md5(src.encode()).hexdigest()[:12],
           "size": os.path.getsize(p)}
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        rec["syntax_error"] = str(e)
        out.append(rec)
        continue
    bad_local, ok_local = [], 0
    for node in ast.walk(tree):
        mods = []
        if isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods = [node.module]
        for m in mods:
            top = m.split(".")[0]
            if top in LOCAL_PKG:
                fp = os.path.join(ROOT, *m.split("."))
                if os.path.exists(fp + ".py") or os.path.isdir(fp) or os.path.exists(os.path.join(fp, "__init__.py")):
                    ok_local += 1
                else:
                    bad_local.append(m)
    missing_data = [d for d in set(DATA_RE.findall(src))
                    if not os.path.exists(os.path.join(ROOT, d.replace("/", os.sep))) and not os.path.isabs(d)]
    abs_missing = [d for d in set(DATA_RE.findall(src)) if os.path.isabs(d) and not os.path.exists(d)]
    rec.update(local_ok=ok_local, local_missing=sorted(bad_local),
               rel_data_missing=sorted(missing_data)[:6], abs_data_missing=sorted(abs_missing)[:4])
    # does it look like an entry point at all?
    rec["has_main"] = "__main__" in src
    rec["calls_main"] = bool(re.search(r"^\s*(?:def main\(\)|if __name__)", src, re.M))
    out.append(rec)

dups = {}
for rec in out:
    dups.setdefault(rec["md5"], []).append(rec["path"])
json.dump(out, open(os.path.join(ROOT, "scratch", "_trainscan_dead.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("=== byte-identical groups ===")
for h, ps in dups.items():
    if len(ps) > 1:
        print(h, ps)
print()
print("=== dead-ish (missing local import or missing data) ===")
for rec in out:
    flags = []
    if rec.get("syntax_error"): flags.append("SYNTAX")
    if rec.get("local_missing"): flags.append("IMP:" + ",".join(rec["local_missing"]))
    if rec.get("rel_data_missing"): flags.append("DATA:" + str(len(rec["rel_data_missing"])))
    if rec.get("abs_data_missing"): flags.append("ABS_DATA:" + str(len(rec["abs_data_missing"])))
    if flags:
        print(f"{rec['nrefs']:>3} {rec['path']:<55} {' '.join(flags)}")
        for k in ("rel_data_missing", "abs_data_missing", "local_missing"):
            if rec.get(k):
                print("        ", k, rec[k])
