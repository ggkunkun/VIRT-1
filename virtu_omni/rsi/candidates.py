"""Development-only diagnoses and solver-verified, non-evaluation SFT candidates."""

from __future__ import annotations

import json
import random
import re
from collections import Counter

from .contracts import fingerprint, question_key, scenario_keys
from .evaluation import strict_score


# Restricted to analytically recomputable tasks with understood contracts.
# mass_props/design are deliberately excluded (historical oracle-unit concerns).
SUPPORTED = {"roughness", "geom_delta", "removal", "fea_fos", "collision",
             "tolerance", "process", "adapt_material", "adapt_machine"}


def development_feedback(cases, records, max_examples=6):
    lookup = {c["id"]: c for c in cases}
    failed_types = Counter()
    weak_tasks = Counter()
    examples = []
    for record in records:
        if record["verdict"] in ("transport_error", "grader_error", "empty_response", "truncated"):
            continue
        if record["all_passed"]:
            continue
        case = lookup[record["case_id"]]
        for check in record["criteria"]:
            if not check["passed"]:
                failed_types[check["type"]] += 1
        tasks = {c["scenario"]["task"] for c in case["criteria"]
                 if isinstance(c.get("scenario"), dict) and c["scenario"].get("task")}
        weak_tasks.update(tasks)
        if len(examples) < max_examples:
            examples.append({"dimension": case["dimension"], "tier": case.get("tier"),
                             "task_prompt": case["prompt"][:1800],
                             "response": record["response"][:1800],
                             "failures": [{"type": c["type"], "evidence": c["evidence"][:600]}
                                          for c in record["criteria"] if not c["passed"]]})
    return {"weak_tasks": dict(weak_tasks), "failed_criteria": dict(failed_types),
            "development_examples": examples,
            "scope": "development-only; validation cases and feedback withheld"}


def _draw(task, rng):
    if task == "roughness":
        values = {"f": round(rng.uniform(.061, .37), 5), "r_eps": round(rng.uniform(.31, 1.51), 5)}
    elif task == "geom_delta":
        before = round(rng.uniform(18000, 180000), 3)
        values = {"feature_vol": round(rng.uniform(90, before * .3), 3), "before": before}
    elif task == "removal":
        values = {"doc": round(rng.uniform(.4, 3), 5), "woc": round(rng.uniform(1, 9), 5),
                  "vf": round(rng.uniform(100, 1000), 4), "L": round(rng.uniform(30, 240), 4),
                  "rho": round(rng.uniform(.00265, .0087), 8),
                  "stock_vol": round(rng.uniform(50000, 350000), 3)}
    elif task in ("fea_fos", "adapt_material"):
        values = {"Sy": round(rng.uniform(210, 600), 4), "sigma": round(rng.uniform(40, 400), 4)}
    elif task == "collision":
        values = {"z_safe": round(rng.uniform(4, 35), 4),
                  "z_min_rapid": round(rng.uniform(-5, 25), 4),
                  "stock_top": round(rng.uniform(0, 20), 4)}
    elif task == "tolerance":
        values = {"tols": [round(rng.uniform(.013, .12), 5) for _ in range(rng.randint(2, 5))],
                  "upper_dev": round(rng.uniform(0, .09), 5),
                  "lower_dev": round(rng.uniform(-.09, 0), 5)}
    elif task == "process":
        values = {"D": round(rng.uniform(12, 95), 5), "L": round(rng.uniform(20, 180), 5),
                  "ap": round(rng.uniform(.3, 3), 5), "f": round(rng.uniform(.065, .26), 5),
                  "vc": round(rng.uniform(70, 185), 5), "r_eps": round(rng.uniform(.35, 1.5), 5)}
    elif task == "adapt_machine":
        values = {"D": round(rng.uniform(12, 95), 5), "vc": round(rng.uniform(70, 200), 5),
                  "n_max": rng.randrange(1500, 7000)}
    else:
        raise ValueError("No trusted synthetic oracle for task")
    return {"task": task, "inputs": values}


def _numbers(text):
    return {float(v) for v in re.findall(r"(?<![\w.])[-+]?\d+(?:\.\d+)?", text)}


def _formula_overlap(scenario, holdout):
    inputs = scenario["inputs"]
    for case in holdout:
        kind = case.get("kind")
        required = None
        if kind == "n" and scenario["task"] in ("process", "adapt_machine"):
            required = [inputs["D"], inputs["vc"]]
        elif kind == "Vf" and scenario["task"] == "process":
            required = [inputs["f"], inputs["D"], inputs["vc"]]
        if required:
            numbers = _numbers(case.get("prompt", ""))
            if all(any(abs(v - n) <= 1e-8 for n in numbers) for v in required):
                return True
    return False


