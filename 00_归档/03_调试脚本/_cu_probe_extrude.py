import win32com.client, sys

sw = win32com.client.GetActiveObject("SldWorks.Application")
part = sw.ActiveDoc
fm = part.FeatureManager
skf = part.FeatureByName("草图1") or part.FeatureByName("Sketch1")
skf.Select2(False, 0)

def call(method, args, label):
    try:
        f = getattr(fm, method)
        r = f(*args)
        print("OK   ", label, "n=", len(args), "ret", r is not None)
        return r
    except Exception as e:
        msg = repr(e)
        print("FAIL ", label, "n=", len(args), "err", msg[:60])
        return None

base20 = [False, False, False, 0, 0, 0.02, 0.0, False, False, False, False, 0, 0.0, 0.0, False, False, False, 0, 0, False]

for n in (20, 21, 22, 23, 24, 25, 26):
    args = base20[:n] if n <= 20 else base20 + [False]*(n-20)
    r = call("FeatureExtrusion2", args, "FE2_%d" % n)
    if r is not None:
        print(">>> FeatureExtrusion2 OK with", n, "args")
        break

# 若仍失败，试 FeatureExtrusion3 22 参数
args3 = [1, True, False, True, False, 0, False, 0, 0, 0.02, False, False, 0, 0.0, False, False, False, False, True, False, False, True]
call("FeatureExtrusion3", args3, "FE3_22")
