# -*- coding: utf-8 -*-
"""GitHub-grounded long-context module for the Virtu main model.

Grounding (cloned / fetched 2026-11-12):
    * ggml-org/llama.cpp  : -ctk/-ctv q8_0, -fa flash attention, --context-shift,
                            --rope-scaling yarn (used by Ollama's llama-server).
    * ollama/ollama       : OLLAMA_FLASH_ATTENTION / OLLAMA_KV_CACHE_TYPE /
                            OLLAMA_CONTEXT_LENGTH, per-request options.num_ctx.
    * microsoft/LLMLingua : prompt compression with protected structural tokens
                            (this module uses a deterministic, model-free variant).
    * mit-han-lab/streaming-llm : attention sinks / rolling KV (concept only;
                            llama.cpp's --context-shift is the available analogue).
    * Qwen3 model card    : n_ctx_train = 40960, YaRN validated to 131072.

HONESTY CONTRACT:
    This is NOT a new attention architecture and NOT a trained compressor.
    On this host the physical long-context capability already exists in the
    runtime (measured from server.log: --cache-type-k q8_0 --cache-type-v q8_0
    --flash-attn on, n_ctx_train 40960). What was missing was (a) a model
    manifest that actually requests a large num_ctx and (b) a context manager
    that can turn an arbitrarily long corpus into a budgeted prompt. Both are
    implemented here. YaRN (>40960) is NOT enabled: Ollama 0.40.14 does not
    expose rope scaling and llama.cpp static YaRN degrades short prompts.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import threading
import time
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

__all__ = [
    "BASE_MODEL", "DEFAULT_MODEL", "DEFAULT_CTX", "BACKEND_ID",
    "TokenEstimator", "ContextBudget", "ContextBudgetExceeded", "LongContextStore",
    "compress_chunk", "NativeChatBackend", "LongContextSession",
    "attach_to_gateway",
]

BASE_MODEL = "virtu-wm-v3:chatml"
DEFAULT_MODEL = "virtu-wm-v3:longctx"
DEFAULT_CTX = 32768
BACKEND_ID = "github-grounded/long-context-v1"
# Measured 2026-11-12: an 8053-char Modelfile SYSTEM renders to 3912 prompt tokens.
SYSTEM_TOKEN_OVERHEAD = 3912
CHARS_PER_TOKEN = 2.06

_CJK = re.compile(r"[\u4e00-\u9fff]+")
_ASCII = re.compile(r"[A-Za-z0-9_.\-]+")
_KEEP_LINE = re.compile(
    r"(\d|[＝=:]|最终|确认|决定|结论|已验证|采用|选用|草案|废弃|外径|内径|厚度|"
    r"转速|安全系数|material|FOS|rc=|sha256|output_file|PASS|FAIL)"
)
_FORCE_CHARS = ("\n", "=", "：", ":", "[", "]", "mm", "FOS")
_QUERY_EXPANSION = {
    "final": "最终确认", "confirmed": "最终确认", "flange": "法兰",
    "outer_dia_mm": "外径", "outer": "外径", "diameter": "外径",
    "safety": "安全系数", "factor": "安全系数", "fos": "安全系数",
    "material": "材料", "spindle": "主轴转速", "feed": "进给量",
}


def _expand_query(query: str) -> str:
    """Bridge English task prompts to a Chinese corpus (measured failure fix).

    Measured 2026-11-12: an English-only recall query matched just ``mm`` in a
    Chinese corpus, so BM25 returned the first draft chunks (model answered 153
    instead of the buried 167.3). Domain-token expansion fixes the mismatch
    without requiring callers to hand-write Chinese search terms.
    """
    lowered = query.lower()
    extra = [zh for en, zh in _QUERY_EXPANSION.items() if en in lowered]
    return query + (" " + " ".join(dict.fromkeys(extra)) if extra else "")


def _normalize(messages: Sequence[Dict[str, Any]]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for m in messages or []:
        content = m.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                str(x.get("text", "")) if isinstance(x, dict) else str(x) for x in content
            )
        out.append({"role": str(m.get("role", "user")), "content": str(content)})
    return out


def _terms(text: str) -> List[str]:
    """Chinese bigrams + whole CJK runs + ascii/number tokens."""
    result: List[str] = []
    lowered = text.lower()
    for run in _CJK.findall(lowered):
        result.append(run)
        if len(run) > 1:
            result.extend(run[i:i + 2] for i in range(len(run) - 1))
    result.extend(t for t in _ASCII.findall(lowered) if t)
    return result


class TokenEstimator:
    """Calibrated character->token estimator (NOT a tokenizer)."""

    def __init__(self, chars_per_token: float = CHARS_PER_TOKEN) -> None:
        self.chars_per_token = max(0.5, float(chars_per_token))

    def estimate(self, text: str) -> int:
        return max(1, math.ceil(len(text) / self.chars_per_token))

    @classmethod
    def from_measurement(cls, chars: int, tokens: int) -> "TokenEstimator":
        return cls(chars / max(1, tokens))


class ContextBudgetExceeded(RuntimeError):
    """Raised when a composed prompt would silently overflow the context."""


@dataclass
class ContextBudget:
    physical_ctx: int = DEFAULT_CTX
    system_overhead: int = SYSTEM_TOKEN_OVERHEAD
    reserve_output: int = 256
    safety_ratio: float = 0.95
    guard_threshold: float = 0.90
    estimator: TokenEstimator = field(default_factory=TokenEstimator)

    def input_budget(self) -> int:
        usable = int(self.physical_ctx * self.safety_ratio) - self.reserve_output
        return max(64, usable - self.system_overhead)

    def projected_limit(self) -> int:
        """Hard ceiling for prompt + system + output headroom."""
        return int(self.physical_ctx * self.guard_threshold)

    def guard(self, projected_tokens: int) -> bool:
        """Falsifiable gate: never let a request silently approach the ceiling.

        Measurement anchor: the 8053-char Modelfile SYSTEM alone costs 3912
        measured prompt tokens, so packet size alone is NOT the projected cost.
        """
        return projected_tokens <= self.projected_limit()


@dataclass
class ChunkHit:
    doc_id: str
    idx: int
    text: str
    score: float


class LongContextStore:
    """Spill-to-disk chunk store with BM25-lite retrieval (no external deps)."""

    def __init__(self, path: str) -> None:
        self.path = str(Path(path).resolve())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        with self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS lc_chunks (
                       doc_id TEXT NOT NULL, idx INTEGER NOT NULL,
                       text TEXT NOT NULL, sha256 TEXT NOT NULL,
                       PRIMARY KEY (doc_id, idx))"""
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=15.0)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def ingest(self, doc_id: str, text: str, *, chunk_chars: int = 800) -> int:
        """Split a document into paragraph-preserving chunks and persist all text."""
        chunks: List[str] = []
        for para in re.split(r"\n\s*\n", text.strip()):
            para = para.strip()
            if not para:
                continue
            if len(para) <= chunk_chars:
                chunks.append(para)
            else:
                for start in range(0, len(para), chunk_chars):
                    chunks.append(para[start:start + chunk_chars])
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM lc_chunks WHERE doc_id=?", (doc_id,))
            for idx, chunk in enumerate(chunks):
                conn.execute(
                    "INSERT OR REPLACE INTO lc_chunks(doc_id, idx, text, sha256) VALUES (?,?,?,?)",
                    (doc_id, idx, chunk, hashlib.sha256(chunk.encode("utf-8")).hexdigest()),
                )
        return len(chunks)

    def _all(self) -> List[Tuple[str, int, str]]:
        with self._lock, self._connect() as conn:
            return conn.execute(
                "SELECT doc_id, idx, text FROM lc_chunks ORDER BY doc_id, idx"
            ).fetchall()

    def search(self, query: str, top_k: int = 4) -> List[ChunkHit]:
        rows = self._all()
        if not rows:
            return []
        q_terms = set(_terms(query))
        if not q_terms:
            return [ChunkHit(r[0], r[1], r[2], 0.0) for r in rows[:top_k]]
        doc_terms = [Counter(_terms(text)) for _, _, text in rows]
        df: Counter = Counter()
        for counter in doc_terms:
            df.update(counter.keys())
        n = len(rows)
        idf = {t: math.log(1.0 + n / (1.0 + df.get(t, 0))) for t in q_terms}
        scored: List[ChunkHit] = []
        for (doc_id, idx, text), tf in zip(rows, doc_terms):
            score = sum(
                idf[t] * (1.0 + math.log(1.0 + tf.get(t, 0)))
                for t in q_terms if tf.get(t, 0) > 0
            )
            score /= math.sqrt(max(1, len(text)))
            scored.append(ChunkHit(doc_id, idx, text, round(score, 4)))
        scored.sort(key=lambda h: (-h.score, h.doc_id, h.idx))
        ranked = scored[:max(1, top_k)]
        positive = [h for h in ranked if h.score > 0]
        # Never return an empty packet: a broad query still deserves the
        # highest-ranked context, even when every BM25 score is zero.
        return positive or ranked

    def stats(self) -> Dict[str, int]:
        with self._lock, self._connect() as conn:
            chunks = conn.execute("SELECT COUNT(*) FROM lc_chunks").fetchone()[0]
            docs = conn.execute("SELECT COUNT(DISTINCT doc_id) FROM lc_chunks").fetchone()[0]
            chars = conn.execute("SELECT COALESCE(SUM(LENGTH(text)),0) FROM lc_chunks").fetchone()[0]
        return {"documents": docs, "chunks": chunks, "total_chars": chars}