def build_sft_candidates(feedback, protected_cases, hard_holdout, config, store):
    from virtu_eval.contamination_check import check_sample, ngrams, prompt_hash
    from virtu_eval.graders import _wm_verifier

    protected_scenarios = {k for c in protected_cases for k in scenario_keys(c)}
    protected_prompts = {question_key(c) for c in protected_cases}
    evaluation_index = []
    for case in protected_cases + hard_holdout:
        prompt = case.get("prompt", "")
        if not prompt and case.get("messages"):
            prompt = "\n".join(m.get("content", "") for m in case["messages"] if m.get("role") == "user")
        evaluation_index.append({"id": case.get("id", "holdout"), "phash": prompt_hash(prompt),
                                 "ngrams": ngrams(prompt), "gold_nums": []})
    rng = random.Random(config.seed + 911)
    rows, seen, skipped = [], set(), Counter()
    weak_tasks = feedback.get("weak_tasks", {})
    for task in sorted(weak_tasks):
        if task not in SUPPORTED:
            skipped["no_trusted_oracle:" + task] += 1
            continue
        accepted = 0
        for attempt in range(config.synthetic_per_task * 12):
            if accepted >= config.synthetic_per_task:
                break
            scenario = _draw(task, rng)
            key = fingerprint(scenario)
            if _formula_overlap(scenario, hard_holdout):
                skipped["hard_holdout_parameter_overlap"] += 1
                continue
            if key in protected_scenarios or key in seen:
                skipped["scenario_overlap"] += 1
                continue
            try:
                ref = _wm_verifier().recompute(scenario)
                answer = json.dumps({"world_state": ref}, ensure_ascii=False, allow_nan=False)
                if not ref:
                    skipped["oracle_empty"] += 1
                    continue
                criteria = [{"type": "physics_invariant", "scenario": scenario},
                            {"type": "world_state_verified", "scenario": scenario, "tol_rel": 1e-7}]
                graded = strict_score(answer, criteria)
                if not graded["all_passed"]:
                    skipped["oracle_failed_verification"] += 1
                    continue
                prompt = ("独立合成练习（非评测题）。场景为 " + json.dumps(scenario, ensure_ascii=False)
                          + "。单位为 mm、min、g、MPa；rho 明确为 g/mm3。"
                            "按制造物理规律计算，只输出 world_state JSON，字段完整、数值有限。"
                          + "要求字段：" + ", ".join(sorted(ref)))
                case = {"prompt": prompt, "criteria": criteria}
                if question_key(case) in protected_prompts:
                    skipped["prompt_overlap"] += 1
                    continue
                row = {"messages": [{"role": "system", "content": "计算制造场景物理量，不执行工具或程序。"},
                                    {"role": "user", "content": prompt},
                                    {"role": "assistant", "content": answer}],
                       "meta": {"id": "rsi-synthetic-" + key[:16], "source": "analytic_solver_synthetic",
                                "task": task, "scenario": scenario, "scenario_sha256": key,
                                "verified": True, "not_real_cad_or_gui": True}}
                if check_sample(row, evaluation_index, ignore_gold_numeric=True):
                    skipped["evaluation_contamination"] += 1
                    continue
                seen.add(key)
                rows.append(row)
                store.append("data/sft_candidate.jsonl", row)
                accepted += 1
            except (ValueError, TypeError, KeyError, ArithmeticError):
                skipped["oracle_error"] += 1
    report = {"valid": True, "n_rows": len(rows), "tasks": dict(Counter(r["meta"]["task"] for r in rows)),
              "skipped": dict(skipped), "seed": config.seed + 911,
              "protection": {"eval_cases": len(protected_cases), "hard_holdout": len(hard_holdout),
                             "normalized_prompt_and_ngram": True, "exact_scenario": True,
                             "formula_parameter_pairs": True,
                             "gold_numeric_substring_not_a_leak_test": True},
              "status": "candidate_only_not_trained", "target_trainer": "scripts/train_qwen3_8b_qlora.py",
              "requires_manual_training_approval": True,
              "warning": "Analytic solver examples are not evidence of real CAD/GUI/simulation capability."}
    store.write("data/validation.json", report)
    return rows, report
