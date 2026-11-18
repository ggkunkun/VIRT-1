# -*- coding: utf-8 -*-
"""独立复核：把落盘的 SLDPRT 复制成新文件名后让 SW 从磁盘重新打开，读回质量属性。"""
import os
import shutil

import win32com.client as w
import pythoncom

SRC = r"D:\Virtu模型\jilunmo_final.SLDPRT"
COPY = r"D:\Virtu模型\_verify_reopen.SLDPRT"

pythoncom.CoInitialize()
try:
    sw = w.GetActiveObject("SldWorks.Application")
except Exception:
    sw = w.Dispatch("SldWorks.Application")
sw.Visible = True
print("FILE", os.path.exists(SRC), os.path.getsize(SRC), flush=True)

if os.path.exists(COPY):
    os.remove(COPY)
shutil.copy2(SRC, COPY)
print("COPY", os.path.getsize(COPY), flush=True)


def errvar():
    return w.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)


doc = None
for label, fn in (
    ("OpenDoc6", lambda: sw.OpenDoc6(COPY, 1, 0, "", errvar(), errvar())),
    ("LoadFile4", lambda: sw.LoadFile4(COPY, "", None, errvar())),
    ("LoadFile2", lambda: sw.LoadFile2(COPY, "")),
):
    try:
        doc = fn()
        print(label, "->", bool(doc), flush=True)
        if doc:
            break
    except Exception as e:
        print(label, "ERR", type(e).__name__, str(e)[:110], flush=True)

if not doc:
    print("REOPEN_FAILED", flush=True)
    raise SystemExit(1)

print("TITLE", doc.GetTitle, flush=True)
mp = doc.GetMassProperties
print("V_mm3 %.4f  A_mm2 %.4f  M_kg %.6f" % (mp[3] * 1e9, mp[4] * 1e6, mp[5]), flush=True)
fs = []
f = doc.FirstFeature
while f:
    if f.GetTypeName2 in ("ProfileFeature", "Revolution", "ICE", "Cut", "Extrusion"):
        fs.append((f.Name, f.GetTypeName2))
    f = f.GetNextFeature
print("FEATS", fs, flush=True)
print("BODIES", len(doc.GetBodies2(0, True) or []), flush=True)
try:
    box = doc.GetBodies2(0, True)[0].GetBodyBox()
    print("BBOX mm", " ".join("%.4f" % (v * 1000) for v in box), flush=True)
except Exception as e:
    print("BBOX_ERR", str(e)[:70], flush=True)

V = mp[3] * 1e9
print("ASSERT_REOPEN_VOLUME", "PASS" if abs(V - 36019.1451) < 0.01 else "FAIL", flush=True)
try:
    doc.ShowNamedView2("*Isometric", 7)
    doc.ViewZoomtofit2()
    print("VIEW_ISO_OK", flush=True)
except Exception as e:
    print("VIEW_ERR", str(e)[:70], flush=True)
