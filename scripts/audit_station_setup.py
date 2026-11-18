# -*- coding: utf-8 -*-
"""逐步审计 VERICUT 工位装配（机床自动设置的自检）。

对 .vcproject 逐项检查：机床/控制文件、Attach 链、夹具/毛坯/设计/NC 模型与矩阵、
刀具库、工位偏置，输出 station_setup_log.json（每步 PASS/FAIL + 证据）。

用法:
  python scripts/audit_station_setup.py --project E:\\vericut_impeller_run\\OP3.vcproject \
      --report station_setup_log.json
"""
from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path


def find_component(root, name):
    for c in root.iter("Component"):
        if c.get("Name") == name:
            return c
    return None


def comp_info(root, name):
    c = find_component(root, name)
    if c is None:
        return None
    poly = c.find("Poly")
    info = {"name": name, "visible": c.get("Visible"), "enabled": c.get("Enabled")}
    if poly is not None:
        f = poly.find("File")
        m = poly.find("ModelMatrix/MatrixOrigin")
        info["file"] = f.text if f is not None else None
        info["matrix_z"] = float(m.get("Z")) if m is not None else None
        info["file_exists"] = bool(info["file"] and Path(info["file"]).exists())
    return info


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--report", required=True)
    args = ap.parse_args()

    steps = []
    project = Path(args.project)
    try:
        root = ET.parse(project).getroot()
        parsed = True
    except Exception as exc:  # noqa: BLE001
        parsed = False
        root = None
        steps.append({"step": "XML 解析", "status": "FAIL", "evidence": str(exc)})

    if parsed:
        steps.append({"step": "XML 解析", "status": "PASS", "evidence": "ElementTree parse OK"})

        # 机床 / 控制
        machine = root.find(".//Machine/File")
        control = root.find(".//Control/File")
        mfile = machine.text if machine is not None else None
        cfile = control.text if control is not None else None
        # 机床库路径解析（CGTECH_LIBRARY）
        libs = [Path(r"E:\library"), Path(r"E:\windows64\controls"),
                Path(r"E:\windows64\machines"), Path(r"E:\samples\TLS"),
                Path(r"E:\samples\Support_files"), Path(r"E:\windows64")]
        def resolve(p):
            if not p:
                return None
            cand = Path(p)
            if cand.exists():
                return cand
            for lib in libs:
                if (lib / p).exists():
                    return lib / p
            return None
        mres, cres = resolve(mfile), resolve(cfile)
        steps.append({
            "step": "机床模型", "status": "PASS" if mres else "FAIL",
            "evidence": {"file": mfile, "resolved": str(mres) if mres else None},
        })
        steps.append({
            "step": "控制系统", "status": "PASS" if cres else "FAIL",
            "evidence": {"file": cfile, "resolved": str(cres) if cres else None},
        })

        # Attach 链（虚拟 Attach 组件）
        attach = None
        for el in root.iter():
            if el.get("Name") == "Attach":
                attach = el
                break
        apos = attach.find("Position") if attach is not None else None
        az = float(apos.get("Z")) if apos is not None else None
        steps.append({
            "step": "Attach 链", "status": "PASS" if attach is not None else "WARN",
            "evidence": {"attach_z": az, "attached": attach is not None},
        })

        # 夹具 / 毛坯 / 设计
        for name in ("Fixture", "Stock", "Design"):
            info = comp_info(root, name)
            ok = bool(info and info.get("file_exists") and info.get("matrix_z") is not None)
            steps.append({
                "step": f"{name} 落位", "status": "PASS" if ok else "FAIL",
                "evidence": info or "component missing",
            })

        # NC
        nc = root.find(".//NCPrograms/NCProgram")
        ncf = nc.find("File") if nc is not None else None
        ncf_path = Path(ncf.text) if ncf is not None and ncf.text else None
        ok = bool(nc is not None and ncf_path and ncf_path.exists() and nc.get("Use") == "on")
        steps.append({
            "step": "NC 程序", "status": "PASS" if ok else "FAIL",
            "evidence": {"file": str(ncf_path) if ncf_path else None,
                          "use": nc.get("Use") if nc is not None else None,
                          "exists": bool(ncf_path and ncf_path.exists())},
        })

        # 刀具库
        tls = root.find(".//ToolMan/Library")
        tlsf = tls.text if tls is not None else None
        tres = resolve(tlsf)
        steps.append({
            "step": "刀具库", "status": "PASS" if tres else "FAIL",
            "evidence": {"file": tlsf, "resolved": str(tres) if tres else None},
        })

        # 工位偏置
        station = root.find(".//Station")
        off = None
        if station is not None:
            o = station.find(".//WorkOffset")
            off = o.get("Number") if o is not None else None
        steps.append({
            "step": "工件偏置", "status": "PASS" if off is not None else "WARN",
            "evidence": {"work_offset": off},
        })

    passed = sum(1 for s in steps if s["status"] == "PASS")
    failed = sum(1 for s in steps if s["status"] == "FAIL")
    report = {
        "project": str(project),
        "steps_total": len(steps),
        "passed": passed,
        "failed": failed,
        "steps": steps,
        "verdict": "PASS" if failed == 0 else "FAIL",
        "basis": "measured (project XML + file existence)",
    }
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
