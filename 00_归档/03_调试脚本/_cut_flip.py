# -*- coding: utf-8 -*-
"""收尾验证：孔草图在 右视基准面(X=0)，实体沿 +X 延伸，切除方向必须翻进实体。

一次性遍历 Flip/Dir 与 27 参布局，用体积变化 ΔV 作为唯一判据。
成功即保存；失败如实报告，不再猜参数。
"""
import math
import os
import sys
import time

sys.path.insert(0, r"D:\Virtu模型")
import win32com.client as w
import pythoncom

pythoncom.CoInitialize()
try:
    sw = w.GetActiveObject("SldWorks.Application")
except Exception:
    sw = w.Dispatch("SldWorks.Application")
sw.Visible = True
part = sw.ActiveDoc
if not part:
    print("NO_ACTIVE_DOC")
    raise SystemExit(1)
print("DOC", part.GetTitle, flush=True)


def feats():
    out = []
    f = part.FirstFeature
    while f:
        out.append((f.Name, f.GetTypeName2))
        f = f.GetNextFeature
    return out


print("FEATS_BEFORE", feats(), flush=True)
V0 = part.GetMassProperties[3] * 1e9
print("V0 %.4f mm3" % V0, flush=True)

# ---- 定位或创建独立的 3×Ø7 @ PCD38 孔草图（右视基准面） ----
sketch_names = [n for n, t in feats() if t == "ProfileFeature"]
print("SKETCHES", sketch_names, flush=True)
skf = None
for n in reversed(sketch_names):
    ft = part.FeatureByName(n)
    try:
        sk = ft.GetSpecificFeature2
        arcs = sk.GetArcCount
    except Exception:
        arcs = -1
    print("  ", n, "arcs", arcs, flush=True)
    if arcs == 3:
        skf = ft
        break

if skf is None:
    print("CREATING_HOLE_SKETCH", flush=True)
    pl = part.FeatureByName("右视基准面")
    part.ClearSelection2(True)
    pl.Select2(False, 0)
    part.InsertSketch2(True)
    sm = part.SketchManager
    sm.AddToDB = True
    R_HOLE, R_PCD = 0.0035, 0.019
    for i in range(3):
        a = math.radians(120.0 * i)
        cx, cy = R_PCD * math.cos(a), R_PCD * math.sin(a)
        sm.CreateCircle(cx, cy, 0, cx + R_HOLE, cy, 0)
    print("  ARCS", sm.ActiveSketch.GetArcCount, flush=True)
    part.InsertSketch2(False)
    skf = part.FeatureByName([n for n, t in feats() if t == "ProfileFeature"][-1])
print("CUT_SKETCH", skf.Name, flush=True)

# ---- 27 参 FeatureCut4：base 与 Extrusion3 同构，S4 为多出的 4 个起始条件参数 ----
S4_VARIANTS = [
    [0, 0.0, False, 0.0],
    [0, 0, False, False],
    [1, 0.0, False, 0.0],
]
layouts = {
    "append": lambda b, s: b + s,
    "ins17": lambda b, s: b[:17] + s + b[17:],
    "ins18": lambda b, s: b[:18] + s + b[18:],
}

hit = None
for flip, direct in ((True, False), (False, True), (True, True), (False, False)):
    for t1, d1 in ((1, 0.0), (0, 0.05)):
        base = [True, flip, direct, t1, 0, d1, 0.0,
                False, False, False, False, 0.0, 0.0,
                False, False, False, False,
                False, True, True,
                False, True, True]
        for sname, s4 in [("s0", S4_VARIANTS[0]), ("s1", S4_VARIANTS[1])]:
            for lname, lf in layouts.items():
                args = lf(base, s4)
                if len(args) != 27:
                    continue
                tag = "F%dD%dT%d/%s/%s" % (flip, direct, t1, sname, lname)
                try:
                    part.ClearSelection2(True)
                    skf.Select2(False, 0)
                    r = part.FeatureManager.FeatureCut4(*args)
                    v = part.GetMassProperties[3] * 1e9
                    dv = V0 - v
                    print("  %-22s -> %-5r V=%.3f dV=%.3f" % (tag, bool(r), v, dv), flush=True)
                    if dv > 50:
                        hit = tag
                except Exception as e:
                    print("  %-22s ERR %s" % (tag, str(e)[:60]), flush=True)
                if hit:
                    break
            if hit:
                break
        if hit:
            break
    if hit:
        break

print("CUT_RESULT", hit or "FAILED", flush=True)
if hit:
    V = part.GetMassProperties[3] * 1e9
    # 3×Ø7 贯穿 12mm 盘体 (x=8..20)：3*pi/4*49*12 = 1385.4 mm3
    expect = 3 * math.pi / 4 * 7 ** 2 * 12
    print("FINAL_V %.4f mm3  dV %.4f  expect %.4f  err %.4f%%" %
          (V, V0 - V, expect, abs((V0 - V) - expect) / expect * 100), flush=True)
    print("FEATS_AFTER", feats(), flush=True)
    OUT = r"D:\Virtu模型\jilunmo_final.SLDPRT"
    try:
        part.SaveAs3(OUT, 0, 1)
        time.sleep(1)
        print("SAVED", os.path.exists(OUT), os.path.getsize(OUT) if os.path.exists(OUT) else 0, flush=True)
    except Exception as e:
        print("SAVE_ERR", str(e)[:80], flush=True)
