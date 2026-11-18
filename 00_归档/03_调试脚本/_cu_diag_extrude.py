import win32com.client, sys

sw = win32com.client.GetActiveObject("SldWorks.Application")
part = sw.ActiveDoc

# 诊断草图
skf = part.FeatureByName("草图1") or part.FeatureByName("Sketch1")
print("SKETCH_FEATURE", skf is not None, skf.Name if skf else None)
if skf:
    skf.Select2(False, 0)
    # 编辑草图看段数
    sm = part.SketchManager
    try:
        segCount = sm.GetSketchSegmentCount and sm.GetSketchSegmentCount()
        print("SEG_COUNT", segCount)
    except Exception as e:
        print("seg err", repr(e))

# 试老版 FeatureExtrusion（15 参数）
part.FeatureByName("草图1").Select2(False, 0)
legacy15 = [False, True, False, 0.02, 0.0, False, False, False, False, False, False, False, False, False, False]
try:
    f = part.FeatureManager.FeatureExtrusion(*legacy15)
    print("LEGACY15", f is not None, f.Name if f else None)
except Exception as e:
    print("LEGACY15_ERR", repr(e)[:80])

# 试老版带更多参数 16/17
for n in (16,17,18):
    a = legacy15 + [False]*(n-15)
    try:
        f = part.FeatureManager.FeatureExtrusion(*a)
        print("LEGACY%d" % n, f is not None)
        if f is not None:
            break
    except Exception as e:
        print("LEGACY%d_ERR" % n, repr(e)[:50])
