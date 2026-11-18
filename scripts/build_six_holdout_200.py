#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/build_six_holdout_200.py — 六大工业软件每软件 n=200 物理与工具双真值留出验证集生成器

确保满足 §5/§8 测量宪法与 Wilson 95% 置信区间要求：
  - 六大软件 (solidworks / nx / autocad / cimco / vericut / sscnc) 分层抽样/生成 n=200 (总 1200 题)；
  - Wilson 95% 下界估算在 90% 准确率 / n=200 时约为 0.8505 (>= 0.85)；
  - 与给定训练集语料实现零问题重合（规范化哈希排查），并落盘 holdout_manifest.json SHA256 封缄。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from gate_all90_dataset import SIX_SOFTWARES, sha256_file
from wm_verifier import recompute as wm_recompute


def wilson_lower_bound(k: int, n: int, z: float = 1.959963984540054) -> float:
    if n <= 0:
        return 0.0
    p = k / n
    denom = 1.0 + (z * z) / n
    center = p + (z * z) / (2.0 * n)
    rad = z * math.sqrt((p * (1.0 - p) + (z * z) / (4.0 * n)) / n)
    return (center - rad) / denom


def _norm_q(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _collect_excluded_queries(exclude_files: List[str | Path]) -> Set[str]:
    banned: Set[str] = set()
    for fp in exclude_files:
        p = Path(fp)
        if not p.exists():
            continue
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                obj = json.loads(s)
                if obj.get("prompt"):
                    banned.add(_norm_q(str(obj["prompt"])))
                for m in obj.get("messages") or []:
                    if isinstance(m, dict) and m.get("role") == "user":
                        banned.add(_norm_q(str(m.get("content") or "")))
    return banned


def _synthesize_case(sw: str, idx: int) -> Dict[str, Any]:
    """生成参数完全唯一化、参考真值直接来自 wm_verifier.recompute 的分层验证样本。"""
    cid = f"holdout_{sw}_{idx:04d}"
    if sw in ("solidworks", "nx"):
        before = 12000.0 + idx * 17.5
        feat = 1400.0 + (idx % 19) * 35.0
        wm_spec = {"task": "geom_delta", "feature_vol": feat, "before": before}
        ref = wm_recompute(wm_spec)
        tool = "cadcam_solidworks_model" if sw == "solidworks" else "cadcam_nx_journal"
        prompt = (
            f"[{cid}] 在 {sw.upper()} 中对初始体积 {before:.2f} mm^3 实体进行特征切除 "
            f"(特征体积 {feat:.2f} mm^3)，请调用 {tool} 并输出 delta_volume_mm3 与 after_volume_mm3。"
        )
    elif sw == "autocad":
        tols = [0.02 + (idx % 5) * 0.005, 0.015 + (idx % 3) * 0.004]
        up_dev = 0.08 + (idx % 7) * 0.01
        lo_dev = 0.02 + (idx % 4) * 0.005
        wm_spec = {"task": "tolerance", "tols": tols, "upper_dev": up_dev, "lower_dev": lo_dev}
        ref = wm_recompute(wm_spec)
        tool = "cadcam_autocad_draw"
        prompt = (
            f"[{cid}] 在 AutoCAD 图纸公差链校核中，组成环半带宽 {tols} mm，上限偏差 {up_dev:.3f} mm，"
            f"下限偏差 {lo_dev:.3f} mm，请调用 {tool} 核算极值半带宽与配合间隙判定。"
        )
    elif sw in ("cimco", "vericut"):
        z_safe = 10.0 + (idx % 5) * 2.0
        stock_top = 5.0
        # 交替构造安全下刀与 gouge 危险路径
        z_min = 6.2 if idx % 3 != 0 else 4.2
        wm_spec = {"task": "collision", "z_safe": z_safe, "z_min_rapid": z_min, "stock_top": stock_top}
        ref = wm_recompute(wm_spec)
        tool = "cadcam_cimco_validate" if sw == "cimco" else "cadcam_vericut_simulate"
        prompt = (
            f"[{cid}] 在 {sw.upper()} 仿真中检查 G00 快速定位安全：{z_safe=:.1f} mm，毛坯顶面 Z={stock_top:.1f} mm，"
            f"快速最低点 Z={z_min:.1f} mm，请调用 {tool} 判断 collision_risk、gouge 与 autodiff 颜色。"
        )
    else:  # sscnc
        D = 40.0 + (idx % 12) * 5.0
        L = 60.0 + (idx % 9) * 10.0
        ap = 1.5
        f_feed = 0.12 + (idx % 4) * 0.02
        vc = 120.0 + (idx % 6) * 10.0
        r_eps = 0.4
        wm_spec = {"task": "process", "D": D, "L": L, "ap": ap, "f": f_feed, "vc": vc, "r_eps": r_eps}
        ref = wm_recompute(wm_spec)
        tool = "cadcam_sscnc_control"
        prompt = (
            f"[{cid}] 在 SSCNC 车削对刀仿真中，工件直径 D={D:.1f} mm，切削长度 L={L:.1f} mm，线速度 Vc={vc:.1f} m/min，"
            f"进给量 f={f_feed:.2f} mm/rev，刀尖圆弧 R={r_eps:.1f} mm，请调用 {tool} 计算主轴转速与理论表面粗糙度 Ra。"
        )

    if not ref:
        raise RuntimeError(f"[FATAL] wm_recompute 对 task={wm_spec.get('task')!r} 返回空参考值")
    return {
        "id": cid,
        "software": sw,
        "expected_tool": tool,
        "wm_sample": wm_spec,
        "expected": ref,
        "prompt": prompt,
    }


def build_holdout(
    out_jsonl: str | Path,
    *,
    per_software: int = 200,
    exclude_train: Optional[List[str | Path]] = None,
) -> Dict[str, Any]:
    banned = _collect_excluded_queries(exclude_train or [])
    items: List[Dict[str, Any]] = []
    counts: Counter = Counter()

    for sw in SIX_SOFTWARES:
        seq = 0
        generated = 0
        while generated < per_software:
            case = _synthesize_case(sw, seq)
            seq += 1
            if _norm_q(case["prompt"]) in banned:
                continue
            items.append(case)
            counts[sw] += 1
            generated += 1

    out_p = Path(out_jsonl)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    with open(out_p, "w", encoding="utf-8") as f:
        for row in items:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    out_sha = sha256_file(out_p)
    wilson_90 = wilson_lower_bound(int(round(0.9 * per_software)), per_software)
    manifest = {
        "holdout_path": str(out_p),
        "holdout_sha256": out_sha,
        "per_software": per_software,
        "total_cases": len(items),
        "software_counts": {sw: counts[sw] for sw in SIX_SOFTWARES},
        "excluded_prompt_count": len(banned),
        "wilson_lb_at_90pct": round(wilson_90, 4),
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    Path(str(out_p) + ".manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def run_self_test() -> int:
    # 验证 n=200 且通过率 90% 时 Wilson 95% 下界 >= 0.85
    lb_200 = wilson_lower_bound(180, 200)
    assert lb_200 >= 0.85, f"Wilson lower bound too low at 180/200: {lb_200}"

    with tempfile.TemporaryDirectory(prefix="holdout_selftest_") as td:
        td_p = Path(td)
        train_f = td_p / "train.jsonl"
        first_case = _synthesize_case("solidworks", 0)
        train_f.write_text(json.dumps({"prompt": first_case["prompt"]}, ensure_ascii=False) + "\n", encoding="utf-8")

        holdout_f = td_p / "holdout.jsonl"
        manifest = build_holdout(holdout_f, per_software=5, exclude_train=[train_f])
        assert manifest["total_cases"] == 30
        assert all(manifest["software_counts"][sw] == 5 for sw in SIX_SOFTWARES)

        # 验证被排除的问题确实未进入 holdout
        built_prompts = {_norm_q(json.loads(line)["prompt"]) for line in holdout_f.read_text(encoding="utf-8").splitlines() if line.strip()}
        assert _norm_q(first_case["prompt"]) not in built_prompts, "Exclude-train filter failed!"

    print(f"[SELF-TEST] PASS: build_six_holdout_200 (wilson_lb@180/200={lb_200:.4f} >= 0.85 + zero overlap)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="构建六大软件 n=200 分层留出验证集")
    parser.add_argument("--out", default=str(ROOT / "data" / "benchmark" / "six_holdout_200.jsonl"))
    parser.add_argument("--per-software", type=int, default=200)
    parser.add_argument("--exclude-train", nargs="*", default=[])
    parser.add_argument("--self-test", "--selftest", dest="self_test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()
    manifest = build_holdout(args.out, per_software=args.per_software, exclude_train=args.exclude_train)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
