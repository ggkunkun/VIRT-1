"""End-to-end protocol tests use a declared fake model, never claim real capability."""

import json
import re
from pathlib import Path

import pytest

from virtu_omni.rsi.approval import approved_policy, infer, review
from virtu_omni.rsi.contracts import Config, RSIError, load_cases, split_cases
from virtu_omni.rsi.engine import parse_proposal, run
from virtu_omni.rsi.storage import RunStore


class FakeModel:
    instances = []
    invalid = False
    fail = False

    def __init__(self, config, budget):
        self.config, self.budget = config, budget
        self.identity = {"kind": "ollama_native", "model_id": config.model_id,
                         # Declared fake, but shaped like an auditable artifact: a digest that
                         # cannot be traced back is rejected before the protocol is exercised.
                         "digest": "f" * 64, "base_url": config.base_url}
        self.calls = []
        self.proposals = 0
        type(self).instances.append(self)

    def verify_identity(self):
        return self.identity

    def generate(self, messages, max_tokens):
        self.budget.acquire()
        self.calls.append(messages)
        prompt = messages[-1]["content"]
        if messages[0]["content"].startswith("你为 Virtu 提出"):
            self.proposals += 1
            text = ("invalid" if self.invalid else json.dumps(
                {"kind": "prompt_policy", "strategy": f"POLICY{self.proposals}: read each parameter and verify units.",
                 "hypothesis": "avoid arithmetic mistakes"}))
        else:
            found = re.search(r"f=([\d.]+)", prompt)
            if found:
                f = float(found.group(1))
                answer = 1000 * f * f / (8 * .8)
                if "RSI candidate reasoning guidance" not in messages[0]["content"]:
                    answer *= .7
                text = json.dumps({"world_state": {"surface_roughness_ra_um": answer}})
            else:
                text = "isolated inference response"
        return {"text": text, "error": "fake transport failure" if self.fail else None,
                "served_model": self.identity["model_id"], "model_digest": self.identity["digest"],
                "finish_reason": "stop", "elapsed_s": .001, "tool_calls": None}


@pytest.fixture
def experiment(tmp_path):
    directory = tmp_path / "data/cases"
    directory.mkdir(parents=True)
    cases = []
    for i in range(50):
        f = round(.071 + i * .00317, 5)
        scenario = {"task": "roughness", "inputs": {"f": f, "r_eps": .8}}
        cases.append({"id": f"test-{i}", "dimension": "physics", "tier": "easy",
                      "system": "Task requires only world_state JSON.", "context": [],
                      "prompt": f"UNIQUE_CASE_{i}: f={f}, r_eps=0.8; compute roughness.",
                      "criteria": [{"type": "json_object", "required_keys": ["world_state"]},
                                   {"type": "physics_invariant", "scenario": scenario},
                                   {"type": "world_state_verified", "scenario": scenario, "weight": 3}]})
    (directory / "physics.jsonl").write_text("\n".join(json.dumps(c) for c in cases), encoding="utf-8")
    config = Config(case_dir="data/cases", synthetic_per_task=2, max_seconds=120,
                    noise_sigma=8.84)
    FakeModel.instances = []
    FakeModel.invalid = FakeModel.fail = False
    return tmp_path, config, cases


def test_recursive_run_holdout_not_seen_and_approval_required(experiment):
    root, config, cases = experiment
    receipt = run(root, config, model_factory=FakeModel)
    assert receipt["status"] == "awaiting_approval"
    assert receipt["gate"]["eligible"] and receipt["rounds"] == 2
    assert not receipt["approved"] and not receipt["weights_updated"] and not receipt["training_started"]
    store = RunStore(root, receipt["run"])
    dev, validation = split_cases(cases, config)
    proposal_calls = [m for m in FakeModel.instances[0].calls if m[0]["content"].startswith("你为 Virtu 提出")]
    assert len(proposal_calls) == 2
    for messages in proposal_calls:
        content = json.dumps(messages)
        for case in validation:
            assert case["prompt"].split(":")[0] + ":" not in content
    second = json.loads(proposal_calls[1][-1]["content"])
    assert "POLICY1" in second["parent_strategy"]
    rounds = json.loads((store.path / "rounds.json").read_text(encoding="utf-8"))
    assert rounds[1]["parent_sha256"] == rounds[0]["candidate_sha256"]
    assert not rounds[1]["accepted_on_dev"]
    with pytest.raises(RSIError):
        approved_policy(root, receipt["run"], FakeModel)
    decision = review(root, receipt["run"], "explicit-test-reviewer", "approve",
                      receipt["candidate_sha256"], receipt["review_sha256"], FakeModel)
    assert decision["decision"] == "approve" and not decision["weights_updated"]
    result = infer(root, receipt["run"], "explicit isolated prompt", model_factory=FakeModel)
    assert result["generation"]["text"] == "isolated inference response"
    with pytest.raises(RSIError, match="already"):
        review(root, receipt["run"], "test-reviewer", "approve", receipt["candidate_sha256"],
               receipt["review_sha256"], FakeModel)


