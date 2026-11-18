# -*- coding: utf-8 -*-
"""叶轮修复少样本构建器（飞轮 builder+setup+inspector 最小实现，非模型锚=独立尺子）。

每条演示的「修正后参数」必须真实通过 closed_impeller_proctor.ruler，「坏参数」必须真实被判红，
否则不入库。运行时渲染掩码（防抄答案）；jsonl 存全精度记录作为 SFT 标签与认证台账。
"""
import sys
import json
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import closed_impeller_proctor as proc
import impeller_iface as iface

OUT = ROOT / "data" / "impeller_repair_demos.jsonl"
LEDGER = ROOT / "data" / "impeller_repair_demos_ledger.json"


def with_claims(p):
    p = dict(p)
    vals, viol, _ = proc.ruler(p)
    if not viol:
        p["claimed_pressure_ratio"] = vals["pressure_ratio_recomputed"]
        p["claimed_tip_speed_m_s"] = vals["u2_m_s"]
        p["claimed_FOS"] = vals["FOS_recomputed"]
    return p


REF_GOOD = with_claims({
    "D2_mm": 200, "N_rpm": 48000, "Z_blades": 12, "beta2b_deg": 25, "b2_mm": 14,
    "D1t_mm": 130, "D1h_mm": 55, "axial_length_mm": 70, "shroud_thickness_mm": 2.0,
    "blade_thickness_mm": 1.5, "hub_disk_thickness_mm": 12, "bore_diameter_mm": 30,
    "fillet_root_mm": 1.5, "eta_total": 0.80, "claimed_pressure_ratio": 4.0,
    "claimed_tip_speed_m_s": 500, "claimed_FOS": 1.5, "design_rationale": "自洽参考解（数值在演示中隐去）"})

BAD_GEOMETRY = {
    "D2_mm": 120, "N_rpm": 45000, "Z_blades": 12, "beta2b_deg": 30, "b2_mm": 10,
    "D1t_mm": 130, "D1h_mm": 100, "axial_length_mm": 30, "shroud_thickness_mm": 1.5,
    "blade_thickness_mm": 1.2, "hub_disk_thickness_mm": 2.0, "bore_diameter_mm": 100,
    "fillet_root_mm": 1.0, "eta_total": 0.75, "claimed_pressure_ratio": 4.5,
    "claimed_tip_speed_m_s": 350, "claimed_FOS": 2.1, "design_rationale": "进口大于出口的错误几何"}

BAD_SPEED = {
    "D2_mm": 160, "N_rpm": 18000, "Z_blades": 12, "beta2b_deg": 30, "b2_mm": 3,
    "D1t_mm": 120, "D1h_mm": 90, "axial_length_mm": 50, "shroud_thickness_mm": 1.5,
    "blade_thickness_mm": 1.2, "hub_disk_thickness_mm": 2.5, "bore_diameter_mm": 30,
    "fillet_root_mm": 1.0, "eta_total": 0.82, "claimed_pressure_ratio": 4.2,
    "claimed_tip_speed_m_s": 360, "claimed_FOS": 2.1, "design_rationale": "低转速编造高叶尖速、流道过窄"}


def make_record(bad, corrected, walk_label):
    _, bad_viol, _ = proc.ruler(bad)
    corr_vals, corr_viol, _ = proc.ruler(corrected)
    assert bad_viol, f"坏样本未被判红: {walk_label}"
    assert not corr_viol, f"修正样本未通过尺子: {walk_label} {corr_viol}"
    brief = "设计封闭式离心叶轮：mdot=2.0kg/s, π≥4.0, Ti-6Al-4V, FOS≥1.5。输出参数 JSON。"
    messages = [
        {"role": "user", "content": brief},
        {"role": "assistant", "content": json.dumps(bad, ensure_ascii=False)},
        {"role": "tool", "content": json.dumps({"status": "rejected", "violations": bad_viol}, ensure_ascii=False)},
        {"role": "assistant", "content": json.dumps(corrected, ensure_ascii=False)},
        {"role": "tool", "content": json.dumps({"status": "accepted", "values": corr_vals}, ensure_ascii=False)},
    ]
    return {"walk": walk_label, "messages": messages,
            "cert": {"bad_violations": len(bad_viol), "corrected_pass": True,
                     "corrected_values": corr_vals}}


def main():
    # corrected2 尝试一个不同的自洽点；若尺子判红则回退到已认证参考解（保证入库件全通过）
    cand2 = with_claims({
        "D2_mm": 210, "N_rpm": 46000, "Z_blades": 14, "beta2b_deg": 28, "b2_mm": 13,
        "D1t_mm": 135, "D1h_mm": 60, "axial_length_mm": 72, "shroud_thickness_mm": 2.0,
        "blade_thickness_mm": 1.5, "hub_disk_thickness_mm": 12, "bore_diameter_mm": 32,
        "fillet_root_mm": 1.5, "eta_total": 0.80, "claimed_pressure_ratio": 4.0,
        "claimed_tip_speed_m_s": 500, "claimed_FOS": 1.5, "design_rationale": "提高叶尖速并放宽流道"})
    _, v2, _ = proc.ruler(cand2)
    corrected2 = cand2 if not v2 else REF_GOOD
    records = [
        make_record(BAD_GEOMETRY, REF_GOOD, "几何定义域修复：D1t>D2/bore=D1h → 恢复直径序"),
        make_record(BAD_SPEED, corrected2, "叶尖速/流道修复：编造u2+b2发散 → 提转速放宽流道据实复算"),
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    rendered = iface.render_fewshot(records, k=len(records))
    leaks = iface.assert_no_copyable_numbers(rendered)
    assert not leaks, f"掩码后仍有可抄数值: {leaks}"
    ledger = {"records": len(records), "certifier": "closed_impeller_proctor.ruler (non-model)",
              "per_record": [{"walk": r["walk"], **r["cert"]} for r in records],
              "masking_leaks": leaks, "rendered_chars": len(rendered)}
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[DEMOS CERTIFIED]", json.dumps({k: ledger[k] for k in ("records", "masking_leaks", "rendered_chars")}, ensure_ascii=False))
    for r in records:
        print(" -", r["walk"], "| bad_violations=", r["cert"]["bad_violations"],
              "| corrected PR=", r["cert"]["corrected_values"]["pressure_ratio_recomputed"],
              "FOS=", r["cert"]["corrected_values"]["FOS_recomputed"])


if __name__ == "__main__":
    main()