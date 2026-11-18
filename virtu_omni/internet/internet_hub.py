# -*- coding: utf-8 -*-
"""virtu_omni/internet/internet_hub.py — Universal Internet & Continual Deep Learning Hub.

Binds all models in the workspace (Ollama, local checkpoints, SuperAgent, REST, MCP)
to the Internet with high-performance web search, automated harmful content filtering,
and continual deep learning capabilities.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from virtu_omni.internet.safety_filter import HarmfulContentFilter, get_safety_filter
from virtu_omni.internet.search_engine import WebSearchEngine, get_search_engine
from virtu_omni.internet.deep_learning_pipeline import ContinualLearningPipeline, get_learning_pipeline

logger = logging.getLogger(__name__)

WORKSPACE_DIR = Path(__file__).resolve().parent.parent.parent


@dataclass
class ModelIdentityInfo:
    """Registered model descriptor in workspace."""
    model_name: str
    source_type: str  # "ollama", "local_weights", "gguf_checkpoint"
    path_or_tag: str
    internet_enabled: bool = True
    safety_guard_enabled: bool = True
    deep_learning_enabled: bool = True


class VirtuInternetHub:
    """Master Hub connecting all workspace models to Internet, Safety Filter, and Deep Learning."""

    OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"
    OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"

    def __init__(
        self,
        safety_filter: Optional[HarmfulContentFilter] = None,
        search_engine: Optional[WebSearchEngine] = None,
        learning_pipeline: Optional[ContinualLearningPipeline] = None,
    ):
        self.safety_filter = safety_filter or get_safety_filter()
        self.search_engine = search_engine or get_search_engine()
        self.learning_pipeline = learning_pipeline or get_learning_pipeline()

    def discover_workspace_models(self) -> List[ModelIdentityInfo]:
        """Discover all models in Ollama, models/ directory, and checkpoints/ directory."""
        models: List[ModelIdentityInfo] = []

        # 1. Ollama models
        try:
            res = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5,
                                 encoding="utf-8", errors="replace")
            if res.returncode == 0:
                lines = res.stdout.strip().split("\n")
                if len(lines) > 1:
                    for line in lines[1:]:
                        parts = line.split()
                        if parts:
                            tag = parts[0]
                            models.append(
                                ModelIdentityInfo(
                                    model_name=tag,
                                    source_type="ollama",
                                    path_or_tag=tag,
                                )
                            )
        except Exception as e:
            logger.debug(f"Failed to list Ollama models: {e}")

        # 2. Local models in models/
        models_dir = WORKSPACE_DIR / "models"
        if models_dir.exists():
            for item in models_dir.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    models.append(
                        ModelIdentityInfo(
                            model_name=f"local:{item.name}",
                            source_type="local_weights",
                            path_or_tag=str(item),
                        )
                    )

        # 3. GGUF Checkpoints in checkpoints/
        checkpoints_dir = WORKSPACE_DIR / "checkpoints"
        if checkpoints_dir.exists():
            for gguf in checkpoints_dir.glob("*.gguf"):
                models.append(
                    ModelIdentityInfo(
                        model_name=f"checkpoint:{gguf.stem}",
                        source_type="gguf_checkpoint",
                        path_or_tag=str(gguf),
                    )
                )

        return models

    def web_search_tool(self, query: str, num_results: int = 4) -> Dict[str, Any]:
        """Tool implementation for model tool calling."""
        search_res = self.search_engine.search(query, num_results=num_results)
        return {
            "query": query,
            "is_safe": search_res.is_safe,
            "filter_verdict": search_res.filter_verdict,
            "total_found": search_res.total_found,
            "sources": [r.to_dict() for r in search_res.results],
            "error": search_res.error_message,
        }

    def fetch_web_content_tool(self, url: str, max_chars: int = 3000) -> Dict[str, Any]:
        """Tool implementation to fetch and sanitize web content."""
        return self.search_engine.fetch_web_content(url, max_chars=max_chars)

    def deep_learning_tool(self, topic: str, content: str, source_url: str = "") -> Dict[str, Any]:
        """Tool implementation for deep learning ingestion."""
        return self.learning_pipeline.ingest_and_learn(topic, content, source_url=source_url or "internet://model_tool")

    def execute_search_and_learn(
        self,
        topic: str,
        num_results: int = 3,
    ) -> Dict[str, Any]:
        """Complete workflow: Safe search -> Extract -> Vector Store -> Continual SFT Learning."""
        # 1. Safe Search
        search_res = self.search_engine.search(topic, num_results=num_results)
        if not search_res.is_safe:
            return {
                "success": False,
                "error": search_res.error_message,
                "filter_verdict": search_res.filter_verdict,
                "topic": topic,
            }

        if not search_res.results:
            return {
                "success": False,
                "error": f"No web search results found for topic: {topic}",
                "topic": topic,
            }

        # 2. Extract & Learn from top results
        learned_entries = []
        for item in search_res.results:
            text_to_learn = f"{item.title}\n{item.snippet}"
            ingest_res = self.learning_pipeline.ingest_and_learn(
                topic=item.title,
                content=text_to_learn,
                source_url=item.url,
            )
            if ingest_res.get("success"):
                learned_entries.append(ingest_res)

        return {
            "success": True,
            "topic": topic,
            "sources_searched": len(search_res.results),
            "learned_entries_count": len(learned_entries),
            "learned_entries": learned_entries,
            "filter_verdict": search_res.filter_verdict,
            "sft_dataset_file": str(self.learning_pipeline.SFT_OUTPUT_FILE) if hasattr(self.learning_pipeline, "SFT_OUTPUT_FILE") else "data/sft/continual_web_learning.jsonl",
        }

    def query_model_with_internet(
        self,
        model_name: str,
        prompt: str,
        enable_search: bool = True,
        enable_deep_learning: bool = True,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """Query any Ollama model with Internet augmentation and automated deep learning.

        1. Audits prompt for safety.
        2. If internet search is needed, executes safe search and retrieves real-time knowledge.
        3. If enable_deep_learning is True, synthesizes learning pairs into knowledge store.
        4. Injects verified search context into the prompt.
        5. Queries model and returns grounded answer.
        """
        start_t = time.perf_counter()

        # Step 1: Safety audit
        audit = self.safety_filter.audit_query(prompt)
        if not audit.is_safe:
            return {
                "success": False,
                "error": f"Prompt blocked by safety filter: {'; '.join(audit.blocked_reasons)}",
                "filter_verdict": audit.verdict,
                "model_name": model_name,
                "response": "抱歉，检测到请求包含不合规或潜在风险信息，根据安全规范已被自动拦截。",
            }

        search_context = ""
        citations = []

        # Step 2: Search internet if enabled
        if enable_search:
            search_res = self.search_engine.search(audit.sanitized_text or prompt, num_results=3)
            if search_res.is_safe and search_res.results:
                citations = [r.to_dict() for r in search_res.results]
                snippets = [f"[{i+1}] {r.title}: {r.snippet} (来源: {r.url})" for i, r in enumerate(search_res.results)]
                search_context = "\n\n【最新互联网权威检索与制造资料】：\n" + "\n".join(snippets)

                # Step 3: Deep learning assimilation
                if enable_deep_learning:
                    for r in search_res.results[:2]:
                        self.learning_pipeline.ingest_and_learn(
                            topic=r.title,
                            content=r.snippet,
                            source_url=r.url,
                        )

        # Step 4: Construct augmented prompt
        augmented_prompt = prompt
        if search_context:
            augmented_prompt = f"{prompt}\n{search_context}\n\n请结合上述最新检索资料，以专业工业与制造工程规范进行严谨回答。"

        # Step 5: Query Ollama model
        model_response_text = ""
        model_ok = False
        failure_reason = ""
        try:
            payload = json.dumps({
                "model": model_name,
                "prompt": augmented_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_ctx": 4096,
                }
            }).encode("utf-8")

            req = urllib.request.Request(
                self.OLLAMA_GENERATE_URL,
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                model_response_text = data.get("response", "")
                model_ok = bool(model_response_text.strip())
                if not model_ok:
                    failure_reason = "Ollama 返回空响应"
        except Exception as e:
            logger.warning(f"Ollama inference error for model {model_name}: {e}")
            failure_reason = f"Ollama inference error: {type(e).__name__}: {e}"
            model_response_text = (
                "[模型不可用：以下仅为检索资料片段，不是模型回答，不得当作推理结果]：\n"
                + search_context
            )

        elapsed = (time.perf_counter() - start_t) * 1000.0

        return {
            "success": model_ok,
            "degraded": not model_ok,
            "reason": failure_reason or None,
            "model_name": model_name,
            "response": model_response_text,
            "internet_citations": citations,
            "safety_verdict": audit.verdict,
            "deep_learning_active": enable_deep_learning,
            "latency_ms": elapsed,
        }


# Global singleton
_GLOBAL_INTERNET_HUB: Optional[VirtuInternetHub] = None


def get_internet_hub() -> VirtuInternetHub:
    global _GLOBAL_INTERNET_HUB
    if _GLOBAL_INTERNET_HUB is None:
        _GLOBAL_INTERNET_HUB = VirtuInternetHub()
    return _GLOBAL_INTERNET_HUB
