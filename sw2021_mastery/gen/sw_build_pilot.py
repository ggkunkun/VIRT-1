# -*- coding: utf-8 -*-
"""分阶段建模试点：每步写日志并 flush，便于定位挂起点。

只做四件事：建件 -> 矩形拉伸 -> 圆孔贯穿 -> 量体积/保存/出预览。
所有 COM 调用串行，任何一步失败即停并落日志。
"""
import json
import math
import os
import subprocess
import sys
import time

SK = r"C:\Users\Administrator\.workbuddy\skills\solidworks-automation\scripts"
sys.path.insert(0, SK)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(BASE, "work")
EVID = os.path.join(BASE, "out", "evidence")
os.makedirs(WORK, exist_ok=True)
os.makedirs(EVID, exist_ok=True)
LOG_PATH = os.path.join(WORK, "pilot.log")
LOG = open(LOG_PATH, "w", encoding="utf-8", buffering=1)


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    LOG.write(line + "\n")


def pids():
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq SLDWORKS.exe", "/NH", "/FO", "CSV"],
                         capture_output=True, text=True, errors="ignore").stdout
    return [l.split('","')[1] for l in out.splitlines() if l.startswith('"SLDWORKS.exe"')]


def main():
    from sw_connect import connect_solidworks, mm, new_document, save_document
    from sw_export import export_to_step
    from sw_part import extrude_boss, extrude_cut
    from sw_review import save_review_previews

    t_all = time.time()
    log("stage=cleanup start pids=" + str(pids()))
    for pid in pids():
        subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True, text=True, errors="ignore")
    time.sleep(6)
    log("stage=cleanup done remaining=" + str(pids()))

    t = time.time()
    sw, _, meta = connect_solidworks(version=2021, wait_seconds=120, visible=True, return_metadata=True)
    log(f"stage=connect done {time.time()-t:.1f}s rev={sw.RevisionNumber} pid={meta['process_id']} progid={meta['prog_id']}")

    t = time.time()
    model = new_document(sw, "part")
    from win32com.client import __WrapDispatch
    model = __WrapDispatch(model, "IModelDoc2")
    log(f"stage=new_part done {time.time()-t:.1f}s title={model.GetTitle()} hasClear={hasattr(model,'ClearSelection2')}")

    t = time.time()
    model.ClearSelection2(True)
    ok = model.Extension.SelectByID2("前视基准面", "PLANE", 0, 0, 0, False, 0, None, 0)
    model.SketchManager.InsertSketch(True)
    model.SketchManager.CreateCenterRectangle(0, 0, 0, mm(60), mm(40), 0)
    model.SketchManager.InsertSketch(True)
    model.ClearSelection2(True)
    feats = model.FeatureManager.GetFeatures(False)
    sketch_name = feats[-1].Name if feats else "Sketch1"
    log(f"stage=rect done {time.time()-t:.1f}s select={ok} sketch={sketch_name} feats={len(feats)}")

    t = time.time()
    f = extrude_boss(model, sketch_name, mm(20))
    log(f"stage=extrude done {time.time()-t:.1f}s ok={f is not None}")

    t = time.time()
    model.ClearSelection2(True)
    model.Extension.SelectByID2("前视基准面", "PLANE", 0, 0, 0, False, 0, None, 0)
    model.SketchManager.InsertSketch(True)
    model.SketchManager.CreateCircleByRadius(0, 0, 0, mm(15))
    model.SketchManager.InsertSketch(True)
    model.ClearSelection2(True)
    feats = model.FeatureManager.GetFeatures(False)
    hole_sketch = feats[-1].Name if feats else "Sketch2"
    f2 = extrude_cut(model, hole_sketch, 0, both_directions=True)
    log(f"stage=cut done {time.time()-t:.1f}s ok={f2 is not None} sketch={hole_sketch}")

    t = time.time()
    model.ForceRebuild3(False)
    model.ViewZoomtofit2()
    mp = model.Extension.CreateMassProperty()
    mp.UseSystemUnits = True
    vol = float(mp.Volume) * 1e9
    expected = (120 * 80 - math.pi * 15 ** 2) * 20
    log(f"stage=measure done {time.time()-t:.1f}s vol={vol:.2f} expected={expected:.2f} dev={abs(vol-expected)/expected:.4%}")

    t = time.time()
    part = os.path.join(WORK, "P05_L_bracket_pilot.SLDPRT")
    ok_save = save_document(model, part)
    step = os.path.join(WORK, "P05_L_bracket_pilot.STEP")
    ok_step = export_to_step(model, step)
    log(f"stage=save done {time.time()-t:.1f}s sldprt={ok_save} step={ok_step} step_bytes={os.path.getsize(step) if os.path.exists(step) else 0}")

    t = time.time()
    previews = save_review_previews(model, EVID, "pilot_P05", views=("isometric", "front", "top"))
    log(f"stage=preview done {time.time()-t:.1f}s {[os.path.basename(str(p)) for p in previews]}")

    result = {
        "ok": bool(ok_save and ok_step),
        "revision": str(sw.RevisionNumber),
        "pid": meta["process_id"],
        "prog_id": meta["prog_id"],
        "volume_mm3": round(vol, 2),
        "expected_mm3": round(expected, 2),
        "volume_deviation": round(abs(vol - expected) / expected, 6),
        "feature_count": len(model.FeatureManager.GetFeatures(False)),
        "part": part, "step": step,
        "previews": [str(p) for p in previews],
        "elapsed_s": round(time.time() - t_all, 1),
    }
    with open(os.path.join(EVID, "pilot_result.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    log("RESULT " + json.dumps({k: result[k] for k in ("ok", "volume_mm3", "expected_mm3", "volume_deviation", "elapsed_s")}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        import traceback
        log("FATAL " + repr(exc))
        LOG.write(traceback.format_exc() + "\n")
        raise
