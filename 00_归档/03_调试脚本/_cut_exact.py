# -*- coding: utf-8 -*-
"""用 sldworks.tlb 读到的 FeatureCut4 真实 27 参签名切 3×Ø7 孔。

参数名（IFeatureManager::FeatureCut4, SW2021）:
  Sd, Flip, Dir, T1, T2, D1, D2, Dchk1, Dchk2, Ddir1, Ddir2, Dang1, Dang2,
  OffsetReverse1, OffsetReverse2, TranslateSurface1, TranslateSurface2,
  NormalCut, UseFeatScope, UseAutoSelect, AssemblyFeatureScope, AutoSelectComponents,
  PropagateFeatureToParts, T0, StartOffset, FlipStartOffset, OptimizeGeometry

孔草图在 右视基准面(X=0)，实体沿 +X 延伸至 40mm，故切除方向可能需要翻转。
唯一判据：切除前后体积差 ΔV（3×Ø7 贯穿 12mm 盘体 ≈ 1385.4 mm³）。
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
    print("NO_ACTIVE_DOC", flush=True)
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

# ---- 定位 3 圆弧的独立孔草图；没有则新建 ----
sketch_names = [n for n, t in feats() if t == "ProfileFeature"]
skf = None
for n in reversed(sketch_names):
    ft = part.FeatureByName(n)
    try:
        arcs = ft.GetSpecificFeature2.GetArcCount
    except Exception:
        arcs = -1
    print("  SKETCH", n, "arcs", arcs, flush=True)
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


def cut_args(flip, direct, t1, d1):
    """严格按 TLB 参数名顺序构造 27 参。"""
    return [
        True,          # Sd: single ended
        flip,          # Flip: 翻转切除方向
        direct,        # Dir
        t1, 0,         # T1/T2: 0=Blind, 1=ThroughAll
        d1, 0.0,       # D1/D2 深度(m)
        False, False, False, False, 0.0, 0.0,   # Dchk1/2, Ddir1/2, Dang1/2
        False, False, False, False,             # OffsetReverse1/2, TranslateSurface1/2
        False,         # NormalCut
        True,          # UseFeatScope
        True,          # UseAutoSelect
        False,         # AssemblyFeatureScope
        True,          # AutoSelectComponents
        True,          # PropagateFeatureToParts
        0,             # T0: 起始条件 = 草图基准面
        0.0,           # StartOffset
        False,         # FlipStartOffset
        False,         # OptimizeGeometry
    ]


hit = None
for flip, direct in ((False, False), (True, False), (False, True), (True, True)):
    for t1, d1 in ((1, 0.0), (0, 0.05), (0, 0.1)):
        args = cut_args(flip, direct, t1, d1)
        assert len(args) == 27, len(args)
        tag = "Flip%d Dir%d T%d D%.3f" % (flip, direct, t1, d1)
        try:
            part.ClearSelection2(True)
            skf.Select2(False, 0)
            r = part.FeatureManager.FeatureCut4(*args)
            v = part.GetMassProperties[3] * 1e9
            dv = V0 - v
            print("  %-24s -> %-5r V=%.3f dV=%.3f" % (tag, bool(r), v, dv), flush=True)
            if dv > 50:
                hit = tag
        except Exception as e:
            print("  %-24s ERR %s" % (tag, str(e)[:70]), flush=True)
        if hit:
            break
    if hit:
        break

print("CUT_RESULT", hit or "FAILED", flush=True)
mp = part.GetMassProperties
V = mp[3] * 1e9
print("FINAL_V %.4f mm3  dV %.4f  A %.4f mm2" % (V, V0 - V, mp[4] * 1e6), flush=True)
print("FEATS_AFTER", feats(), flush=True)
print("BODIES", len(part.GetBodies2(0, True) or []), flush=True)

OUT = r"D:\Virtu模型\jilunmo_final.SLDPRT"
try:
    if os.path.exists(OUT):
        os.remove(OUT)
    part.SaveAs3(OUT, 0, 1)
    time.sleep(1)
    print("SAVED", OUT, os.path.exists(OUT),
          os.path.getsize(OUT) if os.path.exists(OUT) else 0, flush=True)
except Exception as e:
    print("SAVE_ERR", str(e)[:90], flush=True)
