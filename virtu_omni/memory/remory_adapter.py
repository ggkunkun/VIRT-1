# -*- coding: utf-8 -*-
"""Remory compaction adapter for the Virtu main model (text-residual backend).

Source of truth for the protocol:
    external/Remory (github.com/fudan-generative-vision/Remory, MIT, v0.4.0)
    - src/remory/adapters/harness.py : Checkpoint / Harness.compact / on_compact / generate
    - src/remory/client.py           : Client.compact / generate / delete
    - src/remory/types.py            : digest(), backend boundary

HONESTY CONTRACT (read before using):
    Upstream Remory stores *learned soft memory* (float residual embeddings) that
    are injected into the actor's prefill by an SGLang model hook. It requires the
    released Qwen3.8-27B / GLM-5.3-Flash checkpoints, their tokenizers, hidden
    states and a 1.9B/1.24B trained encoder on Linux + CUDA 13 + >=2x80GB GPUs.
    None of that can run on this machine (Windows 11, RTX 4050 Laptop 6 GB,
    Ollama 0.40.14, GGUF main model ``virtu-wm-v3:chatml``), and the released
    checkpoints are NOT weight-compatible with the Virtu actor.

    This module therefore implements the *protocol layer*, not the learned
    memory network:
      * identical Checkpoint descriptor format (``rm_<48 hex>``, prefix SHA256),
      * identical compaction lifecycle (immutable handles, prefix identity guard,
        previous-handle chaining, atomic publish, failed compact keeps the old
        checkpoint, SQLite persistence across restarts),
      * ``summary + residual`` appended after the prefix on every continuation,
      * residual memory is a deterministic TEXT ledger extracted from the removed
        history instead of trained soft tokens.

    Any report produced from this module MUST label the backend as
    ``text-residual``. It must never be presented as upstream soft-memory scores.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
import time
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

__all__ = [
    "DEFAULT_MODEL",
    "BACKEND_ID",
    "Checkpoint",
    "MemoryStore",
    "TextClient",
    "RemoryHarness",
    "RemorySession",
    "OllamaChatBackend",
    "attach_to_gateway",
    "digest",
    "extract_residual",
    "deterministic_summary",
]

DEFAULT_MODEL = "virtu-wm-v3:chatml"
DEFAULT_ENDPOINT = "http://127.0.0.1:11434"
BACKEND_ID = "remory-protocol/text-residual-v1"
_HANDLE_RE = re.compile(r"rm_[0-9a-f]{48}")
_SHA_RE = re.compile(r"[0-9a-f]{64}")


def digest(value: Any) -> str:
    """Byte-identical to upstream ``remory.types.digest``."""
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            str(item.get("text", "")) if isinstance(item, dict) else str(item)
            for item in content
        ).strip()
    return str(content)


def _normalize(messages: Sequence[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Canonical, JSON-stable representation used for prefix identity checks."""
    return [
        {"role": str(m.get("role", "user")), "content": _message_text(m.get("content", ""))}
        for m in (messages or [])
    ]


# ---------------------------------------------------------------------------
# Checkpoint descriptor (same shape and validation as upstream)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Checkpoint:
    handle: str
    summary: str
    prefix_sha256: str

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "Checkpoint":
        if not isinstance(value, dict):
            raise ValueError("invalid Remory checkpoint descriptor")
        if not _HANDLE_RE.fullmatch(str(value.get("handle", ""))):
            raise ValueError("invalid Remory checkpoint descriptor")
        if not isinstance(value.get("summary"), str):
            raise ValueError("missing human-readable summary")
        if not _SHA_RE.fullmatch(str(value.get("prefix_sha256", ""))):
            raise ValueError("missing prefix identity")
        return cls(value["handle"], value["summary"], value["prefix_sha256"])


