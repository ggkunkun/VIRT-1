#!/usr/bin/env python
"""Analyse the AutoCAD-exported DXF of HKGB-3924-HP1&2&3&4-260206.

Extracts per-layout entity inventory, every text / dimension / block reference,
so the drawing's stated dimensions can be checked and the overall length
(total length) can be computed from the geometry itself.
"""
from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter, defaultdict

import ezdxf


def clean(s):
    if s is None:
        return ""
    s = s.replace("\\P", "\n")
    s = re.sub(r"\\[Ff][^;]*;", "", s)     # font switches
    s = re.sub(r"\\[A-Za-z][^;]*;", "", s)  # other codes
    s = s.replace("{", "").replace("}", "")
    return s.strip()


def main() -> int:
    dxf = sys.argv[1]
    out = sys.argv[2]
    doc = ezdxf.readfile(dxf)
    data = {"dxf": dxf, "dxfversion": doc.dxfversion, "layouts": [], "layers": [], "blocks": []}

    for lay in doc.layouts:
        ents = list(lay)
        texts, dims, inserts, kinds = [], [], [], Counter()
        for e in ents:
            kinds[e.dxftype()] += 1
            t = e.dxftype()
            if t == "TEXT":
                texts.append({"kind": "TEXT", "text": clean(e.dxf.text), "layer": e.dxf.layer,
                              "pos": list(e.dxf.insert), "height": e.dxf.height})
            elif t == "MTEXT":
                texts.append({"kind": "MTEXT", "text": clean(e.text), "layer": e.dxf.layer,
                              "pos": list(e.dxf.insert)})
            elif t == "ATTRIB":
                texts.append({"kind": "ATTRIB", "text": clean(e.dxf.text), "tag": e.dxf.tag,
                              "layer": e.dxf.layer, "pos": list(e.dxf.insert)})
            elif t == "DIMENSION":
                try:
                    meas = e.get_measurement()
                except Exception:
                    meas = None
                dims.append({
                    "dimtype": e.dxf.dimtype, "layer": e.dxf.layer,
                    "text": clean(e.dxf.get("text", "")),
                    "measurement": meas,
                    "defpoint": list(e.dxf.defpoint) if e.dxf.hasattr("defpoint") else None,
                    "defpoint2": list(e.dxf.defpoint2) if e.dxf.hasattr("defpoint2") else None,
                    "defpoint3": list(e.dxf.defpoint3) if e.dxf.hasattr("defpoint3") else None,
                    "text_midpoint": list(e.dxf.text_midpoint) if e.dxf.hasattr("text_midpoint") else None,
                    "rotation": getattr(e.dxf, "rotation", None),
                    "style": getattr(e.dxf, "dimstyle", None),
                })
            elif t == "INSERT":
                inserts.append({"block": e.dxf.name, "layer": e.dxf.layer,
                                "pos": list(e.dxf.insert), "rot": e.dxf.get("rotation", 0.0),
                                "scale": [e.dxf.get("xscale", 1.0), e.dxf.get("yscale", 1.0), e.dxf.get("zscale", 1.0)]})
        data["layouts"].append({
            "name": lay.name, "entity_count": len(ents),
            "kinds": dict(kinds), "texts": texts, "dims": dims, "inserts": inserts,
        })

    data["layers"] = [{"name": l.dxf.name, "color": l.dxf.color, "linetype": l.dxf.linetype}
                      for l in doc.layers]
    data["blocks"] = [{"name": b.name, "entity_count": len(list(b))} for b in doc.blocks]

    # ---- geometry based extents per layout (model space profile) ----
    for lay in data["layouts"]:
        xs, ys = [], []
        for e in doc.layouts.get(lay["name"]):
            t = e.dxftype()
            try:
                if t == "LINE":
                    xs += [e.dxf.start.x, e.dxf.end.x]
                    ys += [e.dxf.start.y, e.dxf.end.y]
                elif t == "LWPOLYLINE":
                    for p in e.get_points("xy"):
                        xs.append(p[0]); ys.append(p[1])
                elif t in ("CIRCLE", "ARC"):
                    xs += [e.dxf.center.x - e.dxf.radius, e.dxf.center.x + e.dxf.radius]
                    ys += [e.dxf.center.y - e.dxf.radius, e.dxf.center.y + e.dxf.radius]
                elif t == "SOLID":
                    for p in (e.dxf.vtx0, e.dxf.vtx1, e.dxf.vtx2, e.dxf.vtx3):
                        xs.append(p.x); ys.append(p.y)
            except Exception:
                pass
        lay["extent_x"] = [min(xs), max(xs)] if xs else None
        lay["extent_y"] = [min(ys), max(ys)] if ys else None
        lay["extent_w"] = (max(xs) - min(xs)) if xs else None
        lay["extent_h"] = (max(ys) - min(ys)) if ys else None

    with open(out, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)

    print("layouts:")
    for lay in data["layouts"]:
        print(f"  {lay['name']}: {lay['entity_count']} entities, texts={len(lay['texts'])}, "
              f"dims={len(lay['dims'])}, inserts={len(lay['inserts'])}, "
              f"extent={lay['extent_w']} x {lay['extent_h']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
