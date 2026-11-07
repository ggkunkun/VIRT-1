"""Verify (on disk, not on the console) whether any project file is mojibake.

Earlier confusion came from PowerShell rendering UTF-8 through a GBK console:
a correct path *looks* broken.  This checks the bytes.
"""
from __future__ import annotations

import io
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MARKERS = ["妯″瀷", "锟斤拷", "烫烫烫", "鏂囨湰", "宸ヤ綔", "鍙浠",
           "鏍煎紡", "璁剧疆", "瀹夎」", "鍒嗛暟", "�"]


def check(path, label):
    rel = os.path.relpath(path, ROOT)
    try:
        text = io.open(path, encoding="utf-8").read()
    except Exception as exc:  # noqa: BLE001
        print(f"{label:28s} READ-FAIL {exc}")
        return
    hits = [m for m in MARKERS if m in text]
    print(f"{label:28s} mojibake={hits or 'NONE'}")
    # show the first note/path so a human can eyeball it
    for m in re.finditer(r'"(?:note|model_path|adapter_path|base_url)"\s*:\s*"([^"]{0,90})"', text):
        print(f"    {m.group(0)[:120]}")


def main():
    check(os.path.join(ROOT, "virtu_eval", "arms.json"), "virtu_eval/arms.json")
    p = os.path.join(ROOT, "bridges", "tool_calling_specs.py")
    text = io.open(p, encoding="utf-8").read()
    m = re.search(r'output_path\s*=\s*r?"([^"]*gui_capture[^"]*)"', text)
    print(f"{'bridge gui_capture path':28s} {m.group(1) if m else 'not found'}")
    if m:
        print(f"{'  -> exists on disk':28s} {os.path.exists(m.group(1))}")

    # every absolute path literal inside the project's own python
    import glob
    print("\n--- absolute D:\\ paths in project source ---")
    bad = 0
    for f in glob.glob(os.path.join(ROOT, "**", "*.py"), recursive=True):
        rel = os.path.relpath(f, ROOT)
        if rel.startswith(("external", ".venv", "checkpoints", "models", "runs")):
            continue
        try:
            t = io.open(f, encoding="utf-8").read()
        except Exception:  # noqa: BLE001
            continue
        for mm in re.finditer(r'["\']([dD]:\\\\[^"\'\n]{3,120})["\']', t):
            path = mm.group(1).replace("\\\\", "\\")
            if any(x in path for x in ("%s", "{", "}")):
                continue
            if not os.path.exists(path):
                bad += 1
                print(f"  MISSING {rel}: {path}")
    print(f"  total hardcoded absolute paths that do not exist: {bad}")


if __name__ == "__main__":
    main()
