"""Repair the dangling params layer of the virtu-toolcall Ollama tag.

The 4.6 GB GGUF layer and the config layer are intact; only the tiny params layer
was garbage-collected, which makes the whole tag unloadable even though
`ollama list` still shows it. Nothing here is invented: the parameters are read
back from scripts/Modelfile.virtu-toolcall, and the manifests are backed up first.

    python scripts/repair_virtu_toolcall_tag.py [--check]
"""
import glob
import hashlib
import json
import os
import re
import shutil
import sys

BLOBS = r"E:/ollama/models/blobs"
MODEL_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "scripts", "Modelfile.virtu-toolcall")
TAG = "virtu-toolcall"


def params_from_modelfile(path=MODEL_FILE):
    """Parse PARAMETER lines exactly as Ollama would have."""
    out = {"stop": []}
    for line in open(path, encoding="utf-8"):
        m = re.match(r"\s*PARAMETER\s+(\S+)\s+(.*)", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if key == "stop":
            out["stop"].append(val.strip('"'))
            continue
        try:
            out[key] = int(val)
        except ValueError:
            try:
                out[key] = float(val)
            except ValueError:
                out[key] = val.strip('"')
    return out


def manifest_paths():
    hits = []
    for root in (r"E:/ollama/models/manifests", r"E:/ollama/models/manifests-v2"):
        hits += [p for p in glob.glob(root + "/**/library/%s/*" % TAG, recursive=True)
                 if os.path.isfile(p)]
    return hits


def missing_params(p):
    man = json.load(open(p, encoding="utf-8"))
    for lay in man.get("layers", []):
        if "params" in lay.get("mediaType", ""):
            d = lay["digest"].split(":")[1]
            if not os.path.exists(os.path.join(BLOBS, "sha256-" + d)):
                return lay, d
    return None, None


def main():
    check_only = "--check" in sys.argv
    params = params_from_modelfile()
    print("params read from Modelfile:", json.dumps(params, ensure_ascii=False))
    blob = json.dumps(params, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(blob).hexdigest()
    print("new params blob: sha256:%s (%d bytes)" % (digest[:16], len(blob)))
    if not os.path.exists(os.path.join(BLOBS, "sha256-" + digest)):
        if check_only:
            print("[check] would write blobs/sha256-%s" % digest[:16])
        else:
            with open(os.path.join(BLOBS, "sha256-" + digest), "wb") as f:
                f.write(blob)
            print("wrote blobs/sha256-%s" % digest[:16])
    for p in manifest_paths():
        lay, old = missing_params(p)
        if lay is None:
            print("OK   %s" % p.replace("E:/ollama/models/", ""))
            continue
        print("BROKEN %s  dangling params %s" % (p.replace("E:/ollama/models/", ""), old[:16]))
        if check_only:
            continue
        shutil.copy2(p, p + ".bak_pre_params_repair")
        man = json.load(open(p, encoding="utf-8"))
        for l in man["layers"]:
            if l.get("mediaType", "").endswith(".params"):
                l["digest"] = "sha256:" + digest
                l["size"] = len(blob)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(man, f)
        print("       repointed -> sha256:%s (backup: %s)" % (digest[:16],
              os.path.basename(p) + ".bak_pre_params_repair"))


if __name__ == "__main__":
    main()
