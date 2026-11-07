#!/usr/bin/env python
"""Remove the write protection from the target DWG and prove it is editable.

Root cause: the file carries the NTFS read-only attribute (AutoCAD then opens
it read-only and refuses to save with "the drawing file is write protected").
This script:
  1. records SHA256 before the change
  2. clears the read-only attribute (os.chmod | S_IWRITE)
  3. records SHA256 after -> must be identical (no content touched)
  4. verifies AutoCAD now opens it read-write (ReadOnly == False)
  5. runs a real edit+save+reopen write probe on a COPY (never on the original)
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import sys
import time

import pythoncom
import win32com.client as win32

PROGIDS = ["AutoCAD.Application.25.1", "AutoCAD.Application.25", "AutoCAD.Application"]
RETRY_HRESULTS = (-2147418111, -2147417846, -2147417851, -2147417843)


def call(fn, *a, **kw):
    last = None
    for _ in range(120):
        try:
            return fn(*a, **kw)
        except pythoncom.com_error as exc:  # type: ignore[attr-defined]
            last = exc
            if exc.hresult in RETRY_HRESULTS:
                time.sleep(0.5)
                continue
            raise
    raise last  # type: ignore[misc]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def attach():
    last = None
    for progid in PROGIDS:
        try:
            try:
                app = win32.GetActiveObject(progid)
            except Exception:
                app = win32.Dispatch(progid)
            return app
        except Exception as exc:
            last = exc
    raise RuntimeError(f"cannot attach to AutoCAD COM: {last}")


def main() -> int:
    target = os.path.abspath(sys.argv[1])
    workdir = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.path.dirname(target)
    os.makedirs(workdir, exist_ok=True)
    report = {"target": target}

    st = os.stat(target)
    report["attributes_before"] = {
        "read_only_flag": bool(st.st_file_attributes & stat.FILE_ATTRIBUTE_READONLY),
        "attributes": st.st_file_attributes,
    }
    report["sha256_before"] = sha256(target)
    report["size_before"] = st.st_size

    # 1) clear the read-only attribute
    os.chmod(target, stat.S_IWRITE | (st.st_mode & ~stat.S_IREAD))
    st2 = os.stat(target)
    report["attributes_after"] = {
        "read_only_flag": bool(st2.st_file_attributes & stat.FILE_ATTRIBUTE_READONLY),
        "attributes": st2.st_file_attributes,
    }
    report["sha256_after"] = sha256(target)
    report["content_identical"] = report["sha256_before"] == report["sha256_after"]

    # 2) AutoCAD side: open original read-write (no save) + probe on a copy
    app = attach()
    call(lambda: setattr(app, "Visible", True))
    try:
        doc = call(app.Documents.Open, target, False)
        report["acad_original"] = {
            "name": str(doc.Name),
            "readonly": bool(doc.ReadOnly),
            "saved": bool(doc.Saved),
            "model_entity_count": int(doc.ModelSpace.Count),
        }
        call(doc.Close, False)
    except Exception as exc:
        report["acad_original"] = {"error": str(exc)}

    probe_copy = os.path.join(workdir, "_writeprobe.dwg")
    shutil.copy2(target, probe_copy)
    try:
        d = call(app.Documents.Open, probe_copy, False)
        ms = call(lambda: d.ModelSpace)
        n0 = call(lambda: ms.Count)
        lisp = ('(progn (entmake (list (cons 0 "LINE") (cons 10 (list 0.0 0.0 0.0)) '
                '(cons 11 (list 10.0 10.0 0.0)) (cons 8 "0"))) '
                '(vla-Save (vla-get-ActiveDocument (vlax-get-acad-object))) (princ))')
        call(lambda: d.Activate())
        call(lambda: d.SendCommand(lisp + "\n"))
        time.sleep(3.0)
        n1 = call(lambda: ms.Count)
        call(d.Close, False)
        d2 = call(app.Documents.Open, probe_copy, False)
        n2 = call(lambda: d2.ModelSpace.Count)
        ro = bool(d2.ReadOnly)
        call(d2.Close, False)
        report["write_probe"] = {
            "entities_before": n0, "entities_after_edit": n1, "entities_after_reopen": n2,
            "edit_persisted": n2 == n1 == n0 + 1,
            "readonly_on_reopen": ro,
            "verdict": "WRITABLE" if (n2 == n1 == n0 + 1 and ro is False) else "PROTECTED",
        }
    except Exception as exc:
        report["write_probe"] = {"error": str(exc)}

    report["unlocked"] = bool(
        report["attributes_after"]["read_only_flag"] is False
        and report.get("write_probe", {}).get("verdict") == "WRITABLE"
        and report.get("acad_original", {}).get("readonly") is False
    )

    out = os.path.join(workdir, "unlock_final_report.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0 if report["unlocked"] else 2


if __name__ == "__main__":
    pythoncom.CoInitialize()
    try:
        sys.exit(main())
    finally:
        pythoncom.CoUninitialize()
