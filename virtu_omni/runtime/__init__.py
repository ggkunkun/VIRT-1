# -*- coding: utf-8 -*-
"""Virtu P1 runtime governance: unified LLM gateway + structured tracing.

``trace`` is imported eagerly because it only depends on the standard library.
``llm_gateway`` is loaded lazily (it requires ``pydantic>=2``) so that importing
the trace module never fails when the gateway's dependencies are unavailable.
"""

from __future__ import annotations

import importlib

from . import trace
from .trace import (  # noqa: F401
    ACTION,
    OBSERVATION,
    STAGES,
    THOUGHT,
    VERIFICATION,
    RunHandle,
    Span,
    current,
    emit,
    from_env,
    from_headers,
    get_parent_span_id,
    get_run_id,
    get_span_id,
    get_trace_id,
    inject_env,
    inject_headers,
    span,
    start_run,
)

_LAZY = {
    "LLMGateway": "virtu_omni.runtime.llm_gateway",
    "GatewayConfig": "virtu_omni.runtime.llm_gateway",
    "GatewayResult": "virtu_omni.runtime.llm_gateway",
    "GatewayError": "virtu_omni.runtime.llm_gateway",
    "SchemaError": "virtu_omni.runtime.llm_gateway",
    "AuthError": "virtu_omni.runtime.llm_gateway",
    "ClientError": "virtu_omni.runtime.llm_gateway",
    "NetworkError": "virtu_omni.runtime.llm_gateway",
    "ServerError": "virtu_omni.runtime.llm_gateway",
    "CircuitOpenError": "virtu_omni.runtime.llm_gateway",
    "CircuitBreaker": "virtu_omni.runtime.llm_gateway",
    "ChatRequest": "virtu_omni.runtime.llm_gateway",
    "GenerateRequest": "virtu_omni.runtime.llm_gateway",
    "EmbedRequest": "virtu_omni.runtime.llm_gateway",
}

__all__ = [
    "trace",
    "THOUGHT", "ACTION", "OBSERVATION", "VERIFICATION", "STAGES",
    "start_run", "span", "emit", "current", "RunHandle", "Span",
    "get_trace_id", "get_run_id", "get_span_id", "get_parent_span_id",
    "inject_headers", "from_headers", "inject_env", "from_env",
] + list(_LAZY.keys())


def __getattr__(name: str):
    module_name = _LAZY.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = importlib.import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value
