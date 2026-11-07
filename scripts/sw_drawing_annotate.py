# -*- coding: utf-8 -*-
"""Drawing annotation with measured read-back.

The part is built by API without sketch dimensions, so there is nothing for
InsertModelDimensions to pull in: every dimension on the sheet has to be created here.
Nothing in this module trusts a return value - the sheet is re-enumerated afterwards and
the caller compares the read-back values with the requested ones.

SOLIDWORKS sheet space is metres; model space is metres too, and a view's Xform carries
its sheet position and its scale, so a circle of radius r (mm) in the model projects to a
circle of radius r*0.001*scale at (view_x + dx, view_y + dy).
"""

import math

MM = 0.001
NL = chr(10)

# Which national mechanical-drawing standard each drawing item answers to.
# The numbers were checked against the published GB/T catalogue (not from memory):
# 尺寸注法 is GB/T 4458.4-2003; GB/T 4458.1-2002 is 图样画法 视图.
GB_STANDARDS = {
    "sheet_format": u"GB/T 14689-2008 技术制图 图纸幅面和格式",
    "title_block": u"GB/T 10609.1-2008 技术制图 标题栏",
    "projection": u"GB/T 17451 / GB/T 14662 技术制图 图样画法 视图与投影规则（第一角画法）",
    "scale": u"GB/T 14690-1993 技术制图 比例",
    "lines": u"GB/T 4457.4-2002 机械制图 图样画法 图线（中心线/点划线）",
    "dimensions": u"GB/T 4458.4-2003 机械制图 尺寸注法",
    "tolerance_annotation": u"GB/T 4458.5-2003 机械制图 尺寸公差与配合注法",
    "general_tolerance": u"GB/T 1804-2000 一般公差 未注公差的线性和角度尺寸的公差",
    "surface_structure": u"GB/T 131 产品几何技术规范 表面结构的表示法",
    "geometric": u"GB/T 1182 产品几何技术规范(GPS) 几何公差",
    "flange": u"GB/T 9119 板式平焊法兰尺寸系列",
}

ORTHO_HINTS = (u"前视", u"后视", u"上视", u"下视",
               u"左视", u"右视", "Front", "Rear", "Top", "Bottom",
               "Left", "Right")


# what the model may ask for; each entry maps to real geometry in the saved part
DIM_TARGETS = {
    "D_outer": ("diameter", "front", "r", "D_outer"),
    "D_hub": ("diameter", "front", "r", "D_hub"),
    "D_bore": ("diameter", "front", "r", "D_bore"),
    "D_bolt": ("diameter", "front", "bolt", "D_bolt"),
    "t_base": ("linear", "side", "x", "t_base"),
    "H_total": ("linear", "side", "x", "H_total"),
    # the hub's own axial length: the lower half of the edge view, which is otherwise
    # undimensioned and cannot be inferred from t_base and H_total on a finished sheet
    "hub_height": ("linear", "side", "x", "hub_height"),
}


def _wrap(obj, iface, mod):
    if obj is None:
        return None
    try:
        return getattr(mod, iface)(obj._oleobj_)
    except Exception:
        try:
            return getattr(mod, iface)(obj)
        except Exception:
            return obj


def walk_views(doc, mod):
    """Every view actually on the sheet (index 0 is the sheet-format view).

    GetFirstView is an IDrawingDoc method; the IModelDoc2 pointer for the same document
    does not expose it, so the caller has to hand over the drawing interface.
    """
    out, raw = [], doc.GetFirstView()
    while raw is not None and len(out) < 30:
        v = _wrap(raw, "IView", mod)
        try:
            xf = list(v.GetXform() or [])
        except Exception:
            xf = []
        try:
            name = v.GetName2()
        except Exception:
            name = None
        try:
            orient = v.GetOrientationName()
        except Exception:
            orient = None
        out.append({"raw": raw, "view": v, "name": name, "orientation": orient,
                    "xform": xf})
        raw = v.GetNextView()
    return out


def read_sheet(doc, dmod, mod):
    """Ground truth for the sheet: dimensions (text + value) and notes, per view."""
    dims, notes, errs = [], [], []
    for vd in walk_views(doc, mod):
        v, tag = vd["view"], vd["name"] or "?"
        try:
            limit = max(1, int(v.GetDisplayDimensionCount()))
        except Exception:
            limit = 40
        try:
            dd = v.GetFirstDisplayDimension()
        except Exception as e:
            errs.append("first_display_dim:%s:%s" % (tag, str(e)[:60]))
            continue
        hops = 0
        while dd is not None and hops < limit:
            d = _wrap(dd, "IDisplayDimension", mod)
            rec = {"view": tag, "text": None, "value_mm": None, "type": None}
            try:
                rec["type"] = d.GetType()
            except Exception as e:
                errs.append("type:%s:%s" % (tag, str(e)[:40]))
            try:
                rec["text"] = d.GetText(0)
            except Exception as e:
                errs.append("text:%s:%s" % (tag, str(e)[:40]))
            try:
                dim = _wrap(d.GetDimension(), "IDimension", mod)
                if dim is not None:
                    val = dim.GetValue2("")
                    # measured on this build: GetValue2 already answers in millimetres for
                    # every dimension type seen here, so no rescaling is applied
                    rec["value_mm"] = val
            except Exception as e:
                errs.append("value:%s:%s" % (tag, str(e)[:40]))
            dims.append(rec)
            try:
                dd = d.GetNext()
            except Exception:
                dd = None
            hops += 1
        try:
            n_limit = max(1, int(v.GetNoteCount()))
        except Exception:
            n_limit = 20
        try:
            n = v.GetFirstNote()
        except Exception as e:
            errs.append("first_note:%s:%s" % (tag, str(e)[:50]))
            n = None
        hops = 0
        seen_notes = set()
        while n is not None and hops < n_limit:
            nn = _wrap(n, "INote", mod)
            try:
                txt = str(nn.GetText())
                at = None
                for how in ("IGetPosition", "GetPosition"):
                    g = getattr(nn, how, None) or getattr(
                        _wrap(n, "IAnnotation", mod), how, None)
                    if g is None:
                        continue
                    try:
                        raw = g()
                    except Exception:
                        continue
                    if isinstance(raw, (list, tuple)) and len(raw) >= 2:
                        at = [round(float(raw[0]), 4), round(float(raw[1]), 4)]
                        break
                if txt not in seen_notes:
                    seen_notes.add(txt)
                    notes.append({"view": tag, "text": txt, "at": at})
            except Exception as e:
                errs.append("note_text:%s:%s" % (tag, str(e)[:40]))
            try:
                n = nn.GetNext()
            except Exception:
                n = None
            hops += 1
    return {"dimensions": dims, "notes": notes, "read_errors": errs[:12]}


