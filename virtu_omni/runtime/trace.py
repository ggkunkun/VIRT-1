# -*- coding: utf-8 -*-
"""Virtu P1 runtime governance: structured tracing with cross-boundary propagation.

Provides contextvars-based ``trace_id / run_id / span_id / parent_span_id``,
four explicit lifecycle stages (THOUGHT / ACTION / OBSERVATION / VERIFICATION),
and structured JSONL events written to ``logs/events.jsonl``.

Propagation helpers (``inject_headers`` / ``from_headers`` / ``inject_env`` /
``from_env``) carry the trace context across HTTP calls and subprocess boundaries.

Design rules (P1):
  * A failure to persist an event must NEVER break the caller, but MUST be
    reported explicitly on stderr (never silently swallowed).
  * Every emitted record carries the mandatory fields
    ``ts, run_id, span_id, stage, event, latency_ms, status, error``.
"""

from __future__ import annotations

import contextlib
import contextvars
import json
import os
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Four lifecycle stages (Thought -> Action -> Observation -> Verification)
# ---------------------------------------------------------------------------
THOUGHT = "THOUGHT"
ACTION = "ACTION"
OBSERVATION = "OBSERVATION"
VERIFICATION = "VERIFICATION"
STAGES: Tuple[str, ...] = (THOUGHT, ACTION, OBSERVATION, VERIFICATION)

# Cross-boundary header / env names.
_HDR_TRACE = "X-Virtu-Trace-Id"
_HDR_RUN = "X-Virtu-Run-Id"
_HDR_SPAN = "X-Virtu-Span-Id"
_HDR_PARENT = "X-Virtu-Parent-Span-Id"

ENV_TRACE = "VIRTU_TRACE_ID"
ENV_RUN = "VIRTU_RUN_ID"
ENV_SPAN = "VIRTU_SPAN_ID"
ENV_PARENT = "VIRTU_PARENT_SPAN_ID"

# ---------------------------------------------------------------------------
# contextvars (one isolated context per thread / async task)
# ---------------------------------------------------------------------------
_ctx_trace_id: contextvars.ContextVar[str] = contextvars.ContextVar("virtu_trace_id", default="")
_ctx_run_id: contextvars.ContextVar[str] = contextvars.ContextVar("virtu_run_id", default="")
_ctx_span_id: contextvars.ContextVar[str] = contextvars.ContextVar("virtu_span_id", default="")
_ctx_parent_span_id: contextvars.ContextVar[str] = contextvars.ContextVar("virtu_parent_span_id", default="")

_WORKSPACE = Path(__file__).resolve().parent.parent.parent
LOG_PATH = _WORKSPACE / "logs" / "events.jsonl"
_WRITE_LOCK = threading.Lock()

_REQUIRED_FIELDS: Tuple[str, ...] = (
    "ts", "run_id", "span_id", "stage", "event", "latency_ms", "status", "error",
)


def _now_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def current() -> Dict[str, str]:
    """Return a snapshot of the active trace context."""
    return {
        "trace_id": _ctx_trace_id.get(),
        "run_id": _ctx_run_id.get(),
        "span_id": _ctx_span_id.get(),
        "parent_span_id": _ctx_parent_span_id.get(),
    }


def get_trace_id() -> str:
    return _ctx_trace_id.get()


def get_run_id() -> str:
    return _ctx_run_id.get()


def get_span_id() -> str:
    return _ctx_span_id.get()


def get_parent_span_id() -> str:
    return _ctx_parent_span_id.get()


# ---------------------------------------------------------------------------
# Structured event sink
# ---------------------------------------------------------------------------
def emit(
    stage: str,
    event: str,
    *,
    status: str = "ok",
    error: Optional[str] = None,
    latency_ms: float = 0.0,
    **attrs: Any,
) -> Dict[str, Any]:
    """Emit one structured event. Always returns the record; never raises."""
    cur = current()
    record: Dict[str, Any] = {
        "ts": _now_ts(),
        "run_id": cur["run_id"],
        "span_id": cur["span_id"],
        "stage": stage,
        "event": event,
        "latency_ms": float(latency_ms),
        "status": status,
        "error": error,
        # extra, non-mandatory context
        "trace_id": cur["trace_id"],
        "parent_span_id": cur["parent_span_id"],
    }
    for key, value in attrs.items():
        record.setdefault(key, value)
    _write_event(record)
    return record