# ---------------------------------------------------------------------------
# SQLite store: immutable handles, session isolation, restart durability
# ---------------------------------------------------------------------------
class MemoryStore:
    """Persistent checkpoint store, equivalent in role to ``.remory/memory.sqlite``."""

    def __init__(self, path: str) -> None:
        self.path = str(Path(path).resolve())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        with self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS remory_checkpoints (
                       handle          TEXT PRIMARY KEY,
                       session_id      TEXT NOT NULL,
                       model           TEXT NOT NULL,
                       summary         TEXT NOT NULL,
                       residual_json   TEXT NOT NULL,
                       prefix_sha256   TEXT NOT NULL,
                       previous        TEXT,
                       receipt_json    TEXT NOT NULL,
                       created_at      REAL NOT NULL,
                       deleted         INTEGER NOT NULL DEFAULT 0
                   )"""
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_remory_session ON remory_checkpoints(session_id)"
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=15.0)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def save(
        self,
        checkpoint: Checkpoint,
        *,
        session_id: str,
        model: str,
        residual: Sequence[str],
        previous: Optional[str],
        receipt: Dict[str, Any],
    ) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO remory_checkpoints
                   (handle, session_id, model, summary, residual_json, prefix_sha256,
                    previous, receipt_json, created_at, deleted)
                   VALUES (?,?,?,?,?,?,?,?,?,0)""",
                (
                    checkpoint.handle,
                    session_id,
                    model,
                    checkpoint.summary,
                    json.dumps(list(residual), ensure_ascii=False),
                    checkpoint.prefix_sha256,
                    previous,
                    json.dumps(receipt, ensure_ascii=False, sort_keys=True),
                    time.time(),
                ),
            )

    def load(self, handle: str, session_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """SELECT handle, session_id, model, summary, residual_json,
                          prefix_sha256, previous, receipt_json, created_at
                   FROM remory_checkpoints WHERE handle=? AND deleted=0""",
                (handle,),
            ).fetchone()
        if row is None:
            return None
        if session_id is not None and row[1] != session_id:
            return None
        return {
            "handle": row[0],
            "session_id": row[1],
            "model": row[2],
            "summary": row[3],
            "residual": json.loads(row[4]),
            "prefix_sha256": row[5],
            "previous": row[6],
            "receipt": json.loads(row[7]),
            "created_at": row[8],
        }

    def delete(self, handle: str, session_id: Optional[str] = None) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "UPDATE remory_checkpoints SET deleted=1 WHERE handle=? "
                "AND deleted=0" + (" AND session_id=?" if session_id else ""),
                (handle, session_id) if session_id else (handle,),
            )
            return cur.rowcount > 0

    def count(self, session_id: Optional[str] = None) -> int:
        with self._lock, self._connect() as conn:
            if session_id:
                return conn.execute(
                    "SELECT COUNT(*) FROM remory_checkpoints WHERE session_id=? AND deleted=0",
                    (session_id,),
                ).fetchone()[0]
            return conn.execute(
                "SELECT COUNT(*) FROM remory_checkpoints WHERE deleted=0"
            ).fetchone()[0]


# ---------------------------------------------------------------------------
# Residual extraction + deterministic summary (no model call required)
# ---------------------------------------------------------------------------
_NUM_FACT = re.compile(
    r"([\w\u4e00-\u9fa5·\.]{2,24})\s*(?:[:=＝]|为|是|设定为|取值|取)\s*"
    r"([-+]?\d+(?:\.\d+)?)\s*([A-Za-zµ\u4e00-\u9fa5/%·²³]{0,8})"
)
_DECISION_WORDS = ("决定", "确认", "已验证", "结论", "采用", "选用", "定稿", "禁止", "必须", "PASS", "FAIL", "rc=")
_CREDENTIAL_KEYS = ("output_file", "sha256", "hash", "evidence_hash", "receipt", "rc", "status", "model")


