# -*- coding: utf-8 -*-
"""
gui_cad_cam_chain.py — Virtu CAD/CAM 第 2 步：全链路 GUI 自动执行（magic-hand 驱动）

用 magic-hand (cu_ui.py) 在 GUI 内把工件接进六款软件并跑起来。
设计原则（应对本机第三方 AI 抢焦点 + 重型软件慢启动）：
  - 串行、一次一个软件，每步 focus 目标窗口后再操作
  - 每步截图存档到工程包，供回读验证（不盲信 ok）
  - recon 先行：先把各软件 HWND 树 + 截图摸清楚，再据实定制点击

用法:
  python gui_cad_cam_chain.py recon     # 勘察 6 软件窗口状态（probe/apps/tree/shot）
  python gui_cad_cam_chain.py run       # 执行 GUI 自动操作（需先 recon 定制）
"""

import os
import sys
import time
import subprocess

SKILL = r"C:\Users\Administrator\.workbuddy\skills\magic-hand-windows\scripts"
TEMP = os.environ.get("TEMP", r"C:\Temp")
RUN_DIR = r"D:\Virtu模型\runs\cad_cam_chain\20261030_131502"

# 六软件 exe 名（用于 apps 匹配与 focus）。vericut 真实进程是 javaw.exe。
APPS = {
    "sw2021":    ("sldworks.exe", "SOLIDWORKS 2021", "01_SOLIDWORKS_2021.swb"),
    "nx12":      ("ugraf.exe", "Siemens NX 12.0", "02_Siemens_NX_12.0.py"),
    "acad2026":  ("acad.exe", "AutoCAD 2026", "03_AutoCAD_2026.lsp"),
    "cimco2026": ("cimcoedit.exe", "CIMCO Edit 2026", "04_CIMCO_Edit_2026.nc"),
    "vericut96": ("javaw.exe", "Vericut 9.6", "05_Vericut_9.6.opt"),
    "sscnc72":   ("sscnc.exe", "斯沃数控仿真 7.2", "06_斯沃数控仿真_7.2.md"),
}

ORDER = ["sw2021", "nx12", "acad2026", "cimco2026", "vericut96", "sscnc72"]


def cu(*args, timeout=40):
    """调用 cu_ui.py，返回 (rc, stdout, stderr)。"""
    try:
        p = subprocess.run([sys.executable, os.path.join(SKILL, "cu_ui.py"), *args],
                           capture_output=True, text=True, timeout=timeout, cwd=SKILL)
        return p.returncode, p.stdout, p.stderr
    except Exception as e:
        return -1, "", str(e)


def shot(name):
    """截图全屏 BMP 并转 PNG 存工程包，返回 png 路径。"""
    cu("shot")
    bmp = os.path.join(TEMP, "cu_shot.bmp")
    png = os.path.join(RUN_DIR, "gui_%s.png" % name)
    try:
        subprocess.run([sys.executable, os.path.join(SKILL, "bmp2png.py"), bmp, png],
                       cwd=SKILL, capture_output=True, text=True, timeout=30)
    except Exception:
        pass
    return png


def recon():
    """勘察：probe 会话 → apps 列表 → 每软件 focus/tree/shot 存档。"""
    os.makedirs(RUN_DIR, exist_ok=True)
    print(">>> [recon] probe 会话")
    rc, out, err = cu("probe")
    print(out)
    if "READY" not in out:
        print("[!] 非 READY（NO_GUI_SESSION）：需双击 start_cu_bridge.bat 起桥，中止 recon。")
        return False

    print("\n>>> [recon] apps 运行中应用")
    rc, out, err = cu("apps")
    print(out)
    open(os.path.join(RUN_DIR, "gui_apps.txt"), "w", encoding="utf-8").write(out)

    for key in ORDER:
        exe, label, art = APPS[key]
        print("\n=== %s (%s) ===" % (label, exe))
        cu("focus", exe)
        time.sleep(2.0)  # 等窗口置前 + 抢焦点空窗
        rc, tree, err = cu("tree", exe, "--depth", "12")
        tpath = os.path.join(RUN_DIR, "gui_tree_%s.txt" % key)
        open(tpath, "w", encoding="utf-8").write(tree)
        png = shot(key)
        print("  tree -> %s" % tpath)
        print("  shot -> %s" % png)
        # 预览树前 30 行，便于即时判态
        head = "\n".join(tree.splitlines()[:30])
        print("  (tree 预览)\n" + head)
    print("\n[recon] 完成，结果已存档到 %s" % RUN_DIR)
    return True


def run():
    """GUI 自动操作：recon 后据 tree 定制。当前为骨架，待 recon 输出细化。

    每个软件计划（串行，一次一个）：
      sw2021   : 工具→宏→运行 01_SOLIDWORKS_2021.swb → 生成模型 → 另存/导出 STEP
      nx12     : 文件→打开 journal 02_Siemens_NX_12.0.py → 运行 → 导出
      acad2026 : 命令行 (load "03_AutoCAD_2026.lsp") → 生成工程图
      cimco2026: 已命令行载入 .nc → 运行 NC 程序模拟（仿真）
      vericut96: 打开 05_Vericut_9.6.opt + NC → 运行切削仿真
      sscnc72  : 按 06_斯沃数控仿真_7.2.md 手册设置装夹/对刀 → 试切
    """
    print("[run] 需先执行 recon 获取各软件 HWND 树，再据实定制点击序列。")
    print("       当前环境若已 READY，请先 `python gui_cad_cam_chain.py recon`。")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "recon"
    if cmd == "recon":
        recon()
    elif cmd == "run":
        run()
    else:
        print("用法: gui_cad_cam_chain.py [recon|run]")
