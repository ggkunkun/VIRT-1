"""The cloud entry is the only place a run may leave loopback; pin its contract."""

import pytest

from cloud_train_pack.rsi_cloud_entry import DEFAULT_DIMS, build_config, served_profile
from virtu_omni.rsi.contracts import RSIError


ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
BASE = {"VIRTU_RSI_BASE_URL": "https://vllm.example:8000/v1", "VIRTU_RSI_MODEL_ID": "virtu-13b-moe"}


def test_cloud_config_opts_into_remote_exactly_once():
    config = build_config(ROOT, env=dict(BASE))
    assert config.allow_remote is True
    assert config.arm_spec["kind"] == "http_openai"
    assert config.arm_spec["model_id"] == "virtu-13b-moe"
    assert config.dimensions == DEFAULT_DIMS
    assert config.case_dir == "data/benchmark/virtu_rsi_pool_v2"
    # placement belongs to the remote host, so the local num_gpu knob must not ride along
    assert "num_gpu" not in config.arm_spec


def test_cloud_config_carries_the_measured_tool_schema():
    config = build_config(ROOT, env=dict(BASE))
    assert config.arm_spec["tools"], "toolcall dimension needs the measured tool schema"
    assert config.arm_spec["tools_dimensions"]


@pytest.mark.parametrize("missing", ["VIRTU_RSI_BASE_URL", "VIRTU_RSI_MODEL_ID"])
def test_cloud_config_refuses_to_guess_the_endpoint(missing):
    env = dict(BASE)
    env.pop(missing)
    with pytest.raises(RSIError, match=missing):
        build_config(ROOT, env=env)


@pytest.mark.parametrize("url", [
    "https://vllm.example:8000/v1/chat",       # a path we would have to silently rewrite
    "https://user:pw@vllm.example:8000/v1",    # credentials ride in the URL
    "https://vllm.example/v1",                 # no explicit port
    "http://127.0.0.1:8000/v1",                # loopback is a local run, not a cloud run
])
def test_cloud_config_rejects_unusable_endpoints(url):
    env = dict(BASE, VIRTU_RSI_BASE_URL=url)
    with pytest.raises(RSIError):
        build_config(ROOT, env=env)


def test_cloud_config_reads_budgets_from_the_environment():
    env = dict(BASE, VIRTU_RSI_MAX_CALLS="400", VIRTU_RSI_ROUNDS="3",
               VIRTU_RSI_DIMS="reasoning,toolcall", VIRTU_RSI_MAX_TOKENS="192")
    config = build_config(ROOT, env=env)
    assert (config.max_calls, config.rounds, config.max_tokens) == (400, 3, 192)
    assert config.dimensions == ("reasoning", "toolcall")


def test_served_profile_retargets_the_registry_without_placement():
    profile = served_profile(ROOT, "any-served-id")
    assert profile["kind"] == "http_openai"
    assert profile["model_id"] == "any-served-id"
    assert profile["num_ctx"] == 8192
    assert "num_gpu" not in profile