def _write_event(record: Dict[str, Any]) -> None:
    """Append a JSONL line. Any failure is reported to stderr, never swallowed."""
    try:
        line = json.dumps(record, ensure_ascii=False, default=str)
        with _WRITE_LOCK:
            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(LOG_PATH, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
    except Exception as exc:  # noqa: BLE001 - tracing must never break the request
        print(
            f"[virtu.runtime.trace] failed to persist event to {LOG_PATH}: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# Run lifecycle
# ---------------------------------------------------------------------------
class RunHandle:
    """Handle returned by run/context installers; ``close()`` restores contextvars."""

    def __init__(
        self,
        run_id: str,
        trace_id: str,
        tokens: List[Tuple[contextvars.ContextVar, contextvars.Token]],
    ) -> None:
        self.run_id = run_id
        self.trace_id = trace_id
        self._tokens = tokens
        self._closed = False

    def close(self) -> None:
        if self._closed:
            return
        for var, token in reversed(self._tokens):
            var.reset(token)
        self._closed = True

    def __enter__(self) -> "RunHandle":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.close()
        return False


def _install_context(
    *,
    trace_id: str,
    run_id: str,
    span_id: str,
    parent_span_id: str,
) -> RunHandle:
    rid = run_id or uuid.uuid4().hex
    tid = trace_id or rid
    tokens: List[Tuple[contextvars.ContextVar, contextvars.Token]] = [
        (_ctx_trace_id, _ctx_trace_id.set(tid)),
        (_ctx_run_id, _ctx_run_id.set(rid)),
        (_ctx_span_id, _ctx_span_id.set(span_id or "")),
        (_ctx_parent_span_id, _ctx_parent_span_id.set(parent_span_id or "")),
    ]
    return RunHandle(rid, tid, tokens)


def start_run(run_id: Optional[str] = None, trace_id: Optional[str] = None, **attrs: Any) -> RunHandle:
    """Start a new root run, setting the contextvars for the current context."""
    handle = _install_context(
        trace_id=trace_id or "",
        run_id=run_id or "",
        span_id="",
        parent_span_id="",
    )
    emit(THOUGHT, "run.start", run_attrs=dict(attrs))
    return handle


# ---------------------------------------------------------------------------
# Span lifecycle
# ---------------------------------------------------------------------------
class Span:
    """Live span object yielded by :func:`span`."""

    def __init__(self, stage: str, span_id: str, parent_span_id: str, attrs: Dict[str, Any]) -> None:
        self.stage = stage
        self.span_id = span_id
        self.parent_span_id = parent_span_id
        self.attrs: Dict[str, Any] = dict(attrs)
        self.status = "ok"
        self.error: Optional[str] = None

    def fail(self, error: Any, status: str = "error") -> None:
        """Mark the span as failed without raising (used for explicit rejections)."""
        self.status = status
        self.error = str(error)

    def annotate(self, **attrs: Any) -> None:
        self.attrs.update(attrs)


@contextlib.contextmanager
def span(stage: str, **attrs: Any) -> Iterator[Span]:
    """Context manager creating a child span and emitting start/end events."""
    parent = _ctx_span_id.get()
    sid = uuid.uuid4().hex[:16]
    tok_span = _ctx_span_id.set(sid)
    tok_parent = _ctx_parent_span_id.set(parent)
    active = Span(stage, sid, parent, attrs)
    started = time.perf_counter()
    emit(stage, "span.start", span_attrs=dict(attrs))
    try:
        yield active
    except Exception as exc:  # re-raise, but record the failure explicitly
        active.fail(repr(exc))
        raise
    finally:
        latency = (time.perf_counter() - started) * 1000.0
        emit(stage, "span.end", status=active.status, error=active.error,
             latency_ms=latency, span_attrs=dict(active.attrs))
        _ctx_parent_span_id.reset(tok_parent)
        _ctx_span_id.reset(tok_span)


# ---------------------------------------------------------------------------
# Cross-boundary propagation (HTTP headers)
# ---------------------------------------------------------------------------
def inject_headers(headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Return a header dict carrying the active trace context."""
    out: Dict[str, str] = dict(headers or {})
    cur = current()
    out[_HDR_TRACE] = cur["trace_id"]
    out[_HDR_RUN] = cur["run_id"]
    out[_HDR_SPAN] = cur["span_id"]
    out[_HDR_PARENT] = cur["parent_span_id"]
    return out


def from_headers(headers: Dict[str, str]) -> RunHandle:
    """Install trace context read from (case-insensitive) HTTP headers."""
    lowered = {str(k).lower(): (v or "") for k, v in headers.items()}

    def _get(name: str) -> str:
        return lowered.get(name.lower(), "")

    return _install_context(
        trace_id=_get(_HDR_TRACE),
        run_id=_get(_HDR_RUN),
        span_id=_get(_HDR_SPAN),
        parent_span_id=_get(_HDR_PARENT),
    )


# ---------------------------------------------------------------------------
# Cross-boundary propagation (subprocess environment)
# ---------------------------------------------------------------------------
def inject_env(env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Return an environment dict carrying the active trace context."""
    out: Dict[str, str] = dict(os.environ if env is None else env)
    cur = current()
    out[ENV_TRACE] = cur["trace_id"]
    out[ENV_RUN] = cur["run_id"]
    out[ENV_SPAN] = cur["span_id"]
    out[ENV_PARENT] = cur["parent_span_id"]
    return out


def from_env(env: Optional[Dict[str, str]] = None) -> RunHandle:
    """Install trace context read from an environment mapping (child process)."""
    src = os.environ if env is None else env
    return _install_context(
        trace_id=src.get(ENV_TRACE, ""),
        run_id=src.get(ENV_RUN, ""),
        span_id=src.get(ENV_SPAN, ""),
        parent_span_id=src.get(ENV_PARENT, ""),
    )
