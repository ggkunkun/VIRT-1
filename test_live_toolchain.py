# -*- coding: utf-8 -*-
"""
测试 Agent 工具链：连到【用户已手动打开】的 SOLIDWORKS 实例（或自行启动），
用 COM 自动化建参数化法兰盘（单草图 + 单拉伸，内部轮廓自动成孔）。
- 用 Late Binding（动态调度）绕过 gen_py 对 FeatureExtrusion2 的截断签名（实际 28 参）。
- 不预选基准面（中文界面 SelectByID2 选面不可靠），直接 InsertSketch 落默认前视基准面。
- 单位：读实际长度单位后换算，避免模板单位(米/毫米)歧义。
"""
import win32com.client, pythoncom, math, sys, time, subprocess

LIBID = "{83A33D31-27C5-11CE-BFD4-00400513BB57}"
EXE = r"D:\SOLIDWORKS (2)\SLDWORKS.exe"
# 以用户桌面上的 零件2.SLDPRT 为中文模板/基准（避免 COM 下回退英文默认模板）
TEMPLATE = r"C:\Users\Administrator\Desktop\零件2.SLDPRT"
OUT = r"C:\Users\Administrator\Desktop\Flange_Parametric.SLDPRT"

# 法兰参数（以毫米为基准）
D_Outer, D_Bore, Thk = 120.0, 40.0, 20.0
N, D_Bolt, PCD = 6, 12.0, 95.0

def log(s):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), s), flush=True)

def connect_sw():
    progs = ("SldWorks.Application.29", "SldWorks.Application")
    for attempt in range(30):
        for prog in progs:
            try:
                sw = win32com.client.GetActiveObject(prog)
                if sw:
                    log("  [尝试%d] 已连接活实例: %s" % (attempt + 1, prog))
                    return sw
            except Exception:
                pass
        if attempt == 0:
            log("  等待 SW 完成 COM 注册（每 3s 重试）...")
        time.sleep(3)
    log("  直连超时，Popen 自行启动 SW ...")
    subprocess.Popen([EXE])
    for attempt in range(40):
        for prog in progs:
            try:
                sw = win32com.client.GetActiveObject(prog)
                if sw:
                    log("  [Popen后%d] 已连接: %s" % (attempt + 1, prog))
                    return sw
            except Exception:
                pass
        time.sleep(3)
    return None

