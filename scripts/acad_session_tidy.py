#!/usr/bin/env python
"""Tidy the AutoCAD session: close the scratch documents opened during
diagnosis, then report the state of the real drawing (layouts, dirty flag).
"""
from __future__ import annotations

import json
import os
import sys
import time

import pythoncom
import win32com.client as win32

PROGIDS = ["AutoCAD.Application.25.1", "AutoCAD.Application.25", "AutoCAD.Application"]
RETRY_HRESULTS = (-2147418111, -2147417846, -2147417851, -2147417843, -2147417848, -2147417850)


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


def iter_collection(coll):
    items = []
    try:
        for x in coll:
            items.append(x)
        return items
    except Exception:
        pass
    try:
        count = int(coll.Count)
    except Exception:
        return items
    for i in range(1, count + 1):
        try:
            items.append(coll.Item(i))
        except Exception:
            continue
    return items


def main() -> int:
    target = os.path.abspath(sys.argv[1])
    scratch_root = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else ""
    outdir = os.path.abspath(sys.argv[3]) if len(sys.argv) > 3 else os.getcwd()

    app = attach()
    call(lambda: setattr(app, "Visible", True))
    report = {"closed": [], "remaining": []}

    for d in iter_collection(app.Documents):
        try:
            full = str(d.FullName)
            name = str(d.Name)
            ro = bool(d.ReadOnly)
        except Exception:
            continue
        is_scratch = scratch_root and os.path.normcase(full).startswith(os.path.normcase(scratch_root))
        if is_scratch:
            try:
                call(d.Close, False)  # never save scratch copies
                report["closed"].append({"name": name, "full_name": full, "readonly": ro})
            except Exception as exc:
                report["closed"].append({"name": name, "error": str(exc)})
        else:
            layouts = []
            try:
                for l in iter_collection(d.Layouts):
                    layouts.append({
                        "name": str(l.Name),
                        "model_type": int(l.ModelType),
                        "entity_count": int(l.Block.Count),
                    })
            except Exception:
                pass
            report["remaining"].append({
                "name": name, "full_name": full, "readonly": ro,
                "saved": bool(d.Saved), "model_entities": int(d.ModelSpace.Count),
                "layouts": layouts,
            })

    time.sleep(0.8)
    with open(os.path.join(outdir, "session_tidy_report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    pythoncom.CoInitialize()
    try:
        sys.exit(main())
    finally:
        pythoncom.CoUninitialize()
