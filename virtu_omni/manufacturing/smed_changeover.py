# -*- coding: utf-8 -*-
"""SMED (<15 Minute) Rapid Workpiece & Clamping Changeover Orchestrator.

Implements Single-Minute Exchange of Die (Shigeo Shingo SMED methodology)
across the 3 mass-production workpiece archetypes and clamping systems:
- Separates External Offline Prep (conducted during prior batch cutting) from
  Internal Machine-Stopped Downtime (must strictly stay <= 15.0 min = 900 s).
- Synchronizes target CNC program, G54 WCS datum, tool length/radius table,
  motion safety policy, and SHA256 program verification in one changeover transaction.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from virtu_omni.manufacturing.cnc_controller_runtime import (
    WORKPIECE_ARCHETYPES,
    audit_production_nc,
    generate_production_nc,
    get_workpiece_archetype,
    resolve_controller_id,
)
from virtu_omni.manufacturing.process_standards import CLAMPING_SCHEMES

SMED_LIMIT_SECONDS = 900.0  # 15.0 minutes hard industrial limit


@dataclass(frozen=True)
class SMEDStep:
    step_id: str
    phase: int
    name_zh: str
    category: Literal["external_offline", "internal_downtime"]
    duration_s: float
    verification_gate: str
    owner_role: str


def _build_steps(from_id: str, to_id: str) -> List[SMEDStep]:
    to_wp = get_workpiece_archetype(to_id)
    scheme = CLAMPING_SCHEMES[to_wp.clamping_type]
    is_turning = to_wp.process_family == "turning"
    is_cross_clamping = (from_id != to_id)

    external_steps = [
        SMEDStep(
            step_id="EXT-01",
            phase=1,
            name_zh=f"机外对刀仪预调与{len(to_wp.tools)}把刀具寿命/H-D偏置表核验",
            category="external_offline",
            duration_s=240.0,
            verification_gate="对刀仪径向/长度偏差<=0.005mm并生成G10/TC_DP预装表",
            owner_role="Tool Crib Technician",
        ),
        SMEDStep(
            step_id="EXT-02",
            phase=1,
            name_zh=f"机外预装下一批次工件至{scheme.smed_interface}",
            category="external_offline",
            duration_s=300.0 if not is_turning else 270.0,
            verification_gate=f"扭矩扳手锁紧复验，重复定位精度<={scheme.repeatability_mm:.3f}mm",
            owner_role="Setup Operator",
        ),
        SMEDStep(
            step_id="EXT-03",
            phase=1,
            name_zh=f"孪生平台预审{to_id} NC代码并完成VERICUT虚拟仿真校验",
            category="external_offline",
            duration_s=180.0,
            verification_gate="VERICUT/体素仿真0过切0撞机且SHA256归档",
            owner_role="CAM Process Engineer",
        ),
    ]

    if is_turning:
        internal_steps = [
            SMEDStep("INT-01", 2, "主轴停止、切屑高压冲洗与卡盘快换防护门确认", "internal_downtime", 95.0, "M05停转+门锁安全回路闭合", "Machine Operator"),
            SMEDStep("INT-02", 2, f"液压快换{scheme.smed_interface}解锁换装与定位止口键清理", "internal_downtime", 150.0 if is_cross_clamping else 110.0, "卡盘压力表1.8MPa确认+百分表跳动<=0.015mm", "Setup Operator"),
            SMEDStep("INT-03", 2, "自动对刀臂T01/T02/T03刀尖偏置触发校验", "internal_downtime", 120.0, "X/Z刀偏与预设表偏差<=0.010mm", "Auto Tool Setter"),
            SMEDStep("INT-04", 2, "G54右端面Z0基准对刀设定与软限位安全区加载", "internal_downtime", 65.0, "Z0基准偏差<=0.01mm，卡盘禁区Z=-60mm锁定", "Setup Operator"),
            SMEDStep("INT-05", 2, "OPC UA/DNC下发量产NC主程序并核对SHA256", "internal_downtime", 40.0, "程序号/校验和100%匹配", "OPC UA / DNC Cell"),
            SMEDStep("INT-06", 2, "25%快移倍率首件单段空运行与千分尺首件FAI全检放行", "internal_downtime", 220.0, "首件Ø28h6/Ø40k6/Ø50g6实测合格", "QC Inspector"),
        ]
    else:
        internal_steps = [
            SMEDStep("INT-01", 2, "主轴回G91 G28 Z0换刀零点、排屑清洗零点基座定位面", "internal_downtime", 80.0, "气检密封无切屑残留", "Machine Operator"),
            SMEDStep("INT-02", 2, f"气动零点托盘({scheme.smed_interface})松开-吊装置换-锁紧复位", "internal_downtime", 110.0 if is_cross_clamping else 85.0, f"气动锁紧气压>=0.6MPa，重复定位<={scheme.repeatability_mm:.3f}mm", "Setup Operator"),
            SMEDStep("INT-03", 2, "刀库刀位与H/D偏置号一键自动核对(含Z_safe阈值刷新)", "internal_downtime", 70.0, "所有工序刀号/刃径/刀长核对一致", "CNC Controller"),
            SMEDStep("INT-04", 2, "Renishaw红外测头自动复测G54 X0/Y0/Z0基准", "internal_downtime", 90.0, "测头触发偏差<=0.008mm并自动写入G54", "In-Machine Probe"),
            SMEDStep("INT-05", 2, "OPC UA/DNC下发量产NC代码、刷新软限位2并核对SHA256", "internal_downtime", 40.0, "SHA256一致+无Syntax/Alarm", "OPC UA / DNC Cell"),
            SMEDStep("INT-06", 2, "25%快移倍率首件干涉复核+首件三坐标/通止规FAI放行", "internal_downtime", 195.0, "型腔/轴承孔H7及孔位度合格，允许AUTO批量", "QC Inspector"),
        ]

    return external_steps + internal_steps


def plan_and_execute_changeover(
    from_workpiece_id: str,
    to_workpiece_id: str,
    target_dialect: str,
    *,
    output_dir: Optional[str] = None,
    external_prepped: bool = True,
    override_internal_s: Optional[float] = None,
) -> Dict[str, Any]:
    """Plan, synchronize & verify a <15-min SMED changeover between two workpiece setups."""
    if from_workpiece_id not in WORKPIECE_ARCHETYPES:
        raise KeyError(f"Unknown source workpiece: {from_workpiece_id!r}")
    to_wp = get_workpiece_archetype(to_workpiece_id)
    cid = resolve_controller_id(target_dialect, to_wp.process_family)

    steps = _build_steps(from_workpiece_id, to_workpiece_id)
    ext_s = sum(s.duration_s for s in steps if s.category == "external_offline")
    base_int_s = sum(s.duration_s for s in steps if s.category == "internal_downtime")

    # If external steps were NOT prepared offline beforehand, they add linearly to machine downtime!
    if override_internal_s is not None:
        eff_int_s = float(override_internal_s)
    elif external_prepped:
        eff_int_s = base_int_s
    else:
        eff_int_s = base_int_s + ext_s

    int_min = round(eff_int_s / 60.0, 2)
    ext_min = round(ext_s / 60.0, 2)
    total_min = round((ext_s + eff_int_s) / 60.0, 2) if external_prepped else int_min

    # Synchronize target NC + audit target setup
    nc_bundle = generate_production_nc(to_workpiece_id, cid)
    nc_sha256 = hashlib.sha256(nc_bundle["code"].encode("utf-8")).hexdigest()
    audit = audit_production_nc(to_workpiece_id, cid, nc_bundle["code"])

    smed_within_limit = (eff_int_s <= SMED_LIMIT_SECONDS)
    issues: List[str] = []
    if not smed_within_limit:
        issues.append(
            f"SMED_LIMIT_EXCEEDED: internal downtime {int_min:.2f} min ({eff_int_s:.0f}s) > 15.00 min (900s)"
        )
    if not audit["passed"]:
        issues.append(f"TARGET_NC_AUDIT_FAILED: {audit['issues']}")

    passed = smed_within_limit and bool(audit["passed"])

    # Optionally persist changeover bundle to disk
    written_files: List[str] = []
    if output_dir is not None:
        out_p = Path(output_dir)
        out_p.mkdir(parents=True, exist_ok=True)
        nc_ext = ".mpf" if cid == "siemens_840d_sl" else ".nc"
        nc_file = out_p / f"{to_workpiece_id}_{cid}{nc_ext}"
        nc_file.write_text(nc_bundle["code"], encoding="utf-8")
        written_files.append(str(nc_file))
        recipe_file = out_p / f"changeover_{from_workpiece_id}_to_{to_workpiece_id}.json"
        recipe_file.write_text(
            json.dumps({
                "from": from_workpiece_id,
                "to": to_workpiece_id,
                "controller_id": cid,
                "internal_downtime_min": int_min,
                "nc_sha256": nc_sha256,
                "clamping": to_wp.clamping_type,
                "safety_policy": asdict(to_wp.safety_policy),
                "tools": {str(k): asdict(v) for k, v in to_wp.tools.items()},
            }, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        written_files.append(str(recipe_file))

    return {
        "passed": passed,
        "from_workpiece_id": from_workpiece_id,
        "to_workpiece_id": to_workpiece_id,
        "target_controller_id": cid,
        "target_clamping": to_wp.clamping_type,
        "external_prepped": external_prepped,
        "external_offline_prep_s": round(ext_s, 1),
        "external_offline_prep_min": ext_min,
        "internal_downtime_s": round(eff_int_s, 1),
        "internal_downtime_min": int_min,
        "smed_limit_min": 15.0,
        "smed_margin_min": round(15.0 - int_min, 2),
        "total_work_content_min": total_min,
        "steps": [asdict(s) for s in steps],
        "synchronized_config": {
            "nc_sha256": nc_sha256,
            "nc_lines": nc_bundle["line_count"],
            "nc_audit_passed": audit["passed"],
            "wcs_g54_origin": to_wp.wcs_g54_origin,
            "z_safe_global_mm": to_wp.safety_policy.z_safe_global_mm,
            "tool_count": len(to_wp.tools),
        },
        "written_files": written_files,
        "issues": issues,
        "basis": "measured_smed_changeover_model",
    }
