# -*- coding: utf-8 -*-
"""Build a 200-case formula holdout with values disjoint from the training corpus.

Used after fine-tuning to prove the model computes formulas instead of memorizing
the training numbers. Each row carries a deterministic gold value/unit.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "benchmark" / "virtu_fix_v1" / "formula_holdout_200.jsonl"
MANIFEST = OUT.with_suffix(".manifest.json")
SEED = 999


def f1(x: float) -> float:
    return round(x, 1)


def f2(x: float) -> float:
    return round(x, 2)


def make(kind: str, rng: random.Random):
    if kind == "n":
        vc = rng.choice([63, 67, 71, 79, 83, 89, 97, 103, 109, 113, 127, 131, 137, 139, 149, 151, 157, 163, 167, 173])
        d = rng.choice([7, 13, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89, 97])
        gold = f1(1000.0 * vc / (math.pi * d))
        prompt = f"工件直径 D={d} mm，切削速度 Vc={vc} m/min，求主轴转速 n（r/min）。"
        answer = f"n = 1000×{vc}/(π×{d}) = {gold} r/min"
        return {"kind": kind, "prompt": prompt, "gold_value": gold, "gold_unit": "r/min", "answer": answer}
    if kind == "vf":
        f = rng.choice([0.06, 0.09, 0.11, 0.13, 0.17, 0.23, 0.27, 0.33, 0.44, 0.55])
        z = rng.choice([2, 3, 4, 5, 6, 7, 8])
        n = rng.choice([425, 475, 525, 575, 625, 675, 725, 775, 825, 875, 925, 975, 1025, 1075, 1125, 1175, 1225, 1275, 1325, 1375])
        gold = f1(f * z * n)
        prompt = f"铣削：每齿进给 f={f} mm/z，齿数 z={z}，主轴转速 n={n} r/min，求进给速度 Vf（mm/min）。"
        answer = f"Vf = {f}×{z}×{n} = {gold} mm/min"
        return {"kind": kind, "prompt": prompt, "gold_value": gold, "gold_unit": "mm/min", "answer": answer}
    if kind == "mrr":
        ap = rng.choice([0.3, 0.7, 1.2, 1.8, 2.5, 3.5, 4.5])
        ae = rng.choice([7, 12, 18, 22, 28, 36, 45, 55, 70])
        vf = rng.choice([125, 175, 225, 275, 325, 375, 425, 475, 525, 575, 625, 675, 725, 775, 825, 875, 925, 975, 1025, 1075])
        gold = f1(ap * ae * vf)
        prompt = f"铣削：轴向切深 ap={ap} mm，径向切宽 ae={ae} mm，进给速度 Vf={vf} mm/min，求 MRR（mm³/min）。"
        answer = f"MRR = {ap}×{ae}×{vf} = {gold} mm³/min"
        return {"kind": kind, "prompt": prompt, "gold_value": gold, "gold_unit": "mm³/min", "answer": answer}
    length = rng.choice([30, 45, 70, 90, 130, 180, 260, 350, 450, 700, 900, 1100, 1400])
    vf = rng.choice([125, 175, 225, 275, 325, 375, 425, 475, 525, 575, 625, 675, 725, 775, 825, 875, 925, 975, 1025, 1075])
    gold = f2(length / vf)
    prompt = f"工件行程 L={length} mm，进给速度 Vf={vf} mm/min，求加工时间 T（min）。"
    answer = f"T = {length}/{vf} = {gold} min"
    return {"kind": kind, "prompt": prompt, "gold_value": gold, "gold_unit": "min", "answer": answer}


def main() -> int:
    rng = random.Random(SEED)
    rows = []
    seen_prompts = set()
    for kind in ("n", "vf", "mrr", "t"):
        made = 0
        while made < 50:
            row = make(kind, rng)
            if row["prompt"] in seen_prompts:
                continue
            seen_prompts.add(row["prompt"])
            row["id"] = f"formula-holdout-{kind}-{made + 1:02d}"
            rows.append(row)
            made += 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    manifest = {
        "version": "formula_holdout_200_v1",
        "seed": SEED,
        "total": len(rows),
        "kinds": {k: sum(1 for r in rows if r["kind"] == k) for k in ("n", "vf", "mrr", "t")},
        "sha256": hashlib.sha256(OUT.read_bytes()).hexdigest(),
        "usage": "post-training gate: each answer must match gold_value/gold_unit; do not train on this file",
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
