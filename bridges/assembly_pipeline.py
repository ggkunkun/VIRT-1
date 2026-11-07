# -*- coding: utf-8 -*-
"""装配体全流程编排：理解 BOM -> OCP 拆件/测体积 -> 配合推断 -> SW 装配 -> 工程图 -> 取证。

所有"成功"都由可复现的测量支撑：
  - 零件体积：OCP 实测 vs SW 质量属性（相对误差 <= 0.05%）
  - 组件位姿：AddComponent5 后回读 transform == BOM 4x4 平移（<=0.05mm）
  - 配合：选面后核对曲面类型/半径，加配合后复查无漂移；重开后 GetMates 仍在
  - 工程图：创建后 view_count>=4，重开后 view_count 不变
任何一项缺失即 status=error，并写进 verification.json。
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bridges.step_bom import StepBOM  # noqa: E402
from bridges.step_parts_occ import extract_parts  # noqa: E402
from bridges.step_mates import face_inventory, infer_mates  # noqa: E402

WORKER = os.path.join(ROOT, "bridges", "assembly_worker.py")
SW_WORK_ROOT = r"C:\temp_virtu_sw"


def _run_worker(spec: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    spec_path = spec["result_path"].replace("result.json", "spec.json")
    os.makedirs(os.path.dirname(spec["result_path"]), exist_ok=True)
    with open(spec_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)
    if os.path.exists(spec["result_path"]):
        os.remove(spec["result_path"])
    try:
        p = subprocess.run([sys.executable, "-u", WORKER, spec_path],
                           capture_output=True, text=True, errors="replace",
                           timeout=timeout)
        rc, out = p.returncode, (p.stdout or "")[-2000:] + (p.stderr or "")[-2000:]
    except subprocess.TimeoutExpired as e:
        rc, out = -9, "TIMEOUT after %ss: %s" % (timeout, str(e)[:200])
    result = {"status": "error", "message": "worker produced no result", "worker_rc": rc,
              "worker_output": out}
    if os.path.exists(spec["result_path"]):
        try:
            result = json.load(open(spec["result_path"], encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            result["result_parse_error"] = str(e)[:200]
    result["worker_rc"] = rc
    if rc != 0 and result.get("status") != "ok":
        result.setdefault("worker_output", out)
    return result


def evaluate_gates(build: Dict[str, Any], draw: Dict[str, Any], occ: Dict[str, Any],
                   bom_parts: int, with_drawing: bool) -> Dict[str, bool]:
    b = build.get("steps", {}) if isinstance(build, dict) else {}
    imports = b.get("import", [])
    comps = b.get("components", [])
    contacts_ok = [m for m in b.get("contact_mates", []) if m.get("ok")]
    reopened = build.get("reopen", {}) if isinstance(build, dict) else {}
    reopened_mates = sum(len(c.get("mates") or []) for c in (reopened.get("components") or []))
    return {
        "bom_parts_ge_2": bom_parts >= 2,
        "extract_volumes": bool(occ.get("parts")) and all(
            p.get("roundtrip_ok") and p.get("face_match") for p in occ["parts"]),
        "sw_import_volume": bool(imports) and all(r.get("volume_match") for r in imports),
        "placement_exact": bool(comps) and all(c.get("placement_ok") for c in comps),
        "contact_mates_ge_1": len(contacts_ok) >= 1,
        "mate_persisted": reopened_mates >= len(contacts_ok) and reopened_mates > 0,
        "no_transform_drift": not build.get("transform_drift"),
        "volume_conservation": bool((build.get("assembly") or {}).get("volume_match")),
        "drawing_views": (not with_drawing) or (int(draw.get("view_count") or 0) >= 4
                                                and int(draw.get("reopen_view_count") or 0) >= 4),
    }


def run_pipeline(step_path: str, out_dir: str = "", with_drawing: bool = True,
                 workspace_root: str = "", build_timeout: int = 1800,
                 drawing_timeout: int = 900) -> Dict[str, Any]:
    root = os.path.abspath(workspace_root or ROOT)
    step_path = os.path.abspath(step_path)
    if not os.path.isfile(step_path):
        return {"status": "error", "message": "STEP not found: " + step_path}
    run_id = time.strftime("%Y%m%d_%H%M%S") + "_" + hashlib.sha256(
        open(step_path, "rb").read()).hexdigest()[:8]
    out_dir = os.path.abspath(out_dir or os.path.join(root, "runs", "assembly_pipeline", run_id))
    if not os.path.normcase(out_dir).startswith(os.path.normcase(root)):
        return {"status": "blocked", "message": "out_dir escapes workspace"}
    os.makedirs(out_dir, exist_ok=True)
    work = os.path.join(SW_WORK_ROOT, "virtu_" + run_id)
    parts_ascii = os.path.join(work, "parts")
    out_ascii = os.path.join(work, "out")
    os.makedirs(parts_ascii, exist_ok=True)
    os.makedirs(out_ascii, exist_ok=True)

    report: Dict[str, Any] = {"run_id": run_id, "source_step": step_path,
                              "workspace_out": out_dir, "sw_work_dir": work, "steps": {}}

    # 1. BOM（含旋转位姿）
    t0 = time.time()
    bom = StepBOM(step_path)
    bom_dict = bom.to_dict()
    kids = [c for c in bom_dict["tree"][0].get("children", []) if c.get("solids", 0) > 0] \
        if bom_dict.get("tree") else []
    report["steps"]["bom"] = {"status": "ok" if kids else "error", "ap": bom_dict["ap_version"],
                              "encoding": bom_dict["encoding"], "parts": len(kids),
                              "component_count": bom_dict["component_count"],
                              "placements": [c.get("placement", {}).get("origin_mm") for c in kids],
                              "rotations": [c.get("placement", {}).get("rotation_deg") for c in kids]}

    # 2. OCP 拆件 + 实测体积
    occ = extract_parts(step_path, os.path.join(out_dir, "parts_occ"))
    report["steps"]["extract"] = occ
    if occ.get("status") != "ok":
        report["status"] = "error"
        report["message"] = "OCP extract failed"
        _write_report(report, out_dir)
        return report

    parts = []
    for p in occ["parts"]:
        dst = os.path.join(parts_ascii, "p%d.step" % p["index"])
        shutil.copy(p["step_file"], dst)
        sfiles = []
        for k, sf in enumerate(p.get("solid_files") or []):
            sd = os.path.join(parts_ascii, "p%d_solid_%d.step" % (p["index"], k))
            shutil.copy(sf, sd)
            sfiles.append(sd)
        parts.append({"index": p["index"], "name": p["name"], "step_file": dst,
                      "solid_files": sfiles, "volume_mm3": p["volume_mm3"],
                      "faces": p["faces"], "solids": p["solids"],
                      "placement": p["placement"], "bbox_local_mm": p["bbox_local_mm"]})

    # 3. 配合推断
    inv = face_inventory(step_path)
    inferred = infer_mates(inv)
    report["steps"]["understand"] = {
        "status": "ok", "mate_candidates": inferred["mates"],
        "isolated_parts": inferred["isolated_parts"], "pair_count": inferred["pair_count"],
        "elapsed_s": round(time.time() - t0, 2)}

    # 4. SW 装配（唯一名称，避免 SW "同名文档已打开" 导致重开失败）
    asm_name = "wheel_mold_mated_" + run_id
    build_spec = {"stage": "build", "source_step": step_path, "parts": parts,
                  "mates": inferred["mates"], "inventory": inv,
                  "working_dir": work, "out_dir": out_ascii, "name": asm_name,
                  "part_prefix": "native_" + run_id,
                  "result_path": os.path.join(out_dir, "build_result.json")}
    build = _run_worker(build_spec, build_timeout)
    report["steps"]["build"] = build

    # 5. 工程图
    asm_path = os.path.join(out_ascii, asm_name + ".SLDASM")
    draw = {"status": "error", "message": "skipped"}
    if with_drawing and build.get("status") == "ok" and os.path.exists(asm_path):
        draw_spec = {"stage": "drawing", "assembly_path": asm_path, "out_dir": out_ascii,
                     "result_path": os.path.join(out_dir, "drawing_result.json")}
        draw = _run_worker(draw_spec, drawing_timeout)
    report["steps"]["drawing"] = draw

    # 6. 产物归档 + 门禁
    artifacts_dir = os.path.join(out_dir, "artifacts")
    os.makedirs(artifacts_dir, exist_ok=True)
    copied = []
    for name in (asm_name + ".SLDASM", asm_name + ".SLDDRW"):
        src = os.path.join(out_ascii, name)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(artifacts_dir, name))
            copied.append(name)
    for p in parts:
        for f in [p["step_file"]] + p["solid_files"]:
            if os.path.exists(f):
                shutil.copy(f, os.path.join(artifacts_dir, os.path.basename(f)))
    for src_dir in (out_ascii, work):
        if os.path.isdir(src_dir):
            for name in os.listdir(src_dir):
                if name.upper().endswith(".SLDPRT"):
                    shutil.copy(os.path.join(src_dir, name),
                                os.path.join(artifacts_dir, name))
    report["artifacts"] = copied

    b = build.get("steps", {}) if isinstance(build, dict) else {}
    comps = b.get("components", [])
    contacts_ok = [m for m in b.get("contact_mates", []) if m.get("ok")]
    reopened = build.get("reopen", {}) if isinstance(build, dict) else {}
    reopened_mates = sum(len(c.get("mates") or []) for c in (reopened.get("components") or []))
    gates = evaluate_gates(build, draw, occ, len(kids), with_drawing)
    report["gates"] = gates
    report["measured"] = {
        "part_volumes_mm3": {p["index"]: p["volume_mm3"] for p in parts},
        "assembly_volume_mm3": (build.get("assembly") or {}).get("volume_mm3"),
        "components": comps, "contact_mates": contacts_ok,
        "reopened_mates": reopened_mates,
        "drawing_view_count": draw.get("view_count"),
        "drawing_reopen_view_count": draw.get("reopen_view_count"),
    }
    ok = all(gates.values())
    report["status"] = "ok" if ok else "error"
    if not ok:
        report["failed_gates"] = [k for k, v in gates.items() if not v]
    _write_report(report, out_dir)
    return report


def _write_report(report: Dict[str, Any], out_dir: str) -> None:
    with open(os.path.join(out_dir, "verification.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    lines = ["# 装配体全流程验证报告", "",
             "- run_id: `%s`" % report.get("run_id"),
             "- STEP: `%s`" % report.get("source_step"),
             "- 状态: **%s**" % report.get("status"), ""]
    gates = report.get("gates") or {}
    if gates:
        lines.append("## 门禁")
        for k, v in gates.items():
            lines.append("- %s: %s" % (k, "PASS" if v else "FAIL"))
        lines.append("")
    m = report.get("measured") or {}
    if m:
        lines += ["## 实测",
                  "- 零件体积(mm³): `%s`" % json.dumps(m.get("part_volumes_mm3"), ensure_ascii=False),
                  "- 装配体积(mm³): %s" % m.get("assembly_volume_mm3"),
                  "- 接触配合: %s 个" % len(m.get("contact_mates") or []),
                  "- 重开配合条目: %s" % m.get("reopened_mates"),
                  "- 工程图视图: %s / 重开 %s" % (m.get("drawing_view_count"),
                                                m.get("drawing_reopen_view_count")), ""]
    if report.get("failed_gates"):
        lines.append("失败门禁: " + ", ".join(report["failed_gates"]))
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else ""
    res = run_pipeline(src, out)
    print(json.dumps(res, ensure_ascii=False, indent=2)[:6000])
    raise SystemExit(0 if res.get("status") == "ok" else 2)
