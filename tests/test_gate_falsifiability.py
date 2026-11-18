"""Falsifiability gates for the three always-true verdicts (P0-A).

Each test injects a *bad sample* and asserts the gate must go red. If anyone
restores a hard-coded ``passed=True`` / ``success=True`` / ``success: True``,
at least one test here fails. No network, no Ollama, no CAD software needed.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from virtu_omni.agent.agent_team import AuditorAndSandboxAgent
from virtu_omni.agent.super_agent import VirtuSuperAgent
from virtu_omni.internet import internet_hub as hub_module
from virtu_omni.internet.internet_hub import VirtuInternetHub

ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------
# 1. Auditor & Sandbox facet
# --------------------------------------------------------------------------
class _StubOptimizer:
    def __init__(self, sw_passed: bool = True, macro_passed: bool = True):
        self.sw_passed = sw_passed
        self.macro_passed = macro_passed

    def audit_code(self, code, kind):
        passed = self.sw_passed if kind == "solidworks" else self.macro_passed
        return {"passed": passed, "score": 100 if passed else 0, "issues": []}

    def reflect_and_optimize(self, code, audit):
        return code, "stub reflection"


class _StubSecurityAuditor:
    def __init__(self, prompt_passed: bool = True, tool_passed: bool = True):
        self.prompt_passed = prompt_passed
        self.tool_passed = tool_passed

    def audit_prompt_injection(self, prompt):
        return {"passed": self.prompt_passed}

    def audit_tool_arguments(self, name, args):
        return {"passed": self.tool_passed}


def _make_auditor(*, sw=True, macro=True, prompt=True, tool=True) -> AuditorAndSandboxAgent:
    agent = AuditorAndSandboxAgent.__new__(AuditorAndSandboxAgent)
    agent.name = "test-auditor"
    agent.optimizer = _StubOptimizer(sw, macro)
    agent.security_auditor = _StubSecurityAuditor(prompt, tool)
    agent.verifier = object()
    return agent


def _auditor_context():
    return {
        "user_prompt": "设计一个套筒",
        "architecture": {"parsed_spec": {"material": "Ti-6Al-4V"}},
        "modeling": {"solidworks_vba": "Sub Main()\nEnd Sub"},
        "machining": {"macro_b_code": "G00 X0"},
    }


@pytest.mark.parametrize(
    "bad_kw,expected_failure",
    [
        ({"sw": False}, "solidworks_vba_audit"),
        ({"macro": False}, "macro_b_audit"),
        ({"prompt": False}, "security_audit"),
        ({"tool": False}, "security_audit"),
    ],
)
def test_auditor_gate_must_reject_bad_sample(bad_kw, expected_failure):
    """A single failed sub-audit must make the whole facet report FAIL."""
    result = _make_auditor(**bad_kw).run(_auditor_context())
    assert result["passed"] is False
    assert result["status"] == "FAILED"
    assert expected_failure in result["failed_checks"]
    assert result["audit_breakdown"][expected_failure] is False
    assert "100% PASS" not in result["summary"]


def test_auditor_gate_accepts_only_all_pass():
    result = _make_auditor().run(_auditor_context())
    assert result["passed"] is True
    assert result["status"] == "COMPLETED"
    assert result["failed_checks"] == []
    assert all(result["audit_breakdown"].values())
    assert "100% PASS" not in result["summary"]


# --------------------------------------------------------------------------
# 2. Internet hub: model-offline must not be reported as success
# --------------------------------------------------------------------------
class _StubSafetyFilter:
    def audit_query(self, query):
        return SimpleNamespace(
            is_safe=True,
            sanitized_text=query,
            verdict="safe",
            blocked_reasons=[],
        )


class _StubSearchEngine:
    def search(self, *args, **kwargs):
        raise AssertionError("enable_search=False must not trigger a search")


def _make_hub() -> VirtuInternetHub:
    return VirtuInternetHub(
        safety_filter=_StubSafetyFilter(),
        search_engine=_StubSearchEngine(),
        learning_pipeline=object(),
    )


class _FakeResponse:
    def __init__(self, text):
        self._text = text

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return json.dumps({"response": self._text}).encode("utf-8")


def test_internet_hub_model_offline_is_not_success(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("ollama offline")

    monkeypatch.setattr(hub_module.urllib.request, "urlopen", boom)
    res = _make_hub().query_model_with_internet(
        "virtu-test", "hello", enable_search=False, enable_deep_learning=False, timeout=0.1
    )
    assert res["success"] is False
    assert res["degraded"] is True
    assert res["reason"] and "Ollama" in res["reason"]
    assert "不是模型回答" in res["response"]


def test_internet_hub_empty_response_is_not_success(monkeypatch):
    monkeypatch.setattr(
        hub_module.urllib.request, "urlopen", lambda *a, **k: _FakeResponse("   ")
    )
    res = _make_hub().query_model_with_internet(
        "virtu-test", "hello", enable_search=False, enable_deep_learning=False, timeout=0.1
    )
    assert res["success"] is False
    assert res["degraded"] is True


def test_internet_hub_real_response_is_success(monkeypatch):
    monkeypatch.setattr(
        hub_module.urllib.request, "urlopen", lambda *a, **k: _FakeResponse("模型真实回答")
    )
    res = _make_hub().query_model_with_internet(
        "virtu-test", "hello", enable_search=False, enable_deep_learning=False, timeout=0.1
    )
    assert res["success"] is True
    assert res["degraded"] is False
    assert res["response"] == "模型真实回答"


# --------------------------------------------------------------------------
# 3. REACT mode: success must follow observed evidence
# --------------------------------------------------------------------------
class _StubSleepFramework:
    def __init__(self):
        self.calls = []

    def record_wake_step(self, **kwargs):
        self.calls.append(kwargs)


def _make_react_agent(audit_passed: bool):
    agent = VirtuSuperAgent.__new__(VirtuSuperAgent)
    agent.sleep_framework = _StubSleepFramework()
    agent._tool_registry = {
        "parse_intent": ("", lambda inp: {"parsed_spec": {"material": "Ti-6Al-4V"}}),
        "recall_hindsight_memory": ("", lambda inp: {"memories": []}),
        "generate_parametric_cad": ("", lambda inp: {"solidworks_vba": "Sub Main()"}),
        "web_verify_and_correct": ("", lambda inp: {"corrected_spec": {}, "corrections": []}),
        "verify_product_integrity": ("", lambda inp: {"verified": True, "passed": True}),
        "observe_surface": ("", lambda inp: {"evidence_status": "test_fixture"}),
        "verify_cae_stress": ("", lambda inp: {"fos": 2.0}),
        "generate_cam_toolpath": ("", lambda inp: {"macro_b_code": "G00 X0"}),
        "audit_sandbox_simulation": (
            "",
            lambda inp: {"passed": audit_passed, "summary": "stub audit"},
        ),
    }
    return agent


def test_react_fails_when_sandbox_audit_fails():
    res = _make_react_agent(audit_passed=False)._solve_react_pipeline("设计套筒")
    assert res.success is False
    assert res.metrics["audit_passed"] is False
    assert res.metrics["step_failures"], "failure evidence must be recorded"
    assert res.rcfa_report is not None


def test_react_succeeds_only_with_real_audit_pass():
    res = _make_react_agent(audit_passed=True)._solve_react_pipeline("设计套筒")
    assert res.success is True
    assert res.metrics["completed"] is True
    assert res.metrics["audit_passed"] is True
    assert res.metrics["step_failures"] == []
    assert res.metrics["react_steps"] == 10


@pytest.mark.parametrize("max_steps", [0, 1, 7, 9])
def test_react_incomplete_run_cannot_succeed(max_steps):
    res = _make_react_agent(audit_passed=True)._solve_react_pipeline("设计套筒", max_steps=max_steps)
    assert res.success is False
    assert res.metrics["completed"] is False
    assert res.metrics["react_steps"] == max_steps
    assert res.metrics["audit_passed"] is (True if max_steps == 9 else None)
    assert any("FINISH" in f["reason"] for f in res.metrics["step_failures"])


def test_react_fallback_preserves_step_budget(monkeypatch):
    agent = _make_react_agent(audit_passed=True)
    monkeypatch.setenv("VIRTU_REACT_ENGINE", "deep_agent")

    def unavailable(*args, **kwargs):
        raise RuntimeError("test model unavailable")

    monkeypatch.setattr(agent, "_solve_react_deep", unavailable)
    res = agent._solve_react("设计套筒", max_steps=1)
    assert res.success is False
    assert res.metrics["react_steps"] == 1
    assert res.metrics["completed"] is False
    assert res.metrics["engine"] == "pipeline_fallback"


def test_react_keeps_explicit_missing_mesh_instead_of_substituting_sample(tmp_path):
    agent = _make_react_agent(audit_passed=True)
    missing_mesh = str(tmp_path / "missing-product.stl")
    agent._tool_registry["generate_parametric_cad"] = ("", lambda inp: {"geometry_mesh": missing_mesh})
    observed = []

    def reject_missing_mesh(evidence):
        observed.append(evidence["geometry_mesh"])
        return {"passed": False, "verified": True, "circuit_breaker": True,
                "failures": ["missing product mesh"]}

    agent._tool_registry["verify_product_integrity"] = ("", reject_missing_mesh)
    res = agent._solve_react_pipeline("设计套筒")
    assert observed == [missing_mesh]
    assert res.success is False
    assert "generate_cam_toolpath" not in res.artifacts


# --------------------------------------------------------------------------
# 4. Static regression guards: hard-coded pass literals must stay gone
# --------------------------------------------------------------------------
def test_no_hardcoded_verdict_literals():
    team = (ROOT / "virtu_omni/agent/agent_team.py").read_text(encoding="utf-8")
    auditor_body = team.split("class AuditorAndSandboxAgent")[1].split(
        "class EvolutionAndMemoryAgent"
    )[0]
    assert '"passed": True,' not in auditor_body

    hub = (ROOT / "virtu_omni/internet/internet_hub.py").read_text(encoding="utf-8")
    query_body = hub.split("def query_model_with_internet")[1].split("\n    def ")[0]
    assert '"success": True,' not in query_body

    agent = (ROOT / "virtu_omni/agent/super_agent.py").read_text(encoding="utf-8")
    react_body = agent.split("def _solve_react")[1].split("\n    def ")[0]
    assert "success=True," not in react_body
