#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a solver-verified physics pool that gives the RSI loop statistical power.

Root cause this fixes (measured 2026-11-05, no GPU needed to prove it)::

    dims=('physics',)   selected 30  dev 18  val 12  -> gate reason
                                                "validation too small: 12 < 20"

`virtu_eval_phys_v1` holds 30 physics cases; RSI draws its dev/validation split from the
selected dimension only, so the *largest possible* validation set is 12 while
`Config.min_validation` is 20. Every RSI run against that pool is therefore structurally
incapable of producing an eligible candidate -- which is what today's two small runs hit
("validation n=4, mean_gain -10.0"). The loop was not failing because reasoning policies
do not help; it was failing because a gain could never be measured.

The obvious shortcut -- run RSI with `dimensions=physics,derivation` on the published board
so val=24 -- is a red line: it would tune a policy on the same cases the board publishes.
This script therefore generates a *separate* pool in a new directory:

  * scenarios drawn from `virtu_omni.rsi.candidates._draw` (one input-range source, so the
    pool and the synthetic SFT candidates are the same distribution and stay comparable);
  * gold is `scripts/wm_verifier.recompute` output verbatim -- nobody types a number;
  * the law text shown in the prompt comes from `virtu_eval.derivation.LAWS`, never retyped;
  * the criterion *shape* (types/keys/weights/must_compare) is lifted from the published
    board per (dimension, task) so the pool is graded by the same ruler, with
    `tol_rel` set from the same tier mix the board uses;
  * every row must self-score 100 (`virtu_eval.validate_cases` is run here as a hard gate)
    and must be disjoint from the published boards and the 200-case formula holdout by
    scenario fingerprint, normalized prompt hash and 8-gram Jaccard;
  * rejects are counted and printed; an empty pool or an invalid pool exits non-zero
    instead of quietly shipping nothing.

Usage::

    .venv/Scripts/python.exe scripts/build_rsi_case_pool.py --per-family 16
    .venv/Scripts/python.exe scripts/build_rsi_case_pool.py --selftest   # reverse probes
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "data" / "benchmark" / "virtu_rsi_pool_v1"
MANIFEST_NAME = "POOL_MANIFEST.json"

# Published rulers: this pool must never overlap them, in either direction.
PROTECT_DIRS = (
    "data/benchmark/virtu_eval_phys_v1",
    "data/benchmark/virtu_eval_v1",
    "data/benchmark/virtu_eval_cl_v1",
    "data/benchmark/virtu_text_v1",
)
HOLDOUT = "data/benchmark/virtu_fix_v1/formula_holdout_200.jsonl"

# Families with a trusted analytic oracle. mass_props/design stay out on purpose: their
# historical unit mislabelling (mm^5 stamped as mm^4) is a frozen-evidence concern, not
# something a new pool should quietly re-teach.
FAMILIES = ("roughness", "geom_delta", "removal", "fea_fos", "collision",
            "tolerance", "process", "adapt_material", "adapt_machine")

# Same tier->tolerance ladder the published physics board ships (easy 0.08 / medium 0.03 /
# hard 0.01), so a score here is comparable with a score there.
TOL_BY_TIER = {"easy": 0.08, "medium": 0.03, "hard": 0.01}

GIVEN_UNIT = {
    "f": "mm/rev", "r_eps": "mm", "feature_vol": "mm3", "before": "mm3",
    "doc": "mm", "woc": "mm", "vf": "mm/min", "L": "mm", "rho": "g/mm3",
    "stock_vol": "mm3", "Sy": "MPa", "sigma": "MPa", "z_safe": "mm",
    "z_min_rapid": "mm", "stock_top": "mm", "tols": "mm", "upper_dev": "mm",
    "lower_dev": "mm", "D": "mm", "ap": "mm", "vc": "m/min", "n_max": "r/min",
}

GOAL = {
    "roughness": "车削已加工表面粗糙度估算",
    "geom_delta": "切除一个特征前后的体积账（ΔV 记负值，after=before+ΔV）",
    "removal": "铣削去除量、材料去除率与质量收支（ΔV 记负值）",
    "fea_fos": "静强度安全系数校核（Sy 屈服强度、sigma 峰值 von Mises 应力）",
    "collision": "G00 快速移动碰撞判定与 Auto-Diff 颜色",
    "tolerance": "尺寸链闭环的极值半宽与 RSS 半宽、配合间隙",
    "process": "车削工艺参数换算（转速/进给/MRR/粗糙度/切削时间）",
    "adapt_material": "材料替换后的安全系数折算",
    "adapt_machine": "机床主轴能力是否够用",
}

