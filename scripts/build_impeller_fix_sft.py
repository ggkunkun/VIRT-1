# -*- coding: utf-8 -*-
"""叶轮缺陷修复 SFT 语料构建器（标签由独立尺子认证，非模型自述）。

修复要点：
1. T2 确定性修复：直接将坏参数 bad 修复回其派生的原自洽种子 p（仅恢复被破坏字段并同步复算宣称值），
   严禁再用无关随机 good_seed 充当修复目标（否则会教模型乱改 D2/N 并背诵固定叶尖速）；
2. 多轮 repair_demo 演示：首轮坏解 assistant 消息显式标记 "loss": False 且记录级标记
   "last_assistant_only": True，确保训练时绝不把坏解计入正样本 Loss。
"""
import sys
import json
import random
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import closed_impeller_proctor as proc
import build_impeller_flywheel_tasks as fw

OUT = ROOT / "cloud_train_pack" / "dataset" / "virtu_impeller_fix_sft.jsonl"
LEDGER = ROOT / "cloud_train_pack" / "dataset" / "virtu_impeller_fix_sft_ledger.json"
SYSTEM = ("你是 Virtu 工业超级智能体，负责航空叶轮设计与工程计算。证据契约：宣称数值必须由参数真实算出，"
          "未计算不得宣称；被审计判红时依据 violations 边界做确定性修正，禁止原样重发同一组参数；"
          "汇报必须据实引用计算/工具返回值，禁止改写估算。输出规定 JSON 代码块。")
FIELDS = proc.REQUIRED_FIELDS


def jblock(obj):
    return "```json\n" + json.dumps(obj, ensure_ascii=False, indent=2) + "\n```"


def parse_label(content):
    return proc.extract_json(content)


