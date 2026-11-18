import win32com.client, sys

LOG = "D:/Virtu模型/_cu_model.log"
def log(*a):
    s = " ".join(str(x) for x in a)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(s + "\n")
    print(s, flush=True)

sw = win32com.client.GetActiveObject("SldWorks.Application")
part = sw.ActiveDoc

# 删除所有草图，重来
for nm in ["草图1","草图2","草图3","草图4","草图5","草图6","草图7"]:
    f = part.FeatureByName(nm)
    if f is not None:
        f.Select2(False,0)
        try: part.EditDelete(); log("DEL", nm)
        except: pass

plane = part.FeatureByName("前视基准面")
plane.Select2(False,0)
sm = part.SketchManager
sm.InsertSketch(True)
sm.AddToDB = True
sm.CreateCircle(0.0, 0.0, 0.0, 0.02, 0.0, 0.0)   # 圆心(0,0) 半径20mm
sm.AddToDB = False
sm.InsertSketch(True)
log("CIRCLE_SKETCH featcount", part.GetFeatureCount)

sk = None
for i in range(1,9):
    f = part.FeatureByPositionReverse(i-1)
    if f and f.Name.startswith("草图"):
        sk = f; break
log("SKETCH", sk.Name if sk else None)
if sk is None: sys.exit(1)

base = [False, True, False, 0, 0, 0.02, 0.0,
        False, False, False, False, 0, 0.0, 0.0,
        False, False, False, 0, 0, False]
for tail in ([False,False,False],[False,False,True],[True,False,False]):
    sk.Select2(False,0)
    try:
        f = part.FeatureManager.FeatureExtrusion2(*(base+tail))
        log("TAIL", tail, "->", f is not None, f.Name if f else None)
        if f is not None:
            mp = part.GetMassProperties
            log("VOLUME", mp[14] if mp else None)
            break
    except Exception as e:
        log("ERR", tail, repr(e)[:50])
