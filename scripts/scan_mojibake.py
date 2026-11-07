"""Scan the repository's own source for lossy GBK/UTF-8 transcoding.

A wrong-looking character in a console is often just the console.  A wrong
character *on disk* is a bug: a path like ``D:\\Virtu妯″瀷\\scratch`` does not
exist, the write silently lands somewhere else, and the failure surfaces
much later as "file not found" with no obvious cause.

This scans the files the project actually owns (skipping vendored trees and
binary assets) for the fingerprints of a UTF-8 -> GBK -> UTF-8 round trip.
"""

from __future__ import annotations

import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", ".venv", "__pycache__", "external", "checkpoints", "models",
             "node_modules", ".pytest_cache", ".workbuddy", "runs", "scratch",
             "benchmarks", "logs", "work", "data", "bridges/.cache"}
SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".safetensors", ".gguf", ".pt", ".bin",
            ".zip", ".dwg", ".dxf", ".nc", ".prt", ".sldprt", ".db", ".pdf", ".ico"}

# Fragments that only occur when CJK text survives a wrong-codec round trip.
# Each one is a *specific* corruption, not a generic "unusual character".
MARKERS = [
    ("Virtu妯″瀷", "仓库根目录名 'Virtu模型' 被按 GBK 解码"),
    ("锟斤拷", "U+FFFD 反复转码留下的典型乱码"),
    ("烫烫烫", "GBK 误解码的填充"),
    ("鏂囨湰", "'文件' 的 GBK 误解码"),
    ("宸ヤ綔", "'工作' 的 GBK 误解码"),
    ("妯″瀷", "'模型' 的 GBK 误解码"),
    ("瀹夎」", "'项目' 的 GBK 误解码"),
    ("鍙浠", "'可以' 的 GBK 误解码"),
    ("绀惧悊", "'管理' 的 GBK 误解码"),
    ("鍒嗙暟", "'参数' 的 GBK 误解码"),
    ("璁剧疆", "'设置' 的 GBK 误解码"),
    ("鍚勪涓", "'各个' 的 GBK 误解码"),
    ("鏍囧紡", "'格式' 的 GBK 误解码"),
    ("鎵€鍦", "'所在' 的 GBK 误解码"),
    ("瀹㈡埛", "'客户' 的 GBK 误解码"),
    ("杞ㄩ程式", "'软体' 的 GBK 误解码"),
    ("纭勬垗", "'确定' 的 GBK 误解码"),
    ("鎻愮ず", "'提示' 的 GBK 误解码"),
    ("锛塦", "'，' 的 GBK 误解码"),
    ("銆", "'。' 的 GBK 误解码"),
    ("鈥", "'“' 的 GBK 误解码"),
    ("闂", "'间' 的 GBK 误解码"),
]

# A single U+FFFD means at least one character was already lost.
REPL = "\ufffd"


def main():
    hits = []
    scanned = 0
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames
                       if d not in SKIP_DIRS and not d.startswith(".git")]
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext in SKIP_EXT:
                continue
            path = os.path.join(dirpath, fn)
            try:
                if os.path.getsize(path) > 8 * 1024 * 1024:
                    continue
                raw = open(path, "rb").read()
            except OSError:
                continue
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                # not valid UTF-8 at all - report separately
                hits.append({"path": os.path.relpath(path, ROOT),
                             "issue": "file is not valid UTF-8",
                             "markers": [], "lines": []})
                continue
            scanned += 1
            found = [(m, why) for m, why in MARKERS if m in text]
            rep_lines = []
            if REPL in text:
                for i, line in enumerate(text.splitlines(), 1):
                    if REPL in line:
                        rep_lines.append(i)
            if found or rep_lines:
                lines = []
                for i, line in enumerate(text.splitlines(), 1):
                    if any(m in line for m, _ in found) or REPL in line:
                        lines.append((i, line.strip()[:160]))
                hits.append({
                    "path": os.path.relpath(path, ROOT),
                    "issue": "mojibake" if found else "U+FFFD replacement chars",
                    "markers": [{"text": m, "meaning": why} for m, why in found],
                    "replacement_char_lines": rep_lines[:20],
                    "lines": lines[:20],
                })

    print(f"scanned {scanned} text files, {len(hits)} with transcoding damage")
    out = io.open(os.path.join(ROOT, "benchmarks", "mojibake_scan.txt"), "w", encoding="utf-8")
    for h in hits:
        out.write(f"\n=== {h['path']}  [{h['issue']}]\n")
        for m in h["markers"]:
            out.write(f"    marker {m['text']!r} -> {m['meaning']}\n")
        for ln, txt in h["lines"]:
            out.write(f"    {ln}: {txt}\n")
    out.close()
    print("wrote benchmarks/mojibake_scan.txt")
    for h in hits[:40]:
        print(f"  {h['path']}: {h['issue']} {len(h['lines'])} line(s)")
    if len(hits) > 40:
        print(f"  ... and {len(hits) - 40} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
