# -*- coding: utf-8 -*-
"""量产级数控加工仿真 Agent — 命令行入口。"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_PKG = Path(__file__).resolve()
_SIM_ROOT = _PKG.parent          # cnc_massprod_sim/
_WORKSPACE = _SIM_ROOT.parent    # D:/Virtu模型/
for _p in (str(_WORKSPACE), str(_SIM_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from cnc_massprod_sim import assurance, config  # noqa: E402
from cnc_massprod_sim.agent import MassProductionCNCSimAgent  # noqa: E402
from cnc_massprod_sim.reporting import ReportWriter  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="量产级数控加工仿真 Agent")
    ap.add_argument("--workpiece", action="append", default=None,
                    help="工件ID，可多次；默认全部三种原型")
    ap.add_argument("--dialect", action="append", default=None,
                    choices=config.SUPPORTED_DIALECTS,
                    help="方言 fanuc/siemens/hnc，可多次；默认全部")
    ap.add_argument("--step", type=float, default=1.0, help="逐帧采样步长 mm（默认1.0）")
    ap.add_argument("--batch", type=int, default=50, help="批量规模（默认50）")
    ap.add_argument("--out", default=None, help="输出目录，默认 cnc_massprod_sim/")
    ap.add_argument("--no-opcua", action="store_true", help="跳过 OPC UA 协议栈自检")
    args = ap.parse_args(argv)

    workpieces = args.workpiece or config.SUPPORTED_WORKPIECES
    dialects = args.dialect or config.SUPPORTED_DIALECTS
    for w in workpieces:
        if w not in config.SUPPORTED_WORKPIECES:
            ap.error(f"未知工件 {w}；可选 {config.SUPPORTED_WORKPIECES}")

    out = Path(args.out) if args.out else _SIM_ROOT
    agent = MassProductionCNCSimAgent()
    t0 = time.time()

    print(f"[SIM] 工件={len(workpieces)} 方言={len(dialects)} "
          f"采样步长={args.step}mm 批量={args.batch}")

    runs = []
    for wid in workpieces:
        for dia in dialects:
            r = agent.run_one(wid, dia, step_mm=args.step)
            # 量产保障层
            cfg = r["process_config"]
            q = cfg["quality"]
            a = assurance.build_assurance(
                workpiece_id=wid,
                dialect=dia,
                exec_summary=r["simulation"]["execution"],
                inter_summary=r["simulation"]["interference"]["summary"],
                quality={"tolerance_mm": q.get("tolerance_mm", 0.05)},
                config=cfg,
                target_cpk=float(q.get("target_cpk", 1.67)),
                takt_target_s=float(q.get("takt_target_s", 120.0)),
                batch_size=args.batch,
            )
            r["assurance"] = a
            runs.append(r)
            print(f"  [{wid}/{dia}] {r['status']} gates={r['gates']} "
                  f"frames={r['simulation']['frame_count']} "
                  f"minclr={r['simulation']['interference']['min_clearance_mm']}")

    summary = {
        "total": len(runs),
        "passed": sum(1 for r in runs if r["status"] == "PASS"),
        "failed": sum(1 for r in runs if r["status"] == "FAILED"),
        "elapsed_s": round(time.time() - t0, 2),
    }

    opcua_result = {"available": False, "read_back_ok": False,
                    "basis": "unmeasured", "reason": "skipped by --no-opcua"}
    if not args.no_opcua:
        opcua_result = assurance.opcua_selftest()
        print(f"[OPC UA] available={opcua_result.get('available')} "
              f"read_back_ok={opcua_result.get('read_back_ok')} "
              f"basis={opcua_result.get('basis')}")

    full = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "version": "1.0.0",
        "summary": summary,
        "parameters": {"sample_step_mm": args.step, "batch_size": args.batch,
                       "workpieces": workpieces, "dialects": dialects},
        "runs": runs,
        "opcua": opcua_result,
        "basis": "measured_deterministic_emulator + measured_geometry "
                 "+ simulated_spc(declared) + derived_assurance",
    }

    writer = ReportWriter(out)
    paths = writer.write_all(full)
    print(f"[SUMMARY] {summary}")
    print("[DELIVERABLES]")
    for k, v in paths.items():
        print(f"  {k}: {v}")

    return 0 if summary["failed"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