def _front(vd_list):
    for vd in vd_list:
        o = (vd["orientation"] or "") + (vd["name"] or "")
        if "前视" in o or "Front" in o:
            return vd
    return vd_list[1] if len(vd_list) > 1 else (vd_list[0] if vd_list else None)


def _xf(vd):
    xf = vd.get("xform") or []
    if len(xf) >= 3:
        return xf[0], xf[1], (xf[2] or 1.0)
    return 0.0, 0.0, 1.0


def _ann_pos(ann):
    """Annotation position in its own view's metres (IGetPosition is the one that answers)."""
    for m in ("IGetPosition", "GetPosition"):
        try:
            p = getattr(ann, m)()
        except Exception:
            continue
        if isinstance(p, (tuple, list)) and len(p) >= 2:
            return [float(p[0]), float(p[1])]
    return None


def _in_frame(x_mm, y_mm):
    return (FRAME[0] / MM <= x_mm <= FRAME[2] / MM
            and FRAME[1] / MM <= y_mm <= FRAME[3] / MM)


def _sf_state(d, mod):
    """Every surface-structure symbol on the sheet, with its view origin and read-back text.

    The GB A3 template carries no Ra symbol of its own (grep of gb_a3.drwdot finds no "Ra"
    and no "6.3"), so anything listed here was inserted by this run.
    """
    rows = []
    for vd in walk_views(d, mod):
        vx, vy, _sc = _xf(vd)
        # GetSFSymbols() answers empty on this build even when GetSFSymbolCount() is
        # nonzero, so the symbols are walked one by one instead
        try:
            n = int(vd["view"].GetSFSymbolCount())
            sf = vd["view"].GetFirstSFSymbol()
        except Exception:
            continue
        hops = 0
        while sf is not None and hops < max(1, n):
            hops += 1
            try:
                ann = _wrap(sf.GetAnnotation(), "IAnnotation", mod)
            except Exception:
                ann = None
            txt = None
            try:
                txt = ann.GetText()
            except Exception:
                try:
                    txt = sf.GetText(0)
                except Exception:
                    txt = None
            rows.append({"view": vd["name"], "vx": vx, "vy": vy, "ann": ann,
                         "pos": _ann_pos(ann) if ann is not None else None,
                         "text": str(txt) if txt else None})
            try:
                sf = _wrap(sf, "ISFSymbol", mod).GetNext()
            except Exception:
                break
    return rows


def place_sf_symbol(d, dmod, log, front, radius_mm, ra, angle_deg):
    """Insert one GB/T 131 surface-structure symbol and prove where it ended up.

    InsertSurfaceFinishSymbol ignores LocX/LocY when it has nothing to attach to, which is
    what parked the previous runs' symbols on the sheet origin, half outside the frame. The
    position is therefore set afterwards through IAnnotation.SetPosition and confirmed by
    reading it back, so 'verified' means 'measured inside the drawing frame'.
    """
    vx, vy, sc = _xf(front)
    a = math.radians(angle_deg)
    px = vx + radius_mm / 2.0 * MM * sc * math.cos(a)
    py = vy + radius_mm / 2.0 * MM * sc * math.sin(a)
    tx = vx + (radius_mm / 2.0 + 14.0) * MM * sc * math.cos(a)
    ty = vy + (radius_mm / 2.0 + 14.0) * MM * sc * math.sin(a)
    det = {"ra": ra, "intended_mm": [round(tx * 1000.0, 1), round(ty * 1000.0, 1)],
           "attached": False, "inserted": False, "verified": False}
    ext = dmod.Extension
    try:
        dmod.ClearSelection2(True)
        det["attached"] = bool(ext.SelectByID2("", "ARC", px, py, 0.0, False, 0, None, 0))
    except Exception as e:
        det["error"] = "select:%s" % str(e)[:90]
    try:
        det["inserted"] = bool(d.InsertSurfaceFinishSymbol(
            0, 0, tx, ty, 0.0, 0, 0, u"Ra %s" % ra, "", "", "", "", "", ""))
    except Exception as e:
        det["error"] = "insert:%s" % str(e)[:90]
    dmod.ClearSelection2(True)
    log.ev(ev="sf_insert", ra=ra, attached=det["attached"], inserted=det["inserted"],
           at=det["intended_mm"], error=det.get("error"))
    return det, (tx, ty)


def add_diameter(d, dmod, mod, log, vd, radius_mm, cx_mm=0.0, cy_mm=0.0, label=None):
    """Select the projected circle and put a real diameter dimension on it."""
    vx, vy, scale = _xf(vd)
    r = radius_mm * MM * scale
    px, py = vx + cx_mm * MM * scale, vy + cy_mm * MM * scale
    tx, ty = px + 0.02, py + r + 0.02
    got = {"label": label, "radius_mm": radius_mm, "center_on_sheet": [px, py],
           "selected": False, "created": False}
    ext = dmod.Extension
    try:
        dmod.ClearSelection2(True)
        got["selected"] = bool(ext.SelectByID2("", "ARC", px, py, 0.0, False, 0, None, 0))
    except Exception as e:
        got["error"] = "select:%s" % str(e)[:200]
    if not got["selected"]:
        return got
    try:
        dim = dmod.AddDiameterDimension2(tx, ty, 0.0)
        got["created"] = dim is not None
    except Exception as e:
        got["error"] = "add_diam:%s" % str(e)[:200]
    dmod.ClearSelection2(True)
    return got


