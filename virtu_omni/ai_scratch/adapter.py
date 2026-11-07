"""Virtu AI Scratch Adapter.

Unified interface uniting:
1. Curriculum Registry (542 lessons, 20 phases)
2. First-Principles Computation Engine (Autograd, MHA, RoPE, KV-Cache, LoRA)
3. Interactive Placement Diagnostic & Tutor
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from virtu_omni.ai_scratch.curriculum import CurriculumRegistry, LessonMetadata, PhaseSummary
from virtu_omni.ai_scratch.engine import FirstPrinciplesEngine
from virtu_omni.ai_scratch.tutor import AIScratchTutor

logger = logging.getLogger("virtu_omni.ai_scratch.adapter")


class VirtuAIScratch:
    """Master adapter for ai-engineering-from-scratch within Virtu Foundation Model."""

    _instance: Optional[VirtuAIScratch] = None

    def __init__(self, repo_dir: Optional[Path | str] = None) -> None:
        self.registry = CurriculumRegistry(repo_dir=repo_dir)
        self.engine = FirstPrinciplesEngine()
        self.tutor = AIScratchTutor(registry=self.registry)
        self._ensure_ready()

    @classmethod
    def get_instance(cls, repo_dir: Optional[Path | str] = None) -> VirtuAIScratch:
        if cls._instance is None:
            cls._instance = cls(repo_dir=repo_dir)
        return cls._instance

    def _ensure_ready(self) -> None:
        try:
            self.registry.build_index()
        except Exception as err:
            logger.warning("Failed indexing AI Scratch curriculum on startup: %s", err)

    def get_overview(self) -> Dict[str, Any]:
        """Return system overview, phases count, total lessons, and status."""
        counts = self.registry.get_total_counts()
        phases = self.registry.list_phases()
        return {
            "name": "ai-engineering-from-scratch",
            "curriculum_available": self.registry.is_available(),
            "total_phases": counts["total_phases"],
            "total_lessons": counts["total_lessons"],
            "total_quiz_questions": counts["total_quiz_questions"],
            "phases": phases,
            "engine_capabilities": [
                "scalar_autograd_graph",
                "multi_head_attention_causal_kv_cache",
                "rms_norm",
                "swiglu",
                "lora_decomposition",
                "react_agent_loop",
                "cosine_vector_rag",
            ],
        }

    def get_lesson(self, phase_identifier: str, lesson_identifier: str) -> Optional[Dict[str, Any]]:
        """Fetch complete lesson data including metadata, doc text, and quiz."""
        lesson = self.registry.get_lesson(phase_identifier, lesson_identifier)
        if not lesson:
            return None

        doc = self.registry.get_lesson_doc(phase_identifier, lesson_identifier)
        code_files = self.registry.get_lesson_code(phase_identifier, lesson_identifier)

        res = lesson.to_dict()
        res["doc_markdown"] = doc
        res["code_contents"] = code_files
        return res

    def search_topics(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search curriculum for AI concepts, loss functions, or layers."""
        return self.registry.search_lessons(query=query, limit=limit)

    def run_autograd_verification(self, a_val: float = 2.0, b_val: float = -3.0) -> Dict[str, Any]:
        """Run numerical gradient check vs first-principles Value autograd DAG."""
        return self.engine.verify_autograd(a_val=a_val, b_val=b_val)

    def run_attention_forward(
        self, seq_len: int = 4, d_model: int = 64, num_heads: int = 4, causal: bool = True
    ) -> Dict[str, Any]:
        """Execute Multi-Head Attention from scratch with causal masking and KV cache."""
        return self.engine.compute_attention(
            seq_len=seq_len, d_model=d_model, num_heads=num_heads, causal=causal
        )

    def evaluate_placement(self, answers: Dict[str, int]) -> Dict[str, Any]:
        """Conduct placement test and evaluate proficiency."""
        return self.tutor.evaluate_placement(answers=answers)
