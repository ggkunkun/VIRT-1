#!/usr/bin/env python
"""Definitive probe of a DWG's write-protection state through AutoCAD COM.

Correct API usage: Documents.Open(Name, ReadOnly, Password) -- the 2nd argument
IS ReadOnly, so it must be False (or omitted) to open a document writable.

For each file the probe reports:
  readonly / readonly_recommended (with the real exception text, not swallowed)
  whether a real edit can be made and SAVED and survives a reopen
"""
from __future__ import annotations

import json
import os
import shutil
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


def probe_prop(doc, name):
    try:
        return {"ok": True, "value": getattr(doc, name)}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


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


def probe_file(app, path, workdir, tag):
    out = {"tag": tag, "path": path}
    work = os.path.join(workdir, f"_probe_{tag}.dwg")
    shutil.copy2(path, work)
    doc = call(app.Documents.Open, work, False)  # ReadOnly=False
    out["readonly"] = probe_prop(doc, "ReadOnly")
    out["readonly_recommended"] = probe_prop(doc, "ReadOnlyRecommended")
    out["name"] = probe_prop(doc, "Name")
    out["full_name"] = probe_prop(doc, "FullName")
    out["saved"] = probe_prop(doc, "Saved")

    # try to clear the flag if it is set and writable
    try:
        doc.ReadOnlyRecommended = False
        out["clear_readonly_recommended"] = {"ok": True}
    except Exception as exc:
        out["clear_readonly_recommended"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    # real edit + save + reopen
    try:
        call(lambda: doc.Activate())
        ms = call(lambda: doc.ModelSpace)
        n0 = call(lambda: ms.Count)
        lisp = ('(progn (entmake (list (cons 0 "LINE") (cons 10 (list 0.0 0.0 0.0)) '
                '(cons 11 (list 10.0 10.0 0.0)) (cons 8 "0"))) '
                '(vla-Save (vla-get-ActiveDocument (vlax-get-acad-object))) (princ))')
        call(lambda: doc.SendCommand(lisp + "\n"))
        time.sleep(3.0)
        n1 = call(lambda: ms.Count)
        out["edit"] = {"entities_before": n0, "entities_after": n1,
                       "saved_flag": safe_bool(doc)}
        # save again through COM (independent of the LISP save)
        try:
            call(lambda: doc.Save())
        except Exception as exc:
            out["edit"]["com_save_error"] = str(exc)
        call(doc.Close, False)

        d2 = call(app.Documents.Open, work, False)
        n2 = call(lambda: d2.ModelSpace.Count)
        ro2 = probe_prop(d2, "ReadOnly")
        out["edit"]["entities_reopened"] = n2
        out["edit"]["persisted"] = (n2 == n1 and n1 == n0 + 1)
        out["reopen_readonly"] = ro2
        call(d2.Close, False)
    except Exception as exc:
        out["edit"] = {"error": f"{type(exc).__name__}: {exc}"}
    out["verdict"] = ("WRITABLE" if out.get("edit", {}).get("persisted") else "PROTECTED")
    return out


def safe_bool(doc):
    try:
        return bool(doc.Saved)
    except Exception:
        return None


def main() -> int:
    workdir = os.path.abspath(sys.argv[1])
    files = sys.argv[2:]
    os.makedirs(workdir, exist_ok=True)
    app = attach()
    call(lambda: setattr(app, "Visible", True))
    results = []
    for i, f in enumerate(files):
        path = os.path.abspath(f)
        print(f"--- probing {path}", flush=True)
        try:
            r = probe_file(app, path, workdir, f"f{i}")
        except Exception as exc:
            r = {"path": path, "error": f"{type(exc).__name__}: {exc}", "verdict": "ERROR"}
        results.append(r)
        print(json.dumps(r, ensure_ascii=False), flush=True)
    with open(os.path.join(workdir, "protection_probe.json"), "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    pythoncom.CoInitialize()
    try:
        sys.exit(main())
    finally:
        pythoncom.CoUninitialize()
