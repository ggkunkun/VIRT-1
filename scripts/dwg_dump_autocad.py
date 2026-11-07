#!/usr/bin/env python
"""Dump AutoCAD DWG content via COM (AutoCAD 2026) into structured JSON.

Usage: python scripts/dwg_dump_autocad.py <dwg_path> <out_json>
Handles RPC_E_CALL_REJECTED with retry (AutoCAD busy), copies source into the
run dir first so the original attachment is never mutated.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time

import pythoncom
import win32com.client as win32

PROGIDS = [
    "AutoCAD.Application.25.1",
    "AutoCAD.Application.25",
    "AutoCAD.Application.24.3",
    "AutoCAD.Application.24",
    "AutoCAD.Application",
]

RPC_E_CALL_REJECTED = -2147418111


def call(fn, *a, **kw):
    """Invoke a COM call, retrying while AutoCAD rejects the call (busy)."""
    last = None
    for _ in range(80):
        try:
            return fn(*a, **kw)
        except pythoncom.com_error as exc:  # type: ignore[attr-defined]
            last = exc
            if exc.hresult in (-2147418111, -2147417846, -2147417851):
                time.sleep(0.5)
                continue
            raise
    raise last  # type: ignore[misc]


def pt(p):
    try:
        return [round(float(p[0]), 6), round(float(p[1]), 6), round(float(p[2]), 6)]
    except Exception:
        return None


def safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def dump_entities(ents):
    out = []
    for e in ents:
        try:
            etype = str(e.ObjectName)
        except Exception:
            continue
        rec = {"type": etype}
        rec["layer"] = safe(lambda: str(e.Layer))
        rec["handle"] = safe(lambda: str(e.Handle))
        try:
            for prop, caster in (
                ("TextString", str),
                ("TextContents", str),
                ("StyleName", str),
                ("Name", str),
                ("Measurement", float),
                ("TextOverride", str),
                ("Radius", float),
                ("StartAngle", float),
                ("EndAngle", float),
                ("Height", float),
                ("Width", float),
                ("Rotation", float),
                ("XScaleFactor", float),
                ("YScaleFactor", float),
                ("ZScaleFactor", float),
                ("Area", float),
                ("Length", float),
                ("TrueColor", int),
            ):
                val = safe(lambda p=prop, c=caster: c(getattr(e, p)))
                if val is not None:
                    rec[prop] = val
            for prop in ("InsertionPoint", "StartPoint", "EndPoint", "Center", "MidPoint"):
                val = safe(lambda p=prop: pt(getattr(e, p)))
                if val is not None:
                    rec[prop] = val
            # polyline vertices
            verts = safe(lambda: [pt(v[0]) for v in e.Vertices])
            if verts:
                rec["vertices"] = verts
            # insert attributes
            attrs = safe(lambda: [
                {"tag": str(a.TagString), "text": str(a.TextString), "pos": pt(a.InsertionPoint)}
                for a in e.GetAttributes()
            ])
            if attrs:
                rec["attributes"] = attrs
        except Exception:
            pass
        out.append(rec)
    return out


def main() -> int:
    src = sys.argv[1]
    out_path = sys.argv[2]
    work_dir = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(work_dir, exist_ok=True)

    local = os.path.join(work_dir, os.path.basename(src))
    if os.path.abspath(src) != os.path.abspath(local):
        shutil.copy2(src, local)
    src = local

    app = None
    started = False
    for progid in PROGIDS:
        try:
            try:
                app = win32.GetActiveObject(progid)
            except Exception:
                app = win32.Dispatch(progid)
            break
        except Exception as exc:  # pragma: no cover
            last = exc
    if app is None:
        print("ERROR: cannot attach to AutoCAD COM:", last)
        return 3

    try:
        call(lambda: setattr(app, "Visible", True))
        version = safe(lambda: str(app.Version))
        acad_path = safe(lambda: str(app.Path)) or safe(lambda: str(app.FullPath))
        print("attached version=", version, "path=", acad_path)

        doc = call(app.Documents.Open, src, True)
        data = {
            "source": src,
            "acad_version": version,
            "acad_path": acad_path,
            "doc_name": safe(lambda: str(doc.Name)),
            "layouts": [],
            "layers": [],
            "blocks": [],
            "summary": {},
        }

        for lay in call(lambda: [doc.Layouts.Item(i) for i in range(1, doc.Layouts.Count + 1)]):
            lname = safe(lambda l=lay: str(l.Name))
            blk = call(lambda l=lay: l.Block)
            ents = call(lambda b=blk: dump_entities(b.Count and [b.Item(i) for i in range(1, b.Count + 1)]))
            data["layouts"].append({
                "name": lname,
                "entity_count": safe(lambda b=blk: b.Count),
                "entities": ents,
            })

        for i in range(1, call(lambda: doc.Layers.Count) + 1):
            ly = call(lambda i=i: doc.Layers.Item(i))
            data["layers"].append({
                "name": safe(lambda l=ly: str(l.Name)),
                "color": safe(lambda l=ly: int(l.Color)),
                "linetype": safe(lambda l=ly: str(l.Linetype)),
                "on": safe(lambda l=ly: bool(l.LayerOn)),
                "frozen": safe(lambda l=ly: bool(l.Frozen)),
                "locked": safe(lambda l=ly: bool(l.Lock)),
                "plot": safe(lambda l=ly: bool(l.Plottable)),
            })

        for i in range(1, call(lambda: doc.Blocks.Count) + 1):
            b = call(lambda i=i: doc.Blocks.Item(i))
            ents = call(lambda b=b: dump_entities(b.Count and [b.Item(j) for j in range(1, b.Count + 1)]))
            data["blocks"].append({
                "name": safe(lambda b=b: str(b.Name)),
                "is_layout": safe(lambda b=b: bool(b.IsLayout)),
                "is_xref": safe(lambda b=b: bool(b.IsXRef)),
                "entity_count": safe(lambda b=b: b.Count),
                "entities": ents,
            })

        texts = []
        for lay in data["layouts"]:
            for e in lay["entities"]:
                if e["type"] in ("AcDbText", "AcDbMText", "AcDbAttribute", "AcDbAttributeDefinition"):
                    texts.append({
                        "layout": lay["name"],
                        "layer": e.get("layer"),
                        "type": e["type"],
                        "text": e.get("TextString") or e.get("TextContents"),
                        "pos": e.get("InsertionPoint"),
                    })
        data["texts"] = texts
        data["summary"] = {
            "layouts": len(data["layouts"]),
            "layers": len(data["layers"]),
            "blocks": len(data["blocks"]),
            "texts": len(texts),
            "entities_by_layout": {lay["name"]: lay["entity_count"] for lay in data["layouts"]},
        }

        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
        print("dumped ->", out_path, json.dumps(data["summary"], ensure_ascii=False))

        try:
            call(doc.Close, False)
        except Exception:
            pass
        if started:
            try:
                call(app.Quit)
            except Exception:
                pass
        return 0
    finally:
        pythoncom.CoUninitialize()


if __name__ == "__main__":
    sys.exit(main())
