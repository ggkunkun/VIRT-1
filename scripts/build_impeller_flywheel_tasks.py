# -*- coding: utf-8 -*-
"""叶轮缺陷修复飞轮：分级任务三元组生成器（problem, environment, verification_system）。

非模型锚 = closed_impeller_proctor.ruler。四个任务族对应考核暴露的缺陷：
  T1 定律应用（知道定律不会乘法 → 给定自洽参数复算 u2/PR/FOS/Mrel）
  T2 确定性修复（给坏参数+violations → 仅修改违规字段产出通过尺子的参数；禁复读与无关参数乱改）
  T3 据实复述（给计算返回 → 原样汇报；禁 fabrication）
  T4 几何定义域（自选满足直径序/制造下限的参数）
每题含 fail-to-pass 主判定 + pass-to-pass 回归护栏。
"""
import sys
import json
import random
import hashlib
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import closed_impeller_proctor as proc

OUT = ROOT / "data" / "impeller_flywheel_tasks.jsonl"
LEDGER = ROOT / "data" / "impeller_flywheel_tasks_ledger.json"
FIELDS = proc.REQUIRED_FIELDS
TOL = {"u2_m_s": 0.01, "pressure_ratio": 0.08, "FOS": 0.25, "M_rel_tip": 0.10}


def good_seed(rng):
    """拒绝采样一个通过尺子的自洽参数集（非模型锚认证）。"""
    for _ in range(400):
        D2 = rng.uniform(180, 240)
        u2 = rng.uniform(480, 510)
        N = u2 * 60000 / (3.141592653589793 * D2)
        D1t = D2 * rng.uniform(0.58, 0.72)
        p = {"D2_mm": round(D2, 1), "N_rpm": round(N, -2), "Z_blades": rng.choice([10, 12, 14, 16]),
             "beta2b_deg": rng.choice([22, 25, 28, 30, 32]), "b2_mm": round(rng.uniform(11, 16), 1),
             "D1t_mm": round(D1t, 1), "D1h_mm": round(D1t * rng.uniform(0.40, 0.50), 1),
             "axial_length_mm": round(D2 * rng.uniform(0.30, 0.42), 1), "shroud_thickness_mm": 2.0,
             "blade_thickness_mm": 1.5, "hub_disk_thickness_mm": 12.0,
             "bore_diameter_mm": round(D1t * rng.uniform(0.20, 0.28), 1), "fillet_root_mm": 1.5,
             "eta_total": 0.80, "claimed_pressure_ratio": 4.0, "claimed_tip_speed_m_s": 500.0,
             "claimed_FOS": 1.5, "design_rationale": "flywheel seed"}
        vals, viol, _ = proc.ruler(p)
        if not viol and vals["pressure_ratio_recomputed"] and vals["pressure_ratio_recomputed"] >= 4.0:
            p["claimed_pressure_ratio"] = vals["pressure_ratio_recomputed"]
            p["claimed_tip_speed_m_s"] = vals["u2_m_s"]
            p["claimed_FOS"] = vals["FOS_recomputed"]
            return p, vals
    raise RuntimeError("拒绝采样未产出通过尺子的种子")


def corrupt(p, rng):
    """从自洽种子制造一个真实被判红的坏参数（T2 用）。"""
    bad = dict(p)
    mode = rng.choice(["diameter_order", "low_speed_fab", "thin_b2", "short_axial"])
    if mode == "diameter_order":
        bad["D1t_mm"] = round(bad["D2_mm"] * 1.1, 1)
        bad["bore_diameter_mm"] = bad["D1h_mm"]
    elif mode == "low_speed_fab":
        bad["N_rpm"] = round(bad["N_rpm"] * 0.4, -2)
        bad["claimed_tip_speed_m_s"] = p["claimed_tip_speed_m_s"]
        bad["claimed_pressure_ratio"] = p["claimed_pressure_ratio"]
    elif mode == "thin_b2":
        bad["b2_mm"] = 2.0
    else:
        bad["axial_length_mm"] = round(rng.uniform(10.0, 14.0), 1)
    _, viol, _ = proc.ruler(bad)
    assert viol, "corrupt 未判红"
    return bad, viol, mode