def extract_residual(
    messages: Sequence[Dict[str, Any]], budget: int = 24
) -> List[str]:
    """Pull structured, verifiable leftovers out of the history being removed.

    Upstream encodes these into soft tokens with a trained network. Here they are
    kept as compact text lines; every line is traceable to a removed message.
    """
    lines: List[str] = []
    seen = set()

    def add(line: str) -> None:
        clean = re.sub(r"\s+", " ", line).strip()[:180]
        if clean and clean not in seen:
            seen.add(clean)
            lines.append(clean)

    for msg in _normalize(messages):
        text = msg["content"]
        if not text:
            continue
        for match in _NUM_FACT.finditer(text):
            key, value, unit = match.group(1), match.group(2), match.group(3)
            add(f"[{msg['role']}] {key} = {value}{unit}")
        for raw_line in text.splitlines():
            stripped = raw_line.strip()
            if not stripped:
                continue
            if any(word in stripped for word in _DECISION_WORDS):
                add(f"[{msg['role']}] {stripped}")
            if stripped.startswith("{") and stripped.endswith("}"):
                try:
                    parsed = json.loads(stripped)
                except (ValueError, TypeError):
                    parsed = None
                if isinstance(parsed, dict):
                    for key in _CREDENTIAL_KEYS:
                        if key in parsed:
                            add(f"[receipt] {key} = {str(parsed[key])[:120]}")
        # Keep a short anchor of the first user utterance (task identity).
        if msg["role"] == "user" and not any(line.startswith("[task]") for line in lines):
            add(f"[task] {text[:160]}")
    return lines[:max(1, int(budget))]


