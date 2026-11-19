# -*- coding: utf-8 -*-
"""附着已正常启动的 SW2021，执行建模试点并取证。"""
import json
import math
import os
import sys
import time

SK = r"C:\Users\Administrator\.workbuddy\skills\solidworks-automation\scripts"
sys.path.insert(0, SK)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(BASE, "work")
EVID = os.path.join(BASE, "out", "evidence")
os.makedirs(WORK, exist_ok=True)
os.makedirs(EVID, exist_ok=True)
LOG = open(os.path.join(WORK, "attach_build.log"), "w", encoding="utf-8", buffering=1)


def log(m):
    line = f"[{time.strftime('%H:%M:%S')}] {m}"
    print(line, flush=True)
    LOG.write(line + "\n")


def call(obj, name, *args):
    """早期绑定下部分成员是方法而非属性。"""
    v = getattr(obj, name)
    return v(*args) if callable(v) else v


def main():
    import win32com.client

    t0 = time.time()
    sw = win32com.client.GetActiveObject("SldWorks.Application.29")
    rev = call(sw, "RevisionNumber")
    log(f"attach ok rev={rev} type={type(sw).__name__}")
    assert str(rev).startswith("29."), f"版本不是 2021: {rev}"

    tpl = r"C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2021\templates\gb_part.prtdot"
    log(f"template={tpl} exists={os.path.exists(tpl)}")

    t = time.time()
    model = sw.NewDocument(tpl, 0, 0, 0)
    log(f"stage=newdoc {time.time()-t:.1f}s model={type(model).__name__ if model else None}")
    if model is None:
        raise RuntimeError("GB 模板建件失败")

    def sel(obj, kind, name, mark=0):
        """多种选择调用形式依次尝试，返回生效的那一种。"""
        tries = [
            ("SelectByID2-9", lambda: obj.Extension.SelectByID2(name, kind, 0, 0, 0, False, mark, None, 0)),
            ("SelectByID-5", lambda: obj.SelectByID(name, kind, 0, 0, 0)),
        ]
        for label, fn in tries:
            try:
                r = fn()
                if r:
                    return label
            except Exception as exc:
                log(f"  sel {label} fail {str(exc)[:70]}")
        return None

    t = time.time()
    model.ClearSelection2(True)
    how_plane = sel(model, "PLANE", "前视基准面")
    model.SketchManager.InsertSketch(True)
    model.SketchManager.CreateCenterRectangle(0, 0, 0, 0.06, 0.04, 0)
    model.SketchManager.InsertSketch(True)
    model.ClearSelection2(True)
    feats = model.FeatureManager.GetFeatures(False)
    s1 = feats[-1].Name if feats else "Sketch1"
    log(f"stage=rect {time.time()-t:.1f}s plane={how_plane} sketch={s1} feats={len(feats)}")

    t = time.time()
    try:
        ok_sel = feats[-1].Select2(False, 0)
    except Exception as exc:
        log(f"  feat.Select2 fail {exc!r}")
        ok_sel = sel(model, "SKETCH", s1, 1)
    boss = model.FeatureManager.FeatureExtrusion3(
        True, False, True, 0, 0, 0.02, 0.0, False, False, False, False, 0.0, 0.0,
        False, False, False, False, True, False, True, 0, 0.0, False)
    log(f"stage=extrude {time.time()-t:.1f}s sel={ok_sel} ok={boss is not None}")

    t = time.time()
    model.ClearSelection2(True)
    how_plane2 = sel(model, "PLANE", "前视基准面")
    model.SketchManager.InsertSketch(True)
    model.SketchManager.CreateCircleByRadius(0, 0, 0, 0.015)
    model.SketchManager.InsertSketch(True)
    model.ClearSelection2(True)
    feats = model.FeatureManager.GetFeatures(False)
    s2 = feats[-1].Name if feats else "Sketch2"
    try:
        ok_sel2 = feats[-1].Select2(False, 0)
    except Exception as exc:
        log(f"  feat.Select2 fail {exc!r}")
        ok_sel2 = sel(model, "SKETCH", s2, 1)
    cut = model.FeatureManager.FeatureCut4(
        False, False, True, 1, 1, 0.01, 0.01, False, False, False, False, 0.0, 0.0,
        False, False, False, False, False, True, True, False, False, False, 0, 0.0, False, False)
    log(f"stage=cut {time.time()-t:.1f}s plane={how_plane2} sel={ok_sel2} ok={cut is not None}")

    t = time.time()
    model.ForceRebuild3(False)
    model.ViewZoomtofit2()
    mp = model.Extension.CreateMassProperty()
    mp.UseSystemUnits = True
    vol = float(mp.Volume) * 1e9
    exp = (120 * 80 - math.pi * 15 ** 2) * 20
    log(f"stage=measure {time.time()-t:.1f}s vol={vol:.2f} exp={exp:.2f} dev={abs(vol-exp)/exp:.4%}")

    t = time.time()
    from sw_connect import save_document
    from sw_export import export_to_step
    part = os.path.join(WORK, "P05_pilot.SLDPRT")
    ok_save = save_document(model, part)
    step_path = os.path.join(WORK, "P05_pilot.STEP")
    ok_step = bool(export_to_step(model, step_path))
    log(f"stage=save {time.time()-t:.1f}s sldprt={ok_save} step={ok_step} bytes={os.path.getsize(step_path) if os.path.exists(step_path) else 0}")

    t = time.time()
    model.ClearSelection2(True)
    model.ViewZoomtofit2()
    try:
        model.ViewOrientation = 7  # 等轴测
    except Exception as exc:
        log(f"orientation skip {exc!r}")
    shots = []
    for name, bmp in (("iso", "pilot_iso.bmp"), ("front", "pilot_front.bmp")):
        p = os.path.join(EVID, bmp)
        ok = model.SaveBMP(p, 1600, 1000)
        shots.append(p)
        log(f"stage=preview {name} ok={ok} bytes={os.path.getsize(p) if os.path.exists(p) else 0}")

    res = {"ok": ok_save and ok_step, "revision": str(rev), "volume_mm3": round(vol, 2),
           "expected_mm3": round(exp, 2), "volume_deviation": round(abs(vol - exp) / exp, 6),
           "features": len(model.FeatureManager.GetFeatures(False)),
           "part": part, "step": step_path, "previews": shots,
           "elapsed_s": round(time.time() - t0, 1)}
    with open(os.path.join(EVID, "pilot_result.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    log("RESULT " + json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        import traceback
        log("FATAL " + repr(exc))
        LOG.write(traceback.format_exc())
        raise
