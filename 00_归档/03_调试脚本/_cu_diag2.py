import win32com.client, sys

sw = win32com.client.GetActiveObject("SldWorks.Application")
part = sw.ActiveDoc

# 诊断：进入草图，统计线段
skf = part.FeatureByName("草图1") or part.FeatureByName("Sketch1")
skf.Select2(False, 0)
part.InsertSketch2(True)   # 进入草图
sm = part.SketchManager
try:
    segs = sm.GetSketchSegments()
    print("SEG_COUNT", len(segs) if segs else 0)
except Exception as e:
    print("segs err", repr(e)[:80])
try:
    pts = sm.GetSketchPoints()
    print("POINT_COUNT", len(pts) if pts else 0)
except Exception as e:
    print("pts err", repr(e)[:80])
part.InsertSketch2(True)   # 退出

# 变体 B：前端3 + SDAmount=True, Depth1=20(整数mm)
skf.Select2(False, 0)
front3 = [1, True, False]
rest20 = [True, True, False, 20, 0, 0.02, 0.0,
          False, False, False, False, 0, 0.0, 0.0,
          False, False, False, 0, 0, False]
args23 = front3 + rest20
try:
    f = part.FeatureManager.FeatureExtrusion2(*args23)
    print("VAR_B", f is not None, f.Name if f else None)
except Exception as e:
    print("VAR_B_ERR", repr(e)[:80])

# 变体 C：SDAmount=True 但 Depth1=10
skf.Select2(False, 0)
rest20c = [True, True, False, 10, 0, 0.01, 0.0,
           False, False, False, False, 0, 0.0, 0.0,
           False, False, False, 0, 0, False]
try:
    f = part.FeatureManager.FeatureExtrusion2(*(front3+rest20c))
    print("VAR_C", f is not None, f.Name if f else None)
except Exception as e:
    print("VAR_C_ERR", repr(e)[:80])
