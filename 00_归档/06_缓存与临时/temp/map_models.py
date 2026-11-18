# -*- coding: utf-8 -*-
"""建立 ollama 模型库与 D:\Virtu模型 文件夹中权重文件的对应关系"""
import json, subprocess, hashlib, os, re

def sh(args):
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                          errors="replace").stdout

# 1. ollama list
rows = []
for line in sh(["ollama", "list"]).splitlines()[1:]:
    line = line.rstrip()
    if not line.strip():
        continue
    parts = line.split()
    if len(parts) < 4:
        continue
    name, mid = parts[0], parts[1]
    size = " ".join(parts[2:4])
    rows.append({"name": name, "id": mid, "size": size})

# 2. 每个模型的 blob 与参数
out = []
for r in rows:
    mf = sh(["ollama", "show", "--modelfile", r["name"]])
    froms = [l.split(" ", 1)[1].strip() for l in mf.splitlines() if l.startswith("FROM ")]
    params = [l for l in mf.splitlines() if l.startswith("PARAMETER")]
    has_tools = "tools" in sh(["ollama", "show", r["name"]]).lower()
    out.append({**r, "from": froms, "params": params, "supports_tools": has_tools})

# 3. D 盘权重文件
disk = []
for root, dirs, files in os.walk(r"D:\Virtu模型"):
    dirs[:] = [d for d in dirs if d not in (".git", ".venv", "node_modules", "scratch",
                                            "build", "__pycache__", ".pytest_cache")]
    for f in files:
        if f.endswith((".gguf", ".safetensors")) or f == "config.json":
            p = os.path.join(root, f)
            try:
                sz = os.path.getsize(p)
            except OSError:
                continue
            if sz < 50 * 1024 * 1024 and not f.endswith(".gguf"):
                continue
            if sz < 1024 * 1024:
                continue
            disk.append({"path": p, "gb": round(sz / 1024**3, 2)})

# 4. blob 文件实际大小
blob_dir = r"E:\ollama\models\blobs"
blobs = {}
if os.path.isdir(blob_dir):
    for f in os.listdir(blob_dir):
        p = os.path.join(blob_dir, f)
        try:
            blobs["sha256-" + f.replace("sha256-", "")] = os.path.getsize(p)
        except OSError:
            pass

res = {"ollama_models": out, "disk_weights": disk,
       "blob_count": len(blobs), "blob_total_gb": round(sum(blobs.values()) / 1024**3, 2)}
json.dump(res, open(r"D:\Virtu模型\temp\mapping.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# 5. 输出摘要：D 盘 gguf 的 sha256 是否作为 blob 存在
print("=== MODEL COUNT ===", len(out))
uniq = {}
for m in out:
    key = tuple(m["from"])
    uniq.setdefault(key, []).append(m["name"])
print("=== UNIQUE BLOB SETS ===", len(uniq))
for k, v in sorted(uniq.items(), key=lambda x: -len(x[1])):
    sz = ""
    for b in k:
        bn = os.path.basename(b)
        if bn in blobs:
            sz = f"{blobs[bn]/1024**3:.2f}GB"
    print(f"{sz:>8} | {len(v):2d} tags | {' / '.join(v[:6])}")
