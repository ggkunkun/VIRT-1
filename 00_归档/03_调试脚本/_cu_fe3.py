import win32com.client, sys

LOG = "D:/Virtu模型/_cu_model.log"
def log(*a):
    s = " ".join(str(x) for x in a)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(s + "\n")
    print(s, flush=True)

log("=== FE3风格拉伸 ===")
sw = win32com.client.GetActiveObject("SldWorks.Application")
part = sw.ActiveDoc

sk = part.FeatureByName("草图3") or part.FeatureByName("草图2") or part.FeatureByName("草图1")
if sk is None:
    log("NO_SKETCH"); sys.exit(1)
log("SKETCH", sk.Name)
sk.Select2(False, 0)

# FeatureExtrusion3 风格 22 参数 + 1 额外 = 23
# Scope, Profile, FeatureScope, AutoSelect, AssemblyWeldmentProfile, LayoutProfile, SkipProfile,
# Type, EndCond, Depth, Flip, Directional, EndCond2, Depth2, Flip2, Directional2,
# GeometryPattern, TrimBySelection, ConsumeSelection, ShowPreview, ReverseOffsetDir, IsExtrudeBoss
args = [1, True, False, True, False, 0, False,
        0, 0, 0.02, False, False, 0, 0.0, False, False,
        False, False, True, False, False, True, False]
log("NARGS", len(args))
try:
    f = part.FeatureManager.FeatureExtrusion2(*args)
    log("FE3STYLE", f is not None, f.Name if f else None)
    if f is not None:
        part.ClearSelection2(True)
        part.ForceRebuild3(True)
        part.ViewZoomtofit2()
        mp = part.GetMassProperties
        if mp is not None:
            vol = float(mp[14])
            log("VOLUME_M3", vol, "EXPECTED", 0.05*0.03*0.02)
            log("VOLUME_OK dV>0 PASS" if vol > 0 else "VOLUME_FAIL")
        else:
            log("MP_NONE")
except Exception as e:
    log("FE3STYLE_ERR", repr(e)[:100])
log("=== 结束 ===")
