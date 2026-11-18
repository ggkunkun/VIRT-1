# -*- coding: utf-8 -*-
"""AE-CI-258 量产 NC 生成 + 全流程验证 + 报告/清单/手册。

用法: .venv/Scripts/python.exe scripts/build_production_nc.py
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from virtu_prod import assurance, config, lint, opcua, post, programs, report, sim  # noqa: E402

OUT = ROOT / "production"
NC_DIR = OUT / "nc"
REP_DIR = OUT / "reports"
PROJ = Path(r"E:\vericut_impeller_run\proj.vcproject")
PROJ_OP3 = Path(r"E:\vericut_impeller_run\OP3.vcproject")
RIG_NC = Path(r"E:\vericut_impeller_run\impeller.nc")


def runtime(m) -> Dict:
    return {
        "label": m.label, "controller": m.controller, "dialect": m.dialect,
        "safe_z": 10.0, "tc_z": m.tool_change_point["z"],
        "tc_x": m.tool_change_point["x"], "tc_y": m.tool_change_point["y"],
        "travel_mm": {k: list(v) for k, v in m.travel_mm.items()},
        "rotary_limits_deg": {k: list(v) for k, v in m.rotary_limits_deg.items()},
        "rotary": {k: list(v) for k, v in m.rotary_limits_deg.items()},
        "tool_change_s": m.tool_change_s,
    }


def stock_dict(p: config.Process) -> Dict:
    return {"material": p.part["material"],
            "size": [float(v) for v in p.stock["size_mm"]]}


def tool_dict(p: config.Process) -> Dict[str, Dict]:
    return {tid: {"id": tid, "diameter": t.diameter_mm, "gauge_length": t.gauge_length_mm,
                  "holder_length": t.holder_length_mm,
                  "holder_radius": t.holder_diameter_mm / 2.0,
                  "taylor_c": t.taylor_c, "taylor_n": t.taylor_n}
            for tid, t in p.tools.items()}


def neutral_feed_points(prog: programs.Program) -> List:
    pts = []
    for op in prog.operations:
        x = y = z = 0.0
        for b in op.blocks:
            if b.x is not None:
                x = b.x
            if b.y is not None:
                y = b.y
            if b.z is not None:
                z = b.z
            if b.kind != "rapid":
                pts.append((x, y, z))
    return pts


def roundtrip(prog: programs.Program, parsed) -> Dict:
    want = neutral_feed_points(prog)
    got = [(m.x, m.y, m.z) for m in parsed.moves if m.kind != "rapid"]
    idx = 0
    matched = 0
    max_err = 0.0
    for wx, wy, wz in want:
        while idx < len(got):
            gx, gy, gz = got[idx]
            idx += 1
            err = max(abs(wx - gx), abs(wy - gy), abs(wz - gz))
            if err <= 1e-3:
                matched += 1
                max_err = max(max_err, err)
                break
    return {"matched": matched, "expected": len(want),
            "max_err_mm": round(max_err, 6),
            "verdict": "PASS" if matched == len(want) else "FAIL"}


def main() -> int:
    t_start = time.perf_counter()
    p = config.load()
    bbox = programs.design_bbox(p.part["design_file"])
    cfg_checks = config.validate(p, bbox)
    cfg_sum = config.summary(cfg_checks)

    built = programs.build_all(p)
    prod_keys = [k for k, m in p.machines.items() if m.production_ready]
    results_programs = []
    audits = []
    violations = []
    NC_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {"part": p.part["id"], "programs": {}, "hashes": {}}
    op_cycle: Dict[str, float] = {}
    op_cut: Dict[str, float] = {}

    scenes = {"OP1": PROJ, "OP2": PROJ, "OP3": PROJ_OP3}
    scene_cache = {}

    for key in prod_keys:
        m = p.machines[key]
        mach = runtime(m)
        for prog in built:
            emission = post.emit(prog, mach, stock_dict(p))
            nc = emission["nc"]
            parsed = sim.parse(nc, m.dialect)
            rt = roundtrip(prog, parsed)
            ln = lint.lint(nc, m.dialect, mach, tool_dict(p), len(prog.operations),
                           p.safety["safe_z_work_mm"])
            cyc = sim.cycle_time(parsed, mach)
            path = NC_DIR / key / f"{prog.part_id}_{prog.op_id}.nc"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(nc, encoding="utf-8", newline="\r\n")
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            results_programs.append({
                "op": prog.op_id, "dialect": m.dialect, "machine": key,
                "nc_file": str(path), "lines": len(nc.splitlines()), "sha256": sha,
                "lint": ln, "roundtrip": rt, "cycle": cyc,
                "restart": emission["restart"],
            })
            manifest["programs"][f"{key}/{prog.op_id}"] = {
                "file": str(path), "sha256": sha, "restart": emission["restart"]}
            if m.dialect == "fanuc":
                op_cycle[prog.op_id] = cyc["total_s"]
                op_cut[prog.op_id] = round(sum(cyc["cut_time_s"].values()), 1)

    if cfg_sum["verdict"] != "PASS":
        results_programs_for_report = results_programs
    else:
        results_programs_for_report = results_programs

    # 扫掠碰撞（FANUC 为准；三方言几何一致性由 roundtrip 证明）
    for prog in built:
        m = p.machines["prod_5ax_fanuc_0imf"]
        mach = runtime(m)
        emission = post.emit(prog, mach, stock_dict(p))
        parsed = sim.parse(emission["nc"], "fanuc")
        sp = scenes[prog.op_id]
        if sp not in scene_cache:
            scene_cache[sp] = sim.load_scene(sp)
        audit = sim.audit(parsed, scene_cache[sp], mach, tool_dict(p),
                          float(p.stock["world_z_mm"][1]),
                          {"sample_step_mm": 2.0,
                           "gouge_tolerance_mm": p.safety["gouge_tolerance_mm"],
                           "holder_clearance_mm": p.safety["holder_clearance_mm"]},
                          station=prog.op_id)
        audits.append({"op": prog.op_id, "samples": audit["samples"],
                       "checks": audit["checks"],
                       "min_clearance": audit["min_clearance"]})
        violations.extend([{**v, "op": prog.op_id} for v in audit["violations"]])

    # 培训工位（VERICUT NMV1500 简化模型）行程能力
    rig = p.machines["training_rig_nmv1500"]
    rig_mach = runtime(rig)
    rig_emit = post.emit(built[0], rig_mach, stock_dict(p))
    rig_parsed = sim.parse(rig_emit["nc"], "fanuc")
    rig_audit = sim.audit(rig_parsed, {}, rig_mach, tool_dict(p),
                          float(p.stock["world_z_mm"][1]),
                          {"sample_step_mm": 5.0})
    rig_travel = next((c for c in rig_audit["checks"] if c["gate"] == "MACHINE-TRAVEL"), {})

    # 刀具磨损（按实测节拍）
    wear = []
    for tid, t in p.tools.items():
        used = 0.0
        for prog in built:
            for op in prog.operations:
                if op.tool.tid == tid:
                    used += op_cut.get(prog.op_id, 0.0) / 60.0
        vc = 3.141592653589793 * t.diameter_mm * 700.0 / 1000.0 if tid == "T1" \
            else 3.141592653589793 * t.diameter_mm * 950.0 / 1000.0
        wear.append(assurance.tool_wear({"id": tid, "taylor_c": t.taylor_c,
                                         "taylor_n": t.taylor_n}, vc, used))
    cands = []
    for a in audits:
        for k in ("fixture", "stock_holder"):
            v = a["min_clearance"].get(k)
            if v is not None:
                cands.append(v)
    min_clear = min(cands) if cands else None
    risk = assurance.collision_risk(min_clear, p.safety["holder_clearance_mm"])
    tol = float(p.quality["tolerance_mm"])
    spc_demo = assurance.simulated_spc_demo(tol, -tol)
    batch = assurance.batch_plan(int(p.production["batch_size"]), op_cycle, wear)

    # 毛坯唯一性（复用场景物理校验器的 G-UNIQUE）
    import importlib.util
    spec_v = importlib.util.spec_from_file_location(
        "verify_scene_physics", ROOT / "scripts" / "verify_scene_physics.py")
    vsp = importlib.util.module_from_spec(spec_v)
    spec_v.loader.exec_module(vsp)
    stock_unique = vsp.stock_uniqueness(PROJ)

    t0 = time.perf_counter()
    p2 = config.load()
    for pr in programs.build_all(p2):
        post.emit(pr, runtime(p2.machines["prod_5ax_fanuc_0imf"]), stock_dict(p2))
    software_s = time.perf_counter() - t0
    chg = assurance.changeover_plan(software_s)
    warns = assurance.warnings_report(wear, risk, spc_demo["stats"], op_cycle,
                                     p.production["cycle_target_s"])

    try:
        ocs = opcua.selftest()
    except Exception as exc:  # noqa: BLE001
        ocs = {"available": False, "reason": str(exc), "basis": "unmeasured"}

    op_params = []
    mat = p.standards["materials"][p.part["material"]]["machining"]
    for o in p.operations:
        t = p.tools[o["tool"]]
        vc = 3.141592653589793 * t.diameter_mm * o["rpm"] / 1000.0
        fz = o["feed_cut"] / (o["rpm"] * t.flutes)
        ct = o.get("cut_type", "rough")
        ok = mat["vc_m_min"][ct][0] <= vc <= mat["vc_m_min"][ct][1] and \
            mat["fz_mm_z"][ct][0] <= fz <= mat["fz_mm_z"][ct][1]
        op_params.append({"op": o["id"], "tool": o["tool"], "rpm": o["rpm"],
                          "vc": round(vc, 1), "feed": o["feed_cut"], "fz": round(fz, 4),
                          "ap": str(o["strategy"].get("step_z_mm",
                                                      o["strategy"].get("face_step_mm", "—"))),
                          "cut_type": ct, "status": "PASS" if ok else "FAIL"})

    machines_rows = []
    for key, m in p.machines.items():
        note = "量产可用" if m.production_ready else \
            f"Y 行程 {m.travel_mm['y']} 覆盖不足（需 ±145），禁止用于 Ø264 毛坯"
        if key == "training_rig_nmv1500":
            note += f"；行程门={rig_travel.get('status', '-')}，" \
                    f"违规 {rig_travel.get('evidence', {}).get('violations', '-')} 点"
        machines_rows.append({"key": key, "controller": m.controller,
                              "production_ready": m.production_ready,
                              "travel": m.travel_mm, "note": note})

    lint_ok = all(pr["lint"]["verdict"] == "PASS" for pr in results_programs)
    rt_ok = all(pr["roundtrip"]["verdict"] == "PASS" for pr in results_programs)
    collision_ok = all(
        next(c for c in a["checks"] if c["gate"] == g)["status"] == "PASS"
        for a in audits for g in ("FIXTURE-CLEARANCE", "DESIGN-GOUGE",
                                  "DESIGN-SURFACE", "HOLDER-STOCK"))
    travel_ok = all(next(c for c in a["checks"] if c["gate"] == "MACHINE-TRAVEL")["status"]
                    == "PASS" for a in audits)
    overall = "PASS" if (cfg_sum["verdict"] == "PASS" and lint_ok and rt_ok
                         and collision_ok and travel_ok) else "FAIL"

    res = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "part": p.part, "stock": {
            "size": p.stock["size_mm"], "form": p.stock["form"],
            "chamfer": p.stock["chamfer_bottom_mm"],
            "allow": p.stock["allowances_mm"]},
        "stations": {k: {"fixture": v["fixture"], "work_zero": v["work_zero"],
                         "stock_top": v["stock_top_world_z"]}
                     for k, v in p.stations.items()},
        "safety": {"safe_z": p.safety["safe_z_work_mm"],
                   "rapid_reduction": p.safety["rapid_reduction_mm"],
                   "rotary": "B -180..160 / C 0..360"},
        "config_checks": cfg_checks, "config_summary": cfg_sum,
        "machines": machines_rows,
        "programs": results_programs,
        "audits": audits, "violations": violations,
        "wear": wear, "risk": risk,
        "stock_unique": stock_unique,
        "min_fixture": min([v for v in (a["min_clearance"]["fixture"] for a in audits)
                            if v is not None], default=None),
        "min_holder": min([v for v in (a["min_clearance"]["stock_holder"] for a in audits)
                           if v is not None], default=None),
        "op_cycle_s": op_cycle, "op_cut_s": op_cut,
        "spc": {"stats": spc_demo["stats"], "samples": spc_demo["samples"]},
        "batch": batch, "changeover": chg, "warnings": warns, "opcua": ocs,
        "op_params": op_params,
        "verdicts": {"lint": "PASS" if lint_ok else "FAIL",
                     "roundtrip": "PASS" if rt_ok else "FAIL",
                     "collision": "PASS" if collision_ok else "FAIL",
                     "travel": "PASS" if travel_ok else "FAIL",
                     "overall": overall},
        "limitations": [
            "- 未执行 VERICUT 运行级仿真（batch 介质不执行仿真），碰撞/过切为自研扫掠几何实测（采样步长 2 mm），不是 VERICUT 逐帧布尔材料去除。",
            "- 未做实机首件：三坐标叶型、超声壁厚、动平衡、表面粗糙度均未测。",
            "- 刀具寿命为 Taylor 模型推导，非刀具寿命试验；每刀件数为推导值。",
            "- SPC 为模拟样本演示（basis=simulated），Cpk 不代表真实批次；量产须用首件与抽检实测替换。",
            "- 五轴 RTCP 的机床摆长/枢轴标定未纳入；Siemens 方向按 A3/B3/C3 向量发射，未在 840D sl 实机验证。",
            "- 换产的现场步骤时间为计划值，软件侧重构时间为实测。",
            "- VERICUT 培训模型 NMV1500 的 Y 行程仅 210 mm，无法覆盖本零件；见机床能力表。",
        ],
        "findings": [
            "OP1 原程序在切削深度处执行 G01 X125.5 横移，实测切入叶片 1.5 mm（过切）；本版已删除该横移，改为抬刀后回安全高度。",
            "OP2 原路径基准角取自 camber_theta()（叶片中线），实测刀具走在叶片实体上（最深 22.6 mm）；本版加半个叶距（11.25°）偏置，流道采样点 0/35 落在实体外。",
            "OP2 原程序只旋转 C 不旋转 XY；按转台式工作坐标系，16 条流道会重合成同一条；本版在零件坐标系内按 base 旋转刀路，并取 C=-(θ+base) 使流道正对主轴。",
            "流道出口位于夹持带下方（工作 Z -71.85..-58.16，钳口顶 -58.85），从外圆进入会切穿盖板（实测过切 ≤0.93 mm）；本版改为从进气口进入，出口残留段留待 OP3。",
            "VERICUT 工程的 G54 指向 Stock 组件坐标系（原点在世界 -100），与 NC 的 Z0=毛坯顶面不一致；建议按官方样例增加 NC_ZERO 组件（本版未改工程，因 batch 无法复验）。",
            "OP1 为整圆空切策略，单件节拍 122 min 中大部分为空行程；建议量产改四角扇形或自适应开粗（本版保持已验几何，仅如实计量）。",
        ],
        "manifest": manifest,
        "elapsed_s": round(time.perf_counter() - t_start, 1),
    }
    paths = report.write_reports(res, REP_DIR)
    (REP_DIR / "nc_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"config": cfg_sum, "verdicts": res["verdicts"],
                      "programs": len(results_programs),
                      "audits": [{"op": a["op"], "min": a["min_clearance"]} for a in audits],
                      "rig_travel": rig_travel.get("status"),
                      "reports": paths}, ensure_ascii=False, indent=2))
    return 0 if overall == "PASS" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        raise SystemExit(3)
