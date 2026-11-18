import win32com.client, sys

LOG = "D:/Virtu模型/_cu_model.log"
def log(*a):
    s = " ".join(str(x) for x in a)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(s + "\n")
    print(s, flush=True)

log("=== 草图重建(SM.InsertSketch) ===")
sw = win32com.client.GetActiveObject("SldWorks.Application")
part = sw.ActiveDoc

# 删除已有草图
for nm in ["草图1", "草图2", "草图3", "Sketch1", "Sketch2", "Sketch3"]:
    f = part.FeatureByName(nm)
    if f is not None:
        f.Select2(False, 0)
        try:
            part.EditDelete(); log("DELETED", nm)
        except Exception as e:
            log("DEL_ERR", nm, repr(e)[:40])

# 选前视基准面
plane = part.FeatureByName("前视基准面") or part.FeatureByName("Front Plane")
if plane is None:
    log("NO_PLANE"); sys.exit(1)
plane.Select2(False, 0)

sm = part.SketchManager
sm.InsertSketch(True)        # 进入草图
try:
    sm.AddToDB = True
    log("ADDTODB_ON")
except Exception as e:
    log("ADDTODB_ERR", repr(e)[:50])
seg = sm.CreateCornerRectangle(0.0, 0.0, 0.0, 0.05, 0.03, 0.0)
log("RECT_CREATED", seg is not None)
try:
    sm.AddToDB = False
except Exception:
    pass
sm.InsertSketch(True)        # 退出草图
part.ClearSelection2(True)
part.ViewZoomtofit2()
log("DONE featCount=", part.GetFeatureCount)
