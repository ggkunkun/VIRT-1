import win32com.client.gencache, pythoncom, subprocess, time, math

LIBID = '{83A33D31-27C5-11CE-BFD4-00400513BB57}'
MOD = win32com.client.gencache.EnsureModule(LIBID, 0, 29, 0)


def connect_sw():
    subprocess.run(["taskkill", "/F", "/IM", "SLDWORKS.exe"], capture_output=True)
    time.sleep(8)
    subprocess.Popen([r"D:\SOLIDWORKS (2)\SLDWORKS.exe"])
    sw = None
    for i in range(120):
        time.sleep(2)
        try:
            sw = win32com.client.GetActiveObject("SldWorks.Application.29")
            print("connected @ %ds" % (i * 2)); return sw
        except Exception:
            if i in (40, 80):
                try:
                    subprocess.Popen([r"D:\SOLIDWORKS (2)\SLDWORKS.exe"])
                except Exception:
                    pass
    return None


sw = connect_sw()
if sw is None:
    raise SystemExit("无法连接 SOLIDWORKS")
sw.Visible = True
try:
    sw.CloseAllDocuments(True)
except Exception:
    pass
m = sw.NewDocument(r"D:\SOLIDWORKS (2)\lang\chinese\Tutorial\part.prtdot", 0, 0.0, 0.0)
print("m type:", type(m))

# 直接用 gen_py 的 IModelDoc2 接口类包装底层 IDispatch，绕开名义类型限制
try:
    md = MOD.IModelDoc2(m._oleobj_)
    print("包装为 IModelDoc2 OK:", type(md))
except Exception as e:
    print("包装 ERR:", e)
    md = m

md.SketchManager.InsertSketch(True)
md.SketchManager.CreateCircleByRadius2(0.0, 0.0, 0.0, 0.06)
md.SketchManager.CreateCircleByRadius2(0.0, 0.0, 0.0, 0.02)
md.SketchManager.InsertSketch(True)
feat = md.FeatureManager.FeatureExtrusion2(
    True, False, False, 0, 0, 0.02, 0.0, False, False, 0.0, 0.0,
    False, False, False, False, False, False, 0, 0.0, 0.0)
print("extrude:", "OK" if feat else "FAIL")

md.SketchManager.InsertSketch(True)
for i in range(6):
    a = 2.0 * math.pi * i / 6
    md.SketchManager.CreateCircleByRadius2(0.0475 * math.cos(a), 0.0475 * math.sin(a), 0.0, 0.006)
md.SketchManager.InsertSketch(True)
cut = md.FeatureManager.FeatureCut3(
    True, False, False, 1, 0, 0.0, 0.0, False, False, 0.0, 0.0,
    False, False, False, False, False, False, False, False, False, 0, 0.0, 0.0)
print("cut:", "OK" if cut else "FAIL")

try:
    eqn = md.GetEquationMgr()
    for k, v in [("D_Outer", 0.12), ("D_Bore", 0.04), ("Thk", 0.02),
                 ("N", 6), ("D_Bolt", 0.012), ("PCD", 0.095)]:
        eqn.AddEquation('"%s" = %s' % (k, v))
    print("eqn count:", eqn.GetCount())
except Exception as e:
    print("eqn warn:", e)

md.ForceRebuild3(True)
code = md.SaveAs3(r"D:\Virtu模型\Flange_Parametric.SLDPRT", 0, 0)
print("save code:", code)
print("DONE")