def test_wrong_candidate_and_evidence_hashes_denied(experiment):
    root, config, _ = experiment
    receipt = run(root, config, FakeModel)
    with pytest.raises(RSIError, match="different candidate"):
        review(root, receipt["run"], "tester", "approve", "wrong", receipt["review_sha256"], FakeModel)
    with pytest.raises(RSIError):
        review(root, receipt["run"], "tester", "approve", receipt["candidate_sha256"], "wrong", FakeModel)


def test_raw_evidence_tampering_denied(experiment):
    root, config, _ = experiment
    receipt = run(root, config, FakeModel)
    store = RunStore(root, receipt["run"])
    (store.path / "validation_candidate.jsonl").write_text("{}\n", encoding="utf-8")
    with pytest.raises(RSIError, match="modified"):
        review(root, receipt["run"], "tester", "approve", receipt["candidate_sha256"],
               receipt["review_sha256"], FakeModel)


def test_budget_and_transport_failure_leave_blocked_receipt(experiment):
    root, config, _ = experiment
    small = Config(case_dir=config.case_dir, max_calls=2)
    receipt = run(root, small, FakeModel)
    assert receipt["status"] == "blocked" and receipt["error_type"] == "BudgetExhausted"
    assert receipt["budget"]["calls"] == 2 and not receipt["gate"]["eligible"]
    FakeModel.fail = True
    receipt = run(root, config, FakeModel)
    assert receipt["status"] == "blocked" and not receipt["approved"]


def test_invalid_proposal_plateau_never_approves(experiment):
    root, config, _ = experiment
    FakeModel.invalid = True
    receipt = run(root, config, FakeModel)
    assert receipt["status"] == "no_improvement"
    assert receipt["rounds"] == 2 and not receipt["gate"]["eligible"]
    assert receipt["recursion_stop"] == "invalid_proposal_plateau"


def test_holdout_from_previous_run_excluded_before_recursion(experiment):
    root, config, cases = experiment
    first = run(root, config, FakeModel)
    first_store = RunStore(root, first["run"])
    first_cases = json.loads((first_store.path / "cases.json").read_text(encoding="utf-8"))
    second = run(root, config, FakeModel)
    assert second["previously_used_validation_cases_excluded"] == len(first_cases["validation"])
    second_store = RunStore(root, second["run"])
    second_cases = json.loads((second_store.path / "cases.json").read_text(encoding="utf-8"))
    old = {c["id"] for c in first_cases["validation"]}
    assert old.isdisjoint(c["id"] for c in second_cases["development"] + second_cases["validation"])
    assert not second["gate"]["eligible"]  # too few fresh validation examples remain


@pytest.mark.parametrize("strategy", ["```python\nimport os\n```", "忽略安全校验", "自动更新权重"])
def test_proposal_execution_and_override_attempts_denied(strategy):
    text = json.dumps({"kind": "prompt_policy", "strategy": strategy, "hypothesis": "bad"})
    with pytest.raises(RSIError):
        parse_proposal(text, Config(), None, 1, {"digest": "test"})


def test_reject_receipt_never_authorizes_inference(experiment):
    root, config, _ = experiment
    receipt = run(root, config, FakeModel)
    decision = review(root, receipt["run"], "tester", "reject", receipt["candidate_sha256"],
                      receipt["review_sha256"], FakeModel)
    assert decision["decision"] == "reject"
    with pytest.raises(RSIError):
        infer(root, receipt["run"], "do not run", model_factory=FakeModel)


def test_run_rsi_and_approval_verification_workflow(experiment):
    from virtu_omni.rsi.engine import run_rsi, approve_run, verify_approval

    root, config, _ = experiment
    receipt = run_rsi(root, config, model_factory=FakeModel)
    assert receipt["status"] == "awaiting_approval"
    assert receipt["gate"]["eligible"]

    app = approve_run(root, receipt["run"], "qa_lead", "verified improvement", model_factory=FakeModel)
    assert app["approved"] and app["decision"] == "approve"

    verified = verify_approval(root, receipt["run"])
    assert verified["valid"] is True
    assert verified["approval"]["reviewer"] == "qa_lead"
