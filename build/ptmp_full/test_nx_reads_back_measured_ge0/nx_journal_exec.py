# -*- coding: utf-8 -*-
import json, os
import NXOpen, NXOpen.UF

PART_PATH = r"D:/Virtu模型/build/ptmp_full/test_nx_reads_back_measured_ge0/nx_wheel_mold.prt"
RESULT_PATH = r"D:/Virtu模型/build/ptmp_full/test_nx_reads_back_measured_ge0/stage02_nx.json"
TEMPLATE = "model-plain-1-mm-template.prt"
EXPRESSIONS = ['D_OUTER = 53.000', 'D_BORE = 14.000', 'TOTAL_LENGTH = 45.000', 'GROOVE_PITCH = 11.250']
D_OUTER = 53.000
D_BORE = 14.000
LENGTH = 45.000
GROOVE_Z = [-11.25, -22.5, -33.75]
GROOVE_W = 6.000

d = {"api_signatures": {}}
try:
    s = NXOpen.Session.GetSession()
    uf = NXOpen.UF.UFSession.GetUFSession()
    if os.path.exists(PART_PATH):
        os.remove(PART_PATH)
    fn = s.Parts.FileNew()
    fn.Application = NXOpen.FileNewApplication.Modeling
    fn.Units = NXOpen.PartUnits.Millimeters
    fn.NewFileName = PART_PATH
    fn.TemplateFileName = TEMPLATE
    part = fn.Commit()
    fn.Destroy()
    s.Parts.SetWork(part)
    wp = s.Parts.Work
    d["part_created"] = True

    for eq in EXPRESSIONS:
        try:
            e = wp.Expressions.Create(eq)
            d.setdefault("expressions", []).append("%s=%s" % (e.Name, e.Value))
        except Exception as ex:
            d.setdefault("expression_errors", []).append(repr(ex)[:140])

    SIGN_MEMBERS = [x for x in dir(NXOpen.UF.ModlFeatureSigns) if not x.startswith("_")]

    def pick(names):
        for n in names:
            if hasattr(NXOpen.UF.ModlFeatureSigns, n):
                return getattr(NXOpen.UF.ModlFeatureSigns, n)
        raise AttributeError("no sign member in " + str(SIGN_MEMBERS))

    null_sign = pick(["NullSign", "Nullsign", "Null", "NULLSIGN"])
    neg_sign = pick(["Negative", "Negate", "Subtract", "NEGATIVE"])
    d["sign_members"] = SIGN_MEMBERS
    d["api_signatures"]["CreateCyl1"] = str(uf.ModlFeatures.CreateCyl1.__doc__.split("Signature")[-1][:200])
    cyl = uf.ModlFeatures.CreateCyl1(null_sign, [0.0, 0.0, 0.0], "%.3f" % LENGTH, "%.3f" % D_OUTER, [0.0, 0.0, -1.0])
    bore = uf.ModlFeatures.CreateCyl1(neg_sign, [0.0, 0.0, 0.0], "%.3f" % (LENGTH + 10.0), "%.3f" % D_BORE, [0.0, 0.0, -1.0])
    d["cyl_tag"], d["bore_tag"] = int(cyl), int(bore)

    # 圆弧槽：UF 无 CreateTorus；试高亮 API 的 TorusBuilder，不成则如实记录（不做「切断式」假几何）
    groove = []
    for zc in GROOVE_Z:
        rec = {"z": zc}
        try:
            tb = wp.Features.CreateTorusBuilder(None)
            rec["builder"] = str(type(tb))
            rec["attrs"] = [a for a in dir(tb) if a.lower() in
                            ("majorradius", "minorradius", "toruscenter", "axes", "expression")][:8]
            try:
                tb.Destroy()
            except Exception:
                pass
        except Exception as ex:
            rec["torus_builder_err"] = repr(ex)[:180]
        groove.append(rec)
    d["groove_notes"] = groove

    try:
        uf.Modeling.Update()
        d["update_ok"] = True
    except Exception as ex:
        d["update_err"] = repr(ex)[:180]

    n = 0
    try:
        for f in wp.Features:
            n += 1
    except Exception as ex:
        d["feature_enum_err"] = repr(ex)[:140]
    d["feature_count"] = n

    body_tag = None
    try:
        for b in wp.Bodies:
            body_tag = int(b.Tag)
            break
    except Exception as ex:
        d["body_err"] = repr(ex)[:140]
    d["body_tag"] = body_tag

    if body_tag:
        try:
            d["api_signatures"]["AskBoundingBox"] = str(uf.ModlGeneral.AskBoundingBox.__doc__.split("Signature")[-1][:200])
            bb = uf.ModlGeneral.AskBoundingBox(body_tag)
            d["bbox_raw"] = str(bb)[:400]
        except Exception as ex:
            d["bbox_err"] = repr(ex)[:200]
        try:
            d["api_signatures"]["AskMassProps3d"] = str(uf.Modeling.AskMassProps3d.__doc__.split("Signature")[-1][:260])
        except Exception as ex:
            d["mass_sig_err"] = repr(ex)[:140]

    try:
        wp.Save(getattr(NXOpen.BasePartSaveComponents, "FalseValue"),
                getattr(NXOpen.BasePartCloseAfterSave, "FalseValue"))
        d["saved"] = True
    except Exception as ex:
        d["save_err"] = repr(ex)[:200]
    d["part_exists"] = os.path.exists(PART_PATH)
    d["part_bytes"] = os.path.getsize(PART_PATH) if d["part_exists"] else 0
    d["status"] = "OK"
except Exception as ex:
    d["status"] = "ERR"
    d["error"] = repr(ex)[:400]

with open(RESULT_PATH, "w") as f:
    json.dump(d, f, indent=2)