def main():
    log("Step0 连接 SOLIDWORKS 实例 ...")
    sw = connect_sw()
    if not sw:
        log("ERROR 拿不到 SW 实例，退出")
        return 1

    try:
        log("Step1 SW RevNumber: %s" % sw.RevisionNumber())
    except Exception as e:
        log("  读版本异常(忽略): %s" % e)

    log("Step2 以 零件2.SLDPRT 为模板新建文档 ...")
    try:
        sw.NewDocument(TEMPLATE, 0, 0.0, 0.0)
    except Exception as e:
        log("  NewDocument 失败(%s)，改为直接打开 零件2 ..." % e)
        try:
            sw.OpenDoc6(TEMPLATE, 1, 1, "", 0, 0)   # 1=swDocPART
        except Exception as e2:
            log("  OpenDoc6 失败(%s)，再试 OpenDoc ..." % e2)
            sw.OpenDoc(TEMPLATE, 1)
    m = sw.ActiveDoc
    if not m:
        log("ERROR ActiveDoc 为空")
        return 1
    # Late Binding：动态对象，不受 gen_py 截断签名限制
    md = m
    log("  文档对象(late binding)就绪")

    # 单位：先尝试强制设为毫米；读不准则按“毫米/文档单位”换算
    try:
        md.SetLengthUnit(0, 2)          # 2 = swMM
        log("  已强制设置为毫米(mm)")
    except Exception as e:
        log("  SetLengthUnit 不可用(%s)，改为读取实际单位换算" % str(e)[:60])
    try:
        u = md.LengthUnit
    except Exception:
        u = 2
    # 每个“文档单位”等于多少毫米
    UNIT_MM = {0: 25.4, 1: 304.8, 2: 1.0, 3: 10.0, 4: 1000.0}
    mm_per_unit = UNIT_MM.get(u, 1.0)
    log("  单位代码=%s -> 1 文档单位 = %g mm" % (u, mm_per_unit))
    R_Outer = (D_Outer/2) / mm_per_unit
    R_Bore  = (D_Bore/2)  / mm_per_unit
    R_Bolt  = (D_Bolt/2)  / mm_per_unit
    R_PCD   = (PCD/2)    / mm_per_unit
    DEPTH   = Thk        / mm_per_unit

    log("Step3 进入草图（默认前视基准面，无需预选面）...")
    md.SketchManager.InsertSketch(True)

    log("Step4 画草图：外圆 + 中心孔 + %d 螺栓孔（md.CreateCircle2）..." % N)
    md.CreateCircle2(0.0, 0.0, 0.0, R_Outer, 0.0, 0.0)
    md.CreateCircle2(0.0, 0.0, 0.0, R_Bore, 0.0, 0.0)
    for i in range(N):
        ang = 2 * math.pi * i / N
        cx, cy = R_PCD * math.cos(ang), R_PCD * math.sin(ang)
        md.CreateCircle2(cx, cy, 0.0, cx + R_Bolt, cy, 0.0)
    log("  草图：%d 个圆已下发" % (2 + N))

    log("Step5 退出草图 ...")
    md.SketchManager.InsertSketch(True)

    log("Step6 拉伸（盲孔，深度 %g，内部轮廓自动成孔）..." % DEPTH)
    # FeatureExtrusion2 实际 28 参数；第19个 Bodies 用 pythoncom.Missing 占位
    feat = md.FeatureManager.FeatureExtrusion2(
        True, False, False,        # 1-3  Sd, Flip, Dir
        0, 0, DEPTH, 0.0,         # 4-7  T1(盲孔), T2, D1, D2
        False, False,             # 8-9  Dchk1, Dchk2
        False, False, 0.0, 0.0,   # 10-13 Ddir1, Ddir2, Dang1, Dang2
        False, False,             # 14-15 OffsetReverse1, OffsetReverse2
        False,                    # 16 Merge
        False, False,             # 17-18 UseFeatScope, BodySelect
        pythoncom.Empty,             # 19 Bodies (空)
        False,                    # 20 Preview
        False,                    # 21 AssemCut
        0, 0.0,                   # 22-23 NumSeg, SgmtSize
        False, 0.0,               # 24-25 MidSurf, ThickThk
        False, 0, 0.0)            # 26-28 TrimBy, TrimSeg, TrimSize
    log("  拉伸特征: %s" % ("OK" if feat else "FAIL(None)"))

    log("Step6b 回读包围盒自校验 ...")
    try:
        box = md.GetPartBox(True, True)
        if box and len(box) >= 6:
            x1, y1, z1, x2, y2, z2 = box[0], box[1], box[2], box[3], box[4], box[5]
            w = (x2 - x1) * 1000.0
            h = (y2 - y1) * 1000.0
            d = (z2 - z1) * 1000.0
            log("  实测外形(毫米): %.2f x %.2f x %.2f  (目标 %.0f x %.0f x %.0f)"
                % (w, h, d, D_Outer, D_Outer, Thk))
        else:
            log("  GetPartBox 返回异常: %r" % (box,))
    except Exception as e:
        log("  GetPartBox 异常(忽略): %s" % str(e)[:80])

    log("Step7 注入参数化方程式全局变量（try/except 不影响主体）...")
    try:
        eq = md.GetEquationMgr()
        for name, val in [("D_Outer", D_Outer), ("D_Bore", D_Bore),
                          ("Thk", Thk), ("N", float(N)),
                          ("D_Bolt", D_Bolt), ("PCD", PCD)]:
            eq.AddEquation("%s = %g" % (name, val))
        log("  方程式已写入，数量=%s" % eq.GetCount())
    except Exception as e:
        log("  方程式写入异常(忽略): %s" % e)

    log("Step8 强制重建 ...")
    md.ForceRebuild3(False)

    log("Step9 静默保存为 %s ..." % OUT)
    ok = md.SaveAs3(OUT, 0, 1)   # Options=1 静默，避免保存确认框阻塞
    log("  保存返回: %s (0=成功)" % ok)

    log("DONE 工具链测试结束")
    return 0

if __name__ == "__main__":
    try:
        rc = main()
        sys.exit(rc)
    except Exception as e:
        log("FATAL %s: %s" % (type(e).__name__, e))
        sys.exit(2)
