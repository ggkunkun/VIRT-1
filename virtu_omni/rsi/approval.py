"""Human review receipts. Approval never trains, replaces weights, or deploys."""

from __future__ import annotations

import json
from pathlib import Path

from .contracts import Budget, Config, RSIError, fingerprint, read_jsonl
from .evaluation import LocalModel, policy_messages, strict_score
from .gates import identity_is_real, validation_gate
from .storage import FileLock, RunStore, utc_now, write_json


def _json(store, name):
    try:
        return json.loads(store.target(name).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RSIError(f"Missing or malformed run artifact: {name}") from exc


def retracted_reason(store):
    """Why a sealed run is no longer valid evidence, if it was revoked later.

    Sealed hashes only prove the bytes did not change; they cannot notice that the bytes were
    never evidence to begin with (mock identity, resolution gate switched off). A revocation
    therefore lives beside the runs and is checked before any approval is honoured.
    """
    ledger = store.path.resolve().parents[2] / "runs" / "rsi" / "RETRACTIONS.jsonl"
    if not ledger.exists():
        return None
    try:
        rows = read_jsonl(ledger)
    except RSIError as exc:
        raise RSIError("Retraction ledger is malformed; refusing to honour approvals") from exc
    name = store.path.name
    for row in rows:
        if row.get("run") == name:
            return row.get("reason") or "revoked without a stated reason"
    return None


def _verify_candidate(candidate):
    body = {k: v for k, v in candidate.items() if k != "candidate_sha256"}
    if (candidate.get("kind") != "prompt_policy" or not candidate.get("strategy")
            or fingerprint(body) != candidate.get("candidate_sha256")):
        raise RSIError("Candidate fingerprint or policy type does not match")


def _regrade(records, cases, identity):
    lookup = {case["id"]: case for case in cases}
    result = []
    for record in records:
        case = lookup.get(record["case_id"])
        if case is None:
            raise RSIError("Evaluation record is not in the sealed case set")
        gen = record.get("gen", {})
        if not gen.get("error"):
            if (gen.get("served_model") != identity["model_id"]
                    or gen.get("model_digest") != identity["digest"]):
                raise RSIError("Evaluation response identity does not match the candidate")
        else:
            if record.get("score", 0.0) != 0.0 or record.get("all_passed"):
                raise RSIError("Error record cannot have non-zero score or passed status")
        scored = strict_score(record.get("response", ""), case["criteria"])
        copy = dict(record)
        copy.update(score=scored["score"], all_passed=scored["all_passed"], criteria=scored["criteria"])
        if copy["score"] != record["score"] or copy["all_passed"] != record["all_passed"]:
            raise RSIError("Stored score cannot be reproduced from the raw response")
        result.append(copy)
    return result


def verified_run(store, review_sha256=None):
    evidence = store.verify(review_sha256)
    revoked = retracted_reason(store)
    if revoked:
        raise RSIError(f"Run was retracted and may not be approved: {revoked}")
    receipt = _json(store, "receipt.json")
    config = Config(**_json(store, "config.json"))
    candidate = _json(store, "best_candidate.json")
    manifest = _json(store, "manifest.json")
    _verify_candidate(candidate)
    if (candidate["candidate_sha256"] != receipt.get("candidate_sha256")
            or candidate["model_identity"] != manifest["model_identity"]):
        raise RSIError("Candidate and receipt/manifest disagree")
    if any(receipt.get(key) for key in ("weights_updated", "training_started", "production_changed")):
        raise RSIError("This is not an approval-only run")
    cases = _json(store, "cases.json")
    identity = manifest["model_identity"]
    baseline = _regrade(read_jsonl(store.target("validation_baseline.jsonl")), cases["validation"], identity)
    after = _regrade(read_jsonl(store.target("validation_candidate.jsonl")), cases["validation"], identity)
    data_report = _json(store, "data/validation.json")
    data_path = store.target("data/sft_candidate.jsonl")
    data_rows = read_jsonl(data_path) if data_path.exists() else []
    if len(data_rows) != data_report["n_rows"]:
        raise RSIError("Candidate data count changed")
    eval_scenarios = {fingerprint(c["scenario"]) for case in cases["development"] + cases["validation"]
                      for c in case["criteria"] if isinstance(c.get("scenario"), dict)}
    for row in data_rows:
        scenario = row["meta"]["scenario"]
        if fingerprint(scenario) in eval_scenarios:
            raise RSIError("SFT candidate contains an evaluation scenario")
        criteria = [{"type": "physics_invariant", "scenario": scenario},
                    {"type": "world_state_verified", "scenario": scenario, "tol_rel": 1e-7}]
        if not strict_score(row["messages"][-1]["content"], criteria)["all_passed"]:
            raise RSIError("SFT candidate no longer passes the solver")
    gate = validation_gate(baseline, after, [c["id"] for c in cases["validation"]], config,
                           candidate["candidate_sha256"],
                           identity_valid=identity_is_real(identity),
                           data_valid=data_report["valid"],
                           fresh_validation=receipt.get("fresh_validation") is True)
    from .engine import development_improves

    dev_before = _regrade(read_jsonl(store.target("development_baseline.jsonl")), cases["development"], identity)
    dev_after = _regrade(read_jsonl(store.target(receipt["candidate_development_stage"] + ".jsonl")),
                         cases["development"], identity)
    if not receipt.get("development_improved") or not development_improves(dev_before, dev_after, config):
        gate["eligible"] = False
        gate["certifiable"] = False
        gate["reasons"].append("development improvement evidence does not pass")
    if (not gate["certifiable"] or receipt.get("status") != "awaiting_approval"
            or not receipt["gate"].get("certifiable")):
        raise RSIError("Candidate did not pass the independent approval gates")
    return receipt, candidate, config, evidence


def review(root, run_path, reviewer, decision, candidate_sha256, review_sha256, model_factory=LocalModel):
    if decision not in ("approve", "reject") or not isinstance(reviewer, str) or not reviewer.strip():
        raise RSIError("An explicit reviewer and approve/reject decision are required")
    store = RunStore(root, run_path)
    with FileLock(store.path / ".lock"):
        if store.target("approval.json").exists():
            raise RSIError("This run already has a human decision")
        store.verify(review_sha256)
        candidate = _json(store, "best_candidate.json")
        _verify_candidate(candidate)
        if candidate_sha256 != candidate["candidate_sha256"]:
            raise RSIError("Human review was for a different candidate")
        if decision == "approve":
            receipt, candidate, config, evidence = verified_run(store, review_sha256)
            model = model_factory(config, Budget(config))
            if model.verify_identity() != candidate["model_identity"]:
                raise RSIError("Local model changed since validation")
        approval = {"time": utc_now(), "reviewer": reviewer.strip(), "decision": decision,
                    "approved": decision == "approve",
                    "candidate_sha256": candidate_sha256, "review_sha256": review_sha256,
                    "scope": "explicit use of this prompt policy only; no training or deployment authorized",
                    "weights_updated": False, "production_changed": False}
        approval["approval_sha256"] = fingerprint(approval)
        store.write("approval.json", approval)
        return approval


def approved_policy(root, run_path, model_factory=LocalModel):
    store = RunStore(root, run_path)
    approval = _json(store, "approval.json")
    body = {k: v for k, v in approval.items() if k != "approval_sha256"}
    if approval.get("decision") != "approve" or fingerprint(body) != approval.get("approval_sha256"):
        raise RSIError("This candidate has not been explicitly approved")
    receipt, candidate, config, evidence = verified_run(store, approval["review_sha256"])
    if candidate["candidate_sha256"] != approval["candidate_sha256"]:
        raise RSIError("Approval does not bind this candidate")
    model = model_factory(config, Budget(config))
    if model.verify_identity() != candidate["model_identity"]:
        raise RSIError("Approved strategy is bound to a different model artifact")
    return candidate, config, model, approval


def infer(root, run_path, prompt, system="", model_factory=LocalModel):
    if not isinstance(prompt, str) or not prompt.strip():
        raise RSIError("An explicit prompt is required")
    candidate, config, model, approval = approved_policy(root, run_path, model_factory)
    case = {"prompt": prompt, "system": system, "context": []}
    generation = model.generate(policy_messages(case, candidate["strategy"]), config.max_tokens)
    model.verify_identity()
    result = {"candidate_sha256": candidate["candidate_sha256"], "model_identity": model.identity,
              "approved_by": approval["reviewer"], "generation": generation,
              "scope": "isolated local inference; production routing unchanged"}
    output = RunStore(root)
    output.write("inference.json", result)
    output.write("receipt.json", {"status": "isolated_inference", "weights_updated": False,
                                  "production_changed": False, "parent_run": str(run_path)})
    output.seal({})
    return {**result, "run": output.path.relative_to(Path(root).resolve()).as_posix()}


def find_latest_approved_policy(root, model_id=None):
    """Scan runs/rsi/ for the latest sealed and human-approved candidate matching model_id.

    Returns (candidate, config, approval, run_path) or (None, None, None, None).
    """
    root = Path(root).resolve()
    base = root / "runs" / "rsi"
    if not base.is_dir():
        return None, None, None, None

    for item in sorted(base.iterdir(), reverse=True):
        if not item.is_dir() or item.name.startswith("."):
            continue
        approval_file = item / "approval.json"
        if not approval_file.is_file():
            continue
        try:
            store = RunStore(root, item)
            approval = _json(store, "approval.json")
            body = {k: v for k, v in approval.items() if k != "approval_sha256"}
            if approval.get("decision") != "approve" or fingerprint(body) != approval.get("approval_sha256"):
                continue
            candidate = _json(store, "best_candidate.json")
            _verify_candidate(candidate)
            if candidate["candidate_sha256"] != approval["candidate_sha256"]:
                continue
            config_dict = _json(store, "config.json")
            cfg = Config(**config_dict)
            cand_model = candidate.get("model_identity", {}).get("model_id", "")
            if model_id:
                cand_base = cand_model.split(":")[0]
                req_base = model_id.split(":")[0]
                if cand_model != model_id and cand_base != req_base:
                    continue
            # This is the seam the router injects a strategy through, so it must apply the same
            # two refusals the gate does: revoked evidence, and runs that were never certifiable.
            if retracted_reason(store):
                continue
            receipt = _json(store, "receipt.json")
            gate = _json(store, "gate.json") if (item / "gate.json").is_file() else {}
            if gate.get("certifiable") is not True or receipt.get("status") != "awaiting_approval":
                continue
            return candidate, cfg, approval, item.relative_to(root).as_posix()
        except Exception:
            continue
    return None, None, None, None


def get_active_rsi_strategy(root, model_id=None):
    """Convenience helper: returns strategy string from latest approved RSI candidate or empty string."""
    candidate, _, _, _ = find_latest_approved_policy(root, model_id)
    if candidate and isinstance(candidate.get("strategy"), str):
        return candidate["strategy"].strip()
    return ""

