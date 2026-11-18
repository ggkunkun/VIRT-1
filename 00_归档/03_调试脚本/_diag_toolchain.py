# -*- coding: utf-8 -*-
"""诊断脚本：验证 Python 环境 + 运行 cadcam_cli preflight，输出到文件。"""
import sys, io, os, json, traceback

OUT = r"D:\Virtu模型\_diag_result.txt"

def log(*a):
    with io.open(OUT, "a", encoding="utf-8") as f:
        f.write(" ".join(str(x) for x in a) + "\n")

try:
    if os.path.exists(OUT):
        os.remove(OUT)
    log("PYTHON_OK", sys.executable, sys.version.split()[0])
    os.chdir(r"D:\Virtu模型")
    sys.path.insert(0, r"D:\Virtu模型")
    from bridges.software_registry import diagnose_all, SOFTWARE_SPECS
    log("IMPORT_OK bridges.software_registry")
    report = diagnose_all()
    log("READY_COUNT", report.get("ready_count"), "of", report.get("total_software"))
    for key, info in report.get("software", {}).items():
        log(key,
            "ready=" + str(info.get("is_ready")),
            "running=" + str(info.get("is_running")),
            "lnk=" + str(info.get("shortcut_present")),
            "binary=" + str(info.get("binary_found")),
            "pids=" + str(info.get("running_pids")))
except Exception:
    log("TRACEBACK")
    log(traceback.format_exc())

log("DONE")
