# -*- coding: utf-8 -*-
"""bridges/software_registry.py — Industrial CAD/CAM Six-Software Registry & Discovery.

Provides single-source-of-truth metadata, desktop shortcut (.lnk) resolution,
binary existence checks, process diagnostics, and COM registration status for:
1. SOLIDWORKS 2021
2. 斯沃数控仿真软件 SSCNC 7.2
3. CIMCO Edit 2026
4. AutoCAD 2026
5. Vericut 9.6
6. 中文版 Siemens NX 12.0
"""

import os
import sys
import subprocess
import shutil

# Canonical desktop shortcut locations as referenced by user
DESKTOP_SHORTCUTS = {
    "solidworks": r"C:\Users\Public\Desktop\SOLIDWORKS 2021.lnk",
    "sscnc": r"C:\Users\Public\Desktop\斯沃数控仿真软件.lnk",
    "cimco": r"C:\Users\Public\Desktop\CIMCO Edit 2026.lnk",
    "autocad": r"C:\Users\Public\Desktop\AutoCAD 2026 - 简体中文 (Simplified Chinese).lnk",
    "vericut": r"C:\Users\Public\Desktop\Vericut 9.6.lnk",
    "nx": r"C:\Users\Administrator\Desktop\中文版NX12.0.lnk",
}

# Alias mappings for user friendliness
SOFTWARE_ALIASES = {
    "sw": "solidworks",
    "sldworks": "solidworks",
    "solidworks2021": "solidworks",
    "sw2021": "solidworks",
    "acad": "autocad",
    "autocad2026": "autocad",
    "cad": "autocad",
    "cad2026": "autocad",
    "nx12": "nx",
    "nx12.0": "nx",
    "ug": "nx",
    "ugraf": "nx",
    "siemens_nx": "nx",
    "cimcoedit": "cimco",
    "cimco2026": "cimco",
    "cimco_edit": "cimco",
    "vericut96": "vericut",
    "vericut9.6": "vericut",
    "cgtech_vericut": "vericut",
    "sscnc72": "sscnc",
    "sscnc7.2": "sscnc",
    "斯沃": "sscnc",
    "斯沃数控": "sscnc",
    "斯沃仿真": "sscnc",
}

# Detailed definitions and known default installation paths
SOFTWARE_SPECS = {
    "solidworks": {
        "display_name": "SOLIDWORKS 2021",
        "category": "3D CAD / Parametric Modeling",
        "shortcut": DESKTOP_SHORTCUTS["solidworks"],
        "known_binaries": [
            r"D:\SOLIDWORKS (2)\SLDWORKS.exe",
            r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\SLDWORKS.exe",
        ],
        "process_names": ["SLDWORKS.exe"],
        "com_prog_id": "SldWorks.Application",
        "window_titles": ["SOLIDWORKS", "SLDWORKS"],
        "capabilities": ["parametric_modeling", "equation_manager", "vba_macros", "step_export"],
    },
    "sscnc": {
        "display_name": "斯沃数控仿真软件 SSCNC 7.2",
        "category": "Virtual CNC Machine / Shopfloor Simulation",
        "shortcut": DESKTOP_SHORTCUTS["sscnc"],
        "known_binaries": [
            r"E:\仿真软件\2斯沃7.2（内含安装说明）\SSCNC\CNCLogin.exe",
            r"E:\仿真软件\2斯沃7.2（内含安装说明）\SSCNC\SSCNC.exe",
        ],
        "process_names": ["CNCLogin.exe", "SSCNC.exe"],
        "com_prog_id": None,
        "window_titles": ["斯沃", "SSCNC", "FANUC", "ClassName_CCCStartDlg"],
        "capabilities": ["fanuc_0it_0im_emulation", "wcs_g54_setup", "tool_offset_quadrants", "cycle_start"],
    },
    "cimco": {
        "display_name": "CIMCO Edit 2026",
        "category": "CNC G-code & FANUC Macro B Editor",
        "shortcut": DESKTOP_SHORTCUTS["cimco"],
        "known_binaries": [
            r"E:\仿真软件\CIMCOEdit_20260102\CIMCO 2026\CIMCOEdit\CIMCOEdit.exe",
        ],
        "process_names": ["CIMCOEdit.exe"],
        "com_prog_id": None,
        "window_titles": ["CIMCO Edit"],
        "capabilities": ["macro_b_validation", "gcode_syntax_check", "nc_transmission_prep", "backplot"],
    },
    "autocad": {
        "display_name": "AutoCAD 2026 - 简体中文",
        "category": "2D Drafting & Engineering Drawings",
        "shortcut": DESKTOP_SHORTCUTS["autocad"],
        "known_binaries": [
            r"D:\cad2026\AutoCAD 2026\acad.exe",
            r"D:\cad2026\AutoCAD 2026\accoreconsole.exe",
        ],
        "process_names": ["acad.exe", "accoreconsole.exe"],
        "com_prog_id": "AutoCAD.Application",
        "window_titles": ["AutoCAD"],
        "capabilities": ["autolisp_execution", "headless_ezdxf", "gdt_tolerancing", "multi_layer_drawing"],
    },
    "vericut": {
        "display_name": "VERICUT 9.6",
        "category": "Kinematic Machine Simulation & Collision Detection",
        "shortcut": DESKTOP_SHORTCUTS["vericut"],
        "known_binaries": [
            r"E:\windows64\commands\vericut.bat",
            r"E:\cgtech96\commands\vericut.bat",
        ],
        "process_names": ["vericut.exe", "javaw.exe"],
        "com_prog_id": None,
        "window_titles": ["VERICUT"],
        "capabilities": ["batch_simulation", "autodiff_gouge_check", "collision_detection", "optipath_analysis"],
    },
    "nx": {
        "display_name": "Siemens NX 12.0 (中文版)",
        "category": "High-End CAD/CAM / Multi-Axis Toolpaths",
        "shortcut": DESKTOP_SHORTCUTS["nx"],
        "known_binaries": [
            r"E:\BaiduNetdiskDownload\NX 12.0.2.9\NX12.2.9waigua\NX12.2.9\NX\NXBIN\run_journal.exe",
            r"E:\BaiduNetdiskDownload\NX 12.0.2.9\NX12.2.9waigua\NX12.2.9\NX\UGII\ugraf.exe",
            r"E:\BaiduNetdiskDownload\NX 12.0.2.9\NX12.2.9waigua\NX12.2.9\中文版NX12.0.exe",
        ],
        "process_names": ["ugraf.exe", "run_journal.exe"],
        "com_prog_id": None,
        "window_titles": ["Siemens NX", "NX 12", "UG"],
        "capabilities": ["nxopen_python_journal", "parametric_expressions", "uf_modl_csys", "multi_axis_cam"],
    },
}


