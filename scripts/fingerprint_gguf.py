"""Fingerprint the four exported GGUF releases and map them to what is deployed.

The repository ships four differently named GGUF exports.  If they are byte
identical then the names promise a distinction the bytes do not deliver, and
anyone re-importing from ``checkpoints/`` gets the same weights under four
different labels.

Ollama stores the model file it imported as a blob whose name *is* its
sha256, so hashing the exported files tells us exactly which deployed model
each export corresponds to.
"""

from __future__ import annotations

import hashlib
import json
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CK = os.path.join(ROOT, "checkpoints")
BLOBS = os.path.join(os.environ.get("USERPROFILE", ""), ".ollama", "models", "blobs")
MANIFESTS = os.path.join(os.environ.get("USERPROFILE", ""), ".ollama", "models",
                         "manifests", "registry.ollama.ai", "library")


def sha256(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(chunk), b""):
            h.update(c)
    return h.hexdigest()


def deployed_models():
    """map: ollama model name -> blob digest (which equals the file sha256)"""
    out = {}
    for vendor in os.listdir(MANIFESTS):
        vdir = os.path.join(MANIFESTS, vendor)
        if not os.path.isdir(vdir):
            continue
        for model in os.listdir(vdir):
            mdir = os.path.join(vdir, model)
            if not os.path.isdir(mdir):
                continue
            for tag in os.listdir(mdir):
                tagfile = os.path.join(mdir, tag)
                if not os.path.isfile(tagfile):
                    continue
                try:
                    man = json.load(open(tagfile, encoding="utf-8"))
                except Exception:  # noqa: BLE001
                    continue
                for layer in man.get("layers", []):
                    mt = layer.get("mediaType", "")
                    if mt.endswith("model"):
                        out[f"{model}:{tag}"] = layer["digest"].split("sha256:")[-1]
    return out


def main():
    exports = {}
    for fn in sorted(os.listdir(CK)):
        if fn.endswith(".gguf"):
            p = os.path.join(CK, fn)
            t0 = time.time()
            exports[fn] = {"bytes": os.path.getsize(p), "sha256": sha256(p),
                           "hash_seconds": round(time.time() - t0, 1)}

    deployed = deployed_models()
    by_digest = {}
    for name, dig in deployed.items():
        by_digest.setdefault(dig, []).append(name)

    lines = ["### exported GGUF files (full sha256)"]
    for fn, info in exports.items():
        matches = by_digest.get(info["sha256"], [])
        lines.append(f"  {fn:34s} {info['bytes']:>12,} B  sha256={info['sha256'][:16]}...  "
                     f"deployed_as={matches or 'NOT DEPLOYED (no ollama blob with this digest)'}")
    lines.append("")
    lines.append("### ollama blobs")
    for name, dig in sorted(deployed.items()):
        blob = os.path.join(BLOBS, "sha256-" + dig)
        size = os.path.getsize(blob) if os.path.exists(blob) else None
        lines.append(f"  {name:28s} {size if size else '-':>12} B  sha256={dig[:16]}...")
    lines.append("")
    uniq = {}
    for fn, info in exports.items():
        uniq.setdefault(info["sha256"], []).append(fn)
    lines.append("### distinct exports by content")
    for dig, fns in uniq.items():
        lines.append(f"  {dig[:16]}...  <- {fns}")
    lines.append(f"\n  {len(exports)} exported files, {len(uniq)} distinct by content")

    payload = {"exports": exports, "deployed": deployed,
               "distinct_export_contents": len(uniq)}
    with open(os.path.join(ROOT, "benchmarks", "gguf_fingerprint.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    with open(os.path.join(ROOT, "benchmarks", "gguf_fingerprint.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
