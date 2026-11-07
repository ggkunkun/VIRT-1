#!/usr/bin/env python
"""Reopen the unlocked DWG in AutoCAD so the padlock badge disappears.

An already-open document keeps its read-only state until it is closed and
reopened, so the tab still shows the lock even after the file attribute was
cleared.  This closes the stale read-only document and reopens it writable,
then captures the AutoCAD title-bar region as visual evidence.
"""
from __future__ import annotations

import json
import os
import sys
import time

import pythoncom
import win32com.client as win32
import win32con
import win32gui

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


def acad_window():
    found = []

    def cb(hwnd, _):
        cls = win32gui.GetClassName(hwnd)
        if cls.startswith("AfxMDIFrame") or "AutoCAD" in (win32gui.GetWindowText(hwnd) or ""):
            if win32gui.IsWindowVisible(hwnd):
                found.append(hwnd)

    win32gui.EnumWindows(cb, None)
    return found[0] if found else None


def main() -> int:
    target = os.path.abspath(sys.argv[1])
    outdir = os.path.abspath(sys.argv[2])
    os.makedirs(outdir, exist_ok=True)

    app = attach()
    call(lambda: setattr(app, "Visible", True))
    report = {"target": target}

    # 1) close any open document pointing at the same file
    closed = []
    for d in iter_collection(app.Documents):
        full = ""
        try:
            full = str(d.FullName)
        except Exception:
            pass
        if full and os.path.normcase(os.path.abspath(full)) == os.path.normcase(target):
            ro = None
            name = ""
            try:
                ro = bool(d.ReadOnly)
                name = str(d.Name)
            except Exception:
                pass
            try:
                call(d.Close, False)
                closed.append({"name": name, "was_readonly": ro, "closed": True})
            except Exception as exc:
                closed.append({"name": name, "error": str(exc)})
    report["closed_stale_documents"] = closed
    time.sleep(1.0)

    # 2) reopen writable
    doc = call(app.Documents.Open, target, False)
    call(lambda: doc.Activate())
    report["reopened"] = {
        "name": str(doc.Name),
        "full_name": str(doc.FullName),
        "readonly": bool(doc.ReadOnly),
        "saved": bool(doc.Saved),
        "model_entity_count": int(doc.ModelSpace.Count),
        "layouts": [str(l.Name) for l in iter_collection(doc.Layouts)],
    }

    # 3) visual evidence: capture the AutoCAD window / tab strip
    try:
        from PIL import ImageGrab
        hwnd = acad_window()
        if hwnd:
            try:
                win32gui.SetForegroundWindow(hwnd)
            except Exception:
                pass
            time.sleep(1.5)
            rect = win32gui.GetWindowRect(hwnd)
            img = ImageGrab.grab(bbox=rect)
            shot = os.path.join(outdir, "acad_window_after_unlock.png")
            img.save(shot)
            # crop the top strip (document tab bar)
            tab = img.crop((0, 0, img.width, min(120, img.height)))
            tab.save(os.path.join(outdir, "acad_tabbar_after_unlock.png"))
            report["screenshot"] = shot
    except Exception as exc:
        report["screenshot_error"] = str(exc)

    with open(os.path.join(outdir, "reopen_report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0 if report["reopened"]["readonly"] is False else 2


if __name__ == "__main__":
    pythoncom.CoInitialize()
    try:
        sys.exit(main())
    finally:
        pythoncom.CoUninitialize()
