# -*- coding: utf-8 -*-
"""最终独立复核：审计模型运行期间的产物，并从磁盘重新打开装配体与工程图读回证据。"""
import glob
import json
import os
import shutil
import time

import win32com.client as w
import pythoncom

ROOT = r"D:\Virtu模型"
BASE = os.path.join(ROOT, "runs", "virtu_assembly_baseline.json")
EXT = (".sldprt", ".sldasm", ".slddrw")

import datetime
base = json.load(open(BASE, encoding="utf-8"))
# 分界用「基线捕获时刻」：之前的产物一律算工具自测，不混算成模型成果
cut = datetime.datetime.strptime(base["captured_at"], "%Y-%m-%d %H:%M:%S").timestamp()

print("=== ARTIFACT AUDIT (newer than tool-selftest baseline) ===")
found = []
for p in glob.glob(os.path.join(ROOT, "**", "*"), recursive=True):
    if not os.path.isfile(p) or os.path.splitext(p)[1].lower() not in EXT:
        continue
    st = os.stat(p)
    rel = os.path.relpath(p, ROOT)
    bm = base["files"].get(os.path.basename(p), {})
    changed = st.st_mtime > cut
    found.append({"path": rel, "size": st.st_size,
                  "mtime": time.strftime("%H:%M:%S", time.localtime(st.st_mtime)),
                  "model_run_touched": bool(changed)})
for f in sorted(found, key=lambda x: -os.path.getsize(os.path.join(ROOT, x["path"]))):
    print("  %-58s %9d B  %s  %s" %
          (f["path"], f["size"], f["mtime"],
           "MODEL-RUN" if f["model_run_touched"] else "pre-existing"))
print("TOTAL", len(found), "MODEL_RUN_TOUCHED",
      sum(1 for f in found if f["model_run_touched"]))

pythoncom.CoInitialize()
try:
    sw = w.GetActiveObject("SldWorks.Application")
except Exception:
    sw = w.Dispatch("SldWorks.Application")
sw.Visible = True


def ev():
    return w.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)


def open_doc(path, dtype=1):
    """复制成新文件名再打开，确保是真正从磁盘解析，而非复用内存里的文档。

    dtype: 1=part, 2=assembly, 3=drawing (swDocumentTypes_e)
    """
    if not os.path.exists(path):
        print("  MISSING", path)
        return None
    stem, ext = os.path.splitext(os.path.basename(path))
    cp = os.path.join(ROOT, "_verify_" + stem + ext)
    shutil.copy2(path, cp)
    for label, fn in (
        ("OpenDoc6", lambda: sw.OpenDoc6(cp, dtype, 0, "", ev(), ev())),
        ("LoadFile2", lambda: sw.LoadFile2(cp, "")),
    ):
        try:
            d = fn()
            if d:
                print("  OPENED_BY", label, "TYPE_ARG", dtype)
                return d
        except Exception as e:
            print("  ", label, "ERR", type(e).__name__, str(e)[:80])
    return None


# 模型本轮自己指定的输出目录（不是监督器预设的 runs/virtu_assembly）
dirn = os.path.join(ROOT, "works")
asm = os.path.join(dirn, "wheel_mold_assembly.SLDASM")
drw = os.path.join(dirn, "wheel_mold_assembly.SLDDRW")
prt = os.path.join(dirn, "jilunmo_param.SLDPRT")

print("\n=== ASSEMBLY REOPEN ===")
d = open_doc(asm, 2)
if d:
    print("  TITLE", d.GetTitle, "TYPE", d.GetType)
    try:
        cs = d.GetComponents(False) or []
        print("  COMPONENTS", len(cs))
        for c in cs[:8]:
            print("    -", c.Name2)
    except Exception as e:
        print("  COMP_ERR", str(e)[:80])
    try:
        mp = d.GetMassProperties
        print("  V_cm3 %.4f  A_cm2 %.4f  M_kg %.6f" % (mp[3] * 1e6, mp[4] * 1e4, mp[5]))
    except Exception as e:
        print("  MP_ERR", str(e)[:80])

print("\n=== DRAWING REOPEN ===")
g = open_doc(drw, 3)
if g:
    print("  TITLE", g.GetTitle, "TYPE", g.GetType)
    try:
        print("  VIEW_COUNT", g.GetViewCount())
    except Exception as e:
        print("  COUNT_ERR", str(e)[:80])
    try:
        v = g.GetFirstView()
        names, guard = [], 0
        while v and guard < 20:
            guard += 1
            try:
                names.append(v.GetName2())
            except Exception:
                names.append(v.Name)
            v = v.GetNextView()   # 是方法，不是属性
        print("  VIEWS", names)
    except Exception as e:
        print("  ENUM_ERR", str(e)[:90])

print("\n=== PARAMETRIC PART REOPEN ===")
p = open_doc(prt)
if p:
    print("  TITLE", p.GetTitle)
    try:
        mp = p.GetMassProperties
        print("  V_mm3 %.4f  A_mm2 %.4f" % (mp[3] * 1e9, mp[4] * 1e6))
    except Exception as e:
        print("  MP_ERR", str(e)[:80])
    fs = []
    f = p.FirstFeature
    while f:
        if f.GetTypeName2 in ("ProfileFeature", "Revolution", "ICE"):
            fs.append((f.Name, f.GetTypeName2))
        f = f.GetNextFeature
    print("  FEATS", fs)
