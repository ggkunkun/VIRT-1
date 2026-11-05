"""Finite dev-only recursion, one-shot holdout validation, explicit human approval."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .candidates import build_sft_candidates, development_feedback
from .contracts import (Budget, BudgetExhausted, Config, RSIError, canonical_json, fingerprint,
                        inside, load_cases, question_key, read_jsonl, scenario_keys, split_cases)
from .evaluation import CRITICAL_TYPES, LocalModel, evaluate_cases, summarize
from .gates import BAD_VERDICTS, validation_gate
from .storage import FileLock, RunStore, append_jsonl, assert_sources, source_hashes, utc_now


PROPOSER_SYSTEM = """你为 Virtu 提出通用推理策略，不执行任务、不调用工具、不修改文件或权重。
只输出一个 JSON 对象，恰好包含 kind、strategy、hypothesis。
kind 必须为 prompt_policy；strategy 为可复用的简短中文推理指导；hypothesis 为预期改善原因。
根据开发集反馈改进 parent_strategy，但不得背诵题面、答案或参考数值。
保留任务原有安全规则和输出 JSON 格式，不改变题目参数、评测标准或更新权限。
可以要求逐项读参数、核对单位、分步计算和最终自查，不要提供执行命令、程序或工具调用。
没有独立留出集的信息，不得猜测它的题目或结果。"""


def parse_proposal(text, config, parent_sha256, round_index, identity):
    from virtu_eval.graders import parse_json_candidate

    value, error = parse_json_candidate(text)
    if (not isinstance(value, dict) or set(value) != {"kind", "strategy", "hypothesis"}
            or value["kind"] != "prompt_policy"):
        raise RSIError("Proposal does not match the prompt_policy schema")
    strategy, hypothesis = value["strategy"], value["hypothesis"]
    if (not isinstance(strategy, str) or not strategy.strip()
            or len(strategy) > config.max_strategy_chars
            or not isinstance(hypothesis, str) or len(hypothesis) > 1600):
        raise RSIError("Proposal has missing or oversized text")
    forbidden = (r"```|<tool_call>|(?:^|\n)\s*(?:import |from \w+ import|def |powershell |cmd /|curl |rm )",
                 r"(?:忽略|跳过|绕过).{0,14}(?:安全|评测|审批|校验|原有指令)",
                 r"(?:自动|直接).{0,10}(?:更新权重|修改权重|上线部署)")
    if any(re.search(pattern, strategy, re.I) for pattern in forbidden):
        raise RSIError("Proposal attempts execution or overriding the safety boundary")
    candidate = {"kind": "prompt_policy", "strategy": strategy.strip(),
                 "hypothesis": hypothesis.strip(), "parent_sha256": parent_sha256,
                 "round": round_index, "model_identity": identity}
    candidate["candidate_sha256"] = fingerprint(candidate)
    return candidate


def development_improves(before, after, config):
    if len(before) != len(after) or any(r["verdict"] in BAD_VERDICTS for r in after):
        return False
    b, c = summarize(before), summarize(after)
    if c["mean_score"] < b["mean_score"] + config.min_dev_gain:
        return False
    if any(c["dimensions"].get(d, -1) + config.max_dimension_regression < score
           for d, score in b["dimensions"].items()):
        return False
    earlier = {r["case_id"]: r for r in before}
    regressions = 0
    for record in after:
        previous = earlier.get(record["case_id"])
        if previous is None:
            return False
        regressions += record["score"] < previous["score"]
        previous_checks = {(c["key"], c["type"]): c["passed"] for c in previous["criteria"]}
        if any(not c["passed"] and previous_checks.get((c["key"], c["type"]))
               for c in record["criteria"] if c["type"] in CRITICAL_TYPES):
            return False
    return regressions <= config.max_regressions


def _case_tokens(case):
    return {"q:" + question_key(case)} | {"s:" + value for value in scenario_keys(case)}


def _seen_validation(base, identity):
    path = base / "validation_seen.jsonl"
    seen = set()
    if path.exists():
        for record in read_jsonl(path):
            if record.get("model_digest") == identity["digest"]:
                seen.update(record.get("keys", []))
    return seen


def _protect_validation(base, store, identity, cases):
    append_jsonl(base / "validation_seen.jsonl",
                 {"time": utc_now(), "run": store.path.name,
                  "model_digest": identity["digest"],
                  "keys": sorted({k for case in cases for k in _case_tokens(case)})})


def run(root, config, model_factory=LocalModel):
    """Run one finite experiment. Failed candidates are retained, never deployed."""
    root = Path(root).resolve()
    base = inside(root, "runs/rsi")
    with FileLock(base / ".orchestrator.lock"):
        store = RunStore(root)
        budget = Budget(config)
        receipt = {"status": "running", "run": store.path.relative_to(root).as_posix(),
                   "started": utc_now(), "weights_updated": False, "training_started": False,
                   "production_changed": False, "approved": False}
        store.write("config.json", config.snapshot())
        sources = {}
        stage = "preflight"
        try:
            sources = source_hashes(root, config.case_dir)
            cases, protected = load_cases(root, config.case_dir, config.dimensions)
            model = model_factory(config, budget)
            receipt["model_identity"] = model.identity
            seen = _seen_validation(base, model.identity)
            fresh = [case for case in cases if _case_tokens(case).isdisjoint(seen)]
            receipt["previously_used_validation_cases_excluded"] = len(cases) - len(fresh)
            if len(fresh) < 2:
                raise RSIError("No fresh cases remain; supply a new independent case set")
            dev, validation = split_cases(fresh, config)
            store.write("cases.json", {"development": dev, "validation": validation,
                                      "protected_case_ids": [c["id"] for c in protected]})
            store.write("manifest.json", {"model_identity": model.identity, "sources": sources,
                                          "sampling": {"temperature": 0.0, "seed": config.seed,
                                                       "max_tokens": config.max_tokens,
                                                       "think": False, "retries": 0},
                                          "development_ids": [c["id"] for c in dev],
                                          "validation_ids": [c["id"] for c in validation]})
            store.audit("started", model_digest=model.identity["digest"],
                        development_n=len(dev), validation_n=len(validation))
            stage = "development_baseline"
            baseline_dev = evaluate_cases(model, dev, config, store, "development_baseline")
            if summarize(baseline_dev)["errors"]:
                raise RSIError("Development baseline is incomplete or contains infrastructure/product failures")
            feedback = development_feedback(dev, baseline_dev)
            store.write("development_feedback.json", feedback)
            holdout_path = root / "data/benchmark/virtu_fix_v1/formula_holdout_200.jsonl"
            hard_holdout = read_jsonl(holdout_path) if holdout_path.exists() else []
            _, data_report = build_sft_candidates(feedback, protected, hard_holdout, config, store)
            best, best_records, best_stage = None, baseline_dev, "development_baseline"
            best_attempt = None
            plateau = 0
            rounds = []
            for index in range(1, config.rounds + 1):
                if config.max_calls - budget.calls < 1 + len(dev) + 2 * len(validation):
                    receipt["recursion_stop"] = "budget_reserved_for_independent_validation"
                    break
                stage = f"rounds/{index:02d}"
                parent_strategy = best["strategy"] if best else ""
                parent_sha = best["candidate_sha256"] if best else None
                payload = {"round": index, "parent_strategy": parent_strategy,
                           "development_feedback": development_feedback(dev, best_records)}
                generation = model.generate([{"role": "system", "content": PROPOSER_SYSTEM},
                                             {"role": "user", "content": canonical_json(payload)}],
                                            max_tokens=config.proposal_tokens)
                store.write(stage + "/proposal_raw.json", generation)
                if generation.get("error"):
                    raise RSIError("Local proposer call failed; no network retry or model update performed")
                try:
                    if generation.get("finish_reason") == "length" or generation.get("tool_calls"):
                        raise RSIError("Proposal truncated or attempted a tool call")
                    proposal = parse_proposal(generation.get("text") or "", config,
                                              parent_sha, index, model.identity)
                except RSIError as exc:
                    plateau += 1
                    rounds.append({"round": index, "accepted_on_dev": False, "reason": str(exc)})
                    store.audit("proposal_rejected", round=index, reason=str(exc))
                    if plateau >= config.plateau_rounds:
                        receipt["recursion_stop"] = "invalid_proposal_plateau"
                        break
                    continue
                store.write(stage + "/candidate.json", proposal)
                candidate_records = evaluate_cases(model, dev, config, store,
                                                    stage + "/development", proposal["strategy"])
                adopted = development_improves(best_records, candidate_records, config)
                summary = summarize(candidate_records)
                attempt = (proposal, candidate_records, stage + "/development")
                if not summary["errors"] and (best_attempt is None or summary["mean_score"] >
                                               summarize(best_attempt[1])["mean_score"]):
                    best_attempt = attempt
                rounds.append({"round": index, "candidate_sha256": proposal["candidate_sha256"],
                               "parent_sha256": parent_sha, "accepted_on_dev": adopted,
                               "development": summary})
                store.audit("development_validated", **rounds[-1])
                if adopted:
                    best, best_records, best_stage = attempt
                    plateau = 0
                else:
                    plateau += 1
                if plateau >= config.plateau_rounds:
                    receipt["recursion_stop"] = "no_development_gain_plateau"
                    break
            store.write("rounds.json", rounds)
            receipt["rounds"] = len(rounds)
            receipt["development_baseline"] = summarize(baseline_dev)
            receipt["data_candidate"] = data_report
            selected = (best, best_records, best_stage) if best else best_attempt
            receipt["development_improved"] = best is not None
            if selected is None:
                gate = validation_gate([], [], [c["id"] for c in validation], config, None,
                                       data_valid=data_report["valid"])
                receipt["status"] = "no_improvement"
                receipt["independent_validation"] = "not_run_no_valid_candidate"
            else:
                candidate, selected_dev, selected_stage = selected
                store.write("best_candidate.json", candidate)
                receipt["candidate_sha256"] = candidate["candidate_sha256"]
                receipt["candidate_development_stage"] = selected_stage
                receipt["development_candidate"] = summarize(selected_dev)
                store.audit("candidate_frozen", candidate_sha256=candidate["candidate_sha256"],
                            development_improved=best is not None)
                # Mark the holdout used BEFORE exposing any feedback; interrupted runs cannot recycle it.
                _protect_validation(base, store, model.identity, validation)
                receipt["fresh_validation"] = True
                stage = "validation_baseline"
                baseline_val = evaluate_cases(model, validation, config, store, "validation_baseline")
                stage = "validation_candidate"
                candidate_val = evaluate_cases(model, validation, config, store, "validation_candidate",
                                               candidate["strategy"])
                gate = validation_gate(baseline_val, candidate_val, [c["id"] for c in validation],
                                       config, candidate["candidate_sha256"], data_valid=data_report["valid"])
                gate["development_improved"] = best is not None
                if best is None:
                    gate["eligible"] = False
                    gate["reasons"] = sorted(set(gate["reasons"] + ["development gate did not pass"]))
                receipt["status"] = "awaiting_approval" if gate["eligible"] else "rejected"
                receipt["independent_validation"] = "completed_once_after_candidate_frozen"
            model.verify_identity()
            assert_sources(root, sources)
            store.write("gate.json", gate)
            receipt["gate"] = gate
            store.audit("finished", status=receipt["status"], gate_eligible=gate["eligible"])
        except (Exception, KeyboardInterrupt) as exc:
            receipt.update(status="blocked", blocked_stage=stage,
                           error_type=type(exc).__name__, error=str(exc)[:800])
            store.audit("blocked", stage=stage, error_type=type(exc).__name__)
            gate = {"eligible": False, "reasons": ["Run interrupted or failed; approval forbidden"]}
            receipt["gate"] = gate
            store.write("gate.json", gate)
        receipt["finished"] = utc_now()
        receipt["budget"] = budget.snapshot()
        store.write("receipt.json", receipt)
        evidence = store.seal(sources)
        return {**receipt, "review_sha256": evidence["review_sha256"]}


def run_rsi(root: str | Path, config: Config | None = None, model: LocalModel | None = None, model_factory=None) -> dict:
    """Run finite dev-only recursive improvement, holdout validation gate, and candidate generation."""
    config = config or Config()
    factory = model_factory or (lambda c, b: model if model is not None else LocalModel(c, b))
    return run(root, config, model_factory=factory)


def approve_run(root: str | Path, run_dir: str | Path, approved_by: str, comment: str = "", model_factory=None) -> dict:
    """Explicit human sign-off on a sealed, gate-eligible RSI run."""
    from .approval import review
    from .evaluation import LocalModel

    root = Path(root).resolve()
    store = RunStore(root, path=run_dir)
    evidence = store.verify()
    receipt = json.loads(store.target("receipt.json").read_text(encoding="utf-8"))
    candidate_sha = receipt.get("candidate_sha256")
    if not candidate_sha:
        raise RSIError("No candidate to approve in receipt")
    factory = model_factory or LocalModel
    return review(root, run_dir, approved_by, "approve", candidate_sha, evidence["review_sha256"], model_factory=factory)


def verify_approval(root: str | Path, run_dir: str | Path) -> dict:
    """Verify sealed evidence, gate eligibility, and valid approval signature."""
    from .approval import verified_run

    root = Path(root).resolve()
    store = RunStore(root, path=run_dir)
    try:
        evidence = store.verify()
        receipt, candidate, config, verified_evidence = verified_run(store)
        approval_path = store.target("approval.json")
        if not approval_path.is_file():
            return {"valid": False, "reason": "Missing approval.json", "store": store}
        approval = json.loads(approval_path.read_text(encoding="utf-8"))
        if not approval.get("approved") and approval.get("decision") != "approve":
            return {"valid": False, "reason": "Approval record not marked approved", "store": store}
        return {
            "valid": True,
            "store": store,
            "receipt": receipt,
            "evidence": evidence,
            "approval": approval,
            "candidate": candidate,
        }
    except Exception as exc:
        return {"valid": False, "reason": str(exc), "store": store}
