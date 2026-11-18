# -*- coding: utf-8 -*-
"""P1 runtime governance: fault-injection / counter-evidence tests.

No real network, no Ollama, no services. Every transport is monkeypatched with
a fake. These tests assert the FAILURE behaviour of the hardened components.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import threading
import types
import urllib.error
import urllib.request

import pytest

# bs4 is not installed in the project venv; search_engine imports it at module
# load. Provide a minimal inert stub ONLY when it is genuinely missing.
try:
    import bs4  # noqa: F401
except ImportError:
    _bs4 = types.ModuleType("bs4")

    class _Soup:
        def __init__(self, *a, **k):
            pass

        def __call__(self, *a, **k):
            return []

        def find_all(self, *a, **k):
            return []

        def find(self, *a, **k):
            return None

        def get_text(self, *a, **k):
            return ""

        @property
        def title(self):
            return None

    _bs4.BeautifulSoup = _Soup
    sys.modules["bs4"] = _bs4

import virtu_omni.runtime.llm_gateway as gw
import virtu_omni.runtime.trace as tr
import virtu_omni.internet.search_engine as se
import virtu_omni.context_mode.optimizer as opt


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _cfg(**overrides):
    base = dict(
        endpoint="http://fake.invalid",
        default_model="m",
        timeout=1.0,
        max_retries=2,
        backoff_base=0.05,
        backoff_max=2.0,
        jitter=0.0,
        max_concurrency=2,
        breaker_threshold=3,
        breaker_cooldown=10.0,
        api_key="",
    )
    base.update(overrides)
    return gw.GatewayConfig(**base)


class _Recorder:
    """Fake transport: a scripted list of (status, body) or Exception."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, payload, headers, timeout):
        self.calls.append({"url": url, "headers": dict(headers), "timeout": timeout})
        item = self.responses.pop(0) if self.responses else (200, b'{"ok": true}')
        if isinstance(item, Exception):
            raise item
        return item


class _FakeFilterResult:
    def __init__(self, text):
        self.is_safe = True
        self.sanitized_text = text
        self.blocked_reasons = []
        self.pii_redacted_count = 0


class _FakeSafetyFilter:
    def filter_web_content(self, text, title="", url=""):
        return _FakeFilterResult(text)

    def audit_query(self, query):
        return _FakeFilterResult(query)


# ---------------------------------------------------------------------------
# 1. gateway: schema / 4xx never retried
# ---------------------------------------------------------------------------
def test_schema_error_no_retry():
    rec = _Recorder([(200, b'{"ok": true}')])
    g = gw.LLMGateway(_cfg(), sleep_fn=lambda s: None)
    g._send = rec
    # request schema violation: no transport call at all
    r = g.chat([])
    assert r["success"] is False
    assert r["degraded"] is True
    assert r["reason"]
    assert len(rec.calls) == 0

    # response schema violation: exactly one call, never retried
    rec2 = _Recorder([(200, b'[1, 2, 3]'), (200, b'{"ok": true}')])
    g2 = gw.LLMGateway(_cfg(), sleep_fn=lambda s: None)
    g2._send = rec2
    r2 = g2.chat([{"role": "user", "content": "hi"}])
    assert r2["success"] is False
    assert r2["error_kind"] == "schema_error"
    assert len(rec2.calls) == 1


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
def test_4xx_no_retry(status):
    rec = _Recorder([(status, b'{"error":"x"}'), (200, b'{"ok":true}')])
    g = gw.LLMGateway(_cfg(), sleep_fn=lambda s: None)
    g._send = rec
    r = g.chat([{"role": "user", "content": "hi"}])
    assert r["success"] is False
    assert r["degraded"] is True
    assert r["error_kind"] in ("auth_error", "client_error")
    assert len(rec.calls) == 1  # 4xx is never retried


