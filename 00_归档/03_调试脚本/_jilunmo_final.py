# -*- coding: utf-8 -*-
"""机轮模最终收尾：单进程纯 COM 从头重建 -> 旋转 -> 精确 FeatureCut4 切 3×Ø7 -> 保存。

FeatureCut4 的 27 参来自 pythoncom.LoadTypeLib(sldworks.tlb) 读出的真实签名，
不再靠猜布局。判据只有体积差 ΔV。
"""
import math
import os
import sys
import time

import win32com.client as w
import pythoncom

OUT = r"D:\Virtu模型\jilunmo_final.SLDPRT"

OUTER = [(0, 11.5), (1, 12.5), (8, 12.5), (8, 25.5), (9, 26.5),
         (19, 26.5), (20, 25.5), (20, 12.5), (25, 12.5), (40, 10.0)]
INNER = [(40, 4.5), (38.5, 4.5), (38.5, 3.0), (1.5, 3.0), (1.5, 4.5), (0, 4.5)]
PROFILE = OUTER + INNER

V_BODY = 37404.5875                        # mm3 旋转体解析值（上一轮已验证）
V_HOLES = 3 * math.pi * 3.5 ** 2 * 12.0    # 3×Ø7 贯穿 x=8..20 盘体
V_TARGET = V_BODY - V_HOLES
print("THEORY V_BODY %.4f  V_HOLES %.4f  V_TARGET %.4f mm3" %
      (V_BODY, V_HOLES, V_TARGET), flush=True)

pythoncom.CoInitialize()
try:
    sw = w.GetActiveObject("SldWorks.Application")
    print("COM GetActiveObject", flush=True)
except Exception:
    sw = w.Dispatch("SldWorks.Application")
    print("COM Dispatch", flush=True)
sw.Visible = True

doc = None
try:
    doc = sw.NewPart()
except Exception as e:
    print("NewPart raised (doc may still exist):", str(e)[:70], flush=True)
part = doc or sw.ActiveDoc
if not part:
    print("NO_DOC"); raise SystemExit(1)
print("DOC", part.GetTitle, flush=True)


def feats():
    out = []
    f = part.FirstFeature
    while f:
        out.append((f.Name, f.GetTypeName2))
        f = f.GetNextFeature
    return out


# ---------- 1. 旋转母线 ----------
plane = part.FeatureByName("前视基准面")
part.ClearSelection2(True)
plane.Select2(False, 0)
part.InsertSketch2(True)
sm = part.SketchManager
sm.AddToDB = True
for i in range(len(PROFILE)):
    x1, y1 = PROFILE[i]
    x2, y2 = PROFILE[(i + 1) % len(PROFILE)]
    sm.CreateLine(x1 / 1000, y1 / 1000, 0, x2 / 1000, y2 / 1000, 0)
sm.CreateCenterLine(0, 0, 0, 0.040, 0, 0)
print("SK1_LINES", sm.ActiveSketch.GetLineCount, flush=True)
part.InsertSketch2(False)

sk1 = part.FeatureByName("草图1")
part.ClearSelection2(True)
sk1.Select2(False, 0)
REV = [True, True, False, False, False, False,
       0, 0, 2 * math.pi, 0,
       False, False, 0.0, 0.0,
       0, 0.0, 0.0, True, True, True]
print("REVOLVE", bool(part.FeatureManager.FeatureRevolve2(*REV)), flush=True)
V0 = part.GetMassProperties[3] * 1e9
print("V_AFTER_REVOLVE %.4f mm3 (theory %.4f, err %.4f%%)" %
      (V0, V_BODY, abs(V0 - V_BODY) / V_BODY * 100), flush=True)

# ---------- 2. 3×Ø7 @ PCD38 孔草图（右视基准面，X=0） ----------
pl2 = part.FeatureByName("右视基准面")
part.ClearSelection2(True)
pl2.Select2(False, 0)
part.InsertSketch2(True)
sm.AddToDB = True
R_HOLE, R_PCD = 0.0035, 0.019
for i in range(3):
    a = math.radians(120.0 * i)
    cx, cy = R_PCD * math.cos(a), R_PCD * math.sin(a)
    sm.CreateCircle(cx, cy, 0, cx + R_HOLE, cy, 0)