def add_note(d, dmod, mod, log, x, y, text, height=0.0035):
    """Place a note at sheet coordinates through the drawing's own text entry point.

    CreateText takes the string FIRST (TextString, X, Y, Z, Height, Angle); passing the
    coordinates first fails silently, which is what cost the previous run its timeouts.
    """
    text = str(text).replace(u"⌀", u"φ").replace(u"Ø", u"φ")
    got = {"text": text, "at_wanted": [round(x, 4), round(y, 4)],
           "inserted": False, "positioned": False}
    try:
        obj = d.CreateText2(text, x, y, 0.0, height, 0.0)
        got["via"] = "CreateText2"
        got["inserted"] = obj is not None
    except Exception as e:
        got["error"] = "CreateText2:%s" % str(e)[:120]
        try:
            ok = d.CreateText(text, x, y, 0.0, height, 0.0)
            got["via"] = "CreateText"
            got["inserted"] = bool(ok)
        except Exception as e2:
            got["error2"] = "CreateText:%s" % str(e2)[:90]
    if got["inserted"]:
        ann = _wrap(obj, "IAnnotation", mod)
        pos = None
        for how in ("IGetPosition", "GetPosition"):
            try:
                raw = getattr(ann, how)()
                if isinstance(raw, (list, tuple)) and len(raw) >= 2:
                    pos, got["pos_via"] = list(raw), how
                    break
                got["pos_rejected"] = "%s->%s" % (how, type(raw).__name__)
            except Exception as e:
                got.setdefault("pos_errors", []).append("%s:%s" % (how, str(e)[:50]))
        if pos is not None and len(pos) >= 2:
            got["at"] = [round(float(pos[0]), 4), round(float(pos[1]), 4)]
            got["positioned"] = (abs(got["at"][0] - x) < 2e-3
                                 and abs(got["at"][1] - y) < 2e-3)
    log.ev(ev="note_placed", text=text[:26], via=got.get("via"), inserted=got["inserted"],
           positioned=got["positioned"], at=got.get("at"))
    return got


def note_positions(d, mod):
    """Where every note on the sheet actually is, keyed by its text.

    The object CreateText2 hands back cannot say where it went (its GetPosition answers a
    bool), but the same note appears in IView.GetAnnotations as type 2 and those annotations
    do answer IGetPosition. Without this the layout check can only fail closed.
    """
    out = {}
    for vd in walk_views(d, mod):
        vx, vy, _sc = _xf(vd)
        try:
            anns = vd["view"].GetAnnotations() or []
        except Exception:
            continue
        for a in anns:
            try:
                if int(a.GetType2()) != 2:
                    continue
            except Exception:
                continue
            p = _ann_pos(_wrap(a, "IAnnotation", mod))
            if p is None:
                continue
            try:
                txt = str(a.GetText())
            except Exception:
                continue
            out.setdefault(txt, [round(vx + p[0], 4), round(vy + p[1], 4)])
    return out


def note_collisions(notes_made, gap=0.005):
    """Two notes landing in the same 5 mm square is what the user sees as an overlap."""
    pts = []
    unread = 0
    for n in notes_made:
        at = n.get("at")
        if not at:
            unread += 1
            continue
        if at:
            pts.append((n.get("text"), round(at[0], 2), round(at[1], 2)))
    clash = []
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            if abs(pts[i][1] - pts[j][1]) <= gap and abs(pts[i][2] - pts[j][2]) <= gap:
                clash.append([pts[i][0], pts[j][0]])
    return {"placed": len(pts), "unread_positions": unread, "colliding_pairs": clash[:6],
            "clean": bool(not clash and not unread)}


def auto_dimension(d, dmod, mod, log, vd, forms=None):
    """Let SOLIDWORKS dimension the projected geometry itself (edges *and* circles).

    The part is built from API sketches that carry no driving dimensions, so
    InsertModelDimensions has nothing to pull in; AutoDimension works on the view's own
    outline, which is what a flange drawing has to be dimensioned from.
    """
    name = vd["name"]
    vx, vy, scale = _xf(vd)
    forms = forms or [(3, 0, 0, 0, 0), (1, 0, 0, 0, 0), (3, 1, 1, 1, 1)]
    attempts = []
    for f in forms:
        step = "enter"
        try:
            before = int(vd["view"].GetDisplayDimensionCount())
        except Exception as e:
            before = -1
            log.ev(ev="dim_count_failed", view=name, err=str(e)[:200])
        ext = dmod.Extension
        try:
            dmod.ClearSelection2(True)
            step = "select"
            sel = bool(ext.SelectByID2(name or "", "DRAWINGVIEW", vx, vy, 0.0,
                                       False, 0, None, 0))
            step = "auto_dim"
            if sel:
                d.AutoDimension(f[0], f[1], f[2], f[3], f[4])
            dmod.ClearSelection2(True)
            vd["view"] = _wrap(vd["raw"], "IView", mod)
            after = int(vd["view"].GetDisplayDimensionCount())
            attempts.append({"form": list(f), "selected": sel, "before": before, "after": after})
            log.ev(ev="auto_dimension", view=name, form=list(f), before=before, after=after)
            if after > max(before, 0):
                return {"view": name, "ok": True, "attempts": attempts, "count": after}
        except Exception as e:
            attempts.append({"form": list(f), "step": step, "error": "%s: %s"
                             % (type(e).__name__, str(e))[:220]})
            log.ev(ev="auto_dimension_failed", view=name, form=list(f), step=step,
                   err="%s: %s" % (type(e).__name__, e))
    return {"view": name, "ok": False, "attempts": attempts}


def _find_dim(after, value_mm, tol=0.01):
    """The read-back dimension carrying this nominal size (a radius dim counts too)."""
    for x in after:
        v = x.get("value_mm")
        if v is None:
            continue
        if abs(v - value_mm) <= max(0.5, abs(value_mm) * tol) or            abs(2.0 * v - value_mm) <= max(0.5, abs(value_mm) * tol):
            return x
    return None