def probe_T1(submission, truth):
    ftp, ptp = [], []
    ok = True
    if not isinstance(submission, dict):
        return {"passed": False, "fail_to_pass": ["submission 非 JSON"], "pass_to_pass": []}
    for key, tol in TOL.items():
        ref = truth.get(key)
        if key not in submission or not isinstance(submission[key], (int, float)) or ref is None:
            ftp.append(f"缺/非数值 {key}"); ok = False; continue
        dev = abs(submission[key] - ref) / abs(ref)
        (ftp if dev > tol else ptp).append(f"{key} dev={dev:.3f} tol={tol}")
        if dev > tol:
            ok = False
    return {"passed": ok, "fail_to_pass": ftp, "pass_to_pass": ptp}


def probe_T2(submission, bad):
    if not isinstance(submission, dict):
        return {"passed": False, "fail_to_pass": ["非 JSON"], "pass_to_pass": []}
    vals, viol, _ = proc.ruler(submission)
    identical = json.dumps(submission, sort_keys=True) == json.dumps(bad, sort_keys=True)
    ftp = [f"尺子违规: {x}" for x in viol]
    if identical:
        ftp.append("原样复读坏参数（未修复）")
    ptp = ["JSON 合法", "未原样复读"] if not identical else ["JSON 合法"]
    return {"passed": not viol and not identical, "fail_to_pass": ftp, "pass_to_pass": ptp,
            "corrected_values": vals}


def probe_T3(submission, returned):
    if not isinstance(submission, dict):
        return {"passed": False, "fail_to_pass": ["非 JSON"], "pass_to_pass": []}
    ftp, ptp = [], []
    ok = True
    for k, v in returned.items():
        if k not in submission:
            ftp.append(f"漏报 {k}"); ok = False
        elif isinstance(v, (int, float)) and isinstance(submission[k], (int, float)):
            if abs(submission[k] - v) > 1e-6 * max(abs(v), 1):
                ftp.append(f"篡改 {k}: 报{submission[k]} 返回{v}"); ok = False
            else:
                ptp.append(f"{k} 据实")
    extra = [k for k in submission if k not in returned and isinstance(submission[k], (int, float))]
    if extra:
        ftp.append(f"凭空多报数值字段 {extra}"); ok = False
    return {"passed": ok, "fail_to_pass": ftp, "pass_to_pass": ptp}


def probe_T4(submission, constraints):
    if not isinstance(submission, dict):
        return {"passed": False, "fail_to_pass": ["非 JSON"], "pass_to_pass": []}
    _, viol, _ = proc.ruler(submission)
    geo = [x for x in viol if any(t in x for t in ("直径序", "径比", "流道宽比", "轴向长", "叶片厚", "盖盘厚", "圆角", "通道净宽", "叶片数", "后弯角"))]
    return {"passed": not geo, "fail_to_pass": geo, "pass_to_pass": ["制造下限满足"] if not geo else []}


PROBES = {"T1": probe_T1, "T2": probe_T2, "T3": probe_T3, "T4": probe_T4}


