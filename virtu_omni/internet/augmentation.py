# -*- coding: utf-8 -*-
"""virtu_omni/internet/augmentation.py — Runtime internet grounding for every model path.

``VirtuInternetHub.query_model_with_internet`` runs Ollama itself, so it can only
serve one entry point. This module instead *augments* an existing prompt or chat
message list with live web evidence, letting each serving path keep owning its
own inference call:

  * ``virtu_router.py``            (CLI + OpenAI-compatible gateway, all Ollama models)
  * ``virtu_real_backend.py``      (ollama / transformers / vllm / llamacpp / cloud)
  * ``virtu_omni/serving/server.py`` (VirtuOmni10B HTTP service)

Design rules:
  * Fail-soft: any network / parsing failure leaves the prompt untouched and the
    model answers exactly as before.
  * Honest attribution: the local ``engineering_fallback_kb`` knowledge is NOT
    internet evidence and is never injected as such. The ingested VERICUT 9.6
    official training knowledge is injected under its **own** marker with
    ``source_path`` + sha256, and is explicitly labelled as local measured data.
  * Opt-out: ``VIRTU_INTERNET=off`` disables **web** augmentation globally;
    ``VIRTU_TRAINING_KB=off`` independently disables the local training KB
    (used by the pytest session so hermetic tests stay untouched).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

#: Sentinel that marks an already-augmented prompt, so wiring layers never double-inject.
MARKER = "【互联网实时检索资料"
#: 本地培训知识与联网资料互不冒充，各自独立去重。
TRAINING_MARKER = "【VERICUT 官方培训知识库"

_OFF_VALUES = frozenset({"0", "off", "false", "no", "disabled", "none"})
#: Sources that are local knowledge, not live internet evidence.
_NON_INTERNET_SOURCES = frozenset({"engineering_fallback_kb"})


def internet_enabled() -> bool:
    """Global switch. Default ON; ``VIRTU_INTERNET=off`` disables all model paths."""
    raw = str(os.environ.get("VIRTU_INTERNET", "on")).strip().lower()
    return raw not in _OFF_VALUES


def training_kb_enabled() -> bool:
    """本地培训知识库独立开关。默认 ON；与联网开关互不影响。"""
    raw = str(os.environ.get("VIRTU_TRAINING_KB", "on")).strip().lower()
    return raw not in _OFF_VALUES


def _clip(text: str, limit: int = 400) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[:limit] + "…"


def _last_user_text(messages: List[Dict[str, Any]]) -> str:
    for message in reversed(messages or []):
        if message.get("role") != "user":
            continue
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return " ".join(str(item.get("text", "")) for item in content
                            if isinstance(item, dict))
        return ""
    return ""


def _already_augmented(text: str) -> bool:
    return MARKER in str(text or "")


def web_context_block(query: str, num_results: int = 3) -> Optional[Dict[str, Any]]:
    """Search the web for ``query`` and build an injectable context block.

    Returns ``None`` when disabled, offline, blocked by the safety filter, or when
    the only hits are local fallback knowledge (never passed off as internet).
    """
    if not internet_enabled():
        return None
    q = str(query or "").strip()
    if len(q) < 2 or _already_augmented(q):
        return None
    try:
        from virtu_omni.internet.search_engine import get_search_engine
        response = get_search_engine().search(q, num_results=max(1, int(num_results)))
    except Exception as exc:  # noqa: BLE001 - augmentation must never break inference
        logger.debug("web search unavailable: %s: %s", type(exc).__name__, exc)
        return None
    if not getattr(response, "is_safe", False):
        return None
    items = [r for r in (getattr(response, "results", None) or [])
             if getattr(r, "source_engine", "") not in _NON_INTERNET_SOURCES]
    if not items:
        return None
    lines = [
        f"[{i}] {_clip(r.title, 120)}: {_clip(r.snippet)} (来源: {r.url})"
        for i, r in enumerate(items, 1)
    ]
    text = (
        f"\n\n{MARKER}】\n"
        + "\n".join(lines)
        + "\n请优先依据以上实时资料作答；若资料与本问题无关可忽略，资料不足时请明确说明，不得臆造。"
    )
    citations = [
        {"title": r.title, "url": r.url, "engine": getattr(r, "source_engine", "")}
        for r in items
    ]
    return {"text": text, "citations": citations}


def training_context_block(query: str, top_k: int = 2) -> Optional[Dict[str, Any]]:
    """召回已摄入的 VERICUT 官方培训实测知识，构造可注入的本地上下文块。

    与 ``web_context_block`` 严格分离：这里的数据来自本机文件解析（带
    ``source_path`` / sha256 / basis=measured），**不是**联网检索结果。
    """
    if not training_kb_enabled():
        return None
    q = str(query or "").strip()
    if len(q) < 2 or TRAINING_MARKER in q:
        return None
    try:
        from virtu_omni.internet.deep_learning_pipeline import get_learning_pipeline
        hits = get_learning_pipeline().retrieve_training_knowledge(q, top_k=max(1, int(top_k)))
    except Exception as exc:  # noqa: BLE001 - 召回失败不得影响推理
        logger.debug("training KB unavailable: %s: %s", type(exc).__name__, exc)
        return None
    if not hits:
        return None
    lines = [
        f"[{i}] {_clip(h.get('topic'), 120)}: {_clip(h.get('content'), 500)} "
        f"(本地实测来源: {h.get('source_path')} sha256={str(h.get('source_sha256'))[:12]})"
        for i, h in enumerate(hits, 1)
    ]
    text = (
        f"\n\n{TRAINING_MARKER}｜本地实测资料，非互联网检索】\n"
        + "\n".join(lines)
        + "\n以上为 VERICUT 9.6 官方培训资产的实测抽取结果，可作工程依据引用；"
          "不得当作实时联网资料，也不得据此臆造资料中未给出的数值或单位。"
    )
    citations = [
        {
            "topic": h.get("topic"),
            "source_path": h.get("source_path"),
            "source_sha256": h.get("source_sha256"),
            "source_type": h.get("source_type"),
            "basis": h.get("basis"),
            "similarity": h.get("similarity"),
            "engine": "vericut_training_kb",
        }
        for h in hits
    ]
    return {"text": text, "citations": citations}


def _combined_blocks(query: str, num_results: int) -> Optional[Dict[str, Any]]:
    web = web_context_block(query, num_results=num_results)
    kb = training_context_block(query, top_k=min(2, max(1, num_results)))
    if not web and not kb:
        return None
    return {
        "text": (web["text"] if web else "") + (kb["text"] if kb else ""),
        "citations": list(web["citations"] if web else []) + list(kb["citations"] if kb else []),
    }


def augment_prompt(prompt: str, num_results: int = 3) -> Tuple[str, List[Dict[str, Any]]]:
    """Append live web context and/or local training KB context to a flat prompt."""
    original = prompt if isinstance(prompt, str) else ""
    if not original.strip() or _already_augmented(original):
        return prompt, []
    blocks = _combined_blocks(original, num_results=num_results)
    if not blocks:
        return prompt, []
    return original + blocks["text"], blocks["citations"]


def augment_messages(
    messages: List[Dict[str, Any]], num_results: int = 3
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Inject live web context as a system note; user content is never modified."""
    msgs = list(messages or [])
    if not msgs:
        return messages, []
    if any(_already_augmented(_content_text(m.get("content"))) for m in msgs):
        return messages, []
    user_text = _last_user_text(msgs)
    if not user_text.strip():
        return messages, []
    already_training = any(TRAINING_MARKER in _content_text(m.get("content")) for m in msgs)
    block = (web_context_block(user_text, num_results=num_results) if already_training
             else _combined_blocks(user_text, num_results=num_results))
    if not block:
        return messages, []
    augmented = [dict(m) for m in msgs]
    insert_at = 0
    while insert_at < len(augmented) and augmented[insert_at].get("role") == "system":
        insert_at += 1
    if insert_at > 0 and isinstance(augmented[insert_at - 1].get("content"), str):
        existing = augmented[insert_at - 1]["content"]
        augmented[insert_at - 1] = {**augmented[insert_at - 1], "content": existing + block["text"]}
    else:
        augmented.insert(insert_at, {"role": "system", "content": block["text"].strip()})
    return augmented, block["citations"]


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(str(item.get("text", "")) for item in content
                        if isinstance(item, dict))
    return ""
