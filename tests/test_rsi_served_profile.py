"""RSI must measure the served profile, and a gain must beat the noise before it counts.

Two defects this file pins down:
1. the loop hardcoded num_ctx=8192 with no tool schema, so the 13.63B MoE was scored in a
   configuration nobody serves (its toolcall ceiling is a 4k branch, its best split is num_gpu=30);
2. the accept rule compared a mean gain against min_dev_gain=0.1 while the measured paired
   sigma on this box is 8.84, so a single lucky round could be reported as self-improvement.
"""

import json

import pytest

from virtu_omni.rsi import cli, evaluation
from virtu_omni.rsi.contracts import Budget, Config, RSIError, remote_url
from virtu_omni.rsi.engine import development_improves
from virtu_omni.rsi.gates import validation_gate
from virtu_eval.arms import OllamaNativeArm, build_arm


TOOLS = [{"type": "function", "function": {"name": "lookup", "parameters": {"type": "object"}}}]


class StubArm:
    def __init__(self):
        self._opener = None
        self.timeout = 0

    def tools_for(self, case):
        return TOOLS if case.get("dimension") == "toolcall" else None


def test_arm_spec_reaches_build_arm_with_pinned_endpoint(monkeypatch):
    seen = {}

    def fake_build(spec):
        seen.update(spec)
        return StubArm()

    monkeypatch.setattr("virtu_eval.arms.build_arm", fake_build)
    monkeypatch.setattr(evaluation.LocalModel, "_identity",
                        lambda self: {"kind": "ollama_native", "model_id": self.requested,
                                      "digest": "d", "base_url": self.base})
    config = Config(model_id="virtu-moe-14b:a2103c68",
                    arm_spec={"num_ctx": 8192, "num_gpu": 30, "tools": TOOLS,
                              "tools_dimensions": ["toolcall"], "base_url": "http://evil.example"})
    model = evaluation.LocalModel(config, Budget(config))

    assert seen["model_id"] == "virtu-moe-14b:a2103c68"
    assert seen["num_ctx"] == 8192
    assert seen["num_gpu"] == 30
    assert seen["tools"] == TOOLS and seen["tools_dimensions"] == ["toolcall"]
    assert seen["base_url"].startswith("http://127.0.0.1")   # the loopback pin wins
    assert model.requested == "virtu-moe-14b:a2103c68"


def test_tool_schema_is_scoped_to_declared_dimensions():
    arm = build_arm({"kind": "ollama_native", "model_id": "m", "num_ctx": 8192,
                     "num_gpu": 30, "tools": TOOLS, "tools_dimensions": ["toolcall"]})
    assert isinstance(arm, OllamaNativeArm) and arm.num_gpu == 30
    assert arm.tools_for({"dimension": "toolcall", "tools": TOOLS}) == TOOLS
    assert arm.tools_for({"dimension": "reasoning", "tools": TOOLS}) is None


def test_num_gpu_stays_unset_when_not_pinned():
    assert build_arm({"kind": "ollama_native", "model_id": "m"}).num_gpu is None


def _records(scores, dimension="physics"):
    return [{"case_id": str(i), "dimension": dimension, "score": s,
             "all_passed": s == 100, "verdict": "pass" if s == 100 else "partial",
             "criteria": [{"key": "format", "type": "regex_match", "passed": True}]}
            for i, s in enumerate(scores)]


@pytest.mark.parametrize("noise,ok", [(0.0, False), (8.84, False)])
def test_jitter_sized_gain_never_passes_without_resolution(noise, ok):
    """+2 with sigma=0 used to pass because an unset gate meant no gate. An unset gate now
    means no measurable resolution, which cannot support a gain claim either."""
    baseline = _records([92] * 20)
    candidate = _records([94] * 20)          # +2 points: above min_dev_gain, inside the band
    config = Config(min_gain=1.0, noise_sigma=noise)
    result = validation_gate(baseline, candidate, [str(i) for i in range(20)], config, "sha")
    assert result["eligible"] is ok
    assert result["certifiable"] is False
    if noise:
        assert result["paired_noise_band"] == pytest.approx(1.96 * 8.84 / 20 ** 0.5, abs=1e-3)
        assert any("noise band" in r for r in result["reasons"])
    else:
        assert any("noise resolution gate not configured" in r for r in result["reasons"])


