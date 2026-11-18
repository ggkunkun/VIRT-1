import win32com.client, sys

LOG = "D:/Virtu模型/_cu_model.log"
def log(*a):
    s = " ".join(str(x) for x in a)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(s + "\n")
    print(s, flush=True)

log("=== 闭合矩形+拉伸 ===")
sw = win32com.client.GetActiveObject("SldWorks.Application")
part = sw.ActiveDoc

# 删旧草图
for nm in ["草图3", "草图2", "草图1"]:
    f = part.FeatureByName(nm)
    if f is not None:
        f.Select2(False, 0)
        try: part.EditDelete(); log("DEL", nm)
        except Exception as e: log("DELERR", nm, repr(e)[:40])

plane = part.FeatureByName("前视基准面") or part.FeatureByName("Front Plane")
plane.Select2(False, 0)
sm = part.SketchManager
sm.InsertSketch(True)
sm.AddToDB = True
# 50x30 闭合矩形（4 条线端点完全重合）
sm.CreateLine(0.0, 0.0, 0.0,   0.05, 0.0, 0.0)
sm.CreateLine(0.05, 0.0, 0.0,  0.05, 0.03, 0.0)
sm.CreateLine(0.05, 0.03, 0.0, 0.0, 0.03, 0.0)
sm.CreateLine(0.0, 0.03, 0.0,  0.0, 0.0, 0.0)
sm.AddToDB = False
sm.InsertSketch(True)
log("SKETCH_DONE featcount", part.GetFeatureCount)

sk = None
for nm in ["草图1", "草图2", "草图3"]:
    f = part.FeatureByName(nm)
    if f is not None: sk = f; break
log("SKETCH", sk.Name if sk else None)

if sk is not None:
    base = [False, True, False, 0, 0, 0.02, 0.0,
            False, False, False, False, 0, 0.0, 0.0,
            False, False, False, 0, 0, False]
    for tail in ([False, False, False], [False, False, True]):
        try:
            sk.Select2(False, 0)
            f = part.FeatureManager.FeatureExtrusion2(*(base + tail))
            log("TAIL", tail, "->", f is not None, f.Name if f else None)
            if f is not None:
                part.ClearSelection2(True)
                part.ForceRebuild3(True)
                part.ViewZoomtofit2()
                mp = part.GetMassProperties
                log("VOLUME", mp[14] if mp else None)
                break
        except Exception as e:
            log("ERR", tail, repr(e)[:60])
log("=== 结束 ===")