# Predicates are contract verdicts, not arithmetic: they must be spelled out in the
# statement, otherwise the grader charges the model for a rule it was never given.
PREDICATE_RULE = {
    "fea_fos": "fos_gate：safety_factor>=1.5 记 PASS，否则 FAIL。",
    "collision": ("collision_risk：快速段最低点既低于安全平面又低于毛坯顶面+1mm 记 high，否则 none；"
                  "gouge：最低点低于毛坯顶面记 true；autodiff：过切记 red，有风险但未过切记 yellow，安全记 green。"),
    "adapt_machine": "within_limit：需求转速不超过 n_max 记 true，否则 false。",
    "adapt_material": "只要求 safety_factor=Sy/sigma，Sy 取新材料屈服强度。",
}

# The board's boilerplate is deliberately not copied: shared instruction text would make the
# pool a re-skin of the ruler. Semantics stay the runtime contract (one JSON object,
# world_state top level, 4 significant digits, no assumed quantities).
TAIL = ("答案只写一个 JSON 对象，顶层键 world_state，里面逐项给出下列字段（键名原样、带单位后缀）：{fields}。"
        "每个数值只能由上面给到的量算出来，写 4 位有效数字；题面没给的量不许假设。")

DERIV_TAIL = ("另在顶层加 derivation：为上面每个数值字段用字符串写出代入后的算式，算式里只准出现题面给的数、"
              "该定律自身的常数（8、1000、12、π）以及你已经算出的中间量；乘积由校验器现算。只写符号式不代数值不算完成。")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _law_text(task: str) -> str:
    from virtu_eval.derivation import LAWS

    return "；".join(f"{field}={expr}" for field, expr in LAWS.get(task, []))


def _criteria_template() -> dict:
    """Lift the per-(dimension, task) criterion shape from the published board."""
    board = ROOT / "data" / "benchmark" / "virtu_eval_phys_v1"
    templates = {}
    for name in ("physics.jsonl", "derivation.jsonl"):
        for line in (board / name).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            case = json.loads(line)
            task = next((c["scenario"]["task"] for c in case["criteria"]
                         if isinstance(c.get("scenario"), dict)), None)
            key = (case["dimension"], task)
            if key not in templates:
                templates[key] = [{k: v for k, v in c.items() if k != "scenario"}
                                  for c in case["criteria"]]
    missing = [(d, t) for d in ("physics", "derivation") for t in FAMILIES
               if (d, t) not in templates]
    if missing:
        raise SystemExit(f"board has no criterion shape for {missing}; refusing to invent one")
    return templates


def _build_criteria(template, scenario, ref, tier):
    from virtu_eval.derivation import numeric_laws

    scalar = sorted(k for k, v in ref.items()
                    if isinstance(v, (int, float, str)) and not isinstance(v, bool))
    out = []
    for crit in template:
        c = dict(crit)
        c["scenario"] = scenario
        if c["type"] == "world_state_verified":
            c["tol_rel"] = TOL_BY_TIER[tier]
            c["must_compare"] = list(scalar)
            # The law leg only grades numeric laws; verdict fields belong to the physics leg,
            # otherwise omitting a predicate is charged as a law error (2026-11-04 mismatch).
            if c.get("min_compared"):
                c["min_compared"] = min(int(c["min_compared"]),
                                        max(1, len(numeric_laws(scenario["task"]))))
        out.append(c)
    return out


def _given_text(inputs: dict) -> str:
    chunks = []
    for key, value in inputs.items():
        unit = GIVEN_UNIT.get(key, "")
        if isinstance(value, (list, tuple)):
            body = ",".join(f"{float(v):g}" for v in value)
            chunks.append(f"{key}=[{body}] {unit}".strip())
        else:
            chunks.append(f"{key}={float(value):g} {unit}".strip())
    return "，".join(chunks)


