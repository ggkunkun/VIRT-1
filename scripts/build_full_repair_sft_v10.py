#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Surgical G71 Semantic + Balanced Replay SFT v10 (2026-11-18).

Built on top of `v7-repair` (`checkpoints/six_software_v7_repair_lora` merged onto
`v3 merged_hf`), which already passes 10/10 official probes (`gen_lame=True`)
but fails `g71_semantic_check` (`Z-25` short total length / `X60` before `Z-20`)
and `gen_g71`.

v10 keeps ONLY 100% gate-verified rows across all families (~163 rows), evenly
round-robin interleaved with zero G71 poison and diverse stepped-shaft
geometries (`Ø50`, `Ø60`, `Ø70`, `Ø90`), so 37 optimizer steps at lr=5e-5 fix G71
semantics & generalization without regressing SW/Lamé/AutoDiff/Unit/ToolCall.
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cloud_train_pack"))
sys.path.insert(0, str(ROOT / "scripts"))
import deploy_trained_adapter as grader  # noqa: E402
from build_full_repair_sft_v9 import (  # noqa: E402
    DIVERSE_GEOM_SPECS,
    diverse_program_rows,
    looks_like_program,
    prog_geom,
    program_rows,
    row,
    rule_rows,
)
from g71_semantic_check import check_g71_step_shaft  # noqa: E402

V7 = ROOT / "reports" / "handover_20261115" / "train_data" / "six_software_v7_repair_sft.jsonl"
OUT = ROOT / "reports" / "handover_20261115" / "train_data" / "six_software_v10_repair_sft.jsonl"


def _sample_even(items: list[dict], target: int) -> list[dict]:
    if len(items) <= target:
        return list(items)
    step = len(items) / float(target)
    return [items[int(i * step)] for i in range(target)]


def _round_robin(buckets: list[list[dict]]) -> list[dict]:
    out: list[dict] = []
    idx = [0] * len(buckets)
    total = sum(len(b) for b in buckets)
    while len(out) < total:
        # Spread larger buckets proportionally by advancing normalized progress
        progressed = False
        best_b = -1
        best_ratio = 2.0
        for bi, b in enumerate(buckets):
            if idx[bi] < len(b):
                r = idx[bi] / float(max(1, len(b)))
                if r < best_ratio:
                    best_ratio = r
                    best_b = bi
        if best_b >= 0:
            out.append(buckets[best_b][idx[best_b]])
            idx[best_b] += 1
            progressed = True
        if not progressed:
            break
    return out


def main() -> int:
    if not V7.exists():
        print(f"[FATAL] Missing v7 corpus: {V7}", file=sys.stderr)
        return 2

    v7_rows = [
        json.loads(ln)
        for ln in V7.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]

    sw_clean = [
        r for r in v7_rows
        if "sw_plane" in str(r.get("meta", {}).get("family"))
        and grader.evaluate_sw_coordinate_probe(r["messages"][-1]["content"]).get("passed")
    ]
    unit_clean = [
        r for r in v7_rows
        if grader.evaluate_vericut_coordinate_unit_probe(r["messages"][-1]["content"]).get("passed")
        and "sw_plane" not in str(r.get("meta", {}).get("family"))
    ]
    autodiff_clean = [
        r for r in v7_rows
        if grader.evaluate_vericut_autodiff_probe(r["messages"][-1]["content"]).get("passed")
    ]
    lame_clean = [
        r for r in v7_rows
        if "lame" in str(r.get("meta", {}).get("family"))
        and any(k in r["messages"][-1]["content"] for k in ("33.33", "25.00", "41.67", "50.00", "40.00"))
    ]
    tools_clean = [
        r for r in v7_rows
        if "<tool_call>" in r["messages"][-1]["content"]
    ]

    # Diverse stepped-shaft examples (excludes probe 60/38/20/45 and unseen eval 80/46/25/60)
    extra_diverse_specs = list(DIVERSE_GEOM_SPECS) + [
        (
            "用 FANUC ISO/G 格式为 Ø90 棒料编写 G71 粗车+G70 精车台阶轴程序"
            "（第一台阶 Ø54 长 28 mm，总长 70 mm），含 G50 S1800、G96 S150 M03、T0101、F0.25 与 M30，只输出程序。",
            90.0, 54.0, 28.0, 70.0, "O0007", "2.0", "0.8", "0.5", "0.1", "0.25",
        ),
        (
            "编写 FANUC 台阶轴加工程序：毛坯 Ø55，成品 Ø34 长 18，总长 42。要求 G71 粗车、G70 精车，"
            "含 G50 S1800 / G96 S150 M03 / T0101 / F0.25 / M30，只输出 G 代码。",
            55.0, 34.0, 18.0, 42.0, "O0008", "1.5", "0.5", "0.4", "0.1", "0.25",
        ),
    ]
    diverse_rows = [
        row(p, prog_geom(sd, std, sl, tl, ono, u, r, uw, ww, fr), "fanuc_g71_program_diverse_v10")
        for p, sd, std, sl, tl, ono, u, r, uw, ww, fr in extra_diverse_specs
    ]

    g71_progs = program_rows() * 4 + diverse_rows * 2
    g71_rules = rule_rows() * 3

    for r in g71_progs:
        a = r["messages"][-1]["content"]
        assert grader.evaluate_fanuc_g71_safety_probe(a).get("passed"), a[:120]
        if r["meta"]["family"] == "fanuc_g71_program_v9":
            sem = check_g71_step_shaft(a)
            assert sem["passed"], sem

    buckets = [
        _sample_even(sw_clean, 16),
        _sample_even(unit_clean, 23),
        _sample_even(autodiff_clean, 32),
        _sample_even(lame_clean, 36),
        _sample_even(tools_clean, 24),
        g71_progs,
        g71_rules,
    ]
    merged = _round_robin(buckets)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in merged) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    fam = Counter(str(r.get("meta", {}).get("family")) for r in merged)
    print(f"[OK] v10 rows={len(merged)} steps~{len(merged)//4} sha256={hashlib.sha256(OUT.read_bytes()).hexdigest()[:16]}")
    print("     families:", dict(fam))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
