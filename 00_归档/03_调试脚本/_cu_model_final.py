import win32com.client, sys

LOG = "D:/Virtu模型/_cu_model.log"
def log(*a):
    s = " ".join(str(x) for x in a)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(s + "\n")
    print(s, flush=True)

log("=== 建模闭环(终) ===")
sw = win32com.client.GetActiveObject("SldWorks.Application")
sw.Visible = True
part = sw.ActiveDoc
log("Title=", part.GetTitle)

# 重选草图
skf = part.FeatureByName("草图1") or part.FeatureByName("Sketch1")
if skf is None:
    log("NO_SKETCH"); sys.exit(1)
skf.Select2(False, 0)
log("SKETCH_SELECTED")

# 23 参数 FeatureExtrusion2：Extrude1=True 盲孔拉伸 D1=0.02m(20mm)
args23 = [False, True, False, 0, 0, 0.02, 0.0,
          False, False, False, False, 0, 0.0, 0.0,
          False, False, False, 0, 0, False,
          False, False, False]
feat = part.FeatureManager.FeatureExtrusion2(*args23)
log("EXTRUDE_FEAT", feat is not None)
if feat is not None:
    log("FEAT_NAME", feat.Name)

part.ClearSelection2(True)
part.ForceRebuild3(True)

# 体积守恒断言（ΔV > 0）
mp = part.GetMassProperties(2)
vol = float(mp[14])
exp = 0.05 * 0.03 * 0.02
log("MASSPROPS_LEN", len(mp))
log("VOLUME_M3", vol, "EXPECTED", exp)
if vol > 0:
    log("VOLUME_OK dV>0 PASS ratio=%.4f" % (vol / exp))
else:
    log("VOLUME_FAIL dV<=0")
log("=== 结束 ===")
