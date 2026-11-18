import win32com.client, sys

LOG = "D:/Virtu模型/_cu_model.log"
def log(*a):
    s = " ".join(str(x) for x in a)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(s + "\n")
    print(s, flush=True)

log("=== 建模闭环 v2 ===")
sw = win32com.client.GetActiveObject("SldWorks.Application")
sw.Visible = True
part = sw.ActiveDoc
log("Title=", part.GetTitle)

skf = part.FeatureByName("草图1") or part.FeatureByName("Sketch1")
if skf is None:
    log("NO_SKETCH"); sys.exit(1)
skf.Select2(False, 0)
log("SKETCH_SELECTED")

# 假设 23 参数 = 前端 [Scope, Profile, FeatureScope] + 原 20
front3 = [1, True, False]          # Scope=swFeatureScopeSelectedFeatures, Profile=True, FeatureScope=False
rest20 = [False, True, False, 0, 0, 0.02, 0.0,
          False, False, False, False, 0, 0.0, 0.0,
          False, False, False, 0, 0, False]
args23 = front3 + rest20
feat = part.FeatureManager.FeatureExtrusion2(*args23)
log("EXTRUDE_FEAT", feat is not None)
if feat is not None:
    log("FEAT_NAME", feat.Name)

if feat is not None:
    part.ClearSelection2(True)
    part.ForceRebuild3(True)
    # 体积：本 wrapper 中 GetMassProperties 为属性
    try:
        mp = part.GetMassProperties        # 属性
        if mp is None:
            mp = part.GetMassProperties(2) # 退路
    except Exception as e:
        log("MP_ERR", repr(e)); mp = None
    log("MASSPROPS", mp)
    if mp is not None:
        vol = float(mp[14])
        exp = 0.05*0.03*0.02
        log("VOLUME_M3", vol, "EXPECTED", exp)
        log("VOLUME_OK dV>0" if vol > 0 else "VOLUME_FAIL")
log("=== 结束 ===")