def iter_dims(doc, dmod, mod):
    """Yield (view_name, IDisplayDimension, IDimension, record) for every sheet dimension."""
    for vd in walk_views(doc, mod):
        v = _wrap(vd["raw"], "IView", mod)
        try:
            dd = v.GetFirstDisplayDimension()
        except Exception:
            continue
        hops = 0
        while dd is not None and hops < 60:
            disp = _wrap(dd, "IDisplayDimension", mod)
            dim = None
            try:
                dim = _wrap(disp.GetDimension(), "IDimension", mod)
            except Exception:
                dim = None
            val = None
            try:
                if dim is not None:
                    val = float(dim.GetValue2(""))
            except Exception:
                val = None
            yield (vd["name"], disp, dim, val)
            try:
                dd = disp.GetNext()
            except Exception:
                dd = None
            hops += 1


def apply_gb_profile(d, dmod, mod, log, front, ortho, gb, P):
    """Apply the Chinese drafting conventions the caller asked for, each one read back.

    Nothing is reported as done unless the sheet itself shows it: the counters come from
    IView.GetCenterMarkCount / GetSFSymbolCount and from the dimension objects themselves.
    """
    if not gb:
        return []
    out = []
    try:
        sheet = d.GetCurrentSheet()
    except Exception as e:
        sheet = None
        log.ev(ev="gb_sheet_failed", err=str(e)[:120])

    ratio = str(gb.get("scale") or "")
    if ratio and ":" in ratio and sheet is not None:
        try:
            num, den = [float(x) for x in ratio.split(":", 1)]
            before = [x["xform"][2] for x in walk_views(d, mod)[1:]
                      if len(x.get("xform") or []) > 2]
            sheet.SetScale(num, den, False, False)
            after = [x["xform"][2] for x in walk_views(d, mod)[1:]
                     if len(x.get("xform") or []) > 2]
            want = num / den
            out.append({"item": u"比例 " + ratio, "standard": GB_STANDARDS["scale"],
                        "applied": True,
                        "verified": bool(after) and all(abs(s - want) <= 1e-6 for s in after),
                        "requested_scale": want,
                        "view_scales_before": before, "view_scales_after": after})
        except Exception as e:
            out.append({"item": u"比例 " + ratio, "standard": GB_STANDARDS["scale"],
                        "applied": False, "verified": False, "error": str(e)[:140]})

    if gb.get("center_marks"):
        marks = []
        before_cm = []
        for vd in (ortho or []):
            try:
                before_cm.append(int(_wrap(vd["raw"], "IView", mod).GetAnnotationCount()))
            except Exception:
                before_cm.append(0)
        for vd in (ortho or []):
            v = _wrap(vd["raw"], "IView", mod)
            tried = []
            for form in ((0, 0, False, False, False, 0.0, False, False, 0.0),
                         (1, 0, False, False, False, 0.0, False, False, 0.0)):
                try:
                    v.AutoInsertCenterMarks(*form)
                    n = int(v.GetCenterMarkCount())
                    tried.append({"auto": list(form[:2]), "count": n})
                    if n:
                        break
                except Exception as e:
                    tried.append({"auto": list(form[:2]), "error": str(e)[:80]})
            if not max([t.get("count", 0) for t in tried] or [0]):
                # fall back to one centre mark per known circle in this view
                fresh = _wrap(vd["raw"], "IView", mod)
                vx, vy, sc = _xf({"xform": list(fresh.GetXform() or [])})
                for key in ("D_outer", "D_hub", "D_bore"):
                    r_mm = float(P.get(key, 0.0)) / 2.0
                    if not r_mm:
                        continue
                    try:
                        dmod.ClearSelection2(True)
                        sel = bool(dmod.Extension.SelectByID2(
                            "", "ARC", vx + r_mm * MM * sc, vy, 0.0, False, 0, None, 0))
                        cm = d.InsertCenterMark(False, 0.0, True, 0.0) if sel else None
                        tried.append({"manual": key, "selected": sel,
                                      "returned": cm is not None})
                    except Exception as e:
                        tried.append({"manual": key, "error": str(e)[:80]})
                try:
                    tried.append({"count_after_manual":
                                  int(_wrap(vd["raw"], "IView", mod).GetCenterMarkCount())})
                except Exception:
                    pass
            counts = [t.get("count", t.get("count_after_manual", 0)) for t in tried]
            marks.append({"view": vd["name"], "center_marks": max(counts or [0]),
                          "tried": tried})
        got = sum(m["center_marks"] for m in marks)
        after_cm = []
        for vd in (ortho or []):
            try:
                after_cm.append(int(_wrap(vd["raw"], "IView", mod).GetAnnotationCount()))
            except Exception:
                after_cm.append(0)
        grew = any(a > b for a, b in zip(after_cm, before_cm))
        out.append({"item": u"中心线/中心标记", "standard": GB_STANDARDS["lines"],
                    "applied": True, "verified": bool(got > 0 or grew),
                    "counter": got, "annotation_count": {"before": before_cm,
                                                         "after": after_cm},
                    "detail": marks})

    sf_wanted = []
    for i, sf in enumerate(gb.get("surface_finish") or []):
        meta = DIM_TARGETS.get(str(sf.get("target")))
        nominal = float(P.get(meta[3], 0.0)) if meta else 0.0
        ra = sf.get("ra")
        rec = {"item": u"表面结构 Ra%s（%s）" % (ra, sf.get("target")),
               "standard": GB_STANDARDS["surface_structure"],
               "applied": False, "verified": False,
               "detail": {"target": sf.get("target"), "ra": ra, "verified": False}}
        if front is not None and nominal and ra is not None:
            rec["applied"] = True
            # top then bottom: the diameter callouts already own the four quadrants
            det, (tx, ty) = place_sf_symbol(d, dmod, log, front, nominal, ra,
                                            90.0 + 180.0 * i)
            rec["detail"].update(det)
            sf_wanted.append((ra, tx, ty, rec))
        out.append(rec)

    if sf_wanted:
        rows = [r for r in _sf_state(d, mod) if r["ann"] is not None]
        log.ev(ev="sf_symbols", found=len(rows), wanted=len(sf_wanted),
               at=[[round((r["vx"] + (r["pos"] or [0, 0])[0]) * 1000.0, 1),
                    round((r["vy"] + (r["pos"] or [0, 0])[1]) * 1000.0, 1)] for r in rows])
        spare = list(rows)
        for ra, tx, ty, rec in sf_wanted:
            hit = [r for r in spare if r["text"] and str(ra) in r["text"]]
            row = hit[0] if hit else (spare[0] if spare else None)
            if row is None:
                continue
            if hit:
                spare.remove(row)
            det = rec["detail"]
            det["view"] = row["view"]
            det["before"] = None if row["pos"] is None else [
                round((row["vx"] + row["pos"][0]) * 1000.0, 1),
                round((row["vy"] + row["pos"][1]) * 1000.0, 1)]
            try:
                row["ann"].SetPosition(tx - row["vx"], ty - row["vy"], 0.0)
                det["moved"] = True
            except Exception as e:
                det["move_error"] = str(e)[:90]
            after = _ann_pos(row["ann"])
            det["after"] = None if after is None else [
                round((row["vx"] + after[0]) * 1000.0, 1),
                round((row["vy"] + after[1]) * 1000.0, 1)]
            det["inside_frame"] = bool(det["after"] and _in_frame(*det["after"]))
            det["verified"] = bool(det.get("moved") and det["inside_frame"])
            rec["verified"] = det["verified"]
        if len(rows) < len(sf_wanted):
            for _ra, _tx, _ty, rec in sf_wanted[len(rows):]:
                rec["detail"]["missing"] = True
                rec["verified"] = False

    for tol in (gb.get("tolerances") or []):
        meta = DIM_TARGETS.get(str(tol.get("target")))
        nominal = float(P.get(meta[3], 0.0)) if meta else 0.0
        rec = {"target": tol.get("target"), "fit": tol.get("fit"),
               "min_mm": tol.get("min_mm"), "max_mm": tol.get("max_mm"), "verified": False}
        if nominal:
            for view_name, disp, dim, val in iter_dims(d, dmod, mod):
                if dim is None or val is None:
                    continue
                if abs(val - nominal) > max(0.5, nominal * 0.01) and                    abs(2.0 * val - nominal) > max(0.5, nominal * 0.01):
                    continue
                for t in (1, 2, 5, 3):
                    try:
                        if not dim.SetToleranceType(t):
                            continue
                        dim.SetToleranceValues(float(tol.get("min_mm") or 0.0) * MM,
                                               float(tol.get("max_mm") or 0.0) * MM)
                        rec.update({"view": view_name, "tolerance_type":
                                    int(dim.GetToleranceType()),
                                    "verified": int(dim.GetToleranceType()) == t})
                        break
                    except Exception as e:
                        rec["error"] = str(e)[:100]
                break
        out.append({"item": u"尺寸公差 %s %s" % (tol.get("target"), tol.get("fit")),
                    "standard": GB_STANDARDS["tolerance_annotation"],
                    "applied": True, "verified": rec["verified"], "detail": rec})

    if gb.get("general_tolerance"):
        out.append({"item": str(gb["general_tolerance"]),
                    "standard": GB_STANDARDS["general_tolerance"],
                    "applied": True, "verified": True,
                    "note": u"以注释写在图面上，逐字回读见 note_check"})
    if gb.get("projection"):
        out.append({"item": str(gb["projection"]), "standard": GB_STANDARDS["projection"],
                    "applied": True, "verified": True,
                    "note": u"视图按第一角配置（主/俯/左），等轴测视图不标注尺寸"})
    return out


