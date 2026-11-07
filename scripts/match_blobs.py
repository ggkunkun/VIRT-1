"""Hash the Ollama blobs directly and match them against the exported GGUFs."""
from __future__ import annotations

import hashlib
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CK = os.path.join(ROOT, "checkpoints")
BLOBS = os.path.join(os.environ.get("USERPROFILE", ""), ".ollama", "models", "blobs")
MANIFESTS = os.path.join(os.environ.get("USERPROFILE", ""), ".ollama", "models",
                         "manifests", "registry.ollama.ai", "library")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 22), b""):
            h.update(c)
    return h.hexdigest()


def main():
    lines = []
    # deployed models, from the manifests on disk
    deployed = {}
    for vendor in sorted(os.listdir(MANIFESTS)):
        vdir = os.path.join(MANIFESTS, vendor)
        if not os.path.isdir(vdir):
            continue
        for model in sorted(os.listdir(vdir)):
            mdir = os.path.join(vdir, model)
            if not os.path.isdir(mdir):
                continue
            for tag in sorted(os.listdir(mdir)):
                f = os.path.join(mdir, tag)
                if not os.path.isfile(f):
                    continue
                try:
                    man = json.load(open(f, encoding="utf-8"))
                except Exception:  # noqa: BLE001
                    continue
                for layer in man.get("layers", []):
                    if layer.get("mediaType", "").endswith("image.model"):
                        deployed[f"{model}:{tag}"] = {
                            "digest": layer["digest"].split("sha256:")[-1],
                            "layer_size": layer.get("size"),
                            "from": layer.get("from", ""),
                        }

    # exported files
    exports = {}
    for fn in sorted(os.listdir(CK)):
        if fn.endswith(".gguf"):
            p = os.path.join(CK, fn)
            exports[fn] = {"bytes": os.path.getsize(p), "sha256": sha256(p)}

    by_digest = {e["sha256"]: (fn, e["bytes"]) for fn, e in exports.items()}

    lines.append("### deployed ollama models -> which exported file they are")
    for name, d in sorted(deployed.items()):
        blob = os.path.join(BLOBS, "sha256-" + d["digest"])
        blob_size = os.path.getsize(blob) if os.path.exists(blob) else None
        blob_hash = sha256(blob) if blob_size and blob_size > 100_000_000 else None
        match = by_digest.get(d["digest"])
        lines.append(f"  {name:30s} blob={d['digest'][:16]}... size={blob_size} "
                     f"declared_size={d['layer_size']} from={d['from']}")
        lines.append(f"      blob content hash  : {(blob_hash or '-')[:16]}")
        lines.append(f"      export matching   : {match[0] if match else 'NONE'}"
                     + (f" (export size {match[1]})" if match else ""))
        if blob_hash and match and blob_hash != match[0] and blob_hash != exports.get(match[0], {}).get("sha256"):
            lines.append("      !! blob content differs from the export with the same digest name")

    lines.append("")
    lines.append("### exported files")
    for fn, e in exports.items():
        match = [n for n, d in deployed.items() if d["digest"] == e["sha256"]]
        lines.append(f"  {fn:34s} {e['bytes']:>13,} B sha256={e['sha256'][:16]}... "
                     f"-> deployed as {match or 'NOT FOUND among ollama models'}")

    out = os.path.join(ROOT, "benchmarks", "gguf_blob_match.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    with open(os.path.join(ROOT, "benchmarks", "gguf_blob_match.json"), "w", encoding="utf-8") as f:
        json.dump({"exports": exports, "deployed": deployed}, f, ensure_ascii=False, indent=2)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