def build_prompt(task: str, inputs: dict, ref: dict, derivation: bool) -> str:
    lines = [f"【场景】{_given_text(inputs)}。",
             f"目的：{GOAL[task]}。定律：{_law_text(task)}。"]
    rule = PREDICATE_RULE.get(task)
    if rule:
        lines.append("判定约定：" + rule)
    lines.append(TAIL.format(fields=", ".join(sorted(ref))))
    if derivation:
        lines.append(DERIV_TAIL)
    return "\n".join(lines)


def _system_text() -> str:
    """Reuse the runtime world-model contract instead of inventing a second one.

    ``with_fewshot=False`` on purpose: the shipped few-shot examples carry concrete numbers,
    and copying example values is the measured first failure mode of this checkpoint. A pool
    used to tune a reasoning policy must not hand it numbers to copy.
    """
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    from wm_contract import build_system

    return build_system(with_fewshot=False)


def _protected_index():
    from virtu_eval.contamination_check import load_eval_cases

    index, scenarios = [], set()
    for rel in PROTECT_DIRS:
        directory = ROOT / rel
        if not directory.is_dir():
            continue
        index.extend(load_eval_cases(str(directory)))
        for path in sorted(directory.glob("*.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                case = json.loads(line)
                for crit in case.get("criteria", []):
                    if isinstance(crit.get("scenario"), dict):
                        scenarios.add(hashlib.sha256(json.dumps(
                            crit["scenario"], sort_keys=True, ensure_ascii=False)
                            .encode("utf-8")).hexdigest())
    holdout = []
    if (ROOT / HOLDOUT).is_file():
        for line in (ROOT / HOLDOUT).read_text(encoding="utf-8").splitlines():
            if line.strip():
                holdout.append(json.loads(line))
    return index, scenarios, holdout


def _finite(value) -> bool:
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, dict):
        return all(_finite(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return all(_finite(v) for v in value)
    return True


def _tier_sequence(n: int, rng: random.Random) -> list:
    """Exact published tier mix (30/50/20), shuffled so tier is not welded to a family."""
    from virtu_eval.validate_cases import expected_mix

    easy, medium, hard = expected_mix(n)
    if easy + medium + hard != n:  # rounding can leave one over/under; medium absorbs it
        medium += n - (easy + medium + hard)
    seq = ["easy"] * easy + ["medium"] * medium + ["hard"] * hard
    rng.shuffle(seq)
    return seq


def build_pool(per_family: int, seed: int, out_dir: Path) -> dict:
    from virtu_omni.rsi.candidates import _draw, _formula_overlap
    from virtu_omni.rsi.contracts import question_key
    from virtu_eval.contamination_check import check_sample
    from virtu_eval.graders import _wm_verifier, score_case

    wm = _wm_verifier()
    templates = _criteria_template()
    index, protected_scenarios, holdout = _protected_index()
    rejects = Counter()
    accepted = {"physics": [], "derivation": []}
    seen_scenarios, seen_prompts = set(), set()
    # One sequential rng: ``hash()`` is process-salted on CPython, so per-case seeding via
    # hash() would make the pool non-reproducible (a defect already burned into this repo's
    # history by a tokenizer that did exactly that).
    rng = random.Random(seed)

    for dimension in ("physics", "derivation"):
        derivation = dimension == "derivation"
        for task in FAMILIES:
            made = 0
            for attempt in range(per_family * 8):
                if made >= per_family:
                    break
                scenario = _draw(task, rng)
                key = hashlib.sha256(json.dumps(scenario, sort_keys=True,
                                                ensure_ascii=False).encode("utf-8")).hexdigest()
                if key in protected_scenarios or key in seen_scenarios:
                    rejects["scenario_overlap"] += 1
                    continue
                if _formula_overlap(scenario, holdout):
                    rejects["formula_holdout_overlap"] += 1
                    continue
                ref = wm.recompute(scenario)
                if not ref or not _finite(ref):
                    rejects["oracle_empty_or_nonfinite"] += 1
                    continue
                if wm.l1_check(dict(ref), scenario):
                    rejects["gold_fails_l1"] += 1
                    continue
                answer = {"world_state": dict(ref)}
                if derivation:
                    from virtu_eval.derivation import resolve

                    answer["derivation"] = resolve(task, scenario["inputs"])
                text = json.dumps(answer, ensure_ascii=False)
                prompt = build_prompt(task, scenario["inputs"], ref, derivation)
                qk = question_key({"prompt": prompt, "context": []})
                if qk in seen_prompts:
                    rejects["duplicate_prompt"] += 1
                    continue
                case = {"id": f"rsipool-{dimension[0]}-{task}-{made + 1:02d}",
                        "dimension": dimension, "tier": "medium", "language": "zh",
                        "system": _system_text(), "prompt": prompt, "context": [],
                        "images": [], "max_tokens": 512,
                        "tags": [dimension, task, "rsi_pool_v1", "solver_verified",
                                 "not_real_cad_or_gui"],
                        "criteria": None,
                        "gold": {"answer": text,
                                 "derivation": f"gold=wm_verifier.recompute(task={task}) 原样派生，"
                                               f"无人工填写；tol_rel 由 tier 决定（easy .08 / "
                                               f"medium .03 / hard .01）"}}
                accepted[dimension].append((case, scenario, ref, key, qk, prompt))
                seen_scenarios.add(key)
                seen_prompts.add(qk)
                made += 1

    # Tiers are assigned per file so the published 30/50/20 mix holds exactly, then the
    # criteria are built against that tier and the row must self-score 100.
    rows = {"physics": [], "derivation": []}
    for dimension, items in accepted.items():
        rng = random.Random(seed + len(items))
        seq = _tier_sequence(len(items), rng)
        for (case, scenario, ref, key, qk, prompt), tier in zip(items, seq):
            case["tier"] = tier
            case["criteria"] = _build_criteria(templates[(dimension, scenario["task"])],
                                               scenario, ref, tier)
            graded = score_case(case["gold"]["answer"], case["criteria"])
            if not graded["all_passed"]:
                rejects["gold_not_100:" + ",".join(c["type"] for c in graded["criteria"]
                                                    if not c["passed"])] += 1
                continue
            probe = {"messages": [{"role": "system", "content": case["system"]},
                                  {"role": "user", "content": prompt},
                                  {"role": "assistant", "content": case["gold"]["answer"]}],
                     "criteria": case["criteria"]}
            hits = check_sample(probe, index, ignore_gold_numeric=True)
            if hits:
                rejects["evaluation_contamination"] += 1
                continue
            rows[dimension].append(case)

    total = sum(len(v) for v in rows.values())
    if not total:
        raise SystemExit("pool is empty -- rejects: " + json.dumps(dict(rejects), ensure_ascii=False))

    out_dir.mkdir(parents=True, exist_ok=True)
    files = {}
    for dimension, items in rows.items():
        path = out_dir / f"{dimension}.jsonl"
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in items),
                        encoding="utf-8", newline="\n")
        files[dimension] = {"n": len(items), "sha256": _sha(path),
                            "by_task": dict(Counter(next(c["scenario"]["task"] for c in r["criteria"]
                                                        if isinstance(c.get("scenario"), dict))
                                                    for r in items)),
                            "by_tier": dict(Counter(r["tier"] for r in items))}

    # Hard gate: the pool must pass the project's own case validator, not just my checks.
    from virtu_eval.validate_cases import validate

    problems, _summary = validate(str(out_dir))
    if problems:
        (out_dir / "VALIDATION_FAILED.json").write_text(
            json.dumps(problems, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
        raise SystemExit(f"pool rejected by virtu_eval.validate_cases: {len(problems)} problems; "
                         f"see {out_dir.name}/VALIDATION_FAILED.json")

    manifest = {
        "dir": out_dir.relative_to(ROOT).as_posix(),
        "files": files,
        "n_cases": total,
        "rejects": dict(rejects),
        "seed": seed,
        "ruler": {"tol_by_tier": TOL_BY_TIER,
                  "tier_mix": "30/50/20 enforced by virtu_eval.validate_cases.expected_mix",
                  "criterion_shape_source": "data/benchmark/virtu_eval_phys_v1 per (dimension, task)",
                  "law_text_source": "virtu_eval.derivation.LAWS",
                  "gold_source": "scripts/wm_verifier.recompute",
                  "input_ranges_source": "virtu_omni.rsi.candidates._draw",
                  "system_contract_source": "scripts/wm_contract.build_system(with_fewshot=False)"},
        "disjointness": {"protected_dirs": list(PROTECT_DIRS), "holdout": HOLDOUT,
                         "checked_by": ["scenario sha256", "normalized question key",
                                        "prompt hash + 8-gram Jaccard via "
                                        "virtu_eval.contamination_check.check_sample"]},
        "purpose": "RSI dev/validation pool: min_validation=20 is unreachable on the 30-case "
                   "published physics board, so the improvement loop had no statistical power",
        "not_for": "publishing capability scores -- the published rulers stay in "
                   "data/benchmark/virtu_eval_phys_v1 and virtu_eval_v1",
    }
    (out_dir / MANIFEST_NAME).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                         encoding="utf-8", newline="\n")
    return manifest


# --------------------------------------------------------------------------
# reverse probes: the builder must be falsifiable, not merely green
# --------------------------------------------------------------------------
def selftest() -> int:
    from virtu_eval.graders import _wm_verifier, score_case

    wm = _wm_verifier()
    templates = _criteria_template()
    failures = []

    scenario = {"task": "roughness", "inputs": {"f": 0.2, "r_eps": 0.9}}
    ref = wm.recompute(scenario)
    criteria = _build_criteria(templates[("physics", "roughness")], scenario, ref, "easy")

    # 1. gold whose number disagrees with the solver must NOT pass -> else the ruler is vacuous
    wrong = json.dumps({"world_state": dict(
        ref, surface_roughness_ra_um=ref["surface_roughness_ra_um"] * 3)}, ensure_ascii=False)
    if score_case(wrong, criteria)["all_passed"]:
        failures.append("probe1: solver-disagreeing gold still passes -> ruler is vacuous")

    # 2. a gold that omits a required solver field must be charged (silence is not agreement)
    partial = json.dumps({"world_state": {}}, ensure_ascii=False)
    if score_case(partial, criteria)["all_passed"]:
        failures.append("probe2: empty world_state scored full marks")

    # 3. an unknown tier must not silently fall back to some tolerance
    try:
        _build_criteria(templates[("physics", "roughness")], scenario, ref, "nonsense-tier")
    except KeyError:
        pass
    else:
        failures.append("probe3: unknown tier tolerated silently")

    # 4. families with predicates must require the verdict, or the pool grades an undefined rule
    fos = {"task": "fea_fos", "inputs": {"Sy": 355.0, "sigma": 200.0}}
    fos_ref = wm.recompute(fos)
    if "fos_gate" not in fos_ref:
        failures.append("probe4: fea_fos reference lost the gate predicate")
    fos_criteria = _build_criteria(templates[("physics", "fea_fos")], fos, fos_ref, "easy")
    if not any(c["type"] == "world_state_verified" and "fos_gate" in c.get("must_compare", [])
               for c in fos_criteria):
        failures.append("probe4b: fos_gate not required by the pool criterion")

    # 5. the tier sequence must reproduce the published mix exactly, or validate_cases will
    #    reject the whole pool (this is what silently shipped an ungradeable pool looked like)
    from virtu_eval.validate_cases import expected_mix

    n = 73
    seq = _tier_sequence(n, random.Random(1))
    counts = Counter(seq)
    if sorted(counts.values(), reverse=True) != sorted(expected_mix(n), reverse=True) \
            or sum(counts.values()) != n:
        failures.append(f"probe5: tier mix off for n={n}: {dict(counts)} vs {expected_mix(n)}")

    print("[selftest]", "PASS" if not failures else "FAIL")
    for line in failures:
        print("  -", line)
    return 0 if not failures else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-family", type=int, default=16,
                    help="cases per family per dimension (2 x families x this = total)")
    ap.add_argument("--seed", type=int, default=20261105)
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    manifest = build_pool(args.per_family, args.seed, Path(args.out_dir))
    report = ROOT / "benchmarks" / "VIRTU_RSI_POOL_2026-11-05.json"
    report.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8", newline="\n")
    print("POOL cases=%d rejects=%d" % (manifest["n_cases"], sum(manifest["rejects"].values())))
    for dim, info in manifest["files"].items():
        print(f"  {dim}: n={info['n']} sha256={info['sha256'][:16]} tiers={info['by_tier']}")
    print("REPORT " + report.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
