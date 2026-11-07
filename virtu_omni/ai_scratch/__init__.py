"""Virtu Omni x AI Engineering from Scratch.

First-principles AI Engineering curriculum, computation engine, and interactive tutor.
"""

from virtu_omni.ai_scratch.adapter import VirtuAIScratch
from virtu_omni.ai_scratch.curriculum import (
    CurriculumRegistry,
    LessonMetadata,
    PhaseSummary,
    QuizQuestion,
)
from virtu_omni.ai_scratch.engine import (
    FirstPrinciplesEngine,
    LLMPrimitives,
    MultiHeadAttentionScratch,
    RAGVectorIndexScratch,
    ReActAgentLoop,
    Value,
)
from virtu_omni.ai_scratch.tutor import AIScratchTutor, DIAGNOSTIC_QUESTIONS

__all__ = [
    "VirtuAIScratch",
    "CurriculumRegistry",
    "FirstPrinciplesEngine",
    "Value",
    "MultiHeadAttentionScratch",
    "LLMPrimitives",
    "ReActAgentLoop",
    "RAGVectorIndexScratch",
    "AIScratchTutor",
    "DIAGNOSTIC_QUESTIONS",
    "LessonMetadata",
    "PhaseSummary",
    "QuizQuestion",
]