def normalize_software_key(key: str) -> str:
    """Normalize various names/aliases to one of the 6 canonical keys."""
    if not key:
        return ""
    clean = key.strip().lower()
    if clean in SOFTWARE_SPECS:
        return clean
    if clean in SOFTWARE_ALIASES:
        return SOFTWARE_ALIASES[clean]
    for alias, canonical in SOFTWARE_ALIASES.items():
        if alias in clean:
            return canonical
    for canonical in SOFTWARE_SPECS:
        if canonical in clean:
            return canonical
    return clean


_SHORTCUT_CACHE = {}

def resolve_shortcut(lnk_path: str, use_cache: bool = True) -> dict:
    """Resolve Windows shortcut (.lnk) file to target path and working directory."""
    if use_cache and lnk_path in _SHORTCUT_CACHE:
        return _SHORTCUT_CACHE[lnk_path]

    res = {
        "shortcut_path": lnk_path,
        "exists": os.path.exists(lnk_path),
        "target_path": None,
        "working_directory": None,
        "arguments": None,
        "target_exists": False,
    }
    if not res["exists"]:
        _SHORTCUT_CACHE[lnk_path] = res
        return res

    # 1. Try WScript.Shell COM
    try:
        import win32com.client
        sh = win32com.client.Dispatch("WScript.Shell")
        sc = sh.CreateShortcut(lnk_path)
        res["target_path"] = sc.TargetPath
        res["working_directory"] = sc.WorkingDirectory
        res["arguments"] = sc.Arguments
        if res["target_path"] and os.path.exists(res["target_path"]):
            res["target_exists"] = True
            _SHORTCUT_CACHE[lnk_path] = res
            return res
    except Exception:
        pass

    # 2. Try powershell fallback
    try:
        ps_cmd = f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk_path}'); Write-Output \"$($s.TargetPath)|$($s.WorkingDirectory)|$($s.Arguments)\""
        out = subprocess.check_output(["powershell", "-NoProfile", "-Command", ps_cmd],
                                      stderr=subprocess.DEVNULL, timeout=5).decode("utf-8", errors="ignore").strip()
        parts = out.split("|")
        if len(parts) >= 2 and parts[0]:
            res["target_path"] = parts[0]
            res["working_directory"] = parts[1]
            if len(parts) >= 3:
                res["arguments"] = parts[2]
            res["target_exists"] = os.path.exists(res["target_path"])
    except Exception:
        pass

    _SHORTCUT_CACHE[lnk_path] = res
    return res