def compress_chunk(text: str, max_chars: int) -> Tuple[str, Dict[str, Any]]:
    """Deterministic structured compression (LLMLingua-inspired, model-free).

    Keeps lines carrying numbers, units, decisions, identifiers and receipts;
    drops descriptive prose. Protected structural characters are preserved.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    total = len(lines)
    kept = [line for line in lines if _KEEP_LINE.search(line)]
    if not kept:
        kept = lines[:1]
    compressed = "\n".join(kept)
    if len(compressed) > max_chars:
        compressed = compressed[:max(1, int(max_chars))] + " …[truncated]"
    for ch in _FORCE_CHARS:
        if ch in text and ch not in compressed and ch != "\n":
            compressed += f" {ch}"
    meta = {
        "original_chars": len(text),
        "compressed_chars": len(compressed),
        "kept_lines": len(kept),
        "total_lines": total,
        "ratio": round(len(compressed) / max(1, len(text)), 3),
    }
    return compressed, meta


class NativeChatBackend:
    """Ollama /api/chat with native ``options`` (num_ctx / num_gpu / num_predict)."""

    def __init__(self, endpoint: str = "http://127.0.0.1:11434", *,
                 timeout: float = 600.0, opener: Any = None) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.timeout = float(timeout)
        self.opener = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def chat(self, messages: Sequence[Dict[str, Any]], *, model: str,
             num_ctx: int = DEFAULT_CTX, num_gpu: int = 16,
             max_tokens: int = 256, temperature: float = 0.0) -> Dict[str, Any]:
        payload = {
            "model": model,
            "messages": _normalize(messages),
            "stream": False,
            "keep_alive": "10m",
            "options": {
                "num_ctx": num_ctx,
                "num_gpu": num_gpu,
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }
        req = urllib.request.Request(
            self.endpoint + "/api/chat",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        started = time.time()
        with self.opener.open(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = (data.get("message") or {}).get("content", "")
        return {
            "text": text,
            "usage": {"prompt_tokens": data.get("prompt_eval_count"),
                      "completion_tokens": data.get("eval_count")},
            "latency_s": round(time.time() - started, 2),
            "timings": {"total_ms": round((data.get("total_duration") or 0) / 1e6, 1),
                        "load_ms": round((data.get("load_duration") or 0) / 1e6, 1)},
            "raw": data,
        }


class LongContextSession:
    """Turn an arbitrarily long corpus into a budgeted prompt for the main model."""

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        endpoint: str = "http://127.0.0.1:11434",
        physical_ctx: int = DEFAULT_CTX,
        store_path: Optional[str] = None,
        backend: Any = None,
        top_k: int = 4,
        remory_session: Any = None,
        budget: Optional[ContextBudget] = None,
        auto_recompact: bool = True,
    ) -> None:
        self.model = model
        self.physical_ctx = int(physical_ctx)
        root = Path(os.getenv("VIRTU_WORKSPACE_ROOT", Path(__file__).resolve().parents[2]))
        self.store_path = store_path or str(root / "runs" / "long_context" / "chunks.sqlite")
        self.store = LongContextStore(self.store_path)
        self.backend = backend or NativeChatBackend(endpoint=endpoint)
        self.top_k = int(top_k)
        self.remory_session = remory_session
        self.budget = budget or ContextBudget(physical_ctx=self.physical_ctx)
        self.auto_recompact = bool(auto_recompact)
        self.auto_recompact_count = 0
        self.last_meta: Dict[str, Any] = {}
        self.injection_count = 0

    def ingest(self, doc_id: str, text: str, *, chunk_chars: int = 800) -> int:
        return self.store.ingest(doc_id, text, chunk_chars=chunk_chars)

    def compose(self, query: str, *, top_k: Optional[int] = None,
                retrieval_query: Optional[str] = None,
                _recompact_done: bool = False) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
        """Build a budget-safe message pair: retrieval packet + task query.

        ``query`` is what the model sees; ``retrieval_query`` (optional) is what
        BM25 searches for. When omitted, English domain tokens are expanded to
        their Chinese equivalents before retrieval.
        """
        k = int(top_k or self.top_k)
        budget_tokens = self.budget.input_budget()
        effective_query = retrieval_query or _expand_query(query)
        hits = self.store.search(effective_query, top_k=k)

        # Iteratively tighten compression until the packet fits the budget.
        attempts: List[Dict[str, Any]] = []
        packet_body = ""
        chosen: List[Dict[str, Any]] = []
        compressed_meta: List[Dict[str, Any]] = []
        for round_idx in range(4):
            per_chunk_chars = max(60, int(budget_tokens * CHARS_PER_TOKEN / max(1, k)) // (1 + round_idx))
            chosen, compressed_meta, packet_body = [], [], ""
            for hit in hits:
                compressed, meta = compress_chunk(hit.text, per_chunk_chars)
                chosen.append({"doc": hit.doc_id, "idx": hit.idx, "score": hit.score})
                compressed_meta.append(meta)
                packet_body += (
                    f"\n[SOURCE doc={hit.doc_id} idx={hit.idx} score={hit.score} "
                    f"compression={meta['ratio']}]\n{compressed}\n"
                )
            header = (
                f'<LONG_CONTEXT_RETRIEVAL backend="{BACKEND_ID}" '
                f'physical_ctx="{self.physical_ctx}" budget_tokens="{budget_tokens}" '
                f'retrieved="{len(chosen)}">'
            )
            packet = header + packet_body + "[/LONG_CONTEXT_RETRIEVAL]"
            est = self.budget.estimator.estimate(packet)
            attempts.append({"round": round_idx, "estimated_tokens": est,
                             "per_chunk_chars": per_chunk_chars, "fits": est <= budget_tokens})
            if est <= budget_tokens:
                break
            if len(hits) > 1:
                hits = hits[:-1]
                k = len(hits)

        if self.remory_session is not None and getattr(self.remory_session, "checkpoint", None):
            packet += "\n" + self.remory_session.client.render(
                self.remory_session.checkpoint.handle
            )
        final_est = self.budget.estimator.estimate(packet)
        task_text = f"<TASK>\n{query}\n</TASK>"
        projected = (final_est + self.budget.system_overhead
                     + self.budget.estimator.estimate(task_text))
        guard_passed = self.budget.guard(projected)

        # Hard gate: never let a request silently approach the context ceiling.
        # First remedy is to compact the conversation through Remory, then
        # rebuild once. If it still does not fit, fail loudly instead of
        # letting Ollama context-shift away the middle of the prompt.
        if not guard_passed:
            if self.auto_recompact and self.remory_session is not None and not _recompact_done:
                try:
                    self.remory_session.compact(force=True)
                    self.auto_recompact_count += 1
                    return self.compose(query, top_k=top_k,
                                        retrieval_query=retrieval_query,
                                        _recompact_done=True)
                except Exception as exc:  # noqa: BLE001
                    raise ContextBudgetExceeded(
                        f"projected {projected} tokens exceeds guard limit "
                        f"{self.budget.projected_limit()}; auto re-compaction failed: {exc}"
                    ) from exc
            raise ContextBudgetExceeded(
                f"projected {projected} tokens exceeds guard limit "
                f"{self.budget.projected_limit()} for num_ctx={self.physical_ctx}"
            )

        meta = {
            "backend": BACKEND_ID,
            "model": self.model,
            "physical_ctx": self.physical_ctx,
            "retrieval_query": effective_query,
            "input_budget_tokens": budget_tokens,
            "estimated_packet_tokens": final_est,
            "projected_tokens": projected,
            "guard_limit": self.budget.projected_limit(),
            "guard_passed": guard_passed,
            "auto_recompact_count": self.auto_recompact_count,
            "budget_exceeded": final_est > budget_tokens,
            "retrieved_chunks": len(chosen),
            "sources": chosen,
            "compression": compressed_meta,
            "fit_attempts": attempts,
            "store_stats": self.store.stats(),
        }
        self.last_meta = meta
        messages = [
            {"role": "user", "content": packet},
            {"role": "user", "content": task_text},
        ]
        return messages, meta

    def inject(self, messages: Sequence[Dict[str, Any]],
               *, retrieval_query: Optional[str] = None) -> List[Dict[str, str]]:
        """Insert a retrieval packet immediately before the last user message."""
        msgs = _normalize(messages)
        user_positions = [i for i, m in enumerate(msgs) if m["role"] == "user"]
        if not user_positions:
            return msgs
        pos = user_positions[-1]
        packet, _ = self.compose(msgs[pos]["content"], retrieval_query=retrieval_query)
        self.injection_count += 1
        return msgs[:pos] + [packet[0]] + msgs[pos:]

    def chat(self, query: str, *, num_ctx: Optional[int] = None,
             max_tokens: int = 256,
             retrieval_query: Optional[str] = None) -> Dict[str, Any]:
        messages, meta = self.compose(query, retrieval_query=retrieval_query)
        result = self.backend.chat(
            messages, model=self.model,
            num_ctx=int(num_ctx or self.physical_ctx),
            max_tokens=max_tokens,
        )
        result["context_meta"] = meta
        return result


def attach_to_gateway(gateway: Any, session: LongContextSession) -> Any:
    """Transparently wire long-context retrieval into the unified LLM gateway.

    Physical context is controlled by the model manifest
    (``virtu-wm-v3:longctx`` -> num_ctx 32768); this hook injects the retrieved,
    budgeted packet into every chat call without editing the gateway source.
    """
    if getattr(gateway, "_long_context_attached", False):
        return gateway
    original_chat = gateway.chat

    def wrapped_chat(messages: Any, *, model: Optional[str] = None, **opts: Any) -> Any:
        merged = session.inject(messages)
        return original_chat(merged, model=model or session.model, **opts)

    gateway.chat = wrapped_chat
    gateway._long_context_attached = True
    gateway._long_context_session = session
    return gateway
