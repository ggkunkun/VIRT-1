# -*- coding: utf-8 -*-
"""Unified LLM gateway for the Virtu runtime (P1 runtime governance).

Exposes three primitives -- ``chat`` / ``generate`` / ``embed`` -- with:

  * configurable endpoint / timeout / retry count,
  * exponential backoff + jitter,
  * error-type-aware retry policy (schema / auth / 4xx NEVER retried;
    network timeouts and 5xx ARE retried),
  * a circuit breaker (consecutive failures -> open -> cooldown -> half-open
    -> close on success) with fail-fast while open,
  * a concurrency cap (Semaphore),
  * pydantic (v2) validation of requests and responses,
  * a single ``GatewayError`` hierarchy,
  * trace-context injection from ``virtu_omni.runtime.trace`` (optional).

Hard invariant: every failure response has ``success is False`` and carries
``degraded=True`` plus a non-empty ``reason``. There is NO degraded body with
``success=True``.
"""

from __future__ import annotations

import json
import os
import random
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, RootModel, ValidationError

# Optional trace module: the gateway must work even when tracing is unavailable.
try:
    from virtu_omni.runtime import trace as _trace_mod
except Exception:  # noqa: BLE001 - tracing is strictly optional
    _trace_mod = None


# ---------------------------------------------------------------------------
# Unified error taxonomy
# ---------------------------------------------------------------------------
class GatewayError(Exception):
    kind = "gateway_error"
    retryable = False

    def __init__(self, reason: str, *, status: Optional[int] = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status


class SchemaError(GatewayError):
    """Request/response schema violation -- never retried."""
    kind = "schema_error"
    retryable = False


class AuthError(GatewayError):
    """401 / 403 -- never retried."""
    kind = "auth_error"
    retryable = False


class ClientError(GatewayError):
    """Other 4xx / unexpected 3xx -- never retried."""
    kind = "client_error"
    retryable = False


class NetworkError(GatewayError):
    """Timeout / connection failure -- retried."""
    kind = "network_error"
    retryable = True


class ServerError(GatewayError):
    """5xx -- retried."""
    kind = "server_error"
    retryable = True


class CircuitOpenError(GatewayError):
    """Circuit breaker open -- fail fast, never retried."""
    kind = "circuit_open"
    retryable = False


# ---------------------------------------------------------------------------
# pydantic request / response models
# ---------------------------------------------------------------------------
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    model: str = Field(min_length=1)
    messages: List[ChatMessage] = Field(min_length=1)
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: bool = False


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    model: str = Field(min_length=1)
    prompt: str
    stream: bool = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class EmbedRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    model: str = Field(min_length=1)
    input: Union[str, List[str]]


class UpstreamPayload(RootModel[Dict[str, Any]]):
    """An upstream response must at minimum be a JSON object."""


class GatewayResult(BaseModel):
    """Unified gateway result. ``success`` is mandatory (no implicit default)."""
    model_config = ConfigDict(extra="allow")
    success: bool
    degraded: bool = False
    reason: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    attempts: int = 0
    latency_ms: float = 0.0
    error_kind: Optional[str] = None


def _failure(reason: str, *, error_kind: str, attempts: int, latency_ms: float) -> Dict[str, Any]:
    """Build a degraded failure response. success=False is hard-coded here."""
    return GatewayResult(
        success=False,
        degraded=True,
        reason=reason or "unspecified gateway failure",
        data={},
        attempts=attempts,
        latency_ms=latency_ms,
        error_kind=error_kind,
    ).model_dump()


def _success(data: Dict[str, Any], *, attempts: int, latency_ms: float) -> Dict[str, Any]:
    return GatewayResult(
        success=True,
        degraded=False,
        reason=None,
        data=data,
        attempts=attempts,
        latency_ms=latency_ms,
        error_kind=None,
    ).model_dump()


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
@dataclass
class GatewayConfig:
    endpoint: str = "http://127.0.0.1:11434"
    default_model: str = "virtu-omni"
    timeout: float = 30.0
    max_retries: int = 2
    backoff_base: float = 0.05
    backoff_max: float = 2.0
    jitter: float = 0.01
    max_concurrency: int = 4
    breaker_threshold: int = 3
    breaker_cooldown: float = 1.0
    api_key: str = ""


_ENV_KEYS = {
    "endpoint": "VIRTU_LLM_ENDPOINT",
    "default_model": "VIRTU_LLM_MODEL",
    "timeout": "VIRTU_LLM_TIMEOUT",
    "max_retries": "VIRTU_LLM_MAX_RETRIES",
    "backoff_base": "VIRTU_LLM_BACKOFF_BASE",
    "backoff_max": "VIRTU_LLM_BACKOFF_MAX",
    "jitter": "VIRTU_LLM_JITTER",
    "max_concurrency": "VIRTU_LLM_MAX_CONCURRENCY",
    "breaker_threshold": "VIRTU_LLM_BREAKER_THRESHOLD",
    "breaker_cooldown": "VIRTU_LLM_BREAKER_COOLDOWN",
    "api_key": "VIRTU_LLM_API_KEY",
}


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------
class CircuitBreaker:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, threshold: int, cooldown: float, clock=None) -> None:
        self.threshold = max(1, int(threshold))
        self.cooldown = float(cooldown)
        self._clock = clock or time.monotonic
        self._lock = threading.Lock()
        self._state = self.CLOSED
        self._failures = 0
        self._opened_at = 0.0

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    def before_call(self) -> None:
        with self._lock:
            if self._state == self.OPEN:
                if self._clock() - self._opened_at >= self.cooldown:
                    self._state = self.HALF_OPEN
                    return
                raise CircuitOpenError("circuit breaker is open; failing fast")

    def record_success(self) -> None:
        with self._lock:
            self._state = self.CLOSED
            self._failures = 0

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._state == self.HALF_OPEN or self._failures >= self.threshold:
                self._state = self.OPEN
                self._opened_at = self._clock()


