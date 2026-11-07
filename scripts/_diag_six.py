"""Detect the six major industrial software packages on this Windows host.

Strategy: registry (Uninstall keys + COM ProgID classes) + filesystem probes.
We DO NOT instantiate COM objects (sandbox policy blocks it) — we only read
registrations, which is enough to know what is installed and automation-ready.
"""
import os
import sys
import winreg as reg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---- detection specs -------------------------------------------------------
# each: name, keywords to match in Uninstall DisplayName, candidate exe paths,
#       COM ProgIDs to look up in SOFTWARE\Classes
SPECS = [
    {
        "key": "solidworks",
        "name": "SOLIDWORKS 2021",
        "keywords": ["solidworks"],
        "exes": [
            r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\sldworks.exe",
            r"C:\Program Files (x86)\SOLIDWORKS Corp\SOLIDWORKS\sldworks.exe",
        ],
        "progids": ["SldWorks.Application", "SldWorks.Application.29"],
    },
    {
        "key": "autocad",
        "name": "AutoCAD 2026",
        "keywords": ["autocad 2026", "autocad"],
        "exes": [
            r"C:\Program Files\Autodesk\AutoCAD 2026\acad.exe",
            r"C:\Program Files\Autodesk\AutoCAD 2025\acad.exe",
        ],
        "progids": ["AutoCAD.Application", "AutoCAD.Application.25"],
    },
    {
        "key": "nx",
        "name": "Siemens NX 12.0",
        "keywords": ["siemens nx", "nx 12", "ug nx"],
        "exes": [
            r"C:\Program Files\Siemens\NX 12.0\UGII\ugraf.exe",
            r"C:\Program Files\Siemens\NX 120\UGII\ugraf.exe",
            r"C:\Program Files\Siemens\NX\UGII\ugraf.exe",
        ],
        "progids": [],
    },
    {
        "key": "cimco",
        "name": "CIMCO Edit 2026",
        "keywords": ["cimco"],
        "exes": [
            r"C:\Program Files\CIMCO 2026\CIMCOEdit.exe",
            r"C:\Program Files (x86)\CIMCO\CIMCOEdit.exe",
            r"C:\Program Files\CIMCO Edit\CIMCOEdit.exe",
        ],
        "progids": [],
    },
    {
        "key": "vericut",
        "name": "VERICUT 9.6",
        "keywords": ["vericut"],
        "exes": [
            r"C:\Program Files\CGTech\VERICUT 9.6\windows64\vericut.exe",
            r"C:\Program Files\CGTech\VERICUT 9.6\win64\vericut.exe",
        ],
        "progids": [],
    },
    {
        "key": "sscnc",
        "name": "斯沃数控仿真 SSCNC 7.2",
        "keywords": ["斯沃", "sscnc", "数控仿真", "swansoft"],
        "exes": [
            r"C:\Program Files (x86)\SSCNC\SSCNC.exe",
            r"C:\Swansoft\SSCNC\SSCNC.exe",
            r"C:\Program Files\SSCNC\SSCNC.exe",
        ],
        "progids": [],
    },
]

UNINST_ROOTS = [
    (reg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    (reg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    (reg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
]

CLASSES_ROOTS = [
    (reg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Classes"),
    (reg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Classes"),
]


def read_uninstall_displaynames():
    """Return list of (display_name, version, install_location, publisher)."""
    found = []
    for hkey, sub in UNINST_ROOTS:
        try:
            with reg.OpenKey(hkey, sub) as k:
                n = reg.QueryInfoKey(k)[0]
                for i in range(n):
                    name = reg.EnumKey(k, i)
                    try:
                        with reg.OpenKey(k, name) as sk:
                            try:
                                dn, _ = reg.QueryValueEx(sk, "DisplayName")
                            except OSError:
                                dn = None
                            if not dn:
                                continue
                            try:
                                ver, _ = reg.QueryValueEx(sk, "DisplayVersion")
                            except OSError:
                                ver = ""
                            try:
                                loc, _ = reg.QueryValueEx(sk, "InstallLocation")
                            except OSError:
                                loc = ""
                            try:
                                pub, _ = reg.QueryValueEx(sk, "Publisher")
                            except OSError:
                                pub = ""
                            found.append((dn, ver, loc, pub))
                    except OSError:
                        pass
        except OSError:
            pass
    return found


def progid_registered(progid):
    for hkey, sub in CLASSES_ROOTS:
        try:
            with reg.OpenKey(hkey, sub + r"\\" + progid) as k:
                # if it has a CLSID subkey or default value, it's registered
                try:
                    clsid, _ = reg.QueryValueEx(k, "CLSID")
                    return True
                except OSError:
                    pass
                try:
                    cur, _ = reg.QueryValueEx(k, "CurVer")
                    return True
                except OSError:
                    pass
                # has subkeys?
                if reg.QueryInfoKey(k)[0] > 0:
                    return True
        except OSError:
            pass
    return False


def detect(spec, uninstall_entries):
    # 1) registry DisplayName match
    reg_hits = []
    for dn, ver, loc, pub in uninstall_entries:
        dl = dn.lower()
        if any(kw in dl for kw in spec["keywords"]):
            reg_hits.append((dn, ver, loc, pub))
    # 2) filesystem exe
    exe_found = None
    for p in spec["exes"]:
        if os.path.exists(p):
            exe_found = p
            break
    # 3) COM ProgID
    progid_hits = [pid for pid in spec["progids"] if progid_registered(pid)]

    installed = bool(reg_hits) or bool(exe_found)
    version = reg_hits[0][1] if reg_hits else ""
    # prefer exe path for location evidence, else install location from reg
    loc_evidence = exe_found or (reg_hits[0][2] if reg_hits and reg_hits[0][2] else "")
    return {
        "installed": installed,
        "version": version,
        "path": loc_evidence,
        "reg_display": reg_hits[0][0] if reg_hits else "",
        "com_progids": progid_hits,
    }


def main():
    entries = read_uninstall_displaynames()
    results = {}
    for spec in SPECS:
        r = detect(spec, entries)
        results[spec["key"]] = {"name": spec["name"], **r}
    # ---- report ----
    print("=" * 78)
    print("六大工业软件 安装探测 (registry + filesystem; 不实例化 COM)")
    print("=" * 78)
    for spec in SPECS:
        k = spec["key"]
        r = results[k]
        status = "INSTALLED" if r["installed"] else "not found"
        print(f"\n[{status}] {r['name']}")
        if r["installed"]:
            if r["reg_display"]:
                print(f"    registry : {r['reg_display']}  (ver: {r['version'] or 'n/a'})")
            if r["path"]:
                print(f"    path     : {r['path']}")
            if r["com_progids"]:
                print(f"    COM ProgID: {', '.join(r['com_progids'])}  (automation-ready)")
    print("\n" + "=" * 78)
    installed_count = sum(1 for r in results.values() if r["installed"])
    print(f"SUMMARY: {installed_count}/{len(SPECS)} installed")
    print("=" * 78)
    # machine context
    print("\nENV hints:")
    for e in ["UGII_BASE_DIR", "SOLIDWORKSDIR"]:
        print(f"    {e} = {os.environ.get(e, '(unset)')}")


if __name__ == "__main__":
    main()
