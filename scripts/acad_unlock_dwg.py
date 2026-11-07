#!/usr/bin/env python
"""Remove DWG write-protection ("只读") and dump drawing content.

Route: AutoCAD can't clear an internal write-protection flag via SaveAs (the
flag is copied into the new file), so route the drawing through DXF, which has
no such record, then save that back to DWG.  Also dumps every entity / text /
layer via AutoLISP so the drawing content is available for analysis.

Steps (each persisted to the report as it happens):
  1. open private copy                       -> state_before
  2. WBLOCK to a new .dwg                    -> check ReadOnly
  3. SaveAs DXF (R2013)                      -> intermediate.dxf
  4. open DXF, SaveAs DWG (R2018)            -> candidate clean .dwg
  5. reopen candidate                        -> ReadOnly must be False
  6. write probe (add entity via LISP, save, reopen, recount)
  7. AutoLISP dump of entities/texts/layers  -> dump.tsv
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time

import pythoncom
import win32com.client as win32

PROGIDS = ["AutoCAD.Application.25.1", "AutoCAD.Application.25", "AutoCAD.Application"]
RETRY_HRESULTS = (-2147418111, -2147417846, -2147417851, -2147417843)

REPORT: dict = {}


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


def safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


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


def doc_state(doc):
    return {
        "name": safe(lambda: str(doc.Name)),
        "full_name": safe(lambda: str(doc.FullName)),
        "readonly": safe(lambda: bool(doc.ReadOnly)),
        "readonly_recommended": safe(lambda: bool(doc.ReadOnlyRecommended)),
        "saved": safe(lambda: bool(doc.Saved)),
        "model_entity_count": safe(lambda: doc.ModelSpace.Count),
        "layouts": safe(lambda: [str(l.Name) for l in iter_collection(doc.Layouts)]),
    }


def flush(path):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(REPORT, fh, ensure_ascii=False, indent=1)


def log(msg, path):
    print(msg, flush=True)
    REPORT.setdefault("log", []).append(msg)
    flush(path)


LISP_TEMPLATE = r'''
(defun _dz_str (v) (if v (vl-princ-to-string v) ""))
(defun _dz_clean (s) (setq s (vl-string-subst "\t" " " s)) (setq s (vl-string-subst "\n" " " s)) (setq s (vl-string-subst "\r" " " s)) s)
(defun _dz_pair (e code) (cdr (assoc code e)))
(defun _dz_dump1 (f scope name e / d t ly h extra)
  (setq d (entget e) t (_dz_pair d 0) ly (_dz_pair d 8) h (_dz_pair d 5) extra "")
  (cond
    ((= t "TEXT") (setq extra (strcat "text=" (_dz_clean (_dz_pair d 1)) " |pos=" (_dz_clean (_dz_pair d 10)) " |h=" (_dz_clean (_dz_pair d 40)))))
    ((= t "MTEXT") (setq extra (strcat "text=" (_dz_clean (_dz_pair d 1)) (_dz_clean (_dz_pair d 3)) " |pos=" (_dz_clean (_dz_pair d 10)) " |w=" (_dz_clean (_dz_pair d 41)))))
    ((= t "ATTRIB") (setq extra (strcat "tag=" (_dz_clean (_dz_pair d 2)) " |text=" (_dz_clean (_dz_pair d 1)) " |pos=" (_dz_clean (_dz_pair d 10)))))
    ((= t "ATTDEF") (setq extra (strcat "tag=" (_dz_clean (_dz_pair d 2)) " |text=" (_dz_clean (_dz_pair d 1)) " |pos=" (_dz_clean (_dz_pair d 10)))))
    ((= t "DIMENSION") (setq extra (strcat "text=" (_dz_clean (_dz_pair d 1)) " |measure=" (_dz_clean (_dz_pair d 42)) " |def=" (_dz_clean (_dz_pair d 3)) " |style=" (_dz_clean (_dz_pair d 7)) " |p1=" (_dz_clean (_dz_pair d 10)) " |p2=" (_dz_clean (_dz_pair d 11)) " |p3=" (_dz_clean (_dz_pair d 13)))))
    ((= t "INSERT") (setq extra (strcat "block=" (_dz_clean (_dz_pair d 2)) " |pos=" (_dz_clean (_dz_pair d 10)) " |scale=" (_dz_clean (_dz_pair d 41)) " |rot=" (_dz_clean (_dz_pair d 50)))))
    ((= t "LINE") (setq extra (strcat "start=" (_dz_clean (_dz_pair d 10)) " |end=" (_dz_clean (_dz_pair d 11)))))
    ((= t "CIRCLE") (setq extra (strcat "center=" (_dz_clean (_dz_pair d 10)) " |r=" (_dz_clean (_dz_pair d 40)))))
    ((= t "ARC") (setq extra (strcat "center=" (_dz_clean (_dz_pair d 10)) " |r=" (_dz_clean (_dz_pair d 40)) " |a1=" (_dz_clean (_dz_pair d 50)) " |a2=" (_dz_clean (_dz_pair d 51)))))
    ((= t "LWPOLYLINE") (setq extra (strcat "pts=" (_dz_clean (_dz_pair d 10)) " |closed=" (_dz_clean (_dz_pair d 70)))))
    ((= t "POLYLINE") (setq extra (strcat "closed=" (_dz_clean (_dz_pair d 70)))))
    ((= t "ELLIPSE") (setq extra (strcat "center=" (_dz_clean (_dz_pair d 10)) " |major=" (_dz_clean (_dz_pair d 11)) " |ratio=" (_dz_clean (_dz_pair d 40)))))
    (T (setq extra "")))
  (write-line (strcat scope "\t" name "\t" t "\t" ly "\t" h "\t" extra) f))
(defun c:DUMPALL (/ f ss i e laylst bname blk outpath)
  (setq outpath "__OUTPATH__")
  (setq f (open outpath "w"))
  (if (null f) (princ "\n[DUMPALL] cannot open output") (progn
    (setq laylst (cons "Model" (layoutlist)))
    (foreach lay laylst
      (setq ss (ssget "_X" (list (cons 410 lay))))
      (if ss (progn
        (write-line (strcat "META\t" lay "\tLAYOUT\t" (itoa (sslength ss)) "\t\t") f)
        (setq i 0) (repeat (sslength ss) (setq e (ssname ss i)) (_dz_dump1 f "LAYOUT" lay e) (setq i (1+ i))))))
    (setq blk (tblnext "BLOCK" T))
    (while blk
      (setq bname (_dz_pair blk 2))
      (setq ss (ssget "_X" (list (cons 2 bname))))
      (if ss (progn
        (write-line (strcat "META\t" bname "\tBLOCK\t" (itoa (sslength ss)) "\t\t") f)
        (setq i 0) (repeat (sslength ss) (setq e (ssname ss i)) (_dz_dump1 f "BLOCK" bname e) (setq i (1+ i)))))
      (setq blk (tblnext "BLOCK")))
    (setq laylst (tblnext "LAYER" T))
    (while laylst
      (write-line (strcat "LAYER\t" (_dz_pair laylst 2) "\tLAYER\tcolor=" (_dz_clean (_dz_pair laylst 62)) " ltype=" (_dz_clean (_dz_pair laylst 6)) " flags=" (_dz_clean (_dz_pair laylst 70)) "\t\t") f)
      (setq laylst (tblnext "LAYER")))
    (setq laylst (tblnext "DIMSTYLE" T))
    (while laylst (write-line (strcat "DIMSTYLE\t" (_dz_pair laylst 2) "\tDIMSTYLE\t\t\t") f) (setq laylst (tblnext "DIMSTYLE")))
    (setq laylst (tblnext "STYLE" T))
    (while laylst (write-line (strcat "STYLE\t" (_dz_pair laylst 2) "\tSTYLE\th=" (_dz_clean (_dz_pair laylst 40)) "\t\t") f) (setq laylst (tblnext "STYLE")))
    (close f)
    (princ "\n[DUMPALL] done")))
  (princ))
'''


def write_lisp(out_path: str) -> str:
    tmp_dir = tempfile.mkdtemp(prefix="acadlisp_")
    lsp_path = os.path.join(tmp_dir, "dump.lsp").replace("\\", "/")
    with open(lsp_path, "w", encoding="ascii", errors="replace") as fh:
        fh.write(LISP_TEMPLATE.replace("__OUTPATH__", out_path.replace("\\", "/")))
    return lsp_path


def main() -> int:
    src = os.path.abspath(sys.argv[1])
    outdir = os.path.abspath(sys.argv[2])
    os.makedirs(outdir, exist_ok=True)
    report_path = os.path.join(outdir, "unlock_report.json")

    app = attach()
    call(lambda: setattr(app, "Visible", True))
    REPORT.update({"source": src, "outdir": outdir, "acad_version": safe(lambda: str(app.Version))})
    flush(report_path)

    work = os.path.join(outdir, "_work_src.dwg")
    shutil.copy2(src, work)
    doc = call(app.Documents.Open, work, True)
    REPORT["state_before"] = doc_state(doc)
    log(f"state_before: {json.dumps(REPORT['state_before'], ensure_ascii=False)}", report_path)

    # ---- 2) WBLOCK attempt ----
    wblock = os.path.join(outdir, "candidate_wblock.dwg")
    try:
        if os.path.exists(wblock):
            os.remove(wblock)
        call(lambda: doc.SendCommand(f'_.WBLOCK\n"{wblock.replace(os.sep, "/")}"\n*\n'))
        time.sleep(4.0)
        if os.path.exists(wblock):
            d = call(app.Documents.Open, wblock, True)
            REPORT["wblock"] = doc_state(d)
            call(d.Close, False)
        else:
            REPORT["wblock"] = {"error": "wblock file not produced"}
    except Exception as exc:
        REPORT["wblock"] = {"error": str(exc)}
    log(f"wblock: {json.dumps(REPORT['wblock'], ensure_ascii=False)}", report_path)

    # ---- 3) SaveAs DXF ----
    dxf = os.path.join(outdir, "intermediate.dxf")
    try:
        if os.path.exists(dxf):
            os.remove(dxf)
        call(doc.SaveAs, dxf, 61)  # 61 = R2013 DXF
        REPORT["dxf_export"] = {"ok": os.path.exists(dxf), "size": os.path.getsize(dxf) if os.path.exists(dxf) else 0}
    except Exception as exc:
        REPORT["dxf_export"] = {"ok": False, "error": str(exc)}
    log(f"dxf_export: {json.dumps(REPORT['dxf_export'], ensure_ascii=False)}", report_path)

    # dump content from the original document (still open) before closing it
    tsv = os.path.join(outdir, "drawing_dump.tsv")
    try:
        lsp = write_lisp(tsv)
        call(lambda: doc.Activate())
        call(lambda: doc.SendCommand(f'(load "{lsp}")\n'))
        time.sleep(1.5)
        call(lambda: doc.SendCommand("DUMPALL\n"))
        time.sleep(6.0)
        REPORT["lisp_dump"] = {"ok": os.path.exists(tsv), "size": os.path.getsize(tsv) if os.path.exists(tsv) else 0}
    except Exception as exc:
        REPORT["lisp_dump"] = {"ok": False, "error": str(exc)}
    log(f"lisp_dump: {json.dumps(REPORT['lisp_dump'], ensure_ascii=False)}", report_path)
    call(doc.Close, False)

    # ---- 4) DXF -> DWG ----
    clean = os.path.join(outdir, "HKGB-3924-HP1&2&3&4-260206_nolock.dwg")
    try:
        if os.path.exists(clean):
            os.remove(clean)
        d2 = call(app.Documents.Open, dxf, True)
        REPORT["dxf_state"] = doc_state(d2)
        call(d2.SaveAs, clean, 64)  # 64 = R2018 DWG
        call(d2.Close, False)
        REPORT["dxf_to_dwg"] = {"ok": os.path.exists(clean), "size": os.path.getsize(clean) if os.path.exists(clean) else 0}
    except Exception as exc:
        REPORT["dxf_to_dwg"] = {"ok": False, "error": str(exc)}
    log(f"dxf_to_dwg: {json.dumps(REPORT['dxf_to_dwg'], ensure_ascii=False)}", report_path)

    # ---- 5) reopen candidate and probe writability ----
    if REPORT.get("dxf_to_dwg", {}).get("ok"):
        try:
            d3 = call(app.Documents.Open, clean, True)
            REPORT["state_after"] = doc_state(d3)
            call(lambda: d3.Activate())
            ms = call(lambda: d3.ModelSpace)
            n0 = call(lambda: ms.Count)
            lisp = ('(progn (entmake (list (cons 0 "LINE") (cons 10 (list 0.0 0.0 0.0)) '
                    '(cons 11 (list 10.0 10.0 0.0)) (cons 8 "0"))) '
                    '(vla-Save (vla-get-ActiveDocument (vlax-get-acad-object))) (princ))')
            call(lambda: d3.SendCommand(lisp + "\n"))
            time.sleep(3.0)
            n1 = call(lambda: ms.Count)
            REPORT["write_test"] = {"entities_before": n0, "entities_after": n1,
                                     "saved": safe(lambda: bool(d3.Saved))}
            call(d3.Close, False)
            # reopen to prove the saved edit persisted
            d4 = call(app.Documents.Open, clean, True)
            n2 = call(lambda: d4.ModelSpace.Count)
            REPORT["write_test"]["entities_reopened"] = n2
            REPORT["write_test"]["persisted"] = (n2 == n1)
            REPORT["state_reopened"] = doc_state(d4)
            call(d4.Close, False)
        except Exception as exc:
            REPORT["write_test"] = {"error": str(exc)}
    log(f"write_test: {json.dumps(REPORT.get('write_test'), ensure_ascii=False)}", report_path)

    sa = REPORT.get("state_after", {})
    REPORT["unlocked"] = bool(
        sa.get("readonly") is False
        and REPORT.get("write_test", {}).get("persisted")
    )
    flush(report_path)
    print(json.dumps(REPORT, ensure_ascii=False, indent=1))
    return 0 if REPORT["unlocked"] else 2


if __name__ == "__main__":
    pythoncom.CoInitialize()
    try:
        sys.exit(main())
    finally:
        pythoncom.CoUninitialize()