# ---------------------------------------------------------------------------
# 2. gateway: 5xx retries with exponential backoff + jitter policy
# ---------------------------------------------------------------------------
def test_5xx_retries_with_backoff():
    sleeps = []
    rec = _Recorder([(500, b'{}'), (500, b'{}'), (200, b'{"ok": true}')])
    g = gw.LLMGateway(_cfg(max_retries=2, backoff_base=0.05, jitter=0.0),
                      sleep_fn=lambda s: sleeps.append(s))
    g._send = rec
    r = g.chat([{"role": "user", "content": "hi"}])
    assert r["success"] is True
    assert len(rec.calls) == 3
    assert sleeps == [0.05, 0.1]  # exponential backoff (jitter disabled here)


def test_5xx_exhausted_is_degraded_failure():
    sleeps = []
    rec = _Recorder([(500, b'{}')] * 3)
    g = gw.LLMGateway(_cfg(max_retries=2), sleep_fn=lambda s: sleeps.append(s))
    g._send = rec
    r = g.chat([{"role": "user", "content": "hi"}])
    assert r["success"] is False
    assert r["degraded"] is True
    assert r["error_kind"] == "server_error"
    assert len(rec.calls) == 3
    assert len(sleeps) == 2


def test_timeout_is_retryable():
    rec = _Recorder([TimeoutError("boom"), (200, b'{"ok":true}')])
    g = gw.LLMGateway(_cfg(max_retries=1), sleep_fn=lambda s: None)
    g._send = rec
    r = g.generate("hi")
    assert r["success"] is True
    assert len(rec.calls) == 2


def test_jitter_is_applied():
    sleeps = []
    rec = _Recorder([(500, b'{}'), (200, b'{"ok":true}')])
    g = gw.LLMGateway(_cfg(max_retries=1, backoff_base=0.05, jitter=0.01),
                      sleep_fn=lambda s: sleeps.append(s))
    g._send = rec
    r = g.generate("hi")
    assert r["success"] is True
    assert 0.05 <= sleeps[0] <= 0.06


# ---------------------------------------------------------------------------
# 3. gateway: circuit breaker fail-fast + half-open recovery
# ---------------------------------------------------------------------------
def test_circuit_open_fail_fast():
    rec = _Recorder([(500, b'{}')] * 10)
    g = gw.LLMGateway(_cfg(max_retries=0, breaker_threshold=2, breaker_cooldown=100.0),
                      sleep_fn=lambda s: None)
    g._send = rec
    assert g.chat([{"role": "user", "content": "hi"}])["success"] is False
    assert g.chat([{"role": "user", "content": "hi"}])["success"] is False
    before = len(rec.calls)
    r3 = g.chat([{"role": "user", "content": "hi"}])
    assert r3["success"] is False
    assert r3["error_kind"] == "circuit_open"
    assert "circuit" in r3["reason"].lower()
    assert len(rec.calls) == before  # fail fast: no transport call


def test_circuit_half_open_then_close():
    now = [0.0]

    def clock():
        return now[0]

    rec = _Recorder([(500, b'{}'), (200, b'{"ok":true}')])
    g = gw.LLMGateway(_cfg(max_retries=0, breaker_threshold=1, breaker_cooldown=5.0),
                      sleep_fn=lambda s: None, clock=clock)
    g._send = rec
    assert g.chat([{"role": "user", "content": "hi"}])["success"] is False
    assert g._breaker.state == "open"
    now[0] = 6.0  # past cooldown -> half-open probe
    assert g.chat([{"role": "user", "content": "hi"}])["success"] is True
    assert g._breaker.state == "closed"