def deterministic_summary(
    removed_messages: Sequence[Dict[str, Any]],
    previous: Optional[Checkpoint] = None,
) -> str:
    """JSON summary contract equivalent, produced without an actor generation.

    The main model is a strict world-model that is only allowed to emit
    ``world_state`` JSON, so asking it to write a free-form compaction summary
    would violate its own contract. An optional ``summary_fn`` can override this.
    """
    norm = _normalize(removed_messages)
    roles: Dict[str, int] = {}
    for m in norm:
        roles[m["role"]] = roles.get(m["role"], 0) + 1
    facts = extract_residual(norm, budget=8)
    task = next((m["content"][:180] for m in norm if m["role"] == "user"), "")
    payload = {
        "schema": "remory_text_summary_v1",
        "task_anchor": task,
        "removed_messages": len(norm),
        "role_counts": roles,
        "carried_facts": facts,
        "previous_handle": previous.handle if previous else None,
        "backend": BACKEND_ID,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


# ---------------------------------------------------------------------------
# Transport: Ollama OpenAI-compatible chat endpoint (proxy-free)
# ---------------------------------------------------------------------------
class OllamaChatBackend:
    """Minimal transport. Injectable so tests never need a running model."""

    def __init__(
        self,
        endpoint: str = DEFAULT_ENDPOINT,
        *,
        timeout: float = 180.0,
        opener: Any = None,
        gateway: Any = None,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.timeout = float(timeout)
        # Host-side transparent proxies can intercept 127.0.0.1; build a
        # proxy-free opener so local Ollama traffic never leaves the machine.
        self.opener = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self.gateway = gateway

    def chat(
        self,
        messages: Sequence[Dict[str, Any]],
        *,
        model: str,
        max_tokens: int = 512,
        temperature: float = 0.0,
    ) -> Dict[str, Any]:
        if self.gateway is not None:
            result = self.gateway.chat(
                _normalize(messages), model=model, temperature=temperature,
                max_tokens=max_tokens, stream=False,
            )
            if not result.get("success", False):
                raise RuntimeError(f"gateway failure: {result.get('reason')}")
            data = result.get("data", {})
            choices = data.get("choices") or []
            text = choices[0]["message"]["content"] if choices else ""
            return {"text": text, "usage": data.get("usage", {}), "raw": data}

        payload = {
            "model": model,
            "messages": _normalize(messages),
            "stream": False,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        req = urllib.request.Request(
            self.endpoint + "/v1/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.opener.open(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        choices = data.get("choices") or []
        text = choices[0]["message"]["content"] if choices else ""
        return {"text": text, "usage": data.get("usage", {}), "raw": data}


# ---------------------------------------------------------------------------
# Client: compaction route + memory rendering
# ---------------------------------------------------------------------------
class TextClient:
    """Protocol-compatible stand-in for ``remory.client.Client``.

    ``compact`` / ``generate`` / ``delete`` keep upstream semantics; the payload
    is normalized text instead of token IDs because Ollama exposes neither the
    actor tokenizer nor hidden states.
    """

    def __init__(
        self,
        store: MemoryStore,
        *,
        session_id: str,
        model: str = DEFAULT_MODEL,
        residual_budget: int = 24,
    ) -> None:
        self.store = store
        self.session_id = session_id
        self.model = model
        self.residual_budget = int(residual_budget)

    def compact(
        self,
        *,
        prefix_messages: Sequence[Dict[str, Any]],
        removed_messages: Sequence[Dict[str, Any]],
        summary: str,
        previous: Optional[Checkpoint] = None,
    ) -> Dict[str, Any]:
        prefix_sha = digest(_normalize(prefix_messages))
        if previous and prefix_sha != previous.prefix_sha256:
            raise ValueError("system/tools/task prefix changed since compaction")
        if not isinstance(summary, str) or not summary.strip():
            raise RuntimeError("summary is empty; keep the previous context")
        if not removed_messages:
            raise RuntimeError("nothing to compact; keep the previous context")

        old = self.store.load(previous.handle, self.session_id) if previous else None
        if previous and old is None:
            raise RuntimeError("previous checkpoint is missing; keep the original history")

        new_facts = extract_residual(removed_messages, self.residual_budget)
        # new-first：预算满时淘汰最旧的残差，而不是让新事实永远进不来
        residual = list(dict.fromkeys(new_facts + (old["residual"] if old else [])))
        residual = residual[: self.residual_budget]

        source = {
            "prefix_sha256": prefix_sha,
            "summary": summary,
            "removed_digest": digest(_normalize(removed_messages)),
            "residual": residual,
            "previous": previous.handle if previous else None,
            "model": self.model,
            "session_id": self.session_id,
            "nonce": time.time_ns(),
        }
        handle = "rm_" + digest(source)[:48]
        checkpoint = Checkpoint(handle, summary, prefix_sha)
        receipt = {
            "backend": BACKEND_ID,
            "model": self.model,
            "removed_messages": len(_normalize(removed_messages)),
            "removed_chars": sum(len(m["content"]) for m in _normalize(removed_messages)),
            "summary_chars": len(summary),
            "residual_items": len(residual),
            "compression_depth": (old["receipt"].get("compression_depth", 0) + 1) if old else 1,
            "source_sha256": digest(source),
            "note": "text residual items, NOT trained soft tokens",
        }
        # Atomic publish: only after every validation above succeeds.
        self.store.save(
            checkpoint,
            session_id=self.session_id,
            model=self.model,
            residual=residual,
            previous=previous.handle if previous else None,
            receipt=receipt,
        )
        return {"handle": handle, "summary": summary, "receipt": receipt}

    def render(self, handle: str) -> str:
        record = self.store.load(handle, self.session_id)
        if record is None:
            raise RuntimeError(f"unknown Remory checkpoint: {handle}")
        lines = [
            f'<REMORY_MEMORY handle="{handle}" backend="{BACKEND_ID}" '
            f'model="{record["model"]}">',
            "The following is your persistent compacted memory. Treat it as "
            "established context from earlier in this same task. "
            "Do not contradict it, and do not claim you never received it.",
            "[COMPACTION_SUMMARY]",
            record["summary"],
            "[RESIDUAL_MEMORY - verified leftovers from removed history]",
        ]
        lines.extend(f"- {item}" for item in record["residual"])
        lines.append("[/REMORY_MEMORY]")
        return "\n".join(lines)

    def memory_message(self, handle: str) -> Dict[str, str]:
        """Memory carrier as a USER message, never a SYSTEM message.

        Measured on 2026-11-12 with ``virtu-wm-v3:chatml`` / Ollama 0.40.14:
        an explicit role=system message REPLACES the 8053-char Modelfile SYSTEM
        contract (prompt_tokens 3906 -> 71) and the model stops behaving as the
        world model. A role=user carrier keeps the contract intact and the
        memory is actually consumed (3909 -> 4052 prompt tokens; the model
        emitted ``outer_dia_mm: 160`` from a fact that existed only in memory).
        """
        return {"role": "user", "content": self.render(handle)}

    def delete(self, handle: str) -> bool:
        return self.store.delete(handle, self.session_id)


# ---------------------------------------------------------------------------
# Harness: upstream-compatible compaction lifecycle
# ---------------------------------------------------------------------------
class RemoryHarness:
    def __init__(
        self,
        client: TextClient,
        backend: Any,
        *,
        model: str = DEFAULT_MODEL,
        summary_fn: Optional[Callable[[Sequence[Dict[str, Any]], Optional[Checkpoint]], str]] = None,
    ) -> None:
        self.client = client
        self.backend = backend
        self.model = model
        self.summary_fn = summary_fn or deterministic_summary

    def compact(
        self,
        *,
        prefix_messages: Sequence[Dict[str, Any]],
        removed_messages: Sequence[Dict[str, Any]],
        summary_prompt: str = "",
        previous: Optional[Checkpoint] = None,
    ) -> Checkpoint:
        """Generate a summary, then encode residual memory, then publish.

        Mirrors ``Harness.compact``: publish only after both steps succeed;
        a failure leaves ``previous`` usable and never deletes history.
        """
        summary = self.summary_fn(list(removed_messages), previous)
        if not isinstance(summary, str) or not summary.strip():
            raise RuntimeError("summary did not complete; keep the previous context")
        return self.on_compact(
            prefix_messages=prefix_messages,
            removed_messages=removed_messages,
            summary=summary,
            previous=previous,
        )

    def on_compact(
        self,
        *,
        prefix_messages: Sequence[Dict[str, Any]],
        removed_messages: Sequence[Dict[str, Any]],
        summary: str,
        previous: Optional[Checkpoint] = None,
    ) -> Checkpoint:
        result = self.client.compact(
            prefix_messages=prefix_messages,
            removed_messages=removed_messages,
            summary=summary,
            previous=previous,
        )
        return Checkpoint(result["handle"], summary, digest(_normalize(prefix_messages)))

    def generate(
        self,
        *,
        checkpoint: Checkpoint,
        prefix_messages: Sequence[Dict[str, Any]],
        messages: Sequence[Dict[str, Any]],
        max_tokens: int = 512,
    ) -> Dict[str, Any]:
        """Continue from a checkpoint: prefix + memory carrier + new messages."""
        if digest(_normalize(prefix_messages)) != checkpoint.prefix_sha256:
            raise ValueError("system/tools/task prefix changed since compaction")
        carrier = self.client.memory_message(checkpoint.handle)
        full = list(_normalize(prefix_messages)) + [carrier] + list(_normalize(messages))
        return self.backend.chat(full, model=self.model, max_tokens=max_tokens)

    def plain_generate(
        self,
        *,
        prefix_messages: Sequence[Dict[str, Any]],
        messages: Sequence[Dict[str, Any]],
        max_tokens: int = 512,
    ) -> Dict[str, Any]:
        full = list(_normalize(prefix_messages)) + list(_normalize(messages))
        return self.backend.chat(full, model=self.model, max_tokens=max_tokens)


# ---------------------------------------------------------------------------
# Session: one-line integration surface for the main model
# ---------------------------------------------------------------------------
class RemorySession:
    def __init__(
        self,
        *,
        session_id: str = "virtu-main",
        model: str = DEFAULT_MODEL,
        store_path: Optional[str] = None,
        prefix_messages: Optional[Sequence[Dict[str, Any]]] = None,
        backend: Any = None,
        endpoint: str = DEFAULT_ENDPOINT,
        keep_recent: int = 4,
        residual_budget: int = 24,
    ) -> None:
        self.session_id = session_id
        self.model = model
        root = Path(os.getenv("VIRTU_WORKSPACE_ROOT", Path(__file__).resolve().parents[2]))
        self.store_path = store_path or str(root / "runs" / "remory" / "memory.sqlite")
        self.store = MemoryStore(self.store_path)
        self.client = TextClient(
            self.store, session_id=session_id, model=model, residual_budget=residual_budget
        )
        self.backend = backend or OllamaChatBackend(endpoint=endpoint)
        self.harness = RemoryHarness(self.client, self.backend, model=model)
        self.prefix_messages = _normalize(prefix_messages or [])
        self.history: List[Dict[str, str]] = []
        self.checkpoint: Optional[Checkpoint] = None
        self.keep_recent = int(keep_recent)
        self.injection_count = 0
        self.last_injected_handle: Optional[str] = None

    # -- history -------------------------------------------------------------
    def append(self, role: str, content: Any) -> None:
        self.history.append({"role": role, "content": _message_text(content)})

    def should_compact(self, threshold: int = 8) -> bool:
        return len(self.history) > threshold

    def compact(self, *, force: bool = False) -> Optional[Checkpoint]:
        """Compact the old part of the history; keep the recent window verbatim."""
        if not force and not self.should_compact():
            return self.checkpoint
        cut = max(1, len(self.history) - self.keep_recent)
        removed, retained = self.history[:cut], self.history[cut:]
        if not removed:
            return self.checkpoint
        checkpoint = self.harness.compact(
            prefix_messages=self.prefix_messages,
            removed_messages=removed,
            previous=self.checkpoint,
        )
        # Publish only after the store succeeded.
        self.checkpoint = checkpoint
        self.history = retained
        return checkpoint

    def inject(self, messages: Sequence[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Insert the memory carrier after the immutable prefix."""
        normalized = _normalize(messages)
        prefix = self.prefix_messages
        if prefix and normalized[: len(prefix)] == prefix:
            body = normalized[len(prefix) :]
        else:
            body = normalized
        out = list(prefix)
        if self.checkpoint:
            out.append(self.client.memory_message(self.checkpoint.handle))
            self.injection_count += 1
            self.last_injected_handle = self.checkpoint.handle
        out.extend(body)
        return out

    def chat(self, user_text: str, *, max_tokens: int = 512) -> Dict[str, Any]:
        """One turn through the main model, with Remory memory if a checkpoint exists."""
        new_messages = list(self.history) + [{"role": "user", "content": user_text}]
        if self.checkpoint:
            result = self.harness.generate(
                checkpoint=self.checkpoint,
                prefix_messages=self.prefix_messages,
                messages=new_messages,
                max_tokens=max_tokens,
            )
        else:
            result = self.harness.plain_generate(
                prefix_messages=self.prefix_messages,
                messages=new_messages,
                max_tokens=max_tokens,
            )
        self.append("user", user_text)
        self.append("assistant", result.get("text", ""))
        return result

    def resume(self, handle: str) -> Checkpoint:
        """Restore a checkpoint from SQLite after a process restart."""
        record = self.store.load(handle, self.session_id)
        if record is None:
            raise RuntimeError(f"cannot resume unknown checkpoint: {handle}")
        self.checkpoint = Checkpoint(record["handle"], record["summary"], record["prefix_sha256"])
        return self.checkpoint

    def descriptor(self) -> Optional[Dict[str, str]]:
        return self.checkpoint.to_dict() if self.checkpoint else None


def attach_to_gateway(gateway: Any, session: RemorySession) -> Any:
    """Transparently wire Remory into the unified LLM gateway (zero source edits).

    After this call, every ``gateway.chat(...)`` sends
    ``prefix + <REMORY_MEMORY> + caller messages`` to the main model. Idempotent:
    a second call on the same gateway is a no-op.
    """
    if getattr(gateway, "_remory_attached", False):
        return gateway
    original_chat = gateway.chat

    def wrapped_chat(messages: Any, *, model: Optional[str] = None, **opts: Any) -> Any:
        merged = session.inject(messages)
        return original_chat(merged, model=model or session.model, **opts)

    gateway.chat = wrapped_chat
    gateway._remory_attached = True
    gateway._remory_session = session
    return gateway
