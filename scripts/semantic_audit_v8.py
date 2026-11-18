#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验收后语义审计：把某版本三轮 G71 回答同时过「令牌门」与「语义门」，输出对照表。

用法：python scripts/semantic_audit_v8.py v8
读取 runs/full_repair_<ver>_*/verify_<tag>_r*.json，写 reports/G71_SEMANTIC_AUDIT_<ver>.json
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "cloud_train_pack"))
import deploy_trained_adapter as grader  # noqa: E402
from g71_semantic_check import check_g71_step_shaft  # noqa: E402


def audit(ver: str) -> dict:
    pats = [
        str(ROOT / "runs" / f"*{ver}*" / "verify_*_r*.json"),
        str(ROOT / "runs" / f"full_repair_{ver}_*" / "verify_*_r*.json"),
    ]
    files: list[str] = []
    for p in pats:
        files.extend(glob.glob(p))
    files = sorted(set(files))
    rounds = []
    for f in files:
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        a = (d.get("detail") or {}).get("fanuc_g71_safety_probe") or {}
        txt = a.get("full_response", "") or ""
        tok = bool(a.get("passed"))
        sem = check_g71_step_shaft(txt)
        rounds.append({
            "file": Path(f).name,
            "round": d.get("round"),
            "tag": d.get("tag"),
            "token_gate": tok,
            "semantic_gate": sem["passed"],
            "violations": sem["violations"],
            "evidence": {k: sem["evidence"].get(k) for k in
                         ("z_min_at_step", "shoulder_z", "z_min_after_shoulder", "profile_end_X", "profile_motion_blocks")},
            "program": txt[:1200],
        })
    ok = sum(1 for r in rounds if r["semantic_gate"])
    out = {
        "version": ver,
        "rounds": rounds,
        "token_gate_passed": sum(1 for r in rounds if r["token_gate"]),
        "semantic_gate_passed": ok,
        "total_rounds": len(rounds),
        "semantic_gate_all_pass": bool(rounds) and ok == len(rounds),
    }
    p = ROOT / "reports" / f"G71_SEMANTIC_AUDIT_{ver}.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    v = (sys.argv[1] if len(sys.argv) > 1 else "v8").strip().lstrip("v")
    r = audit("v" + v)
    print(f"version=v{v} rounds={r['total_rounds']} token_gate={r['token_gate_passed']}/{r['total_rounds']} "
          f"semantic_gate={r['semantic_gate_passed']}/{r['total_rounds']}")
    for x in r["rounds"]:
        print(f"  r{x['round']}: token={'P' if x['token_gate'] else 'F'} semantic={'P' if x['semantic_gate'] else 'F'} "
              f"{','.join(x['violations'][:4])}")
    print(f"report → reports/G71_SEMANTIC_AUDIT_v{v}.json")
