import win32com.client
sw = win32com.client.GetActiveObject("SldWorks.Application")
part = sw.ActiveDoc
skf = part.FeatureByName("草图1") or part.FeatureByName("Sketch1")
skf.Select2(False, 0)
part.InsertSketch2(True)   # 进入
sm = part.SketchManager
try:
    segs = sm.GetSketchSegments      # 属性（非方法）
    print("SEG_COUNT", len(segs) if segs else 0)
except Exception as e:
    print("segs err", repr(e)[:80])
try:
    pts = sm.GetSketchPoints
    print("PT_COUNT", len(pts) if pts else 0)
except Exception as e:
    print("pts err", repr(e)[:80])
# 尝试读取草图定义
try:
    defn = skf.GetDefinition()
    print("DEF_OK", defn is not None)
    # 列出草图段
    s2 = defn.GetSketchSegments()
    print("DEF_SEG", len(s2) if s2 else 0)
except Exception as e:
    print("def err", repr(e)[:80])
part.InsertSketch2(True)   # 退出
