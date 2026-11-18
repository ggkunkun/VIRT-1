import win32com.client
sw = win32com.client.GetActiveObject("SldWorks.Application")
fm = sw.ActiveDoc.FeatureManager
ole = fm._oleobj_
try:
    ti = ole.GetTypeInfo(0)
except Exception as e:
    print("GetTypeInfo(0) err:", e)
    ti = None
if ti is None:
    try:
        ti = ole.GetTypeInfo()
    except Exception as e:
        print("GetTypeInfo() err:", e)
        raise SystemExit(1)
ta = ti.GetTypeAttr()
print("cFuncs=", ta.cFuncs, "iid=", ta.iid)
for i in range(ta.cFuncs):
    fd = ti.GetFuncDesc(i)
    nm = ti.GetNames(fd.memid)[0]
    if "Extrusion" in nm:
        print("METHOD", nm, "cParams=", fd.cParams, "cParamsOpt=", fd.cParamsOpt)