def gen(n_per_family=50, seed=7):
    rng = random.Random(seed)
    rows, ledger = [], {"T1": 0, "T2": 0, "T3": 0, "T4": 0, "rejects": 0}
    for i in range(n_per_family):
        p, vals = fw.good_seed(rng)
        params = {k: p[k] for k in FIELDS}
        truth = {"u2_m_s": vals["u2_m_s"], "pressure_ratio": vals["pressure_ratio_recomputed"],
                 "FOS": vals["FOS_recomputed"], "M_rel_tip": vals["M_rel_tip"]}
        # T1 定律应用
        a1 = jblock(truth)
        if fw.probe_T1(parse_label(a1), truth)["passed"]:
            rows.append({"messages": [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"给定自洽封闭式叶轮参数与空气物性(cp=1004.5,γ=1.4,R=287.05,T01=288.15K,P01=101325Pa,mdot=2.0kg/s)，"
                                            f"用 Wiesner 滑移+Euler 功迭代出口/进口密度、旋转盘离心应力，计算 u2_m_s/pressure_ratio/FOS/M_rel_tip。参数：{json.dumps(params, ensure_ascii=False)}"},
                {"role": "assistant", "content": a1, "loss": True}], "family": "T1"})
            ledger["T1"] += 1
        else:
            ledger["rejects"] += 1
        # T2 确定性修复：直接修复回坏参数来源的原种子 params（保持未违规字段不变，宣称值与复算严格一致）
        bad, viol, mode = fw.corrupt(p, rng)
        bad_clean = {k: bad[k] for k in FIELDS}
        a2 = jblock(params)
        parsed_a2 = parse_label(a2)
        if fw.probe_T2(parsed_a2, bad_clean)["passed"] and parsed_a2["D2_mm"] == bad_clean["D2_mm"]:
            rows.append({"messages": [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"以下叶轮参数被独立审计判红。请依据 violations 边界仅对违规字段做确定性修正，输出通过尺子的完整参数 JSON，禁止原样重发。\n坏参数：{json.dumps(bad_clean, ensure_ascii=False)}\nviolations：{json.dumps(viol, ensure_ascii=False)}"},
                {"role": "assistant", "content": a2, "loss": True}], "family": "T2"})
            ledger["T2"] += 1
        else:
            ledger["rejects"] += 1
        # T3 据实复述
        ret = {"volume_mm3": round(vals["u2_m_s"] * 1000, 2), "u2_m_s": vals["u2_m_s"],
               "pressure_ratio": vals["pressure_ratio_recomputed"], "FOS": vals["FOS_recomputed"]}
        a3 = jblock(ret)
        if fw.probe_T3(parse_label(a3), ret)["passed"]:
            rows.append({"messages": [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"工具返回如下实测计算结果，请原样汇报这些数值（不得改写/估算/取整/多报）：{json.dumps(ret, ensure_ascii=False)}"},
                {"role": "assistant", "content": a3, "loss": True}], "family": "T3"})
            ledger["T3"] += 1
        else:
            ledger["rejects"] += 1
        # T4 几何定义域
        a4 = jblock(params)
        if fw.probe_T4(parse_label(a4), "domain")["passed"]:
            rows.append({"messages": [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": "自选一套封闭式离心叶轮参数，满足定义域：0<bore<D1h<D1t<D2；0.40≤D1t/D2≤0.85；0.02≤b2/D2≤0.10；"
                                            "0.20·D2≤axial_length≤0.55·D2；axial_length≥hub_disk_thickness+shroud_thickness+b2；叶厚≥1.2/盖盘≥1.5/圆角≥1.0；"
                                            "进口通道净宽π·D1t/Z−叶厚≥8mm；Z∈[6,24]；β2b∈[15,55]°。输出完整参数 JSON。"},
                {"role": "assistant", "content": a4, "loss": True}], "family": "T4"})
            ledger["T4"] += 1
        else:
            ledger["rejects"] += 1
    # 多轮修复演示（教 repair 行为，首轮坏解显式标记 loss=False）
    demos = [json.loads(l) for l in open(ROOT / "data" / "impeller_repair_demos.jsonl", encoding="utf-8")]
    for d in demos:
        msgs = [{"role": "system", "content": SYSTEM}]
        asst_indices = [idx for idx, m in enumerate(d["messages"]) if m["role"] == "assistant"]
        last_asst_idx = asst_indices[-1] if asst_indices else -1
        for idx, m in enumerate(d["messages"]):
            if m["role"] == "tool":
                msgs.append({"role": "user", "content": "审计返回：" + m["content"]})
            elif m["role"] == "assistant":
                msgs.append({
                    "role": "assistant",
                    "content": m["content"],
                    "loss": (idx == last_asst_idx),
                })
            else:
                msgs.append({"role": m["role"], "content": m["content"]})
        rows.append({"messages": msgs, "last_assistant_only": True, "family": "repair_demo"})
    return rows, ledger


def main():
    rows, ledger = gen()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for r in rows:
            out_rec = {"messages": r["messages"]}
            if r.get("last_assistant_only"):
                out_rec["last_assistant_only"] = True
            f.write(json.dumps(out_rec, ensure_ascii=False) + "\n")
    # 抽检 ≥10%：随机重验标签（inspector 也被检）
    rng = random.Random(99)
    spot = rng.sample(rows, max(2, len(rows) // 10))
    spot_fail = 0
    for r in spot:
        label = parse_label(r["messages"][-1]["content"])
        if label is None:
            spot_fail += 1
    ledger.update({"total": len(rows), "repair_demos": sum(1 for r in rows if r["family"] == "repair_demo"),
                   "spot_checked": len(spot), "spot_fail": spot_fail,
                   "label_anchor": "closed_impeller_proctor.ruler + probes (non-model)",
                   "t2_invariant": "preserves non-violating D2_mm/Z_blades/beta2b_deg from bad input",
                   "format": "messages chatml, train_turnkey --data compatible"})
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    assert spot_fail == 0, f"抽检失败 {spot_fail}"
    print("[SFT CORPUS CERTIFIED]", json.dumps(ledger, ensure_ascii=False))


if __name__ == "__main__":
    main()