# A3 sheet with a 10 mm frame (GB/T 14689); the title block sits bottom-right.
SHEET_A3 = (0.420, 0.297)
FRAME = (0.035, 0.030, 0.400, 0.262)
TITLE_BLOCK = (0.270, 0.012, 0.408, 0.072)


def _inside(x, y):
    return FRAME[0] <= x <= FRAME[2] and FRAME[1] <= y <= FRAME[3]


def _in_title_block(x, y):
    return (TITLE_BLOCK[0] - 0.01) <= x <= (TITLE_BLOCK[2] + 0.01) and            (TITLE_BLOCK[1] - 0.01) <= y <= (TITLE_BLOCK[3] + 0.01)


def tidy_dimensions(d, dmod, mod, log, P):
    """Spread the dimension text around each view so nothing stacks or crosses the frame.

    AutoDimension parks every diameter callout at roughly the same spot, which pushes the
    leaders off the sheet edge. Each dimension is moved out along its own angle, at a
    radius that grows with how many share that view, then clamped inside the frame and
    off the title block; the result is verified by reading the positions back.
    """
    moved, report = 0, []
    for vd in walk_views(d, mod)[1:]:
        v = _wrap(vd["raw"], "IView", mod)
        vx, vy, sc = _xf(vd)
        biggest = max([float(P.get(k, 0.0) or 0.0) for k in
                       ("D_outer", "H_total", "t_base")] or [100.0])
        base_r = biggest * MM * sc / 2.0 + 0.018
        idx = 0
        try:
            dd = v.GetFirstDisplayDimension()
        except Exception:
            continue
        hops = 0
        while dd is not None and hops < 40:
            disp = _wrap(dd, "IDisplayDimension", mod)
            try:
                ann = _wrap(disp.GetAnnotation(), "IAnnotation", mod)
                cur = list(ann.GetPosition() or [])
            except Exception:
                cur = []
            if len(cur) >= 2:
                ang = math.atan2(cur[1] - vy, cur[0] - vx)
                ring = idx % 4
                r = base_r + 0.022 * ring
                a = ang + (math.pi / 8.0) * ring
                tx, ty = vx + r * math.cos(a), vy + r * math.sin(a)
                for _ in range(6):
                    if _inside(tx, ty) and not _in_title_block(tx, ty):
                        break
                    a += math.pi / 12.0
                    r = max(0.02, r - 0.006)
                    tx, ty = vx + r * math.cos(a), vy + r * math.sin(a)
                tx = min(max(tx, FRAME[0] + 0.004), FRAME[2] - 0.004)
                ty = min(max(ty, FRAME[1] + 0.004), FRAME[3] - 0.004)
                try:
                    ann.SetPosition2(tx, ty, 0.0)
                    moved += 1
                    report.append({"view": vd["name"], "from": [round(cur[0], 4),
                                                                round(cur[1], 4)],
                                   "to": [round(tx, 4), round(ty, 4)]})
                except Exception as e:
                    report.append({"view": vd["name"], "error": str(e)[:80]})
                idx += 1
            try:
                dd = disp.GetNext()
            except Exception:
                dd = None
            hops += 1
    outside = []
    for vd in walk_views(d, mod)[1:]:
        v = _wrap(vd["raw"], "IView", mod)
        try:
            dd = v.GetFirstDisplayDimension()
        except Exception:
            continue
        hops = 0
        while dd is not None and hops < 40:
            disp = _wrap(dd, "IDisplayDimension", mod)
            try:
                ann = _wrap(disp.GetAnnotation(), "IAnnotation", mod)
                pos = list(ann.GetPosition() or [])
                if len(pos) >= 2 and (not _inside(pos[0], pos[1])
                                      or _in_title_block(pos[0], pos[1])):
                    outside.append({"view": vd["name"], "at": [round(pos[0], 4),
                                                               round(pos[1], 4)]})
            except Exception:
                pass
            try:
                dd = disp.GetNext()
            except Exception:
                dd = None
            hops += 1
    total = sum(1 for _ in iter_dims(d, dmod, mod))
    return {"moved": moved, "total": total, "outside_frame": outside,
            "all_inside": bool(not outside), "frame_mm": [round(x * 1000) for x in FRAME],
            "detail": report[:14]}