# ---------------------------------------------------------------------------
# 4. gateway: concurrency cap
# ---------------------------------------------------------------------------
def test_concurrency_cap():
    limit = 2
    lock = threading.Lock()
    state = {"inflight": 0, "max": 0}

    def fake_send(url, payload, headers, timeout):
        with lock:
            state["inflight"] += 1
            state["max"] = max(state["max"], state["inflight"])
        try:
            threading.Event().wait(0.02)  # force overlap, no real network
            return 200, b'{"ok": true}'
        finally:
            with lock:
                state["inflight"] -= 1

    g = gw.LLMGateway(_cfg(max_concurrency=limit, breaker_threshold=999),
                      sleep_fn=lambda s: None)
    g._send = fake_send
    results = []
    threads = [threading.Thread(target=lambda: results.append(g.generate("hi")))
               for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(results) == 8
    assert all(r["success"] is True for r in results)
    assert state["max"] <= limit
    assert state["max"] >= 2  # concurrency was actually exercised


# ---------------------------------------------------------------------------
# 5. gateway: EVERY failure body is success=False + degraded + reason
# ---------------------------------------------------------------------------
def test_all_failure_shapes():
    cases = []
    # schema
    g = gw.LLMGateway(_cfg(), sleep_fn=lambda s: None)
    g._send = _Recorder([(200, b'{"ok":true}')])
    cases.append(g.chat([]))
    # 4xx
    g = gw.LLMGateway(_cfg(), sleep_fn=lambda s: None)
    g._send = _Recorder([(403, b'{}')])
    cases.append(g.chat([{"role": "user", "content": "hi"}]))
    # 5xx exhausted
    g = gw.LLMGateway(_cfg(max_retries=1), sleep_fn=lambda s: None)
    g._send = _Recorder([(500, b'{}'), (500, b'{}')])
    cases.append(g.generate("hi"))
    # bad JSON
    g = gw.LLMGateway(_cfg(), sleep_fn=lambda s: None)
    g._send = _Recorder([(200, b'not-json')])
    cases.append(g.embed("x"))
    # network timeout exhausted
    g = gw.LLMGateway(_cfg(max_retries=0), sleep_fn=lambda s: None)
    g._send = _Recorder([TimeoutError("x")])
    cases.append(g.embed("x"))
    # circuit open
    g = gw.LLMGateway(_cfg(max_retries=0, breaker_threshold=1, breaker_cooldown=999),
                      sleep_fn=lambda s: None)
    g._send = _Recorder([(500, b'{}')])
    g.chat([{"role": "user", "content": "hi"}])
    cases.append(g.chat([{"role": "user", "content": "hi"}]))

    for r in cases:
        assert r["success"] is False
        assert r["degraded"] is True
        assert r["reason"]
        assert r["data"] == {}


# ---------------------------------------------------------------------------
# 6. gateway: trace headers + optional tracing + from_env
# ---------------------------------------------------------------------------
def test_trace_headers_and_optional_trace(monkeypatch):
    rec = _Recorder([(200, b'{"ok":true}')])
    g = gw.LLMGateway(_cfg(), sleep_fn=lambda s: None)
    g._send = rec
    h = tr.start_run(run_id="run-abc")
    assert g.chat([{"role": "user", "content": "hi"}])["success"] is True
    assert rec.calls[0]["headers"].get("X-Virtu-Run-Id") == "run-abc"
    h.close()

    # trace module missing -> must not crash
    monkeypatch.setattr(gw, "_trace_mod", None)
    g2 = gw.LLMGateway(_cfg(), sleep_fn=lambda s: None)
    g2._send = _Recorder([(200, b'{"ok":true}')])
    assert g2.generate("hi")["success"] is True

    # trace module present but broken -> still must not crash
    class _Broken:
        def inject_headers(self):
            raise RuntimeError("trace down")

    monkeypatch.setattr(gw, "_trace_mod", _Broken())
    g3 = gw.LLMGateway(_cfg(), sleep_fn=lambda s: None)
    g3._send = _Recorder([(200, b'{"ok":true}')])
    assert g3.embed("x")["success"] is True


def test_gateway_from_env():
    env = {
        "VIRTU_LLM_ENDPOINT": "http://example.invalid:9",
        "VIRTU_LLM_TIMEOUT": "7",
        "VIRTU_LLM_MAX_RETRIES": "4",
        "VIRTU_LLM_MAX_CONCURRENCY": "3",
    }
    g = gw.LLMGateway.from_env(env)
    assert g.config.endpoint == "http://example.invalid:9"
    assert g.config.timeout == 7.0 and isinstance(g.config.timeout, float)
    assert g.config.max_retries == 4
    assert g.config.max_concurrency == 3


# ---------------------------------------------------------------------------
# 7. SSRF guard
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("url", [
    "http://127.0.0.1:11434/api/tags",
    "http://169.254.169.254/",
    "http://10.0.0.5/",
    "http://192.168.1.10/",
    "http://localhost/",
    "ftp://example.com/",
    "http://example.com:8080/",
])
def test_ssrf_blocked(monkeypatch, url):
    opened = []
    monkeypatch.setattr(se, "_open_and_read",
                        lambda u, h, t: opened.append(u) or "<html></html>")
    eng = se.WebSearchEngine(safety_filter=_FakeSafetyFilter(), enable_cache=False)
    res = eng.fetch_web_content(url)
    assert res["success"] is False
    assert res["error"] and "SSRF guard" in res["error"]
    assert opened == []  # rejected before ANY network I/O


def test_ssrf_dns_private_rejected(monkeypatch):
    monkeypatch.setattr(se.socket, "getaddrinfo",
                        lambda h, p, proto=0: [(2, 1, 6, "", ("10.0.0.7", p))])
    with pytest.raises(se.UnsafeFetchURLError):
        se._validate_fetch_url("http://example.com/")


def test_ssrf_public_literal_allowed(monkeypatch):
    se._validate_fetch_url("http://93.184.216.34/")  # public IP literal: OK
    seen = {}

    def fake_open(u, h, t):
        seen["u"] = u
        seen["timeout"] = t
        return "<html><body><p>hello world content here</p></body></html>"

    monkeypatch.setattr(se, "_open_and_read", fake_open)
    eng = se.WebSearchEngine(safety_filter=_FakeSafetyFilter(),
                             enable_cache=False, timeout=3.0)
    res = eng.fetch_web_content("http://93.184.216.34/")
    assert res["success"] is True
    assert seen["u"] == "http://93.184.216.34/"
    assert seen["timeout"] == 3.0  # caller timeout preserved


def test_no_redirect_handler():
    handler = se._NoRedirectHandler()
    req = urllib.request.Request("http://93.184.216.34/")
    with pytest.raises(urllib.error.HTTPError):
        # a redirect to a loopback target must be denied, not followed
        handler.redirect_request(req, None, 302, "Found", {}, "http://127.0.0.1/")


# ---------------------------------------------------------------------------
# 8. optimizer: shell metachars / allowlist / restricted exec
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("command", [
    "echo hi" + chr(59) + " echo bye",
    "echo hi && echo bye",
    "echo hi | findstr x",
    "echo `whoami`",
    "echo $(whoami)",
    "echo hi > out.txt",
    "notepad.exe foo.txt",
])
def test_shell_metachars_and_allowlist_rejected(command):
    o = opt.ContextModeOptimizer()
    res = o.execute_sandboxed(command)
    assert res.ok is False
    assert res.error and "rejected by sandbox" in res.error
    assert res.output == ""  # no silent fallback output


def test_echo_still_works():
    o = opt.ContextModeOptimizer()
    res = o.execute_sandboxed("echo Sandboxed Output")
    assert res.ok is True
    assert "Sandboxed Output" in res.output


@pytest.mark.parametrize("script", [
    "import os; output = os.getcwd()",
    "output = open('/etc/passwd').read()",
    "output = __import__('os').getcwd()",
    "output = eval('1+1')",
    "output = str([].__class__.__mro__)",
])
def test_filter_script_ast_blocked(script):
    o = opt.ContextModeOptimizer()
    res = o.execute_sandboxed("echo hello", filter_script=script)
    assert res.ok is False
    assert res.error and "rejected by sandbox" in res.error
    assert res.output == ""


def test_filter_script_legal_still_works():
    o = opt.ContextModeOptimizer()
    res = o.execute_sandboxed("echo hello", filter_script='output = " | ".join(lines[:3])')
    assert res.ok is True
    assert res.filter_applied == "custom_filter_script"


# ---------------------------------------------------------------------------
# 9. trace: contextvars, four stages, env/header propagation, stderr on log fail
# ---------------------------------------------------------------------------
def test_four_stages():
    assert tr.STAGES == (tr.THOUGHT, tr.ACTION, tr.OBSERVATION, tr.VERIFICATION)


def test_trace_env_roundtrip():
    h = tr.start_run(run_id="run-xyz", trace_id="trace-xyz")
    with tr.span(tr.ACTION) as sp:
        env = tr.inject_env({})  # clean env, like a child process would receive
        assert env["VIRTU_RUN_ID"] == "run-xyz"
        assert env["VIRTU_TRACE_ID"] == "trace-xyz"
        assert env["VIRTU_SPAN_ID"] == sp.span_id
        child = tr.from_env(env)
        assert tr.get_run_id() == "run-xyz"
        assert tr.get_trace_id() == "trace-xyz"
        assert tr.get_span_id() == sp.span_id
        assert tr.get_parent_span_id() == ""
        child.close()
    h.close()


def test_trace_headers_roundtrip():
    h = tr.start_run(run_id="run-hdr")
    with tr.span(tr.OBSERVATION) as sp:
        headers = tr.inject_headers({"Content-Type": "application/json"})
        assert headers["X-Virtu-Run-Id"] == "run-hdr"
        assert headers["X-Virtu-Span-Id"] == sp.span_id
        assert headers["Content-Type"] == "application/json"
        lowered = {k.lower(): v for k, v in headers.items()}
    child = tr.from_headers(lowered)  # case-insensitive
    assert tr.get_run_id() == "run-hdr"
    assert tr.get_span_id() == sp.span_id
    child.close()
    h.close()


def test_trace_env_cross_process():
    """A real child process must see exactly the injected trace context."""
    h = tr.start_run(run_id="run-cross", trace_id="trace-cross")
    with tr.span(tr.VERIFICATION) as sp:
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith("VIRTU_")}
        env = tr.inject_env(clean_env)
        code = (
            "import os,json; "
            "print(json.dumps({k: os.environ.get(k) for k in "
            "['VIRTU_TRACE_ID','VIRTU_RUN_ID','VIRTU_SPAN_ID','VIRTU_PARENT_SPAN_ID']}))"
        )
        proc = subprocess.run([sys.executable, "-c", code], env=env,
                              capture_output=True, text=True, timeout=30)
        assert proc.returncode == 0, proc.stderr
        payload = json.loads(proc.stdout.strip().splitlines()[-1])
        assert payload["VIRTU_RUN_ID"] == "run-cross"
        assert payload["VIRTU_TRACE_ID"] == "trace-cross"
        assert payload["VIRTU_SPAN_ID"] == sp.span_id
        child = tr.from_env(payload)
        assert tr.get_run_id() == "run-cross"
        assert tr.get_span_id() == sp.span_id
        child.close()
    h.close()


def test_trace_log_failure_reports_stderr(monkeypatch, tmp_path):
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("x", encoding="utf-8")
    # LOG_PATH.parent is now a regular file -> open() must fail.
    monkeypatch.setattr(tr, "LOG_PATH", blocker / "events.jsonl")
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stderr", buf)
    rec = tr.emit(tr.VERIFICATION, "test.event", status="ok")  # must not raise
    assert set(tr._REQUIRED_FIELDS).issubset(rec.keys())
    assert "failed to persist event" in buf.getvalue()  # explicit, not silent
