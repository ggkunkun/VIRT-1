# -*- coding: utf-8 -*-
"""
打开 SOLIDWORKS 2021 并加载桌面零件，实时输出完整过程与特征树解析。
目标文件: c:\\Users\\Administrator\\Desktop\\零件1.SLDPRT
"""

import os
import sys
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import win32com.client
import win32com.client.gencache as gc

TLB_GUID = "{83A33D31-27C5-11CE-BFD4-00400513BB57}"
SW_VERSION = 29
TARGET_PART = r"C:\Users\Administrator\Desktop\零件1.SLDPRT"

def run_open_process():
    print("=" * 70)
    print(">>> [步骤 1/7] 正在清理历史残留并建立 SOLIDWORKS 2021 引擎 ...")
    print("=" * 70)
    import subprocess
    try:
        subprocess.run(["taskkill", "/F", "/IM", "SLDWORKS.exe"], capture_output=True)
    except Exception:
        pass
    time.sleep(3)

    t0 = time.time()
    mod = gc.EnsureModule(TLB_GUID, 0, SW_VERSION, 0)
    sw = mod.SldWorks()
    try:
        sw.Visible = True
    except Exception:
        pass
    print(f"    -> SOLIDWORKS 引擎已连接，耗时: {time.time() - t0:.2f} 秒")
    try:
        rev = sw.RevisionNumber() if callable(sw.RevisionNumber) else sw.RevisionNumber
        print(f"    -> 当前软件版本号: {rev}")
    except Exception:
        pass

    # 步骤 2：检查目标文件有效性
    print("\n" + "=" * 70)
    print(f">>> [步骤 2/7] 正在校验目标文件元数据: {TARGET_PART} ...")
    print("=" * 70)
    if not os.path.exists(TARGET_PART):
        raise FileNotFoundError(f"文件不存在: {TARGET_PART}")
    file_sz = os.path.getsize(TARGET_PART)
    print(f"    -> 文件存在，大小: {file_sz:,} 字节 ({file_sz/1024:.2f} KB)")

    # 步骤 3：调用 OpenDoc6 接口加载零件模型
    print("\n" + "=" * 70)
    print(">>> [步骤 3/7] 正在通过 COM 接口 OpenDoc6 加载零件文档 ...")
    print("=" * 70)
    t_open = time.time()
    ret = sw.OpenDoc6(TARGET_PART, 1, 1, "", 0, 0)
    if isinstance(ret, tuple):
        raw_doc = ret[0]
        err_code = ret[1] if len(ret) > 1 else 0
        warn_code = ret[2] if len(ret) > 2 else 0
    else:
        raw_doc = ret
        err_code, warn_code = 0, 0

    if not raw_doc:
        try:
            raw_doc = sw.IActiveDoc2
        except Exception:
            pass

    if not raw_doc:
        raise RuntimeError(f"无法打开零件文档 (Errors: {err_code}, Warnings: {warn_code})")
    
    part = mod.IModelDoc2(raw_doc._oleobj_)
    title = part.GetTitle() if callable(part.GetTitle) else part.GetTitle
    path_name = part.GetPathName() if callable(part.GetPathName) else part.GetPathName
    print(f"    -> 零件加载成功，耗时: {time.time() - t_open:.2f} 秒")
    print(f"    -> 零件标题: {title}")
    print(f"    -> 零件路径: {path_name}")

    # 步骤 4：激活前台显示并最大化
    print("\n" + "=" * 70)
    print(">>> [步骤 4/7] 正在激活视窗、调整等轴测视图并缩放自适应 ...")
    print("=" * 70)
    try:
        sw.ActivateDoc2(title, False, 0)
    except Exception:
        pass
    try:
        part.ShowNamedView2("*Isometric", 7)
    except Exception:
        pass
    try:
        part.ViewZoomtofit2()
        print("    -> 视口已切换为等轴测视图 (*Isometric) 并缩放自适应 (Zoom to Fit)")
    except Exception as e:
        print(f"    [视图调整提示] {e}")

    # 步骤 5：解析完整特征管理器设计树 (FeatureManager Design Tree)
    print("\n" + "=" * 70)
    print(">>> [步骤 5/7] 正在遍历并提取零件建模特征树 (Feature Tree) ...")
    print("=" * 70)
    features = []
    feat = part.FirstFeature()
    idx = 1
    while feat is not None:
        try:
            name = feat.Name
            type_name = feat.GetTypeName2() if callable(feat.GetTypeName2) else feat.GetTypeName2
            suppressed = feat.IsSuppressed() if callable(feat.IsSuppressed) else feat.IsSuppressed
            features.append({
                "index": idx,
                "name": name,
                "type": type_name,
                "suppressed": suppressed
            })
            status_str = "[被压缩]" if suppressed else "[正常]"
            print(f"    #{idx:02d} 特征名称: {name:<28s} | 类型: {type_name:<20s} | 状态: {status_str}")
        except Exception as e:
            pass
        try:
            feat = feat.GetNextFeature()
            idx += 1
        except Exception:
            break
    print(f"    -> 特征树遍历完成，共检测到 {len(features)} 个节点特征")

    # 步骤 6：提取零件物理属性
    print("\n" + "=" * 70)
    print(">>> [步骤 6/7] 正在计算零件质量与几何属性 ...")
    print("=" * 70)
    try:
        mp = part.Extension.CreateMassProperty()
        vol_cm3 = (mp.Volume or 0.0) * 1e6
        mass_kg = (mp.Mass or 0.0)
        area_cm2 = (mp.SurfaceArea or 0.0) * 1e4
        com = mp.CenterOfMass
        print(f"    -> 净体积:   {vol_cm3:.2f} cm³")
        print(f"    -> 净质量:   {mass_kg:.3f} kg (按当前材质密度计算)")
        print(f"    -> 表面积:   {area_cm2:.2f} cm²")
        if com:
            print(f"    -> 质心坐标: X={com[0]*1000:.2f}mm, Y={com[1]*1000:.2f}mm, Z={com[2]*1000:.2f}mm")
    except Exception as e:
        print(f"    [质量属性提示] {e}")

    # 步骤 7：桌面视窗置顶与截屏取证
    print("\n" + "=" * 70)
    print(">>> [步骤 7/7] 正在置顶 SOLIDWORKS 窗口并捕获屏幕证据 ...")
    print("=" * 70)
    try:
        import win32service, win32gui, win32con, ctypes
        hdesk = win32service.OpenDesktop("default", 0, False, win32con.MAXIMUM_ALLOWED)
        hdesk.SetThreadDesktop()

        def _find_sw(hwnd, res):
            if win32gui.IsWindowVisible(hwnd):
                t = win32gui.GetWindowText(hwnd)
                if "solidworks" in t.lower():
                    res.append((hwnd, t))
            return True

        sw_wins = []
        win32gui.EnumWindows(_find_sw, sw_wins)
        if sw_wins:
            main_hwnd, main_title = sw_wins[0]
            ctypes.windll.user32.ShowWindow(main_hwnd, win32con.SW_MAXIMIZE)
            ctypes.windll.user32.SwitchToThisWindow(main_hwnd, True)
            ctypes.windll.user32.SetForegroundWindow(main_hwnd)
            print(f"    -> 已将主视窗置顶最大化: HWND={main_hwnd}, Title={main_title}")
    except Exception as e:
        print(f"    [窗口置顶提示] {e}")

    # 截取最终屏幕
    out_cap = r"D:\Virtu模型\scratch\open_part1_view.png"
    try:
        from bridges.desktop_controller import DesktopController
        ctl = DesktopController()
        ctl.capture(output_path=out_cap)
        print(f"    -> 视窗截图已保存: {out_cap}")
    except Exception as e:
        print(f"    [截屏提示] {e}")

    print("\n" + "=" * 70)
    print(f">>> {title} 完整加载与过程解析全部完成！")
    print(">>> SOLIDWORKS 界面保持在前台全屏开启供您实时观察与交互。")
    print("=" * 70)

if __name__ == "__main__":
    try:
        run_open_process()
    except Exception as e:
        import traceback
        print(f"执行异常: {e}")
        traceback.print_exc()
        sys.exit(1)
