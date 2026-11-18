import win32com.client, sys

LOG = "D:/Virtu模型/_cu_model.log"
def log(*a):
    s = " ".join(str(x) for x in a)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(s + "\n")
    print(s, flush=True)

log("=== 早期绑定拉伸开始 ===")
sw = win32com.client.GetActiveObject("SldWorks.Application")
try:
    sw = win32com.client.gencache.EnsureDispatch(sw)
    log("EARLY_BIND_OK")
except Exception as e:
    log("EARLY_BIND_FAIL", repr(e))

part = sw.ActiveDoc
if part is None:
    log("NO_ACTIVE_DOC"); sys.exit(1)
log("Title=", part.GetTitle)

# 选草图1
skf = None
for name in ["草图1", "Sketch1"]:
    f = part.FeatureByName(name)
    if f is not None:
        skf = f; log("FOUND_SKETCH", name); break
if skf is None:
    log("SKETCH_NOT_FOUND"); sys.exit(1)
skf.Select2(False, 0)

# 盲孔拉伸 20mm（早期绑定按真实签名转换类型）
try:
    feat = part.FeatureManager.FeatureExtrusion2(
        False, False, False, 0, 0, 0.02, 0.0,
        False, False, False, False, 0, 0.0, 0.0,
        False, False, False, 0, 0, False)
    log("EXTRUDE_FEAT", feat is not None)
    if feat is not None:
        log("FEAT_NAME", feat.Name)
except Exception as e:
    log("EXTRUDE_ERR", repr(e))
    feat = None

if feat is not None:
    part.ClearSelection2(True)
    part.ForceRebuild3(True)
    mp = part.GetMassProperties(2)
    vol = float(mp[14])
    exp = 0.05*0.03*0.02
    log("VOLUME_M3", vol, "EXPECTED", exp)
    log("VOLUME_OK dV>0" if vol > 0 else "VOLUME_FAIL")
log("=== 结束 ===")
