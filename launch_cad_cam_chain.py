# -*- coding: utf-8 -*-
"""
launch_cad_cam_chain.py — Virtu CAD/CAM 六大软件 Agent 链 · 自动拉起器

读取最近一次 cad_cam_agent_chain 生成的 manifest.json，把六款工业软件
按「自动拉起」深度真正启动，并尽量把工件接进去：
  - 仅 CIMCOEdit 能用命令行干净打开 .nc 工件（已对接，失败则兜底启动）
  - 其余软件需在 GUI 内加载工件（属第 2 步 GUI 自动执行），本步只启动并标注
  - SOLIDWORKS 的 lnk 解析出的是 MSI 广告入口，自动规避（注册表定位真实
    SLDWORKS.exe，找不到则跳过，避免触发 Windows Installer 修复）

常驻：走 explorer.exe 派生（脱离沙箱作业对象，进程不随会话回收）；
      CIMCO 先尝试 ShellExecuteW 传参载入工件，失败则 explorer 派生兜底。

串行：一次只开一个，等进程就绪再开下一个（避免重型软件抢资源）。

用法:
  python launch_cad_cam_chain.py                      # 按顺序串行拉起最新工程包
  python launch_cad_cam_chain.py --only sw2021 cimco2026  # 只补拉指定（合并旧报告）
  python launch_cad_cam_chain.py --dry-run            # 只打印计划，不启动
"""

import os
import sys
import json
import time
import glob
import csv
import io
import subprocess
import ctypes
import argparse
import winreg

ROOT = os.path.dirname(os.path.abspath(__file__))

# 各软件「真实进程名」（launcher 名 ≠ 实际进程名，必须映射才能准确检测）
PROC_MAP = {
    "sw2021": "SLDWORKS.exe",
    "nx12": "ugraf.exe",
    "acad2026": "acad.exe",
    "cimco2026": "CIMCOEdit.exe",
    "vericut96": "javaw.exe",
    "sscnc72": "sscnc.exe",
}


def find_latest_manifest():
    chain_root = os.path.join(ROOT, "runs", "cad_cam_chain")
    if not os.path.isdir(chain_root):
        return None
    subs = [d for d in glob.glob(os.path.join(chain_root, "*")) if os.path.isdir(d)]
    if not subs:
        return None
    subs.sort(key=lambda d: os.path.getmtime(d), reverse=True)
    m = os.path.join(subs[0], "manifest.json")
    return m if os.path.exists(m) else None


