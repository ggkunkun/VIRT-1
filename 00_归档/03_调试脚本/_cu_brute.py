import win32com.client, sys

LOG = "D:/Virtu模型/_cu_model.log"
def log(*a):
    s = " ".join(str(x) for x in a)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(s + "\n")
    print(s, flush=True)

sw = win32com.client.GetActiveObject("SldWorks.Application")
part = sw.ActiveDoc
sk = part.FeatureByName("草图5") or part.FeatureByName("草图4") or part.FeatureByName("草图3")
if sk is None:
    log("NO_SKETCH"); sys.exit(1)
log("SKETCH", sk.Name)

found = False
for e_idx in (1, 0, 2, 3, 4):
    for d_idx in range(3, 23):
        if d_idx == e_idx:
            continue
        args = [False] * 23
        args[e_idx] = True
        args[d_idx] = 0.02
        try:
            sk.Select2(False, 0)
            f = part.FeatureManager.FeatureExtrusion2(*args)
        except Exception:
            continue
        if f is None:
            continue
        # 检查是否有体积
        try:
            mp = part.GetMassProperties
            vol = float(mp[14]) if mp else 0.0
        except Exception:
            vol = 0.0
        if vol > 0:
            log("SUCCESS e_idx=%d d_idx=%d vol=%.8f name=%s" % (e_idx, d_idx, vol, f.Name))
            part.ClearSelection2(True)
            part.ForceRebuild3(True)
            part.ViewZoomtofit2()
            log("VOLUME_M3", vol, "EXPECTED", 0.05*0.03*0.02)
            log("VOLUME_OK dV>0 PASS")
            found = True
            raise SystemExit(0)
        else:
            # 无效特征，删除后继续
            try:
                f.Select2(False, 0)
                part.EditDelete()
            except Exception:
                pass
if not found:
    log("NO_COMBO_WORKED")
