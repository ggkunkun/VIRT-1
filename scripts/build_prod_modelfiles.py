#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""「全面补齐短板」第 1 层：把所有唯一权重统一到同一份干净生产构件。

补齐的是**工程层缺陷**，不是背答案：
  - 统一完整 ChatML 模板（旧构件有 TEMPLATE {{ .Prompt }} 裸模板，system 轮被静默丢弃）
  - 统一 num_ctx 8192 / temperature 0 / seed / num_predict 512 / repeat_penalty
  - 统一 702 B 原则性 system（`checkpoints/PRODUCTION_SYSTEM_702B.txt`），
    该层 sha256 = 7f997deb7e1b…，不含任何题库答案、不含任何具体数值
  - 权重层 sha256 不变（本机无训练资源，绝不假称"训练强化"）

每个权重一个 `virtu-max:<sha8>` 标签，身份可逐层核验。
用法:
  python scripts/build_prod_modelfiles.py            # 只生成 Modelfile + 清单
  python scripts/build_prod_modelfiles.py --create   # 额外执行 ollama create
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLOBS = r"E:\ollama\models\blobs"
MANIFESTS = r"E:\ollama\models\manifests-v2"
OUTDIR = os.path.join(ROOT, "modelfiles", "prod")
SYSTEM_FILE = os.path.join(ROOT, "checkpoints", "PRODUCTION_SYSTEM_702B.txt")
TEMPLATE_SRC = os.path.join(ROOT, "checkpoints", "virtu-v3-all90.Modelfile")
LIST_JSON = os.path.join(ROOT, "benchmarks", "PRODUCTION_BUILD_MANIFEST_2026-11-08.json")

# 6 GB 显存放不下的权重，明确排除并记账，不假装测过
MAX_BYTES = 12_000_000_000
SKIP_NAME_HINTS = ("bge-", "nomic-", "embed")

TEMPLATE = '''TEMPLATE """{{ if .System }}system
{{ .System }}
{{ end }}{{ if .Prompt }}user
{{ .Prompt }}
{{ end }}assistant
{{ .Response }}"""'''

PARAMS = """PARAMETER num_ctx 8192
PARAMETER temperature 0
PARAMETER top_p 1
PARAMETER seed 1234
PARAMETER num_predict 512
PARAMETER repeat_penalty 1.15
"""


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def unique_weights():
    groups = {}
    for p in glob.glob(os.path.join(MANIFESTS, "**", "*"), recursive=True):
        if not os.path.isfile(p):
            continue
        try:
            d = json.load(open(p, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        ml = [l for l in d.get("layers", [])
              if str(l.get("mediaType", "")).endswith(".model")]
        if not ml:
            continue
        l = ml[0]
        rel = os.path.relpath(p, MANIFESTS).replace("\\", "/")
        parts = rel.split("/")
        alias = ":".join(parts[2:]) if len(parts) >= 3 else rel
        key = (l["digest"], l["size"])
        groups.setdefault(key, []).append(alias)
    return groups


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--create", action="store_true")
    a = ap.parse_args()

    sys_bytes = open(SYSTEM_FILE, "rb").read()
    sys_txt = sys_bytes.decode("utf-8")
    sys_sha = "sha256:" + sha256_bytes(sys_bytes)
    template_src = open(TEMPLATE_SRC, encoding="utf-8").read()
    m = re.search(r'TEMPLATE\s+"""(.*?)"""', template_src, re.S)
    assert m and ".System" in m.group(1), "源 Modelfile 缺 ChatML 模板"
    template_txt = m.group(1)
    template_sha = "sha256:" + sha256_bytes(template_txt.encode("utf-8"))

    os.makedirs(OUTDIR, exist_ok=True)
    rows, skipped = [], []
    for (digest, size), aliases in sorted(unique_weights().items(), key=lambda x: -x[0][1]):
        hexd = digest.split(":", 1)[-1]
        short = hexd[:12]
        blob = os.path.join(BLOBS, "sha256-" + hexd)
        reason = None
        if size > MAX_BYTES:
            reason = "权重 %.1f GB > 6GB 显存可承载范围" % (size / 1e9)
        elif not os.path.exists(blob):
            reason = "权重 blob 不在盘上"
        elif any(h in x.lower() for x in aliases for h in SKIP_NAME_HINTS):
            reason = "embedding 模型，无 completion 能力"
        if reason:
            skipped.append({"sha": short, "bytes": size, "aliases": aliases, "reason": reason})
            continue

        tag = "virtu-max:" + short[:8]
        lines = [
            "FROM " + blob.replace("\\", "/"), "",
            TEMPLATE, "",
            'SYSTEM """' + sys_txt.rstrip("\n") + '"""', "",
            PARAMS.rstrip("\n"), "",
        ]
        content = "\n".join(lines)
        mf_path = os.path.join(OUTDIR, "virtu-max-" + short[:8] + ".Modelfile")
        with open(mf_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        rows.append({
            "tag": tag,
            "model_layer": digest, "model_bytes": size,
            "system_layer": sys_sha, "system_bytes": len(sys_bytes),
            "template_layer": template_sha,
            "modelfile": os.path.relpath(mf_path, ROOT).replace("\\", "/"),
            "modelfile_sha256": sha256_bytes(content.encode("utf-8")),
            "source_aliases": sorted(set(aliases)),
            "blob_path": blob.replace("\\", "/"),
        })

    manifest = {
        "purpose": "2026-11-08 全面补齐短板后的统一生产构件（工程层补齐，权重未改）",
        "basis": "asserted + 逐层 sha256 可核验",
        "system_source": os.path.relpath(SYSTEM_FILE, ROOT).replace("\\", "/"),
        "system_sha256": sys_sha,
        "system_contains_case_answers": False,
        "template_sha256": template_sha,
        "template_source": os.path.relpath(TEMPLATE_SRC, ROOT).replace("\\", "/"),
        "params": "num_ctx=8192, temperature=0, seed=1234, num_predict=512, repeat_penalty=1.15",
        "weight_training": "未做；权重层 sha256 与 11-07/11-08 评测时完全相同",
        "built": rows, "skipped": skipped,
        "ollama_create_run": False,
    }

    if a.create:
        for r in rows:
            p = os.path.join(ROOT, r["modelfile"])
            try:
                cp = subprocess.run(["ollama", "create", r["tag"], "-f", p],
                                    capture_output=True, text=True, timeout=300)
                r["create_rc"] = cp.returncode
                r["create_ok"] = cp.returncode == 0 and "success" in (cp.stdout + cp.stderr)
                if not r["create_ok"]:
                    r["create_err"] = (cp.stdout + cp.stderr)[-400:]
            except Exception as e:  # noqa: BLE001
                r["create_rc"] = -1
                r["create_ok"] = False
                r["create_err"] = repr(e)
            print("[create]", r["tag"], "OK" if r.get("create_ok") else "FAIL", flush=True)
        manifest["ollama_create_run"] = True

    with open(LIST_JSON, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print("built=%d skipped=%d system=%s" % (len(rows), len(skipped), sys_sha[:22]))
    for s in skipped:
        print("  skip", s["sha"], s["reason"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
