# -*- coding: utf-8 -*-
"""给一次装配全流程运行封缄：内容指纹 + 每项指标口径/证据 + 证据文件 seal。

用法：python scripts/seal_assembly_run.py --run runs/model_drive_20261107_134057
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from virtu_eval.provenance import Metric, RunIdentity, render_table, seal_leg, verify_seal  # noqa: E402

RULERS = ["bridges/assembly_pipeline.py", "bridges/assembly_worker.py",
          "bridges/step_mates.py", "bridges/step_parts_occ.py", "bridges/step_bom.py"]
OLLAMA = os.environ.get("VIRTU_OLLAMA", "http://127.0.0.1:11434")


def _sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _model_digest(tag: str) -> dict:
    try:
        with urllib.request.urlopen(OLLAMA + "/api/tags", timeout=10) as r:
            for m in json.load(r).get("models", []):
                if m.get("name") == tag:
                    return {"tag": tag, "digest": m.get("digest"),
                            "size": m.get("size"), "quant": m.get("details", {}).get("quantization_level")}
    except Exception as e:  # noqa: BLE001
        return {"tag": tag, "error": str(e)[:120]}
    return {"tag": tag, "error": "tag not found"}


def seal_run(run_dir: str, owner: str = "assembly-pipeline") -> dict:
    vpath = os.path.join(run_dir, "verification.json")
    tpath = os.path.join(run_dir, "transcript.json")
    ver = json.load(open(vpath, encoding="utf-8"))
    tra = json.load(open(tpath, encoding="utf-8")) if os.path.exists(tpath) else {}
    m = ver.get("measured", {})
    model_tag = tra.get("model", "")
    ident = RunIdentity.capture(model_ids=[], case_dirs=[], ruler_files=RULERS,
                                extra={"step_sha256": _sha(ver["source_step"]),
                                       "model": _model_digest(model_tag) if model_tag else None})
    evidence = vpath
    metrics = []
    for idx, vol in (m.get("part_volumes_mm3") or {}).items():
        metrics.append(Metric("part_%s_volume_mm3" % idx, vol, basis="measured", n=1,
                              evidence=evidence, run_id=ident.run_id,
                              note="OCP 实测体积，与 SW 质量属性对账"))
    if m.get("assembly_volume_mm3") is not None:
        sumvol = sum((m.get("part_volumes_mm3") or {}).values())
        metrics.append(Metric("assembly_volume_mm3", m["assembly_volume_mm3"],
                              basis="measured", n=1, evidence=evidence, run_id=ident.run_id,
                              note="SW 装配质量属性；零件体积和=%.3f，差=%.3f mm3" % (
                                  sumvol, m["assembly_volume_mm3"] - sumvol)))
    metrics.append(Metric("contact_mates", len(m.get("contact_mates") or []), basis="measured",
                          n=1, evidence=evidence, run_id=ident.run_id,
                          note="选面核对曲面类型/半径；加配合后无漂移"))
    metrics.append(Metric("reopened_mate_entries", m.get("reopened_mates"), basis="measured",
                          n=1, evidence=evidence, run_id=ident.run_id,
                          note="重开 SLDASM 后 IComponent2.GetMates 条目数"))
    metrics.append(Metric("drawing_views", m.get("drawing_view_count"), basis="measured", n=1,
                          evidence=evidence, run_id=ident.run_id, note="GB 第一角三视图+等轴测"))
    metrics.append(Metric("drawing_reopen_views", m.get("drawing_reopen_view_count"),
                          basis="measured", n=1, evidence=evidence, run_id=ident.run_id,
                          note="重开 SLDDRW 后 IDrawingDoc.GetViewCount"))
    gates = ver.get("gates") or {}
    metrics.append(Metric("gates_passed", sum(1 for v in gates.values() if v), basis="measured",
                          n=len(gates), planned=len(gates), evidence=evidence,
                          run_id=ident.run_id, note="共 %d 项门禁" % len(gates)))
    if tra:
        calls = sum(len(r.get("tool_calls") or []) for r in tra.get("rounds") or [])
        metrics.append(Metric("model_tool_calls", calls, basis="measured", n=1,
                              evidence=tpath, run_id=ident.run_id,
                              note="driver=%s / served=%s" % (
                                  tra.get("driver"), tra.get("rounds", [{}])[0].get("served_model"))))
    for metric in metrics:
        metric.check()
    table = render_table(metrics)
    prov = {"run_id": ident.run_id, "captured_at": ident.captured_at,
            "artifacts": ident.artifacts, "cases": {"step": _sha(ver["source_step"])},
            "ruler": ident.ruler, "extra": ident.extra, "drift": ident.drift(),
            "verification": vpath, "transcript": tpath if tra else None,
            "metrics": [{"name": x.name, "value": x.value, "basis": x.basis, "n": x.n,
                         "evidence": x.evidence, "note": x.note} for x in metrics],
            "table": table, "status": ver.get("status")}
    with open(os.path.join(run_dir, "provenance.json"), "w", encoding="utf-8") as f:
        json.dump(prov, f, ensure_ascii=False, indent=2)
    with open(os.path.join(run_dir, "provenance.md"), "w", encoding="utf-8") as f:
        f.write("# 装配全流程证据封缄\n\n- run_id: `%s`\n- 状态: **%s**\n- STEP sha256: `%s`\n\n"
                "```\n%s\n```\n" % (ident.run_id, ver.get("status"),
                                    prov["cases"]["step"], table))
    # 证据文件封缄：写入 sealed/raw.jsonl 并 hash 固化
    sealed_dir = os.path.join(run_dir, "sealed")
    os.makedirs(sealed_dir, exist_ok=True)
    with open(os.path.join(sealed_dir, "raw.jsonl"), "w", encoding="utf-8") as f:
        for x in metrics:
            f.write(json.dumps({"metric": x.name, "value": x.value, "basis": x.basis,
                                "n": x.n, "evidence": x.evidence, "run_id": ident.run_id},
                               ensure_ascii=False) + "\n")
        f.write(json.dumps({"gate": "summary", "gates": gates,
                            "status": ver.get("status"), "run_id": ident.run_id},
                           ensure_ascii=False) + "\n")
    seal = seal_leg(sealed_dir, owner=owner)
    verify_seal(sealed_dir)
    prov["seal"] = seal
    with open(os.path.join(run_dir, "provenance.json"), "w", encoding="utf-8") as f:
        json.dump(prov, f, ensure_ascii=False, indent=2)
    return prov


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    args = ap.parse_args()
    p = seal_run(os.path.abspath(args.run))
    print(json.dumps({"run_id": p["run_id"], "status": p["status"], "drift": p["drift"],
                      "seal": p["seal"], "provenance": os.path.join(args.run, "provenance.json")},
                     ensure_ascii=False, indent=2))
