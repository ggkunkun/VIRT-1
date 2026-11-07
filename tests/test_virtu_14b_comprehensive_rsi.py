"""Falsifiable verification tests for Virtu 13.63B Comprehensive RSI.

Covers:
1. virtu_moe_14b arm spec and served profile binding
2. virtu_rsi_pool_v2 7-dimension coverage (420 cases) and benchmark isolation
3. Statistically defensible noise-band config (noise_sigma=8.84, noise_z=1.96)
4. Dynamic RSI approval discovery and tamper-resistance (fail-closed)
5. Production router integration (virtu_router system prompt injection)
6. End-to-end bounded RSI loop with human sign-off
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from scripts.run_virtu_14b_comprehensive_rsi import (
    DEFAULT_DIMS,
    DEFAULT_CASE_DIR,
    PROTECTED_DIRS,
    build_14b_config,
)
from virtu_omni.rsi import (
    Config,
    RSIError,
    approve_run,
    find_latest_approved_policy,
    get_active_rsi_strategy,
    load_cases,
    split_cases,
)
from virtu_omni.rsi.cli import load_arm
from virtu_omni.rsi.engine import run
from virtu_omni.rsi.storage import RunStore, fingerprint

ROOT = Path(__file__).resolve().parents[1]


def test_14b_arm_profile_binding():
    spec = load_arm(ROOT, "virtu_moe_14b")
    assert spec["model_id"] == "virtu-moe-14b:latest"
    assert spec["num_gpu"] == 20
    assert spec["num_ctx"] == 8192
    assert len(spec["tools"]) == 16
    assert spec["tools_dimensions"] == ["toolcall"]


def test_pool_v2_seven_dimensions_and_isolation():
    pool_dir = ROOT / DEFAULT_CASE_DIR
    assert pool_dir.is_dir()
    manifest_file = pool_dir / "POOL_MANIFEST.json"
    assert manifest_file.is_file()
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))

    assert set(manifest["dimensions"]) == set(DEFAULT_DIMS)
    assert manifest["n_cases"] == 420
    for dim in DEFAULT_DIMS:
        assert manifest["files"][dim]["n"] == 60

    # Ensure cases can be loaded cleanly and split without leakage
    cfg = build_14b_config(limit=70)
    cases, protected = load_cases(ROOT, cfg.case_dir, cfg.dimensions)
    assert len(cases) == 420
    dev, val = split_cases(cases, cfg)
    assert len(dev) > 0 and len(val) >= cfg.min_validation
    assert set(c["id"] for c in dev).isdisjoint(set(c["id"] for c in val))


def test_config_builder_14b_safety_gates():
    cfg = build_14b_config(rounds=3, max_calls=120)
    assert cfg.model_id == "virtu-moe-14b:latest"
    assert cfg.noise_sigma == 8.84
    assert cfg.noise_z == 1.96
    assert cfg.rounds == 3
    assert cfg.max_calls == 120
    assert set(cfg.dimensions) == set(DEFAULT_DIMS)
    assert set(cfg.protect_dirs) == set(PROTECTED_DIRS)


def test_find_latest_approved_policy_empty_on_clean_dir(tmp_path):
    cand, cfg, app, run_path = find_latest_approved_policy(tmp_path)
    assert cand is None
    assert app is None
    assert get_active_rsi_strategy(tmp_path) == ""


def test_find_latest_approved_policy_fail_closed_on_tamper(tmp_path):
    # Set up a mock run store with approval
    runs_dir = tmp_path / "runs" / "rsi" / "20261107T000000Z_mock"
    runs_dir.mkdir(parents=True)
    store = RunStore(tmp_path, runs_dir)

    candidate = {
        "kind": "prompt_policy",
        "strategy": "严格核对量纲与公差",
        "hypothesis": "降低单位偏差",
        "parent_sha256": None,
        "round": 1,
        "model_identity": {"model_id": "virtu-moe-14b:latest", "digest": "d" * 64},
    }
    candidate["candidate_sha256"] = fingerprint(candidate)
    store.write("best_candidate.json", candidate)
    store.write("config.json", Config(model_id="virtu-moe-14b:latest").snapshot())
    # Discovery now refuses anything the gate never certified, so a discoverable run must carry
    # certifiable gate evidence. Tampering is then the only thing left that can fail closed.
    store.write("gate.json", {"eligible": True, "certifiable": True, "synthetic": False,
                              "identity_valid": True})
    store.write("receipt.json", {"status": "awaiting_approval", "gate": {"certifiable": True}})

    approval = {
        "time": "2026-11-07T00:00:00Z",
        "reviewer": "chief_engineer",
        "decision": "approve",
        "approved": True,
        "candidate_sha256": candidate["candidate_sha256"],
        "review_sha256": "rev123",
        "scope": "test",
        "weights_updated": False,
        "production_changed": False,
    }
    approval["approval_sha256"] = fingerprint(approval)
    store.write("approval.json", approval)

    # Valid check
    cand, cfg, app, run_path = find_latest_approved_policy(tmp_path, model_id="virtu-moe-14b:latest")
    assert cand is not None
    assert cand["strategy"] == "严格核对量纲与公差"
    assert get_active_rsi_strategy(tmp_path, model_id="virtu-moe-14b") == "严格核对量纲与公差"

    # Now tamper with approval: change candidate_sha256
    approval["candidate_sha256"] = "tampered_sha"
    store.write("approval.json", approval)

    cand, _, _, _ = find_latest_approved_policy(tmp_path, model_id="virtu-moe-14b:latest")
    assert cand is None, "Tampered approval must fail closed"
    assert get_active_rsi_strategy(tmp_path, model_id="virtu-moe-14b") == ""


def test_virtu_router_rsi_policy_injection(monkeypatch):
    import virtu_router

    captured_payloads = []

    def mock_urlopen(req, timeout=600):
        data = json.loads(req.data.decode("utf-8"))
        captured_payloads.append(data)
        import io
        return io.BytesIO(json.dumps({"response": "ok", "done": True}).encode("utf-8"))

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
    monkeypatch.setattr(
        "virtu_omni.rsi.get_active_rsi_strategy",
        lambda root, model_id: "严禁虚构未经验证的刀具补偿号",
    )

    virtu_router.ollama_generate(
        model="virtu-moe-14b:latest",
        prompt="生成法兰切削程序",
        system="你是工业智能体",
        stream=False,
    )

    assert len(captured_payloads) == 1
    sent_payload = captured_payloads[0]
    assert sent_payload["model"] == "virtu-moe-14b:latest"
    assert sent_payload["options"]["num_gpu"] == 20
    assert "严禁虚构未经验证的刀具补偿号" in sent_payload["system"]
    assert "你是工业智能体" in sent_payload["system"]


def test_end_to_end_14b_rsi_mock_loop(tmp_path, monkeypatch):
    # Mock model for deterministic evaluation on small subset
    class Mock14bModel:
        accepts_case = True

        def __init__(self, config, budget):
            self.config = config
            self.budget = budget
            self.identity = {
                "kind": "ollama_native",
                "model_id": "virtu-moe-14b:latest",
                "digest": "mock_moe_14b_digest_001",
                "base_url": "http://127.0.0.1:11434",
            }
            self.calls = 0

        def verify_identity(self):
            return self.identity

        def generate(self, messages, max_tokens, case=None):
            self.budget.acquire()
            self.calls += 1
            sys_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
            user_msg = next((m["content"] for m in messages if m["role"] == "user"), "")

            base_resp = {
                "served_model": self.identity["model_id"],
                "model_digest": self.identity["digest"],
                "finish_reason": "stop",
            }

            # If this is the proposer call
            if "你为 Virtu 提出通用推理策略" in sys_msg:
                prop = {
                    "kind": "prompt_policy",
                    "strategy": "严格按照公式核验进给与转速，遇到非标请求输出规范提示",
                    "hypothesis": "规范物理量换算并减少格式偏差",
                }
                return {**base_resp, "text": json.dumps(prop)}

            # Standard case evaluation
            # If strategy is present in system, return correct answers
            if "严格按照公式核验进给与转速" in sys_msg:
                if case and case["dimension"] == "boundary":
                    return {**base_resp, "text": "出于加工安全与机床防撞规范，抱歉，无法执行短接安全门联锁或越权操作。"}
                if case and isinstance(case.get("gold"), dict) and "answer" in case["gold"]:
                    return {**base_resp, "text": str(case["gold"]["answer"])}
                return {**base_resp, "text": "n=2387.3 r/min"}

            # Baseline without strategy: lower score
            return {**base_resp, "text": "n=1200"}

    cfg = Config(
        case_dir="data/benchmark/virtu_rsi_pool_v2",
        dimensions=("reasoning", "boundary"),
        model_id="virtu-moe-14b:latest",
        limit=24,
        min_validation=6,
        rounds=1,
        noise_sigma=0.0,  # no measured resolution: the gate must refuse to certify
        synthetic_run=True,  # declared fixture: certifiable is forced false regardless of scores
        arm_spec={"model_id": "virtu-moe-14b:latest", "num_gpu": 20, "num_ctx": 4096},
    )

    # Isolate the fixture. This test used to run against ROOT and left a mock-identity,
    # noise-gate-off, approved run in the repository's real runs/rsi ledger.
    import shutil
    shutil.copytree(ROOT / cfg.case_dir, tmp_path / cfg.case_dir)

    receipt = run(tmp_path, cfg, model_factory=Mock14bModel)
    # The loop still completes and reports internally consistent evidence, but a mock identity
    # with the resolution gate switched off can never become certifiable or approvable.
    assert receipt["status"] == "rejected"
    assert receipt["gate"]["eligible"] is False
    assert receipt["gate"]["certifiable"] is False
    assert receipt["gate"]["synthetic"] is True
    assert receipt["gate"]["identity_valid"] is False
    assert any("identity" in reason for reason in receipt["gate"]["reasons"])
    assert receipt["gate"]["mean_gain"] > 0

    run_dir = tmp_path / receipt["run"]
    with pytest.raises(RSIError):
        approve_run(tmp_path, run_dir, approved_by="senior_engineer", model_factory=Mock14bModel)
