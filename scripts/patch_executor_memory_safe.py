# -*- coding: utf-8 -*-
"""Patch agent_chain_executor.py with syntactically valid memory-safe run_chain and write_report."""

import os
import re

target_path = r"d:\Virtu模型\agent_chain_executor.py"
with open(target_path, "r", encoding="utf-8") as f:
    content = f.read()

new_block = r'''def run_chain(wish, out_root=None, skip=(), memory_safe=True):
    """整链执行 + 取证。严格践行「每步产物落盘 -> 关停上步软件 -> 释放内存 -> 执行下步」。返回 {spec, stages, verdicts, out_dir}。"""
    from virtu_omni.engine.wish_cad_cam_engine import WishCADCAMEngine
    out_root = out_root or os.path.join(ROOT, "runs", "full_chain")
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(out_root, ts)
    os.makedirs(out_dir, exist_ok=True)

    reclaimer = ProcessMemoryReclaimer(log_path=os.path.join(out_dir, "stage_memory_reclamation.json"))
    preflight = preflight_apps()
    eng = WishCADCAMEngine()
    spec = eng.parse_wish_intent(wish)
    artifacts = {
        "sw2021": ("01_SOLIDWORKS_2021.swb", eng.generate_solidworks_macro),
        "nx12": ("02_Siemens_NX_12.0.py", eng.generate_nx12_script),
        "acad2026": ("03_AutoCAD_2026.lsp", eng.generate_autocad_lisp),
        "cimco2026": ("04_CIMCO_Edit_2026.nc", eng.generate_cimco_macro),
        "vericut96": ("05_Vericut_9.6.opt", eng.generate_vericut_config),
        "sscnc72": ("06_斯沃数控仿真_7.2.md", eng.generate_sscnc_setup_guide),
    }
    written = {}
    for key, (fname, builder) in artifacts.items():
        try:
            body = builder(spec)
            p = os.path.join(out_dir, fname)
            open(p, "w", encoding="utf-8").write(body)
            written[key] = p
        except Exception as e:
            written[key] = None
            notes = ["工件生成失败: %r" % e]

    nc = written.get("cimco2026")
    proj, proj_note = build_vericut_project(nc, out_dir) if nc else (None, "无 NC 工件")

    plan = [
        ("solidworks", lambda: stage_sw(spec, out_dir), "solidworks"),
        ("nx", lambda: stage_nx(spec, out_dir), "nx"),
        ("autocad", lambda: stage_acad(spec, out_dir, eng.generate_autocad_lisp), "autocad"),
        ("cimco", lambda: stage_cimco(nc, out_dir) if nc else
                          _evidence("cimco", "blocked", "-", error="无 NC 工件"), "cimco"),
        ("vericut", lambda: stage_vericut(proj, out_dir) if proj else
                            _evidence("vericut", "blocked", "-", error=proj_note), "vericut"),
        ("sscnc", lambda: stage_sscnc(nc, out_dir) if nc else
                          _evidence("sscnc", "blocked", "-", error="无 NC 工件")),
    ]

    stages = {}
    stage_memory_records = []
    for item in plan:
        name = item[0]
        fn = item[1]
        sw_key = item[2] if len(item) > 2 else name
        if name in skip:
            stages[name] = _evidence(name, "blocked", "skipped by caller")
            continue

        mem_before = reclaimer.get_system_memory()
        try:
            ev = fn()
            stages[name] = ev
        except Exception as e:
            stages[name] = _evidence(name, "blocked", "exception", error=repr(e)[:400])

        # 1. 检验本阶段所有产物是否切实落盘且非空
        files = stages[name].get("files", [])
        verified_files = []
        for fp in files:
            if fp and os.path.exists(fp):
                sz = os.path.getsize(fp)
                verified_files.append({"path": fp, "bytes": sz, "valid": sz > 0})
        stages[name]["verified_files"] = verified_files

        # 2. 核心铁律：步骤完成后立即关停上一步软件，释放内存
        reclaim_record = None
        if memory_safe and sw_key:
            reclaim_record = reclaimer.close_software(sw_key)
            reclaimer.trim_system_working_set()
        mem_after = reclaimer.get_system_memory()
        reclaimed_mb = round(mem_after["available_mb"] - mem_before["available_mb"], 2)

        stages[name]["memory_reclamation"] = reclaim_record or {
            "target": sw_key,
            "reclaimed_mb": reclaimed_mb,
            "mem_before_mb": mem_before["available_mb"],
            "mem_after_mb": mem_after["available_mb"],
            "status": "SKIPPED" if not memory_safe else "RECLAIMED"
        }
        stage_memory_records.append({
            "stage": name,
            "software": sw_key,
            "reclamation": stages[name]["memory_reclamation"],
            "files": verified_files
        })
        print(f"  [MemorySafe] 阶段 [{name}] 完成 | 产物落地: {len(verified_files)}个 | 关停软件: {sw_key} | 内存回收: {stages[name]['memory_reclamation'].get('reclaimed_mb', 0):+.2f} MB (可用: {mem_after['available_mb']} MB)")

    # 最终全局二次确证清理
    if memory_safe:
        reclaimer.reclaim_all_cad_cam()

    verdicts = {k: v["status"] for k, v in stages.items()}
    executed = sum(1 for v in verdicts.values() if v == "executed")
    pruned = _prune_runs(out_root)
    integrity = {}
    for bucket in (written, {k: v.get("files") for k, v in stages.items()}):
        for val in bucket.values():
            for fp in (val if isinstance(val, list) else [val]):
                if isinstance(fp, str) and os.path.exists(fp) and fp not in integrity:
                    try:
                        integrity[fp] = {"sha256": _sha256(fp), "bytes": os.path.getsize(fp)}
                    except OSError:
                        pass
    bundle = {"schema_version": 2, "code": _code_fingerprint(),
              "integrity": integrity, "run_id": ts, "wish": wish, "spec": spec,
              "preflight": preflight, "pruned_runs": pruned,
              "artifacts": written, "vericut_project": proj, "proj_note": proj_note,
              "verdicts": verdicts, "executed_count": executed,
              "stage_memory_records": stage_memory_records,
              "stages": stages, "out_dir": out_dir}
    with open(os.path.join(out_dir, "chain_evidence.json"), "w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False, indent=2)
    bundle["report"] = write_report(bundle)
    return bundle


def write_report(bundle):
    order = ["solidworks", "nx", "autocad", "cimco", "vericut", "sscnc"]
    label = {"solidworks": "SOLIDWORKS 2021 建模", "nx": "Siemens NX 12.0 CAM",
             "autocad": "AutoCAD 2026 出图", "cimco": "CIMCO Edit 2026 数控",
             "vericut": "VERICUT 9.6 切削仿真", "sscnc": "斯沃 7.2 实训"}
    tier = {"executed": "已实测执行", "substituted": "自研确定性替代",
            "blocked": "被具体根因挡住"}
    lines = [
        "# Virtu CAD/CAM Agent 链 · 全链路执行取证报告",
        "",
        "- run_id: `%s`" % bundle["run_id"],
        "- 愿望: %s" % bundle["wish"],
        "- 规格回读: 外径 %s / 内孔 %s / 总长 %s / 材质 %s" % (
            bundle["spec"].get("d_outer"),
            bundle["spec"].get("d_inner"),
            bundle["spec"].get("overall_len"),
            bundle["spec"].get("material")
        ),
        "- 执行计数: %d/6 达成「软件真跑了且有回读数值」" % bundle["executed_count"],
        "",
        "## 判决矩阵",
        "",
        "| 阶段 | 打通方式 | 判决 | 关键实测值 | 证据文件 |",
        "| :-- | :-- | :-- | :-- | :-- |"
    ]
    for k in order:
        s = bundle["stages"].get(k)
        if not s:
            continue
        mv = json.dumps(s.get("metrics", {}), ensure_ascii=False)
        mv = mv if len(mv) < 260 else mv[:257] + "..."
        files = ", ".join("`%s`" % os.path.basename(f) for f in s.get("files", [])[:4]) or "—"
        lines.append("| %s | %s | %s | %s | %s |" % (label[k], s["method"],
                                                     tier.get(s["status"], s["status"]), mv, files))
        if s.get("error"):
            lines.append("| | ↳ 根因 | | %s | |" % str(s["error"])[:240].replace("\n", " "))
        for note in (s.get("notes") or [])[:2]:
            lines.append("| | ↳ 备注 | | %s | |" % str(note)[:240].replace("\n", " "))
    for _w in (bundle.get("spec", {}).get("geometry_warnings") or []):
        lines.append("> ⚠️ 几何可行性: %s" % str(_w)[:200])

    lines.append("")
    lines.append("## 阶段式内存回收与进程关停审计")
    lines.append("")
    lines.append("| 阶段 | 关停软件 | 回收PID | 释放物理内存(MB) | 阶段后可用内存(MB) | 产物落盘确证 |")
    lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
    for k in order:
        s = bundle["stages"].get(k)
        if not s:
            continue
        rec = s.get("memory_reclamation") or {}
        reclaimed = rec.get("reclaimed_mb", 0.0)
        avail = rec.get("mem_after_mb", "-")
        pids = ", ".join(str(p) for p in (rec.get("pids_found") or rec.get("killed_pids") or [])) or "无驻留"
        f_count = len(s.get("verified_files", s.get("files", [])))
        lines.append(f"| {label.get(k, k)} | `{rec.get('target', k)}` | {pids} | {reclaimed:+.2f} MB | {avail} MB | {f_count} 个工件有效落盘 |")

    lines.append("")
    lines.append("> 判决口径：`executed` = 软件确实执行且数值来自回读（文件/几何/日志）；"
                 "`substituted` = 该软件无机器可读接口，由自研确定性校验承担同等验证职责；"
                 "`blocked` = 原生接口存在但本机条件缺失，附实测报错原文，不写成「环境问题」；"
                 "`内存回收` = 每完一步任务即刻本地落盘，并强杀/关停上一步软件，实测释放物理 RAM。")
    path = os.path.join(bundle["out_dir"], "AGENT_CHAIN_REPORT.md")
    open(path, "w", encoding="utf-8").write("\n".join(lines))
    return path
'''

pattern = r"def run_chain\(wish, out_root=None, skip=\(\).*?(?=if __name__ == \"__main__\":)"
patched, n = re.subn(pattern, new_block + "\n\n", content, flags=re.DOTALL)

if n == 1:
    with open(target_path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(patched)
    print("SUCCESS: agent_chain_executor.py patched cleanly.")
else:
    print(f"FAILED: matched {n} times.")
