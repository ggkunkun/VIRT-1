"""Offline security tests for the local Router HTTP API.

The tests bind only to an ephemeral loopback port and replace model calls with
mocks; they never start Ollama or contact another service.
"""

from __future__ import annotations

import http.client
import json
import threading
from contextlib import contextmanager

import pytest

from scripts.router import router_server as router

TOKEN = "router-test-token-" + "x" * 48


@contextmanager
def running_server():
    server = router.BoundedThreadingHTTPServer(("127.0.0.1", 0), router.make_handler())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def request(port, method, path, payload=None, token=TOKEN, headers=None):
    # 超时不要压得太紧：整轮测试并发跑时，3s 会让客户端先断连，
    # 服务端随后的写回变成 ConnectionAbortedError（表现为假失败），
    # 与本测试要验证的鉴权/容量语义无关。
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    body = None
    req_headers = dict(headers or {})
    if payload is not None:
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
    if token is not None:
        req_headers["Authorization"] = f"Bearer {token}"
    try:
        conn.request(method, path, body=body, headers=req_headers)
        response = conn.getresponse()
        raw = response.read()
        try:
            data = json.loads(raw.decode("utf-8")) if raw else None
        except (UnicodeDecodeError, json.JSONDecodeError):
            data = raw
        return response.status, data
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def router_token(monkeypatch):
    monkeypatch.setattr(router, "_ROUTER_TOKEN", TOKEN)


def test_all_get_and_post_routes_require_bearer_before_work():
    with running_server() as port:
        for path in ("/", "/health", "/stats", "/help"):
            status, data = request(port, "GET", path, token=None)
            assert status == 401
            assert "router-test-token" not in json.dumps(data)
        for path in ("/route", "/ask"):
            status, data = request(port, "POST", path, {"prompt": "no auth"}, token="wrong")
            assert status == 401
            assert data["error"] == "Valid Bearer token required"


def test_valid_bearer_route_uses_only_the_mock(monkeypatch):
    called = []
    monkeypatch.setattr(router.R, "route", lambda prompt: called.append(prompt) or {"prompt": prompt})
    with running_server() as port:
        status, data = request(port, "POST", "/route", {"prompt": "hello"})
    assert status == 200
    assert data == {"prompt": "hello"}
    assert called == ["hello"]


def test_router_rejects_oversized_body_and_prompt_before_backend(monkeypatch):
    monkeypatch.setattr(router, "MAX_BODY_BYTES", 64)
    monkeypatch.setattr(router, "MAX_PROMPT_CHARS", 8)
    called = []
    monkeypatch.setattr(router.R, "route", lambda prompt: called.append(prompt) or {})
    with running_server() as port:
        status, _ = request(port, "POST", "/route", b"x" * 65)
        assert status == 413
        status, _ = request(port, "POST", "/route", {"prompt": "123456789"})
        assert status == 413
    assert called == []


@pytest.mark.parametrize("max_tokens", [0, -1, 4097, True, "12"])
def test_router_rejects_invalid_generation_budget(monkeypatch, max_tokens):
    called = []
    monkeypatch.setattr(router.R, "ask", lambda *a, **k: called.append((a, k)) or {})
    with running_server() as port:
        status, _ = request(port, "POST", "/ask", {"prompt": "hello", "max_tokens": max_tokens})
    assert status == 400
    assert called == []


def test_router_rejects_malformed_json_and_non_object(monkeypatch):
    with running_server() as port:
        status, _ = request(port, "POST", "/route", b"{bad")
        assert status == 400
        status, _ = request(port, "POST", "/route", b"[]")
        assert status == 400
        status, _ = request(port, "POST", "/route", b"{}", headers={"Content-Type": "text/plain"})
        assert status == 415


def test_router_busy_is_rejected_and_capacity_recovers(monkeypatch):
    entered = threading.Event()
    release = threading.Event()
    calls = []

    def blocked_ask(prompt, max_tokens):
        calls.append(prompt)
        entered.set()
        assert release.wait(timeout=3)
        return {
            "decision": {"target": "mock", "kind": "FAST(dense)", "basis": "test",
                         "margin": 0, "kw_hits": [], "reason": "mock"},
            "model": "mock", "response": "ok", "tok_s": 1, "eval_count": 1,
            "elapsed_s": 0.1,
        }

    monkeypatch.setattr(router, "MAX_CONCURRENT", 1)
    monkeypatch.setattr(router, "sem", threading.BoundedSemaphore(1))
    monkeypatch.setattr(router.R, "ask", blocked_ask)
    monkeypatch.setattr(router.R, "route", lambda prompt: {"prompt": prompt})
    with running_server() as port:
        first_result = []
        first = threading.Thread(
            target=lambda: first_result.append(request(port, "POST", "/ask", {"prompt": "first"})),
            daemon=True,
        )
        first.start()
        assert entered.wait(timeout=2)
        status, data = request(port, "POST", "/route", {"prompt": "second"})
        assert status == 503
        assert data["error"] == "router is busy; retry later"
        release.set()
        first.join(timeout=3)
        assert not first.is_alive()
        assert first_result[0][0] == 200
        status, data = request(port, "POST", "/route", {"prompt": "after"})
        assert status == 200
        assert data == {"prompt": "after"}
    assert calls == ["first"]


def test_http_worker_capacity_is_bounded(monkeypatch):
    entered = threading.Event()
    release = threading.Event()
    monkeypatch.setattr(router, "MAX_HTTP_WORKERS", 1)
    monkeypatch.setattr(router, "MAX_CONCURRENT", 1)
    monkeypatch.setattr(router, "sem", threading.BoundedSemaphore(1))
    monkeypatch.setattr(router.R, "route", lambda prompt: entered.set() or release.wait(timeout=3) or {"ok": True})
    with running_server() as port:
        first_result = []
        first = threading.Thread(
            target=lambda: first_result.append(request(port, "POST", "/route", {"prompt": "first"})),
            daemon=True,
        )
        first.start()
        assert entered.wait(timeout=2)
        status, _ = request(port, "GET", "/help")
        assert status == 503
        release.set()
        first.join(timeout=3)
        assert not first.is_alive()
        assert first_result[0][0] == 200