# ---------------------------------------------------------------------------
# Gateway
# ---------------------------------------------------------------------------
class LLMGateway:
    """Single entry point for all local/upstream LLM traffic."""

    def __init__(
        self,
        config: Optional[GatewayConfig] = None,
        *,
        sleep_fn=None,
        clock=None,
        rng=None,
    ) -> None:
        self.config = config or GatewayConfig()
        self._semaphore = threading.Semaphore(max(1, int(self.config.max_concurrency)))
        self._breaker = CircuitBreaker(
            self.config.breaker_threshold, self.config.breaker_cooldown, clock=clock
        )
        self._sleep = sleep_fn or time.sleep
        self._rng = rng or random

    @classmethod
    def from_env(cls, env: Optional[Dict[str, str]] = None, **overrides: Any) -> "LLMGateway":
        """Build a gateway from environment variables (with optional overrides)."""
        src = os.environ if env is None else env
        defaults = GatewayConfig()
        values: Dict[str, Any] = {}
        for field_name, env_key in _ENV_KEYS.items():
            if env_key not in src:
                continue
            raw = src[env_key]
            current_value = getattr(defaults, field_name)
            try:
                values[field_name] = type(current_value)(raw)
            except (TypeError, ValueError):
                values[field_name] = raw
        values.update(overrides)
        return cls(config=GatewayConfig(**values))

    # -- public primitives ---------------------------------------------------
    def chat(self, messages, *, model=None, temperature=None, max_tokens=None,
             stream=False, **opts) -> Dict[str, Any]:
        try:
            req = ChatRequest(
                model=model or self.config.default_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
                **opts,
            )
        except ValidationError as exc:
            return _failure(f"request schema violation: {exc}",
                            error_kind="schema_error", attempts=0, latency_ms=0.0)
        return self._execute(req, "/v1/chat/completions")

    def generate(self, prompt, *, model=None, **opts) -> Dict[str, Any]:
        try:
            req = GenerateRequest(model=model or self.config.default_model, prompt=prompt, **opts)
        except ValidationError as exc:
            return _failure(f"request schema violation: {exc}",
                            error_kind="schema_error", attempts=0, latency_ms=0.0)
        return self._execute(req, "/api/generate")

    def embed(self, input_, *, model=None, **opts) -> Dict[str, Any]:
        try:
            req = EmbedRequest(model=model or self.config.default_model, input=input_, **opts)
        except ValidationError as exc:
            return _failure(f"request schema violation: {exc}",
                            error_kind="schema_error", attempts=0, latency_ms=0.0)
        return self._execute(req, "/api/embed")

    # -- internals -----------------------------------------------------------
    def _build_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        headers.update(self._trace_headers())
        return headers

    def _trace_headers(self) -> Dict[str, str]:
        if _trace_mod is None:
            return {}
        try:
            return dict(_trace_mod.inject_headers())
        except Exception as exc:  # noqa: BLE001 - tracing must never break a call
            print(
                f"[virtu.runtime.llm_gateway] trace headers unavailable: "
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            return {}

    def _backoff(self, attempt: int) -> float:
        base = min(self.config.backoff_base * (2 ** (attempt - 1)), self.config.backoff_max)
        jitter = self._rng.uniform(0.0, self.config.jitter) if self.config.jitter > 0 else 0.0
        return base + jitter

    def _send(self, url: str, payload: bytes, headers: Dict[str, str], timeout: float):
        """Default transport. Returns ``(status, body_bytes)``."""
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, (exc.read() or b"")

    def _parse_response(self, status: int, body: bytes) -> Dict[str, Any]:
        if status in (401, 403, 407):
            raise AuthError(f"authentication/authorization failed: HTTP {status}", status=status)
        if 400 <= status < 500:
            raise ClientError(f"client error (non-retryable): HTTP {status}", status=status)
        if 500 <= status < 600:
            raise ServerError(f"server error (retryable): HTTP {status}", status=status)
        if status >= 300:
            raise ClientError(f"unexpected status (non-retryable): HTTP {status}", status=status)
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SchemaError(f"response is not valid JSON: {exc}")
        try:
            validated = UpstreamPayload.model_validate(payload)
        except ValidationError as exc:
            raise SchemaError(f"response schema violation: {exc}")
        return validated.root

    def _execute(self, req: BaseModel, path: str) -> Dict[str, Any]:
        started = time.perf_counter()
        url = self.config.endpoint.rstrip("/") + path
        payload = json.dumps(req.model_dump(exclude_none=True), ensure_ascii=False).encode("utf-8")
        headers = self._build_headers()
        attempts = 0
        total_attempts = max(0, int(self.config.max_retries)) + 1

        def _elapsed() -> float:
            return (time.perf_counter() - started) * 1000.0

        for attempt in range(1, total_attempts + 1):
            try:
                self._breaker.before_call()
            except CircuitOpenError as exc:
                return _failure(exc.reason, error_kind=exc.kind,
                                attempts=attempts, latency_ms=_elapsed())
            attempts = attempt
            try:
                with self._semaphore:
                    status, body = self._send(url, payload, headers, self.config.timeout)
                data = self._parse_response(status, body)
            except GatewayError as exc:
                if exc.retryable and attempt <= self.config.max_retries:
                    self._sleep(self._backoff(attempt))
                    continue
                self._breaker.record_failure()
                return _failure(exc.reason, error_kind=exc.kind,
                                attempts=attempts, latency_ms=_elapsed())
            except (TimeoutError, urllib.error.URLError, OSError) as exc:
                reason = f"network/timeout error: {type(exc).__name__}: {exc}"
                if attempt <= self.config.max_retries:
                    self._sleep(self._backoff(attempt))
                    continue
                self._breaker.record_failure()
                return _failure(reason, error_kind="network_error",
                                attempts=attempts, latency_ms=_elapsed())
            except Exception as exc:  # noqa: BLE001 - unknown transport failure -> classified
                reason = f"unexpected transport error: {type(exc).__name__}: {exc}"
                if attempt <= self.config.max_retries:
                    self._sleep(self._backoff(attempt))
                    continue
                self._breaker.record_failure()
                return _failure(reason, error_kind="network_error",
                                attempts=attempts, latency_ms=_elapsed())
            else:
                self._breaker.record_success()
                return _success(data, attempts=attempts, latency_ms=_elapsed())

        # Defensive: the loop always returns; this is unreachable in practice.
        return _failure("retry loop exhausted", error_kind="gateway_error",
                        attempts=attempts, latency_ms=_elapsed())
