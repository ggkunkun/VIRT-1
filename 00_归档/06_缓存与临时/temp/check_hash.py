# -*- coding: utf-8 -*-
import json, hashlib, os
m = json.load(open(r"D:\Virtu模型\temp\mapping.json", encoding="utf-8"))
bd = r"E:\ollama\models\blobs"
blobs = set(os.listdir(bd))
print("=== D盘 GGUF 是否已在 ollama 库中 ===")
for d in m["disk_weights"]:
    p = d["path"]
    if not p.endswith(".gguf"):
        continue
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            h.update(chunk)
    key = "sha256-" + h.hexdigest()
    print("  %6.2fGB  in_ollama=%-5s  %s" % (d["gb"], key in blobs, p))

print("\n=== D盘 safetensors 汇总 ===")
tot = 0
for d in m["disk_weights"]:
    if d["path"].endswith(".safetensors"):
        tot += d["gb"]
print("  total %.2f GB, %d files" % (tot, sum(1 for d in m["disk_weights"] if d["path"].endswith(".safetensors"))))

print("\n=== ollama 唯一 blob 集 ===", len(m["ollama_models"]), "tags")
