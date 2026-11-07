# -*- coding: utf-8 -*-
"""
scripts/moe14b_noise_probe.py — 给判分器本身量噪声（仓库里此前只有消费者，没有生产者）

`virtu_eval/provenance.py::noise_envelope` 早就写着「没有配对复测就不准称增益」，
`delta_verdict` 也要求传 sigma，但仓库里没有任何脚本产出过 probe 文件 —— 于是今天所有
MoE-vs-dense 的「领先 2.78 / 4.44 分」都是在没有噪声底线的情况下发出的。本脚本补上生产者。

做法：同一臂、同一题、temperature=0、同一 seed 问两遍，用同一个 graders.score_case 打分，
落 records[{case_id, scores:[s1,s2]}]，再用 noise_envelope 出 paired_sigma，
最后反解「要判出 Δ 分差需要多少题」：n = 2·(z·σ/Δ)²。

用法：
  python scripts/moe14b_noise_probe.py --arm moe14b_gate_random --dims knowledge,toolcall --n 5
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from virtu_eval.arms import build_arm                  # noqa: E402
from virtu_eval.graders import score_case              # noqa: E402
from virtu_eval.provenance import noise_envelope       # noqa: E402
from virtu_eval.runner import build_messages, load_cases  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, help="key into virtu_eval/arms.json")
    ap.add_argument("--case-dir", default="data/benchmark/virtu_eval_v1")
    ap.add_argument("--dims", default="knowledge,toolcall")
    ap.add_argument("--n", type=int, default=5, help="cases per dimension (each asked twice)")
    ap.add_argument("--max-tokens", type=int, default=224)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--out", default=os.path.join(ROOT, "runs", "moe14b_noise_probe.json"))
    args = ap.parse_args()

    arms = json.load(open(os.path.join(ROOT, "virtu_eval", "arms.json"), encoding="utf-8"))
    if args.arm not in arms:
        raise SystemExit(f"[FATAL] arm {args.arm!r} not in arms.json; have {sorted(arms)}")
    spec = arms[args.arm]

    cases = load_cases(os.path.join(ROOT, args.case_dir),
                       dims=[d for d in args.dims.split(",") if d],
                       limit_per_dim=args.n)
    if not cases:
        raise SystemExit("[FATAL] 用例集为空 —— 空样本不得算通过")

    arm = build_arm(spec)
    records, errors = [], 0
    print(f"=== noise probe on {spec['model_id']} · {len(cases)} cases × 2 asks "
          f"(temp=0, seed={args.seed}, max_tokens={args.max_tokens}) ===", flush=True)

    for case in cases:
        scores = []
        for rep in (1, 2):
            try:
                gen = arm.generate(build_messages(case), max_tokens=args.max_tokens,
                                   temperature=0.0, seed=args.seed,
                                   images=case.get("images"), tools=arm.tools_for(case))
                text = gen.get("text") or ""
                scores.append(float(score_case(text, case["criteria"])["score"]))
                if not text.strip():
                    errors += 1
            except Exception as exc:  # noqa: BLE001 - one transport failure must not fake a 0
                errors += 1
                print(f"  [{case['case_id']}] ask{rep} ERROR {type(exc).__name__}: {exc}", flush=True)
        if len(scores) == 2:
            records.append({"case_id": case["id"], "dimension": case["dimension"],
                            "tier": case.get("tier"), "scores": scores})
            print(f"  [{case['id']:<28}] scores={scores[0]:.2f} / {scores[1]:.2f} "
                  f"delta={abs(scores[0]-scores[1]):.2f}", flush=True)

    transport_rate = errors / max(1, 2 * len(cases))
    if transport_rate > 0.2:
        raise SystemExit(f"[FATAL] 传输/空回答率 {transport_rate:.0%} > 20%，本轮噪声不可用")

    doc = {"run_id": hashlib.sha256((json.dumps(spec, sort_keys=True) + str(len(records))
                                     + args.case_dir).encode()).hexdigest()[:16],
           "generated_at": _dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z"),
           "basis": "measured",
           "arm": args.arm, "model_id": spec["model_id"], "base_url": spec.get("base_url"),
           "sampling": {"temperature": 0.0, "seed": args.seed, "max_tokens": args.max_tokens},
           "served_layers": getattr(arm, "served_layers", None),
           "transport_errors": errors, "transport_rate": round(transport_rate, 4),
           "records": records}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)

    env = noise_envelope(args.out)
    print("\n=== measured noise floor of this ruler ===")
    print(json.dumps(env, indent=2, ensure_ascii=False))

    print("\n=== 要判出这个分差，需要多少道配对题（band = 1.96·σ·√(2/n) ≤ Δ）===")
    sigma = env["paired_sigma"]
    for delta in (1.0, 2.78, 4.44, 6.95):
        if sigma <= 0:
            print(f"  Δ={delta:5.2f} 需要 n=1（σ=0，判分器完全确定）")
            continue
        n = math.ceil(2.0 * (1.96 * sigma / delta) ** 2)
        print(f"  Δ={delta:5.2f} 需要 n≥{n:4d} 题/臂   "
              f"(MoE 腿 ~10 tok/s × {args.max_tokens} tok ⇒ ≈{n*args.max_tokens/10/60:.0f} min)")
    print(f"\n[out] {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