def test_real_gain_clears_the_noise_band():
    result = validation_gate(_records([40] * 20), _records([100] * 20),
                             [str(i) for i in range(20)], Config(min_gain=1.0, noise_sigma=8.84),
                             "sha")
    assert result["eligible"] and result["mean_gain"] == 60


def test_development_floor_is_raised_to_the_noise_resolution():
    config = Config(noise_sigma=8.84, min_dev_gain=0.1)
    assert not development_improves(_records([92] * 20), _records([94] * 20), config)
    assert development_improves(_records([40] * 20), _records([100] * 20), config)


@pytest.mark.parametrize("kwargs,message", [
    ({"arm_spec": {"kind": "hf_local"}}, "arm kind"),
    ({"arm_spec": {"kind": "http_openai"}}, "allow_remote"),
    ({"arm_spec": {"kind": "http_openai"}, "allow_remote": True,
      "base_url": "http://vllm.example:8000/v1/chat"}, "bare http"),
    ({"arm_spec": {"kind": "http_openai"}, "allow_remote": True,
      "base_url": "https://user:pw@vllm.example:8000"}, "bare http"),
    ({"arm_spec": {"kind": "http_openai"}, "allow_remote": True,
      "base_url": "http://vllm.example"}, "explicit port"),
    ({"arm_spec": {"num_ctx": 8192, "made_up": 1}}, "unknown keys"),
    ({"noise_sigma": -1.0}, "nonnegative"),
    ({"noise_sigma": 8.84, "noise_z": 1.0}, "must exceed 1"),
])
def test_config_rejects_unservable_or_unmeasurable_requests(kwargs, message):
    with pytest.raises(RSIError, match=message):
        Config(**kwargs)


def test_remote_endpoint_accepts_an_openai_v1_prefix():
    """vLLM/SGLang serve /v1/models and /v1/chat/completions; the bare origin form alone
    cannot reach them, so exactly "/v1" is admitted and the prefix is preserved."""
    config = Config(arm_spec={"kind": "http_openai"}, allow_remote=True,
                    base_url="https://vllm.example:8000/v1/")
    assert remote_url(config.base_url) == "https://vllm.example:8000/v1"
    with pytest.raises(RSIError, match="without credentials"):
        Config(arm_spec={"kind": "http_openai"}, allow_remote=True,
               base_url="https://vllm.example:8000/v1?key=1")


def test_cli_copies_the_measured_arm_profile():
    spec = cli.load_arm(cli.ROOT, "moe14b_gate_random")
    assert spec["model_id"] == "virtu-moe-14b:a2103c68"
    assert spec["num_ctx"] == 8192 and spec["tools"]
    assert "note" not in spec                # prose stays in the registry, not in the run spec
    with pytest.raises(RSIError, match="Unknown arm"):
        cli.load_arm(cli.ROOT, "no_such_arm")


def test_cli_arm_flag_feeds_the_config(monkeypatch, tmp_path):
    parser = cli.parser()
    args = parser.parse_args(["run", "--arm", "moe14b_gate_random", "--noise-sigma", "8.84",
                              "--model-id", "virtu-moe-14b:latest"])
    config = cli.config_from(args, cli.ROOT)
    assert config.arm_spec["model_id"] == "virtu-moe-14b:a2103c68"   # the arm entry wins
    assert config.noise_sigma == 8.84
    assert config.model_id == "virtu-moe-14b:latest"                # identity still explicit
    snapshot = json.loads(json.dumps(config.snapshot()))            # receipt-safe
    assert snapshot["arm_spec"]["num_ctx"] == 8192