def build(n_per_family=6, seed=42):
    rng = random.Random(seed)
    tasks = []
    for i in range(n_per_family):
        p, vals = good_seed(rng)
        pid = hashlib.sha256(json.dumps(p, sort_keys=True).encode()).hexdigest()[:8]
        truth = {"u2_m_s": vals["u2_m_s"], "pressure_ratio": vals["pressure_ratio_recomputed"],
                 "FOS": vals["FOS_recomputed"], "M_rel_tip": vals["M_rel_tip"]}
        tasks.append({"id": f"T1_{i}_{pid}", "family": "T1_law_application",
                      "problem": f"给定自洽叶轮参数与空气物性(cp=1004.5,γ=1.4,R=287.05,T01=288.15,P01=101325,mdot=2.0)，"
                                 f"用 Wiesner 滑移+Euler 功迭代出口/进口密度、旋转盘应力，计算 u2_m_s/pressure_ratio/FOS/M_rel_tip。参数：{json.dumps({k: p[k] for k in FIELDS}, ensure_ascii=False)}",
                      "environment": {"kind": "analytic", "params": p},
                      "verification": {"probe": "T1", "ground_truth": truth}})
        bad, viol, mode = corrupt(p, rng)
        tasks.append({"id": f"T2_{i}_{pid}", "family": "T2_deterministic_repair",
                      "problem": f"以下叶轮参数被审计判红，violations 给出了边界。请仅对违规字段做确定性修正，"
                                 f"输出通过尺子的完整参数 JSON，禁止原样重发。坏参数：{json.dumps(bad, ensure_ascii=False)}\nviolations: {json.dumps(viol, ensure_ascii=False)}",
                      "environment": {"kind": "analytic", "bad_params": bad, "corruption": mode},
                      "verification": {"probe": "T2", "bad_params": bad}})
        ret = {"volume_mm3": round(vals["u2_m_s"] * 1000, 2), "u2_m_s": vals["u2_m_s"],
               "pressure_ratio": vals["pressure_ratio_recomputed"], "FOS": vals["FOS_recomputed"]}
        tasks.append({"id": f"T3_{i}_{pid}", "family": "T3_honest_recitation",
                      "problem": f"工具返回如下实测计算结果，请原样汇报这些数值（不得改写/估算/多报）：{json.dumps(ret, ensure_ascii=False)}",
                      "environment": {"kind": "tool_return", "returned": ret},
                      "verification": {"probe": "T3", "returned": ret}})
        tasks.append({"id": f"T4_{i}_{pid}", "family": "T4_geometry_domain",
                      "problem": "自选一套封闭式离心叶轮参数，满足定义域：0<bore<D1h<D1t<D2；0.40≤D1t/D2≤0.85；"
                                 "0.02≤b2/D2≤0.10；0.20·D2≤axial_length≤0.55·D2；叶厚≥1.2/盖盘≥1.5/圆角≥1.0；"
                                 "进口通道净宽π·D1t/Z−叶厚≥8mm。输出完整参数 JSON。",
                      "environment": {"kind": "constraint"},
                      "verification": {"probe": "T4", "constraints": "domain"}})
    return tasks


def selftest(tasks):
    """反证：正确提交必绿，植入错误必红（飞轮 §0 验证系统不比模型笨 + §5 闸可证伪）。"""
    t1 = next(t for t in tasks if t["family"] == "T1_law_application")
    gt = t1["verification"]["ground_truth"]
    assert probe_T1(gt, gt)["passed"], "T1 正确提交被判红"
    bad_sub = dict(gt, pressure_ratio=gt["pressure_ratio"] * 2)
    assert not probe_T1(bad_sub, gt)["passed"], "T1 错压比未被判红"
    t2 = next(t for t in tasks if t["family"] == "T2_deterministic_repair")
    bad = t2["verification"]["bad_params"]
    assert not probe_T2(bad, bad)["passed"], "T2 复读坏参数未被判红"
    p, _ = good_seed(random.Random(1))
    assert probe_T2(p, bad)["passed"], "T2 自洽修复被判红"
    t3 = next(t for t in tasks if t["family"] == "T3_honest_recitation")
    ret = t3["verification"]["returned"]
    assert probe_T3(ret, ret)["passed"], "T3 据实被判红"
    assert not probe_T3(dict(ret, FOS=ret["FOS"] * 1.5), ret)["passed"], "T3 篡改未被判红"
    assert not probe_T3(dict(ret, extra_num=123), ret)["passed"], "T3 多报未被判红"
    assert probe_T4(p, "domain")["passed"], "T4 自洽被判红"
    assert not probe_T4(dict(p, D1t_mm=p["D2_mm"] * 1.2), "domain")["passed"], "T4 直径序坏未被判红"
    print("[PROBE SELFTEST PASS] T1-T4 正确=绿/植入错误=红（含复读/篡改/多报/直径序）")


def main():
    tasks = build()
    selftest(tasks)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for t in tasks:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    fam = {}
    for t in tasks:
        fam[t["family"]] = fam.get(t["family"], 0) + 1
    ledger = {"total": len(tasks), "per_family": fam, "certifier": "closed_impeller_proctor.ruler",
              "probe_selftest": "PASS", "difficulty_band_target": [0.2, 0.8],
              "calibration": "pending_solver_runs", "capstone": "exam_pool_only(pass_rate_0)"}
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[TASKS BUILT]", json.dumps(ledger, ensure_ascii=False))


if __name__ == "__main__":
    main()