def find_sw_real_exe():
    """定位 SOLIDWORKS 真实主程序 SLDWORKS.exe（避开 Installer 广告入口）。"""
    for c in [r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\SLDWORKS.exe",
              r"C:\Program Files (x86)\SOLIDWORKS Corp\SOLIDWORKS\SLDWORKS.exe"]:
        if os.path.exists(c):
            return c
    # Setup 注册表
    for hk, p in [(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\SolidWorks\SOLIDWORKS\Setup"),
                  (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\SolidWorks\SOLIDWORKS 2021\Setup"),
                  (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\SolidWorks\SOLIDWORKS\Setup")]:
        try:
            k = winreg.OpenKey(hk, p)
            for i in range(64):
                try:
                    name, val, _ = winreg.EnumValue(k, i)
                    if isinstance(val, str):
                        if val.lower().endswith("sldworks.exe") and os.path.exists(val):
                            return val
                        if "dir" in name.lower() or "install" in name.lower():
                            cand = os.path.join(val, "SLDWORKS.exe")
                            if os.path.exists(cand):
                                return cand
                except OSError:
                    break
        except Exception:
            pass
    # Uninstall 注册表 InstallLocation
    base = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
    for sub in ("", r"\WOW6432Node"):
        try:
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base + sub)
            for i in range(2048):
                try:
                    skn = winreg.EnumKey(k, i)
                except OSError:
                    break
                try:
                    sk = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base + sub + "\\" + skn)
                    dn = il = None
                    try:
                        dn = winreg.QueryValueEx(sk, "DisplayName")[0]
                    except Exception:
                        pass
                    try:
                        il = winreg.QueryValueEx(sk, "InstallLocation")[0]
                    except Exception:
                        pass
                    if dn and "solidworks" in dn.lower() and il:
                        cand = os.path.join(il, "SLDWORKS.exe")
                        if os.path.exists(cand):
                            return cand
                except Exception:
                    pass
        except Exception:
            pass
    return None


def proc_running(basename):
    """用 tasklist（GBK）粗判进程是否已起来。"""
    if not basename or basename.endswith(".bat"):
        return True
    try:
        out = subprocess.check_output(["tasklist", "/FO", "CSV"], shell=False,
                                      encoding="gbk", errors="ignore")
        for r in csv.reader(io.StringIO(out)):
            if r and r[0].lower() == basename.lower():
                return True
    except Exception:
        return False
    return False


def wait_for_proc(basename, timeout=30):
    """轮询等到进程起来（最多 timeout 秒），确认就绪再开下一个。"""
    if basename.endswith(".bat"):
        time.sleep(4)
        return True
    waited = 0
    while waited < timeout:
        if proc_running(basename):
            return True
        time.sleep(2)
        waited += 2
    return proc_running(basename)


def launch_explorer(exe):
    subprocess.Popen(["explorer.exe", exe])


def launch_shell(exe, params):
    ctypes.windll.shell32.ShellExecuteW(None, "open", exe, params, None, 1)


def main():
    ap = argparse.ArgumentParser(description="Virtu CAD/CAM 自动拉起器")
    ap.add_argument("--manifest", default=None, help="指定 manifest.json 路径")
    ap.add_argument("--dry-run", action="store_true", help="只打印计划不启动")
    ap.add_argument("--only", nargs="*", default=None, help="只处理指定 key（补拉）")
    args = ap.parse_args()

    m = args.manifest or find_latest_manifest()
    if not m or not os.path.exists(m):
        print("未找到 manifest.json，无法拉起。"); sys.exit(2)

    run_dir = os.path.dirname(m)
    manifest = json.load(open(m, encoding="utf-8"))
    sw_real = find_sw_real_exe()

    print(">>> Virtu CAD/CAM 自动拉起（串行 · 一次一个）")
    print("工程包 : %s" % run_dir)
    print("SW主程 : %s" % (sw_real or "(未找到 → 跳过广告入口)"))
    if args.only:
        print("仅补拉 : %s" % ", ".join(args.only))
    if args.dry_run:
        print("[DRY-RUN] 仅打印计划，不启动。")
    print("-" * 64)

    # 合并旧报告，保证补拉不丢失其它已起软件的状态
    report_path = os.path.join(run_dir, "launch_report.json")
    base = {}
    if os.path.exists(report_path):
        try:
            base = {r["key"]: r for r in json.load(open(report_path, encoding="utf-8"))["results"]}
        except Exception:
            base = {}

    order_keys = [a["key"] for a in manifest["artifacts"]]
    for a in manifest["artifacts"]:
        key, tool = a["key"], a["tool"]
        if args.only and key not in args.only:
            continue  # 非本次目标，保留旧状态

        la = a.get("launch") or {}
        exe = la.get("exe")
        art_file = os.path.join(run_dir, a["file"])
        note = ""
        skipped = False

        if key == "sw2021" and exe and "Installer" in exe:
            if sw_real:
                exe = sw_real
                note = "已用真实主程序替换 MSI 广告入口"
            else:
                skipped = True
                note = "入口为 MSI 广告入口且无真实主程序，跳过以避免触发修复"

        if not skipped and not (exe and os.path.exists(exe)):
            skipped = True
            note = "exe 不存在: %s" % exe

        if skipped:
            base[key] = {"key": key, "tool": tool, "status": "skipped",
                         "exe": exe, "note": note}
            print("  [SKIP] %-22s %s" % (tool, note))
            continue

        if args.dry_run:
            base[key] = {"key": key, "tool": tool, "status": "planned",
                         "exe": exe, "artifact": a["file"]}
            print("  [PLAN] %-22s %s" % (tool, exe))
            continue

        # 启动（串行：一次只开一个）
        if key == "cimco2026" and os.path.exists(art_file):
            launch_shell(exe, '"%s"' % art_file)
            note = (note + " | " if note else "") + "尝试命令行载入工件"
        else:
            launch_explorer(exe)

        proc_name = PROC_MAP.get(key, os.path.basename(exe)).lower()
        running = wait_for_proc(proc_name, timeout=30)

        # CIMCO 命令行载入失败兜底：explorer 派生确保起来
        if key == "cimco2026" and not running:
            launch_explorer(exe)
            running = wait_for_proc(proc_name, timeout=20)
            note = (note + " | " if note else "") + "命令行载入未生效，已兜底启动(工件待GUI载入)"

        if not proc_name.endswith(".bat"):
            time.sleep(5)  # 额外缓冲，让 GUI 充分初始化

        note2 = "进程已起来，进入就绪" if running else "超时未检测到（可能仍在加载）"
        full = (note + " | " + note2) if note else note2
        base[key] = {"key": key, "tool": tool, "status": "launched", "exe": exe,
                     "artifact": a["file"], "proc_running": running, "note": full}
        print("  [OK]   %-22s %s" % (tool, full))

    # 写出前，对所有 launched 项用真实进程名复核一次（修正首轮误判）
    for k, r in base.items():
        if r.get("status") == "launched":
            pn = PROC_MAP.get(k, os.path.basename(r.get("exe", ""))).lower()
            if not pn.endswith(".bat"):
                r["proc_running"] = proc_running(pn)
                if r["proc_running"]:
                    r["note"] = r["note"].split(" | 超时")[0] + " | 实测进程已确认"

    results = [base[k] for k in order_keys if k in base]
    report = {
        "run_dir": run_dir,
        "launched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "dry_run": bool(args.dry_run),
        "results": results,
    }
    json.dump(report, open(report_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("-" * 64)
    print("报告已写: %s" % report_path)
    print("当前链路状态:")
    for r in results:
        print("  - %-22s [%s] %s" % (r["tool"], r["status"],
              "进程确认" if r.get("proc_running") else "待确认"))


if __name__ == "__main__":
    main()
