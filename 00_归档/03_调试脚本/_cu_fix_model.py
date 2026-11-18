import win32com.client, sys

LOG = "D:/Virtu模型/_cu_model.log"
def log(*a):
    s = " ".join(str(x) for x in a)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(s + "\n")
    print(s, flush=True)

log("=== 修复建模(AddToDB) ===")
sw = win32com.client.GetActiveObject("SldWorks.Application")
part = sw.ActiveDoc
log("Title=", part.GetTitle)

# 1) 删除已有的空草图
old = part.FeatureByName("草图1") or part.FeatureByName("Sketch1")
if old is not None:
    old.Select2(False, 0)
    try:
        part.EditDelete()
        log("DELETED_OLD_SKETCH")
    except Exception as e:
        log("DEL_ERR", repr(e)[:60])

# 2) 选前视基准面并进入草图
plane = part.FeatureByName("前视基准面") or part.FeatureByName("Front Plane")
plane.Select2(False, 0)
part.InsertSketch2(True)
sm = part.SketchManager
# 关键：开启 AddToDB，几何才会真正写入
try:
    sm.AddToDB = True
    log("ADDTODB_ON")
except Exception as e:
    log("ADDTODB_ERR", repr(e)[:60])
seg = sm.CreateCornerRectangle(0.0, 0.0, 0.0, 0.05, 0.03, 0.0)
log("RECT_CREATED", seg is not None)
try:
    sm.AddToDB = False
except Exception:
    pass
part.InsertSketch2(True)   # 退出草图
log("SKETCH_EXITED featCount=", part.GetFeatureCount)

# 3) 拉伸：优先前端3参数 + Extrude1=True
sk = part.FeatureByName("草图1") or part.FeatureByName("Sketch1")
feat = None
if sk is not None:
    sk.Select2(False, 0)
    front3 = [1, True, False]
    rest20 = [False, True, False, 0, 0, 0.02, 0.0,
              False, False, False, False, 0, 0.0, 0.0,
              False, False, False, 0, 0, False]
    try:
        feat = part.FeatureManager.FeatureExtrusion2(*(front3 + rest20))
        log("EXTRUDE_FRONT3", feat is not None, feat.Name if feat else None)
    except Exception as e:
        log("EXTRUDE_FRONT3_ERR", repr(e)[:80])
    if feat is None:
        # 退路：尾部3参数
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
        if mp is None:
            mp = part.GetMassProperties(2)
    except Exception as e:
        log("MP_ERR", repr(e)[:60]); mp = None
    if mp is not None:
        vol = float(mp[14])
        exp = 0.05 * 0.03 * 0.02
        log("VOLUME_M3", vol, "EXPECTED", exp)
        log("VOLUME_OK dV>0 PASS ratio=%.4f" % (vol/exp) if vol > 0 else "VOLUME_FAIL")
log("=== 结束 ===")
