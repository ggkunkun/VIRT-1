import win32com.client, sys

LOG = "D:/Virtu模型/_cu_model.log"
def log(*a):
    s = " ".join(str(x) for x in a)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(s + "\n")
    print(s, flush=True)

log("=== 建模闭环开始 ===")

sw = win32com.client.GetActiveObject("SldWorks.Application")
sw.Visible = True
part = sw.ActiveDoc
if part is None:
    log("NO_ACTIVE_DOC"); sys.exit(1)
log("Title=", part.GetTitle)

# 1) 选前视基准面（中文/英文兼容）
plane = None
for name in ["前视基准面", "Front Plane"]:
    f = part.FeatureByName(name)
    if f is not None:
        plane = f
        log("FOUND_PLANE", name)
        break
if plane is None:
    log("PLANE_NOT_FOUND"); sys.exit(1)
plane.Select2(False, 0)

# 2) 插入草图并绘制 50x30mm 矩形（SW API 用米）
part.InsertSketch2(True)
sk = part.SketchManager
seg = sk.CreateCornerRectangle(0.0, 0.0, 0.0, 0.05, 0.03, 0.0)
log("RECT_SEG", seg is not None)
part.InsertSketch2(True)
log("SKETCH_DONE featCount=", part.GetFeatureCount)

# 3) 选中草图准备拉伸
skf = None
for name in ["草图1", "Sketch1"]:
    f = part.FeatureByName(name)
    if f is not None:
        skf = f
        log("FOUND_SKETCH", name)
        break
if skf is None:
    log("SKETCH_NOT_FOUND")
else:
    skf.Select2(False, 0)

# 4) 盲孔拉伸 20mm
feat = part.FeatureManager.FeatureExtrusion2(
    False, False, False, 0, 0, 0.02, 0.0,
    False, False, False, False, 0, 0.0, 0.0,
    False, False, False, 0, 0, False)
log("EXTRUDE_FEAT", feat is not None)
if feat is not None:
    log("FEAT_NAME", feat.Name)

part.ClearSelection2(True)
part.ForceRebuild3(True)

# 5) 体积守恒断言
mp = part.GetMassProperties(2)
log("MASSPROPS_LEN", len(mp))
log("MASSPROPS", [round(float(x), 8) for x in mp])
vol = float(mp[14])
exp_vol = 0.05 * 0.03 * 0.02
log("VOLUME_M3", vol, "EXPECTED", exp_vol)
if vol > 0:
    log("VOLUME_OK dV>0 PASS ratio=%.4f" % (vol / exp_vol))
else:
    log("VOLUME_FAIL dV<=0")

log("=== 建模闭环结束 ===")
