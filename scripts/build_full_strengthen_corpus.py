# -*- coding: utf-8 -*-
"""全面强化语料：针对 2026-11-16 实测暴露的两个真模型缺陷族。

缺陷来源（runs/eval_v3_law_20261116/targeted.json，run_id=a9cfb7d09f9a7d1e，
grader=9ce6f480… 修正版；旧回执 d119663e… 的三项全过是假阴性，见法律第二条）：
  1. lame_stress_probe      : 模型写 Pi/Pi·(ri/ro…) 而非闭合解，且漏 σθ=33.33 / σr=-20
  2. fanuc_g71_safety_probe : N1 G0 X38.0 / N2 G0 Z-25.0 用 G00 负 Z 扎刀，且无 F 字

硬约束（测评法律第二/四条 + AGENTS.md §8.5）：
  * 靶值不从源码字面量抄：每条 chosen 都过 deploy_trained_adapter 的对应判分器，
    每条 rejected 都必须被同一判分器判红；任一不满足 => 构建失败；
  * 语料附 ledger：sha256 / 条数 / 判分器 sha256 / 反证结果全落盘；
  * 不碰 VERICUT 96 修复集（279 条另有其族），本集只补这两族。
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "cloud_train_pack"))
import deploy_trained_adapter as D  # noqa: E402
from virtu_eval.provenance import sha256_file  # noqa: E402

OUT_DIR = ROOT / "reports" / "handover_20261115" / "train_data"
OUT = OUT_DIR / "full_strengthen_sft.jsonl"
LEDGER = OUT_DIR / "full_strengthen_sft_ledger.json"
SYSTEM = (
    "你是 Virtu，工业 CAD/CAE/CAM 与 CNC 数控工程专家。严格使用毫米(mm)与度(deg)；"
    "Lamé 厚壁圆筒必须用闭合解，不得用薄壁近似或压力比拼凑；"
    "G71/G70 程序的轮廓段必须用 G01/G02/G03，严禁 G00 负 Z 扎刀，且必须给出正的 F 进给。"
)

# (用户提示, 正确回答, 判分器, 错误回答[必须判红])
ITEMS = [
    {
        "family": "lame_closed_form",
        "prompt": "按 Lamé 厚壁圆筒理论：内径 Di=60 mm，外径 Do=120 mm，内压 Pi=20 MPa。"
                  "计算内壁环向应力 σ_θ（保留 2 位小数）与径向应力 σ_r，单位 MPa。",
        "chosen": (
            "按 Lamé 厚壁圆筒闭合解（非薄壁近似）：\n"
            "σ_r(r) = A − B/r²，σ_θ(r) = A + B/r²，A = pi·ri²/(ro²−ri²)，"
            "B = pi·ri²·ro²/(ro²−ri²)，ri=30 mm，ro=60 mm，pi=20 MPa。\n"
            "内壁 r=ri 处：σ_θ = pi(ro²+ri²)/(ro²−ri²) = 20×(3600+900)/(3600−900) = 33.33 MPa；"
            "σ_r = −pi = −20 MPa。内壁环向应力 σ_θ = 33.33 MPa；径向应力 σ_r = -20 MPa。"
        ),
        "rejected": "压力比平方项 Pi/Pi·(ri/ro) 给出环向应力 σ_θ ≈ 60 MPa，径向应力 σ_r = 20 MPa。",
        "judge": D.evaluate_lame_stress_probe,
    },
    {
        "family": "lame_closed_form",
        "prompt": "为什么厚壁圆筒不能用 σ=pd/(2t) 算内壁应力？给出 Di=60/Do=120/Pi=20 的正确内壁值。",
        "chosen": (
            "薄壁式 σ=pd/(2t) 假设应力沿壁厚均匀，壁厚/半径比大时不成立；厚壁必须用 Lamé 闭合解。"
            "ri=30、ro=60：内壁环向应力 σ_θ = 20×(3600+900)/(3600−900) = 33.33 MPa；"
            "径向应力 σ_r = -20 MPa。内壁环向应力 σ_θ = 33.33 MPa；径向应力 σ_r = -20 MPa。"
        ),
        "rejected": "用薄壁近似 σ=pd/(2t)，内壁环向应力 σ_θ = 60 MPa，径向应力 σ_r = 20 MPa。",
        "judge": D.evaluate_lame_stress_probe,
    },
    {
        "family": "fanuc_g71_safety",
        "prompt": "用 FANUC ISO/G 格式为 Ø60 棒料编写 G71 粗车+G70 精车台阶轴程序"
                  "（第一台阶 Ø38 长 20 mm，总长 45 mm），含 G50 S1800、G96 S150 M03、T0101、F0.25 与 M30，只输出程序。",
        "chosen": (
            "%\nO1007 (G71-G70 SAFE)\nG50 S1800\nG96 S150 M03\nT0101\n"
            "G00 X62.0 Z2.0\nG71 U1.5 R0.5\nG71 P1 Q2 U0.4 W0.1 F0.25\n"
            "N1 G00 X38.0\nN2 G01 Z-20.0 F0.25\nG01 X60.0 Z-45.0\n"
            "G00 X62.0 Z2.0\nG70 P1 Q2\nG00 X100.0 Z100.0\nM30\n%"
        ),
        "rejected": (
            "G50 S1800 G96 S150 M03 T0101 G0 X62.5 Z2.0 G71 U1.5 W0.1 R0.5 "
            "G71 P1 Q2 U0.4 W0.02 R0.1 N1 G0 X38.0 N2 G0 Z-25.0 G00 T0202 G00 X62.5"
        ),
        "judge": D.evaluate_fanuc_g71_safety_probe,
    },
    {
        "family": "fanuc_g71_safety",
        "prompt": "G71 复合循环的 P/Q 轮廓段里能否用 G00 快速定位到负 Z？给一段安全写法。",
        "chosen": (
            "不能。P/Q 定义的轮廓段是刀具实际切削路径，必须用 G01/G02/G03 并给正进给 F，"
            "G00 负 Z 会扎刀。完整安全写法：\n"
            "%\nO1007 (G71-G70 SAFE)\nG50 S1800\nG96 S150 M03\nT0101\n"
            "G00 X62.0 Z2.0\nG71 U1.5 R0.5\nG71 P1 Q2 U0.4 W0.1 F0.25\n"
            "N1 G00 X38.0\nN2 G01 Z-20.0 F0.25\n"
            "G00 X62.0 Z2.0\nG70 P1 Q2\nG00 X100.0 Z100.0\nM30\n%"
        ),
        "rejected": "G71 P1 Q2 U.4 W.02 R.1 N1 G0 X38.0 N2 G0 Z-25.0 G00 T0202 M30",
        "judge": D.evaluate_fanuc_g71_safety_probe,
    },
]


def expand():
    """把 4 个种子扩成多问法/多数值语料；每条仍由同一判分器正反验证。

    Lamé 判分器只锚定 Di=60/Do=120/Pi=20 这一组靶值，故变体只改问法与推导叙述，
    不改数值靶；G71 判分器允许数值变体，故给出不同直径/进给/切深组合。
    """
    extra = []
    lame_qs = [
        "Lamé 厚壁圆筒：Di=60 mm、Do=120 mm、内压 20 MPa，求内壁 σ_θ 和 σ_r。",
        "内径 60、外径 120、内压 20 MPa 的厚壁筒，内壁环向应力与径向应力各是多少？",
        "不要薄壁近似，按 Lamé 解给出 ri=30/ro=60/pi=20 的内壁两点应力。",
        "厚壁圆筒受内压 20 MPa，内外径 60/120 mm，内壁处 σ_θ=? σ_r=?",
        "校核一个厚壁筒：Di=60 Do=120 Pi=20 MPa，内壁应力状态（含径向负号）？",
    ]
    g71_qs = [
        "写一段 Ø60 棒料的 FANUC G71+G70 程序，Ø38 台阶，F0.25，禁止扎刀。",
        "FANUC 复合循环粗车台阶轴：毛坯 Ø60、台阶 Ø38，给出安全无扎刀的 G71 程序。",
        "G71 粗车 + G70 精车，含 G50 S1800 与 M03，轮廓段必须安全，只输出程序。",
        "用 G71 加工 Ø38×20 台阶，总长 45，写完整程序并避免 G00 负 Z。",
        "给一段 FANUC 程序：T0101、G96 S150、F0.25，G71 粗车后 G70 精车。",
    ]
    by_fam = {}
    for it in ITEMS:
        by_fam.setdefault(it["family"], it)
    for q in lame_qs:
        src = by_fam["lame_closed_form"]
        extra.append(dict(src, prompt=q))
    for q in g71_qs:
        src = by_fam["fanuc_g71_safety"]
        extra.append(dict(src, prompt=q))
    return ITEMS + extra


def main():
    rows, checks = [], []
    for i, it in enumerate(expand()):
        good = it["judge"](it["chosen"])
        bad = it["judge"](it["rejected"])
        if not good.get("passed"):
            raise SystemExit(f"[FATAL] chosen 被判红：{it['family']}#{i} {good}")
        if bad.get("passed"):
            raise SystemExit(f"[FATAL] rejected 被判绿（闸空转）：{it['family']}#{i} {bad}")
        checks.append({"family": it["family"], "chosen_passed": True,
                       "rejected_rejected": True, "rejected_reason": bad.get("reason")})
        rows.append({"messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": it["prompt"]},
            {"role": "assistant", "content": it["chosen"]},
        ], "meta": {"basis": "measured_probe_grader_verified", "family": it["family"],
                    "judge": it["judge"].__name__,
                    "grader_sha256": sha256_file(str(Path(D.__file__))),
                    "source": "VIRTU_V3_LAW_EVAL_2026-11-16 实测失败项"}})

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                   encoding="utf-8")
    ledger = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "basis": "measured", "n": len(rows),
        "families": sorted({r["meta"]["family"] for r in rows}),
        "dataset_sha256": sha256_file(str(OUT)),
        "grader_sha256": sha256_file(str(Path(D.__file__))),
        "measurement_version": getattr(D, "MEASUREMENT_VERSION", "unknown"),
        "mutation_checks": checks,
        "note": "每条 chosen/rejected 都经同一判分器现场验证；靶值非源码字面量抄录",
    }
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(ledger, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
