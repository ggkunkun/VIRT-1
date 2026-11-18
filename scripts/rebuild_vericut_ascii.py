# -*- coding: utf-8 -*-
"""Rebuild the impeller VERICUT project in an ASCII-only directory.

Root cause fixed here: the previous project referenced stock/design/NC via
ABSOLUTE paths containing Chinese characters (D:\\Virtu模型\\...).  VERICUT 9.6
is a Java app and fails to resolve such paths, so the NC program node never
appeared in the GUI project tree.  The official sample uses BARE relative
filenames resolved through CGTECH_LIBRARY / project directory.  We mirror that.

Outputs (all under E:/vc_impeller_run):
  AE_CLOSED_IMPELLER_VERICUT.vcproject  (all <File> paths -> bare basenames)
  AE_CLOSED_IMPELLER_stock.stl          (near-net blank, copied)
  AE_CLOSED_IMPELLER_NASA1975.stl       (design, copied)
  AE_CLOSED_IMPELLER_5AXIS_FIXED.nc     (NC program, copied)
  force-impeller_fixture{1,2,3}.ply     (fixtures, copied)
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

SRC = Path(r"D:\Virtu模型\artifacts\aero_closed_impeller")
DST = Path(r"E:\vc_impeller_run")

FILES = [
    "AE_CLOSED_IMPELLER_stock.stl",
    "AE_CLOSED_IMPELLER_NASA1975.stl",
    "AE_CLOSED_IMPELLER_5AXIS_FIXED.nc",
]
FIXTURES = [f"force-impeller_fixture{i}.ply" for i in (1, 2, 3)]
FIX_SRC = Path(r"E:\samples\Support_files")
PROJ = "AE_CLOSED_IMPELLER_VERICUT.vcproject"


def main() -> int:
    DST.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in FILES:
        s = SRC / name
        assert s.is_file(), f"missing {s}"
        shutil.copy2(s, DST / name)
        copied.append((s.name, (DST / name).stat().st_size))
    for name in FIXTURES:
        s = FIX_SRC / name
        assert s.is_file(), f"missing {s}"
        shutil.copy2(s, DST / name)
        copied.append((s.name, (DST / name).stat().st_size))

    text = (SRC / PROJ).read_text(encoding="utf-8")
    # Replace any absolute file path (Windows, with or without Chinese chars)
    # inside a <File>...</File> tag with its bare basename.
    def repl(m: re.Match) -> str:
        inner = m.group(1).strip()
        if not inner or "*" in inner or inner.lower().endswith(".csv"):
            return m.group(0)
        # Windows path could use \ or /; take the last component.
        base = re.split(r"[\\/]", inner)[-1]
        return f"<File>{base}</File>"

    new_text, n = re.subn(r"<File>(.*?)</File>", repl, text, flags=re.S)
    assert n > 0, "no <File> tags found"

    # Sanity: no non-ASCII characters anywhere in the project file.
    bad = [(i + 1, ln) for i, ln in enumerate(new_text.splitlines())
           if any(ord(c) > 127 for c in ln)]
    # The <Comment> line contains ASCII tags only in our project; keep strict.
    out = DST / PROJ
    out.write_text(new_text, encoding="ascii", errors="strict")
    print("wrote", out)
    print("file tags rewritten:", n)
    print("copied:", copied)
    if bad:
        print("WARN non-ascii lines kept:", bad[:5])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
