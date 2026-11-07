;;; =========================================================================
;;; AutoCAD AutoLISP drawing dumper  (c:DUMPALL)
;;; Writes one TSV line per entity for every layout and block definition.
;;; Fields: SCOPE \t NAME \t TYPE \t LAYER \t HANDLE \t DATA
;;; =========================================================================

(defun _dz_str (v)
  (if (and v (not (vl-string-mismatch "" (vl-princ-to-string v))))
    (vl-princ-to-string v)
    ""))

(defun _dz_clean (s)
  ;; collapse tabs / newlines so one entity stays on one TSV line
  (setq s (vl-string-subst "\t" " " s))
  (setq s (vl-string-subst "\r\n" " " s))
  (setq s (vl-string-subst "\n" " " s))
  (setq s (vl-string-subst "\r" " " s))
  s)

(defun _dz_pair (e code)
  (cdr (assoc code e)))

(defun _dz_dump1 (f scope name e / d t ly h extra)
  (setq d (entget e))
  (setq t (_dz_pair d 0))
  (setq ly (_dz_pair d 8))
  (setq h (_dz_pair d 5))
  (setq extra "")
  (cond
    ((= t "TEXT")
     (setq extra (strcat "text=" (_dz_clean (_dz_pair d 1))
                         " |pos=" (_dz_clean (_dz_pair d 10))
                         " |h=" (_dz_clean (_dz_pair d 40)))))
    ((= t "MTEXT")
     (setq extra (strcat "text=" (_dz_clean (_dz_pair d 1))
                         (_dz_clean (_dz_pair d 3))
                         " |pos=" (_dz_clean (_dz_pair d 10))
                         " |w=" (_dz_clean (_dz_pair d 41)))))
    ((= t "ATTRIB")
     (setq extra (strcat "tag=" (_dz_clean (_dz_pair d 2))
                         " |text=" (_dz_clean (_dz_pair d 1))
                         " |pos=" (_dz_clean (_dz_pair d 10)))))
    ((= t "ATTDEF")
     (setq extra (strcat "tag=" (_dz_clean (_dz_pair d 2))
                         " |text=" (_dz_clean (_dz_pair d 1))
                         " |pos=" (_dz_clean (_dz_pair d 10)))))
    ((= t "DIMENSION")
     (setq extra (strcat "text=" (_dz_clean (_dz_pair d 1))
                         " |measure=" (_dz_clean (_dz_pair d 42))
                         " |def=" (_dz_clean (_dz_pair d 3))
                         " |style=" (_dz_clean (_dz_pair d 7))
                         " |p1=" (_dz_clean (_dz_pair d 10))
                         " |p2=" (_dz_clean (_dz_pair d 11))
                         " |p3=" (_dz_clean (_dz_pair d 13)))))
    ((= t "INSERT")
     (setq extra (strcat "block=" (_dz_clean (_dz_pair d 2))
                         " |pos=" (_dz_clean (_dz_pair d 10))
                         " |scale=" (_dz_clean (_dz_pair d 41))
                         " |rot=" (_dz_clean (_dz_pair d 50)))))
    ((= t "LINE")
     (setq extra (strcat "start=" (_dz_clean (_dz_pair d 10))
                         " |end=" (_dz_clean (_dz_pair d 11)))))
    ((= t "CIRCLE")
     (setq extra (strcat "center=" (_dz_clean (_dz_pair d 10))
                         " |r=" (_dz_clean (_dz_pair d 40)))))
    ((= t "ARC")
     (setq extra (strcat "center=" (_dz_clean (_dz_pair d 10))
                         " |r=" (_dz_clean (_dz_pair d 40))
                         " |a1=" (_dz_clean (_dz_pair d 50))
                         " |a2=" (_dz_clean (_dz_pair d 51)))))
    ((= t "LWPOLYLINE")
     (setq extra (strcat "pts=" (_dz_clean (_dz_pair d 10))
                         " |closed=" (_dz_clean (_dz_pair d 70)))))
    ((= t "POLYLINE")
     (setq extra (strcat "closed=" (_dz_clean (_dz_pair d 70)))))
    ((= t "ELLIPSE")
     (setq extra (strcat "center=" (_dz_clean (_dz_pair d 10))
                         " |major=" (_dz_clean (_dz_pair d 11))
                         " |ratio=" (_dz_clean (_dz_pair d 40)))))
    ((= t "HATCH")
     (setq extra (strcat "pattern=" (_dz_clean (_dz_pair d 2)))))
    (T
     (setq extra "")))
  (write-line (strcat scope "\t" name"\t" t"\t" ly"\t" h"\t" extra) f)
)

(defun c:DUMPALL (/ f ss i e laylst bname blk outpath)
  (setq outpath (getvar "DWGPREFIX"))            ;; overwritten by caller env
  (setq outpath "D:/VirtuDump/dump.tsv")
  (setq f (open outpath "w"))
  (if (null f) (princ "\n[DUMPALL] cannot open output file") (progn
    ;; ---- layouts (incl. Model space) ----
    (setq laylst (cons "Model" (layoutlist)))
    (foreach lay laylst
      (setq ss (ssget "_X" (list (cons 410 lay))))
      (if ss
        (progn
          (write-line (strcat "META\t" lay"\tLAYOUT\t" (itoa (sslength ss))"\t\t") f)
          (setq i 0)
          (repeat (sslength ss)
            (setq e (ssname ss i))
            (_dz_dump1 f "LAYOUT" lay e)
            (setq i (1+ i)))))
    ;; ---- block definitions ----
    (setq blk (tblnext "BLOCK" T))
    (while blk
      (setq bname (_dz_pair blk 2))
      (setq ss (ssget "_X" (list (cons 2 bname))))
      (if ss
        (progn
          (write-line (strcat "META\t" bname"\tBLOCK\t" (itoa (sslength ss))"\t\t") f)
          (setq i 0)
          (repeat (sslength ss)
            (setq e (ssname ss i))
            (_dz_dump1 f "BLOCK" bname e)
            (setq i (1+ i)))))
      (setq blk (tblnext "BLOCK")))
    ;; ---- layers ----
    (setq laylst (tblnext "LAYER" T))
    (while laylst
      (write-line (strcat "LAYER\t" (_dz_pair laylst 2)"\tLAYER\t"
                          "color=" (_dz_clean (_dz_pair laylst 62))
                          " ltype=" (_dz_clean (_dz_pair laylst 6))
                          " flags=" (_dz_clean (_dz_pair laylst 70))"\t\t") f)
      (setq laylst (tblnext "LAYER")))
    ;; ---- dimension styles ----
    (setq laylst (tblnext "DIMSTYLE" T))
    (while laylst
      (write-line (strcat "DIMSTYLE\t" (_dz_pair laylst 2)"\tDIMSTYLE\t\t\t") f)
      (setq laylst (tblnext "DIMSTYLE")))
    ;; ---- text styles ----
    (setq laylst (tblnext "STYLE" T))
    (while laylst
      (write-line (strcat "STYLE\t" (_dz_pair laylst 2)"\tSTYLE\t\th=" (_dz_clean (_dz_pair laylst 40))"\t\t") f)
      (setq laylst (tblnext "STYLE")))
    (close f)
    (princ (strcat "\n[DUMPALL] wrote " outpath))
  ))
  (princ)
)
