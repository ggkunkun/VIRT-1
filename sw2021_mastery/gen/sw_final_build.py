# -*- coding: utf-8 -*-
"""绕开空转的 UI 线程：用 COM 完成建件/拉伸/切除/量体积/保存/预览。"""
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
LOG = open(os.path.join(WORK, "final_build.log"), "w", encoding="utf-8", buffering=1)


def log(m):
    line = f"[{time.strftime('%H:%M:%S')}] {m}"
    print(line, flush=True)
    LOG.write(line + "\n")


def timed(label, fn):
    t = time.time()
    r = fn()
    log(f"{label} {time.time()-t:.1f}s -> {r if isinstance(r,(bool,int,str,type(None))) else type(r).__name__}")
    return r


def main():
    import win32com.client
    from win32com.client import __WrapDispatch

    t0 = time.time()
    # ROT 只在实例存活且客户端在线时可见：启动、附着、建模必须在同一进程内完成
    def pids():
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq SLDWORKS.exe", "/NH", "/FO", "CSV"],
                             capture_output=True, text=True, errors="ignore").stdout
        return [int(l.split('","')[1]) for l in out.splitlines() if l.startswith('"SLDWORKS.exe"')]

    for p in pids():
        subprocess.run(["taskkill", "/PID", str(p), "/F"], capture_output=True)
    time.sleep(5)
    log(f"launch exe pids_before={pids()}")
    subprocess.Popen(["explorer.exe", r"D:\SOLIDWORKS (2)\SLDWORKS.exe"])
    for _ in range(24):
        time.sleep(5)
        if pids():
            break
    time.sleep(45)
    log(f"sw pid={pids()}")

    sw = None
    for i in range(8):
        try:
            sw = win32com.client.GetActiveObject("SldWorks.Application.29")
            break
        except Exception as exc:
            log(f"  attach#{i+1} fail {str(exc)[:60]}")
            time.sleep(5)
    if sw is None:
        raise RuntimeError("无法附着 SOLIDWORKS 2021")
    rev = sw.RevisionNumber
    rev = rev() if callable(rev) else rev
    log(f"attach rev={rev}")
    assert str(rev).startswith("29.")

    tpl = r"C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2021\templates\gb_part.prtdot"
    model = None
    for attempt in range(3):
        model = timed(f"newdoc#{attempt+1}", lambda: sw.NewDocument(tpl, 0, 0, 0))
        if model is not None:
            break
        time.sleep(3)
    if model is None:
        raise RuntimeError("模板建件失败")
    model = __WrapDispatch(model, "IModelDoc2")
    title = model.GetTitle
    title = title() if callable(title) else title
    log(f"model title={title}")

    timed("clear_sel", lambda: model.ClearSelection2(True))
    how = None
    for label, fn in (
        ("SelectByID", lambda: model.SelectByID("前视基准面", "PLANE", 0, 0, 0)),
        ("Ext.SelectByID2", lambda: model.Extension.SelectByID2("前视基准面", "PLANE", 0, 0, 0, False, 0, None, 0)),
    ):
        try:
            if fn():
                how = label
                break
        except Exception as exc:
            log(f"  {label} fail {str(exc)[:80]}")
    log(f"select plane -> {how}")
    if not how:
        raise RuntimeError("无法选中前视基准面")

    timed("insert_sketch", lambda: model.SketchManager.InsertSketch(True))
    timed("rect", lambda: model.SketchManager.CreateCenterRectangle(0, 0, 0, 0.06, 0.04, 0))
    timed("exit_sketch", lambda: model.SketchManager.InsertSketch(True))
    timed("clear_sel2", lambda: model.ClearSelection2(True))

    feats = model.FeatureManager.GetFeatures(False)
    log(f"features={len(feats)} last={feats[-1].Name if feats else None}")
    sk = __WrapDispatch(feats[-1], "IFeature")
    log("sketch select -> " + str(timed("sketch_sel", lambda: sk.Select2(False, 0))))

    boss = timed("extrude", lambda: model.FeatureManager.FeatureExtrusion3(
        True, False, True, 0, 0, 0.02, 0.0, False, False, False, False, 0.0, 0.0,
        False, False, False, False, True, False, True, 0, 0.0, False))
    if boss is None:
        raise RuntimeError("拉伸失败")

    model.ClearSelection2(True)
    model.SelectByID("前视基准面", "PLANE", 0, 0, 0)
    model.SketchManager.InsertSketch(True)
    model.SketchManager.CreateCircleByRadius(0, 0, 0, 0.015)
    model.SketchManager.InsertSketch(True)
    model.ClearSelection2(True)
    feats = model.FeatureManager.GetFeatures(False)
    sk2 = __WrapDispatch(feats[-1], "IFeature")
    log("hole sketch select -> " + str(timed("hole_sel", lambda: sk2.Select2(False, 0))))
    cut = timed("cut", lambda: model.FeatureManager.FeatureCut4(
        False, False, True, 1, 1, 0.01, 0.01, False, False, False, False, 0.0, 0.0,
        False, False, False, False, False, True, True, False, False, False, 0, 0.0, False, False))
    log(f"cut ok={cut is not None}")

    timed("rebuild", lambda: model.ForceRebuild3(False))
    mp = model.Extension.CreateMassProperty()
    mp.UseSystemUnits = True
    v = mp.Volume
    vol = float(v() if callable(v) else v) * 1e9
    exp = (120 * 80 - math.pi * 15 ** 2) * 20
    log(f"volume={vol:.2f} expected={exp:.2f} dev={abs(vol-exp)/exp:.4%}")

    from sw_connect import save_document
    from sw_export import export_to_step
    part = os.path.join(WORK, "P05_pilot.SLDPRT")
    ok_save = bool(timed("save_sldprt", lambda: save_document(model, part)))
    step_path = os.path.join(WORK, "P05_pilot.STEP")
    ok_step = bool(timed("export_step", lambda: export_to_step(model, step_path)))

    shots = []
    for bmp in ("pilot_iso.bmp", "pilot_front.bmp"):
        p = os.path.join(EVID, bmp)
        try:
            ok = model.SaveBMP(p, 1600, 1000)
            shots.append({"path": p, "ok": bool(ok), "bytes": os.path.getsize(p) if os.path.exists(p) else 0})
        except Exception as exc:
            shots.append({"path": p, "ok": False, "error": str(exc)[:120]})
        log(f"savebmp {bmp} -> {shots[-1]}")

    res = {"ok": ok_save and ok_step and abs(vol - exp) / exp < 0.005,
           "revision": str(rev), "volume_mm3": round(vol, 2), "expected_mm3": round(exp, 2),
           "volume_deviation": round(abs(vol - exp) / exp, 6),
           "features": len(model.FeatureManager.GetFeatures(False)),
           "part": part, "step": step_path, "step_bytes": os.path.getsize(step_path) if os.path.exists(step_path) else 0,
           "previews": shots, "elapsed_s": round(time.time() - t0, 1),
           "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    with open(os.path.join(EVID, "pilot_result.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    log("RESULT " + json.dumps({k: res[k] for k in ("ok", "volume_mm3", "expected_mm3", "volume_deviation", "step_bytes", "elapsed_s")}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        import traceback
        log("FATAL " + repr(exc))
        LOG.write(traceback.format_exc())
        raise