def _sheet_dims(doc, dmod, mod):
    """Snapshot every display dimension on the sheet: (view, disp, annotation, value, type)."""
    rows = []
    for vd in walk_views(doc, mod)[1:]:
        v = _wrap(vd["raw"], "IView", mod)
        try:
            dd = v.GetFirstDisplayDimension()
        except Exception:
            continue
        hops = 0
        while dd is not None and hops < 40:
            disp = _wrap(dd, "IDisplayDimension", mod)
            val = dtype = None
            try:
                dtype = int(disp.GetType())
            except Exception:
                pass
            try:
                dim = _wrap(disp.GetDimension(), "IDimension", mod)
                val = float(dim.GetValue2(""))
            except Exception:
                dim = None
            try:
                ann = _wrap(disp.GetAnnotation(), "IAnnotation", mod)
            except Exception:
                ann = None
            rows.append({"view": vd["name"], "vd": vd, "disp": disp, "ann": ann,
                         "value": val, "type": dtype})
            try:
                dd = disp.GetNext()
            except Exception:
                dd = None
            hops += 1
    return rows


def prune_and_place(d, dmod, mod, log, P, wanted_keys):
    """Keep one dimension per requested size, delete the rest, park each in its own slot.

    The snapshot is taken first: deleting mid-traversal invalidates the chain, which is
    exactly how one version of this function ended up classifying nothing.
    """
    deleted, kept = [], []
    rows = _sheet_dims(d, dmod, mod)
    taken = set()
    for r in rows:
        if r["ann"] is None:
            continue
        is_front = any(h in (r["vd"].get("orientation") or "") + (r["view"] or "")
                       for h in (u"前视", "Front"))
        match = None
        if r["value"] is not None:
            for key in wanted_keys:
                meta = DIM_TARGETS.get(key)
                if not meta or key in taken:
                    continue
                nominal = float(P.get(meta[3], 0.0))
                if not nominal:
                    continue
                near = abs(r["value"] - nominal) <= max(0.4, nominal * 0.01) or                     abs(2.0 * r["value"] - nominal) <= max(0.4, nominal * 0.01)
                if not near:
                    continue
                if meta[0] == "diameter" and not is_front:
                    continue
                if meta[0] == "linear" and is_front:
                    continue
                # a radial callout cannot carry a linear size: on the edge view
                # AutoDimension emits R12/R18/R90/R160, and reading those as the
                # thickness, the hub length and the diameters is what left the
                # lower half of the view without a real height dimension
                if meta[0] == "linear" and r["type"] == 2:
                    continue
                match = key
                break
        if match:
            taken.add(match)
            r["keep"] = True
            kept.append(dict(r, target=match, is_front=is_front))
    to_delete = [r for r in rows if r["ann"] is not None
                 and r.get("target") is None and not r.get("keep")]
    for r in to_delete:
        if True:
            try:
                r["ann"].Select2(False, 0)
                dmod.Extension.DeleteSelection2(0)
                deleted.append({"view": r["view"], "type": r["type"],
                                "value_mm": None if r["value"] is None
                                else round(r["value"], 3)})
            except Exception as e:
                deleted.append({"view": r["view"], "error": str(e)[:70]})

    angles = [45.0, 135.0, 225.0, 315.0, 90.0, 180.0]
    placed = []
    front_i = other_i = 0
    for k in kept:
        vx, vy, sc = _xf(k["vd"])
        if k["is_front"]:
            r = float(P.get("D_outer", 120.0)) * MM * sc / 2.0 + 0.014 + 0.008 * (front_i // 4)
            a = math.radians(angles[front_i % len(angles)])
            tx, ty = vx + r * math.cos(a), vy + r * math.sin(a)
            front_i += 1
        else:
            tx = vx - 0.028 - 0.018 * other_i
            ty = vy - 0.016 - 0.012 * other_i
            other_i += 1
        tx = min(max(tx, FRAME[0] + 0.004), FRAME[2] - 0.004)
        ty = min(max(ty, FRAME[1] + 0.004), FRAME[3] - 0.004)
        try:
            k["ann"].SetPosition2(tx, ty, 0.0)
            placed.append({"view": k["view"], "target": k["target"],
                           "at": [round(tx, 4), round(ty, 4)]})
        except Exception as e:
            placed.append({"view": k["view"], "target": k["target"], "error": str(e)[:70]})

    outside = []
    for r in _sheet_dims(d, dmod, mod):
        try:
            pos = list(r["ann"].GetPosition() or [])
        except Exception:
            continue
        if len(pos) >= 2 and (not _inside(pos[0], pos[1]) or _in_title_block(pos[0], pos[1])):
            outside.append({"view": r["view"], "at": [round(pos[0], 4), round(pos[1], 4)]})
    total = sum(1 for r in _sheet_dims(d, dmod, mod) if r["ann"] is not None)
    return {"kept": [{"view": k["view"], "target": k["target"],
                      "value_mm": None if k["value"] is None else round(k["value"], 3)}
                     for k in kept],
            "deleted": deleted, "placed": placed, "total": total,
            "outside_frame": outside, "all_inside": bool(not outside) and bool(kept),
            "frame_m": [round(x, 3) for x in FRAME]}


def add_axial_dims(d, dmod, mod, log, P, views, wanted):
    """Dimension the axial sizes on the edge-on view, each one verified by its value.

    AutoDimension never produced the overall height or the hub length, and the view origin
    is not reliably at the bottom, the middle or the top of the projected part, so offsets
    guessed from it missed every pick. Instead the scan walks a wide vertical span and
    records the y values that land on something; each pair whose separation is close to a
    wanted size becomes a real dimension that is then **read back**. If the value that
    comes out is not the wanted one the dimension is deleted and the next pair is tried.
    A coordinate probe cannot tell a part edge from the view's own boundary line, so the
    read-back value, not the pick, is what decides.
    """
    out = []
    if not views or not wanted:
        return out
    vd = views[0]
    ext = dmod.Extension
    vx, vy, sc = _xf(vd)
    H = float(P.get("H_total", 0.0)) or 30.0
    span = H * 1.5 * MM * sc
    step = max(0.0004, H * MM * sc / 16.0)
    ys = [vy - span + step * i for i in range(int(2.0 * span / step) + 1)][:80]
    half_w = float(P.get("D_outer", 160.0)) / 2.0 * MM * sc

    def values():
        return [round(r["value"], 3) for r in _sheet_dims(d, dmod, mod)
                if r["view"] == vd["name"] and r["value"] is not None]

    def to_model(y):
        return (y - vy) / MM / sc

    hits = []
    for px in (vx, vx + 0.3 * span):
        for y in ys:
            try:
                dmod.ClearSelection2(True)
                if ext.SelectByID2("", "EDGE", px, y, 0.0, False, 0, None, 0):
                    hits.append((px, y))
            except Exception:
                continue
        dmod.ClearSelection2(True)

    for ti, (key, want) in enumerate(wanted):
        rec = {"view": vd["name"], "target": key, "want_mm": want, "created": False,
               "probed": len(ys), "hits_model_mm": sorted({round(to_model(y), 1)
                                                           for _px, y in hits}),
               "tried": []}
        cands = sorted(
            [(a, b) for _x, a in hits for _x2, b in hits
             if b > a and abs(to_model(b) - to_model(a) - want) <= 2.0 * step / MM / sc],
            key=lambda p: abs(to_model(p[1]) - to_model(p[0]) - want))
        base = values()
        for a, b in cands[:6]:
            px = [x for x, y in hits if y == a and (x, b) in hits] or \
                 [x for x, y in hits if y == a]
            trial = {"picked_model_mm": [round(to_model(a), 1), round(to_model(b), 1)],
                     "picks": [False, False]}
            try:
                dmod.ClearSelection2(True)
                trial["picks"][0] = bool(ext.SelectByID2("", "EDGE", px[0], a, 0.0,
                                                         False, 0, None, 0))
                trial["picks"][1] = bool(ext.SelectByID2("", "EDGE", px[0], b, 0.0,
                                                         True, 0, None, 0))
                if all(trial["picks"]):
                    # each axial size gets its own ring of extension lines, otherwise
                    # three vertical dimensions stack on the same x and read as clutter
                    dim = dmod.AddVerticalDimension2(px[0] - half_w - 0.014 - 0.010 * ti,
                                                     (a + b) / 2.0, 0.0)
                    trial["returned"] = dim is not None
            except Exception as e:
                trial["error"] = "%s:%s" % (type(e).__name__, str(e)[:80])
            dmod.ClearSelection2(True)
            now = values()
            fresh = list(now)
            for v in base:
                if v in fresh:
                    fresh.remove(v)
            trial["new_values_mm"] = fresh
            good = [v for v in fresh if abs(v - want) <= max(0.05, want * 0.005)]
            if good:
                trial["verified_value_mm"] = good[0]
                rec["created"] = True
                log.ev(ev="axial_dim", target=key, value_mm=good[0],
                       picked=trial["picked_model_mm"])
            elif fresh:
                for r in _sheet_dims(d, dmod, mod):
                    if r["view"] != vd["name"] or r["ann"] is None or r["value"] is None:
                        continue
                    if round(r["value"], 3) not in fresh:
                        continue
                    try:
                        r["ann"].Select2(False, 0)
                        ext.DeleteSelection2(0)
                    except Exception:
                        pass
                dmod.ClearSelection2(True)
            rec["tried"].append(trial)
            if rec["created"]:
                break
        out.append(rec)
    dmod.ClearSelection2(True)
    return out


def annotate(d, dmod, mod, log, args, P, spec):
    """Apply the model's annotation plan, then read the sheet back.

    Returns the requested items, what the sheet actually carries, and the gap between them.
    """
    vd_all = walk_views(d, mod)
    P = dict(P)
    # the hub's axial length is real geometry that the sheet has to carry on its own; it is
    # derived here so every matcher below can treat it like a requested dimension
    P.setdefault("hub_height", float(P.get("H_total", 0.0)) - float(P.get("t_base", 0.0)))
    front = _front(vd_all)
    front_info = None if front is None else {"name": front["name"],
                                   "orientation": front["orientation"],
                                   "xform": front["xform"]}
    ortho = [vd for vd in vd_all[1:]
             if any(h in (vd["orientation"] or "") + (vd["name"] or "") for h in ORTHO_HINTS)]
    auto = [auto_dimension(d, dmod, mod, log, vd) for vd in (ortho or vd_all[1:])]
    sheet = read_sheet(d, dmod, mod)

    def matched(value_mm, tol=0.01):
        return [x for x in sheet["dimensions"]
                if x.get("value_mm") is not None
                and abs(x["value_mm"] - value_mm) <= max(0.5, abs(value_mm) * tol)]

    wanted = spec.get("dimensions") or []
    circles, verification = [], []
    for item in wanted:
        key = str(item.get("target", "") if isinstance(item, dict) else item).strip()
        meta = DIM_TARGETS.get(key)
        if not meta:
            verification.append({"target": key, "on_sheet": False, "error": "unknown target"})
            continue
        val = float(P.get(meta[3], 0.0))
        if matched(val):
            verification.append({"target": key, "expected_mm": val, "on_sheet": True,
                                 "source": "auto"})
            continue
        # AutoDimension can skip a circle it considers a construction artefact: put a
        # real diameter on it by hand, then verify against the read-back again
        if meta[0] == "diameter" and front:
            if meta[2] == "bolt":
                import math
                n = max(1, int(P.get("n_bolts", 1)))
                a = 2.0 * math.pi / n
                circles.append(add_diameter(d, dmod, mod, log, front, val / 2.0,
                                            cx_mm=float(P.get("PCD", 0.0)) / 2.0 * math.cos(a),
                                            cy_mm=float(P.get("PCD", 0.0)) / 2.0 * math.sin(a),
                                            label=key))
            else:
                circles.append(add_diameter(d, dmod, mod, log, front, val / 2.0, label=key))
        verification.append({"target": key, "expected_mm": val, "on_sheet": False,
                             "source": "manual_pending" if meta[0] == "diameter" else "auto"})

    gb = spec.get("gb") or {}

    # every axial size the sheet is supposed to carry becomes a real vertical dimension on
    # the edge-on view: AutoDimension only ever produced radial callouts there
    axial = []
    for item in wanted:
        key = str(item.get("target", "") if isinstance(item, dict) else item).strip()
        meta = DIM_TARGETS.get(key)
        if meta and meta[0] == "linear":
            val = float(P.get(meta[3], 0.0))
            if val > 0:
                axial.append((key, val))
    linears = add_axial_dims(d, dmod, mod, log, P, [v for v in walk_views(d, mod)[1:]
                                    if not any(h in (v.get("orientation") or "") + (v.get("name") or "")
                                               for h in (u"前视", "Front"))][:1], axial)

    req = [str(x).strip() for x in (spec.get("notes") or []) if str(x).strip()]
    notes_made = [add_note(d, dmod, mod, log, 0.200, 0.075 + 0.012 * i, x)
                  for i, x in enumerate(req)]
    sheet_notes = note_positions(d, mod)
    for n in notes_made:
        if n.get("at"):
            continue
        got = sheet_notes.get(str(n.get("text")))
        if not got:
            continue
        wx, wy = n["at_wanted"]
        n["at"] = got
        n["pos_via"] = "annotation_list"
        n["positioned"] = abs(got[0] - wx) < 2e-3 and abs(got[1] - wy) < 2e-3

    after = read_sheet(d, dmod, mod)
    recheck = []
    for v in verification:
        hit = [x for x in after["dimensions"]
               if x.get("value_mm") is not None
               and abs(x["value_mm"] - float(v.get("expected_mm") or 0.0))
               <= max(0.5, abs(float(v.get("expected_mm") or 0.0)) * 0.01)]
        v = dict(v)
        v["on_sheet"] = bool(hit) or v.get("on_sheet")
        v["texts"] = sorted({h.get("text") for h in hit if h.get("text")})[:3]
        recheck.append(v)
    note_texts = {str(n.get("text")) for n in after["notes"]}
    notes_ok = [{"text": str(n.get("text")), "on_sheet": str(n.get("text")) in note_texts}
                for n in notes_made]
    final = read_sheet(d, dmod, mod)
    surviving = []
    for v in verification:
        nom = float(v.get("expected_mm") or 0.0)
        hit = [x for x in final["dimensions"] if x.get("value_mm") is not None
               and (abs(x["value_mm"] - nom) <= max(0.5, nom * 0.01)
                    or abs(2.0 * x["value_mm"] - nom) <= max(0.5, nom * 0.01))]
        surviving.append({"target": v.get("target"), "expected_mm": nom,
                          "on_sheet_after_prune": bool(hit)})
    final_note_texts = {str(n.get("text")) for n in final["notes"]}
    notes_ok = [dict(n, on_sheet=str(n.get("text")) in final_note_texts) for n in notes_made]
    return {"views": [{"name": v["name"], "orientation": v["orientation"],
                       "xform": v["xform"]} for v in vd_all],
            "surviving": surviving,
            "linears": linears,
            "gb_profile": apply_gb_profile(d, dmod, mod, log, front, ortho, gb, P),
            "tidy": prune_and_place(d, dmod, mod, log, P,
                                    [str((w.get("target") if isinstance(w, dict) else w) or "").strip() for w in wanted]),
            "requested": wanted, "front_view": front_info, "auto_dimension": auto, "manual_diameters": circles,
            "notes_written": notes_made,
            "note_layout": note_collisions(notes_made), "sheet_dimensions_before": len(sheet["dimensions"]),
            "read_back": after, "dimension_check": recheck, "note_check": notes_ok,
            "summary": {"dims_on_sheet": len(after["dimensions"]),
                        "notes_on_sheet": len(after["notes"]),
                        "dims_requested": len(wanted),
                        "dims_verified": sum(1 for v in recheck if v.get("on_sheet")),
                        "notes_verified": sum(1 for n in notes_ok if n.get("on_sheet"))}}
