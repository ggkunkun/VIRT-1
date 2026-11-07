#!/usr/bin/env python
"""Dump every entity / text / layer / block of a DWG through AutoCAD + AutoLISP.

AutoCAD's SECURELOAD blocks (load ...) from untrusted paths, which is why the
first attempt produced no output; SECURELOAD is temporarily disabled and then
restored to its original value.

Usage: python scripts/acad_dump_lisp.py <dwg> <outdir>
"""
from __future__ import annotations

import json
import os
import sys
import time

import pythoncom
import win32com.client as win32

PROGIDS = ["AutoCAD.Application.25.1", "AutoCAD.Application.25", "AutoCAD.Application"]
RETRY_HRESULTS = (-2147418111, -2147417846, -2147417851, -2147417843)

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


def main() -> int:
    dwg = os.path.abspath(sys.argv[1])
    outdir = os.path.abspath(sys.argv[2])
    os.makedirs(outdir, exist_ok=True)
    tsv = os.path.join(outdir, "drawing_dump.tsv")
    lsp_path = os.path.join(outdir, "dump_drawing.lsp")
    with open(lsp_path, "w", encoding="ascii", errors="replace") as fh:
        fh.write(LISP_TEMPLATE.replace("__OUTPATH__", tsv.replace("\\", "/")))

    app = attach()
    call(lambda: setattr(app, "Visible", True))

    sec_old = None
    try:
        sec_old = app.GetSystemVariable("SECURELOAD")
        app.SetSystemVariable("SECURELOAD", 0)
    except Exception as exc:
        print("SECURELOAD toggle failed:", exc)

    report = {"dwg": dwg, "tsv": tsv, "secureload_before": sec_old}
    try:
        doc = call(app.Documents.Open, dwg, False)
        report["readonly"] = bool(doc.ReadOnly)
        call(lambda: doc.Activate())
        call(lambda: doc.SendCommand(f'(load "{lsp_path.replace(os.sep, "/")}")\n'))
        time.sleep(2.0)
        call(lambda: doc.SendCommand("DUMPALL\n"))
        time.sleep(8.0)
        report["tsv_exists"] = os.path.exists(tsv)
        report["tsv_size"] = os.path.getsize(tsv) if os.path.exists(tsv) else 0
        call(doc.Close, False)
    except Exception as exc:
        report["error"] = str(exc)
    finally:
        try:
            if sec_old is not None:
                app.SetSystemVariable("SECURELOAD", sec_old)
                report["secureload_restored"] = app.GetSystemVariable("SECURELOAD")
        except Exception:
            pass

    with open(os.path.join(outdir, "lisp_dump_report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0 if report.get("tsv_exists") else 2


if __name__ == "__main__":
    pythoncom.CoInitialize()
    try:
        sys.exit(main())
    finally:
        pythoncom.CoUninitialize()