print("SK2_ARCS", sm.ActiveSketch.GetArcCount, flush=True)
part.InsertSketch2(False)
sks = [n for n, t in feats() if t == "ProfileFeature"]
print("SKETCHES", sks, "INDEPENDENT", len(sks) >= 2, flush=True)
skf = part.FeatureByName(sks[-1])


# ---------- 3. FeatureCut4 真实 27 参 ----------
def cut_args(flip, direct, t1, d1):
    # 顺序严格对应 TLB：
    # Sd,Flip,Dir,T1,T2,D1,D2, Dchk1,Dchk2,Ddir1,Ddir2,Dang1,Dang2,
    # OffsetReverse1,OffsetReverse2,TranslateSurface1,TranslateSurface2,
    # NormalCut,UseFeatScope,UseAutoSelect,AssemblyFeatureScope,AutoSelectComponents,
    # PropagateFeatureToParts,T0,StartOffset,FlipStartOffset,OptimizeGeometry
    return [
        True, flip, direct, t1, 0, d1, 0.0,
        False, False, False, False, 0.0, 0.0,
        False, False, False, False,
        False, True, True,
        False, True, True,
        0, 0.0, False, False,
    ]


# 上一轮已实测命中：Dir=True（反向切进 +X 实体）+ T1=1 完全贯穿。
# 放在首位一次命中，避免多余 COM 调用消耗内存；保留兜底组合但不盲试。
COMBOS = [(False, True, 1, 0.0), (True, True, 1, 0.0),
          (False, True, 0, 0.05), (True, True, 0, 0.05),
          (False, False, 1, 0.0), (True, False, 1, 0.0)]
hit = None
for flip, direct, t1, d1 in COMBOS:
    args = cut_args(flip, direct, t1, d1)
    assert len(args) == 27
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

print("CUT_RESULT", hit or "FAILED", flush=True)

# ---------- 4. 量化验证 + 保存 ----------
mp = part.GetMassProperties
V, A = mp[3] * 1e9, mp[4] * 1e6
print("FINAL_V %.4f mm3  FINAL_A %.4f mm2" % (V, A), flush=True)
print("BODIES", len(part.GetBodies2(0, True) or []), flush=True)
try:
    box = part.GetBodies2(0, True)[0].GetBodyBox()
    print("BBOX mm", " ".join("%.4f" % (v * 1000) for v in box), flush=True)
except Exception as e:
    print("BBOX_ERR", str(e)[:70], flush=True)
print("FEATS", feats(), flush=True)
err = abs(V - (V_TARGET if hit else V_BODY)) / (V_TARGET if hit else V_BODY) * 100
print("ERR_VS_THEORY %.6f%%  ASSERT_DV %s" %
      (err, "PASS" if hit and err < 0.1 else "FAIL"), flush=True)

part.ClearSelection2(True)
# 关键：保存前不做任何视图/图形重绘。上一轮 ShowNamedView2+ViewZoomtofit2
# 之后 SW 在 SaveAs3 期间崩溃，磁盘只留下 0 字节空壳。
if os.path.exists(OUT):
    os.remove(OUT)
saved_ok = False
for attempt in (1, 2, 3):
    try:
        part.SaveAs3(OUT, 0, 1)
        time.sleep(1.5)
        size = os.path.getsize(OUT) if os.path.exists(OUT) else 0
        head = open(OUT, "rb").read(8) if size else b""
        # SW2021 .SLDPRT 是自定义容器：[4字节CRC] + 00 00 00 04，不是 OLE2 复合文档。
        # 已验证可打开的 flange/jilunmo_revolve 文件头同为此格式，勿用 D0CF11E0 判定。
        is_sw = head[4:8] == b"\x00\x00\x00\x04"
        print("SAVE_TRY %d  size=%d  head=%s  SWFMT=%s" %
              (attempt, size, head[:8].hex(), is_sw), flush=True)
        if size > 10000 and is_sw:
            saved_ok = True
            break
    except Exception as e:
        print("SAVE_ERR %d %s" % (attempt, str(e)[:90]), flush=True)
print("SAVED_OK", saved_ok, "TITLE", part.GetTitle, flush=True)
