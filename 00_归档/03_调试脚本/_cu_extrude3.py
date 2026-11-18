import win32com.client, sys

LOG = "D:/Virtu模型/_cu_model.log"
def log(*a):
    s = " ".join(str(x) for x in a)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(s + "\n")
    print(s, flush=True)

log("=== 退出草图+拉伸 ===")
sw = win32com.client.GetActiveObject("SldWorks.Application")
part = sw.ActiveDoc

# 退出草图（编辑态下 toggles 退出）
try:
    part.SketchManager.InsertSketch(True)
    log("EXIT_SKETCH_TOGGLE_OK")
except Exception as e:
    log("EXIT_ERR", repr(e)[:60])

# 找到草图（名字可能是草图1/2/3）
sk = None
for nm in ["草图3", "草图2", "草图1", "Sketch3", "Sketch2", "Sketch1"]:
    f = part.FeatureByName(nm)
    if f is not None:
        sk = f; log("FOUND_SKETCH", nm); break

if sk is None:
    log("NO_SKETCH"); sys.exit(1)

sk.Select2(False, 0)
front3 = [1, True, False]
rest20 = [False, True, False, 0, 0, 0.02, 0.0,
          False, False, False, False, 0, 0.0, 0.0,
          False, False, False, 0, 0, False]
feat = None
try:
    feat = part.FeatureManager.FeatureExtrusion2(*(front3 + rest20))
    log("EXTRUDE_FRONT3", feat is not None, feat.Name if feat else None)
except Exception as e:
    log("EXTRUDE_FRONT3_ERR", repr(e)[:80])

if feat is None:
    sk.Select2(False, 0)
    try:
        feat = part.FeatureManager.FeatureExtrusion2(*(rest20 + [False, False, False]))
        log("EXTRUDE_TAIL3", feat is not None, feat.Name if feat else None)
    except Exception as e:
        log("EXTRUDE_TAIL3_ERR", repr(e)[:80])

if feat is not None:
    part.ClearSelection2(True)
    part.ForceRebuild3(True)
    part.ViewZoomtofit2()
    try:
        mp = part.GetMassProperties
    except Exception as e:
        mp = None
        log("MP_ERR", repr(e)[:50])
    if mp is not None:
        vol = float(mp[14])
        exp = 0.05 * 0.03 * 0.02
        log("VOLUME_M3", vol, "EXPECTED", exp)
        log("VOLUME_OK dV>0 PASS" if vol > 0 else "VOLUME_FAIL")
log("=== 结束 ===")