def get_running_processes(timeout_s: float = 15.0) -> dict:
    """Return map of running process names to list of PIDs.

    Uses CreateToolhelp32Snapshot (Win32 API) instead of `tasklist`:
    full `tasklist /FO CSV /NH` hangs for >10s on this host (probe 8:
    all full-scan variants timed out; only /FI-filtered tasklist and
    PowerShell Get-Process returned). Toolhelp32 is a native, instant,
    in-process snapshot with no subprocess, no shell, no pipe.
    """
    procs = {}
    try:
        import ctypes
        from ctypes import wintypes

        TH32CS_SNAPPROCESS = 0x2
        INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", ctypes.c_wchar * 260),
            ]

        kernel32 = ctypes.windll.kernel32
        snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snap == INVALID_HANDLE_VALUE:
            return procs
        try:
            entry = PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
            if not kernel32.Process32FirstW(snap, ctypes.byref(entry)):
                return procs
            while True:
                name = entry.szExeFile.strip()
                pid = int(entry.th32ProcessID)
                if name:
                    procs.setdefault(name, []).append(pid)
                if not kernel32.Process32NextW(snap, ctypes.byref(entry)):
                    break
        finally:
            kernel32.CloseHandle(snap)
    except Exception:
        # Fallback: per-name /FI tasklist (fast, ~2s each) — never full scan.
        try:
            for name in ("SLDWORKS.exe", "CNCLogin.exe", "SSCNC.exe", "CIMCOEdit.exe",
                         "acad.exe", "accoreconsole.exe", "vericut.exe", "javaw.exe",
                         "ugraf.exe", "run_journal.exe"):
                out = subprocess.check_output(
                    ["tasklist", "/FI", f"IMAGENAME eq {name}", "/FO", "CSV", "/NH"],
                    shell=False, encoding="gbk", errors="ignore",
                    timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                import csv
                import io
                for row in csv.reader(io.StringIO(out)):
                    if len(row) >= 2 and row[0].strip().lower() == name.lower():
                        try:
                            procs.setdefault(name, []).append(int(row[1]))
                        except ValueError:
                            pass
        except Exception:
            pass
    return procs


def check_com_registration(prog_id: str) -> bool:
    """Check if COM ProgID is registered in Windows Registry."""
    if not prog_id:
        return False
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, prog_id)
        winreg.CloseKey(key)
        return True
    except Exception:
        return False


def get_software_health(key: str, running_procs: dict = None) -> dict:
    """Detailed health evaluation for a specific industrial software."""
    canonical = normalize_software_key(key)
    spec = SOFTWARE_SPECS.get(canonical)
    if not spec:
        return {"error": f"Unknown software [{key}]"}

    if running_procs is None:
        running_procs = get_running_processes()

    # Shortcut info
    sc_info = resolve_shortcut(spec["shortcut"])

    # Locate executable binary
    binary_found = None
    # Prioritize direct executable binaries over installer shortcuts
    for b in spec["known_binaries"]:
        if os.path.exists(b):
            binary_found = b
            break
    if not binary_found and sc_info["target_exists"]:
        binary_found = sc_info["target_path"]

    # Running status
    running_pids = []
    for pname in spec["process_names"]:
        for live_name, pids in running_procs.items():
            if pname.lower() == live_name.lower():
                running_pids.extend(pids)

    # COM registration
    com_ok = check_com_registration(spec["com_prog_id"]) if spec["com_prog_id"] else None

    # Readiness score
    is_ready = bool(binary_found) or (sc_info["exists"] and sc_info["target_path"] is not None)

    return {
        "key": canonical,
        "display_name": spec["display_name"],
        "category": spec["category"],
        "shortcut_present": sc_info["exists"],
        "shortcut_path": spec["shortcut"],
        "resolved_target": sc_info["target_path"],
        "binary_found": binary_found,
        "is_ready": is_ready,
        "is_running": len(running_pids) > 0,
        "running_pids": running_pids,
        "com_registered": com_ok,
        "capabilities": spec["capabilities"],
    }


def diagnose_all() -> dict:
    """Diagnose all 6 CAD/CAM applications simultaneously."""
    running_procs = get_running_processes()
    results = {}
    ready_count = 0
    running_count = 0

    for key in SOFTWARE_SPECS:
        info = get_software_health(key, running_procs)
        results[key] = info
        if info.get("is_ready"):
            ready_count += 1
        if info.get("is_running"):
            running_count += 1

    return {
        "total_software": len(SOFTWARE_SPECS),
        "ready_count": ready_count,
        "running_count": running_count,
        "all_ready": ready_count == len(SOFTWARE_SPECS),
        "software": results,
    }


if __name__ == "__main__":
    report = diagnose_all()
    print(f"Industrial CAD/CAM Registry Diagnosis: {report['ready_count']}/{report['total_software']} Ready, {report['running_count']} Running")
    for k, v in report["software"].items():
        status = "READY" if v["is_ready"] else "MISSING"
        run_st = f"RUNNING(PID {v['running_pids']})" if v["is_running"] else "STOPPED"
        print(f" - [{k:10s}] {v['display_name']:<30s} | {status} | {run_st} | Bin: {v['binary_found']}")
