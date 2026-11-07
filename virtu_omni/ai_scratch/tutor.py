"""Interactive Tutor and Placement Diagnostic for AI Engineering from Scratch.

Evaluates student or AI agent skill levels, recommends starting phases,
and generates structured study plans in `LEARNING.md`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from virtu_omni.ai_scratch.curriculum import CurriculumRegistry, LessonMetadata, QuizQuestion


@dataclass
class PlacementQuestion:
    id: str
    phase_id: str
    topic: str
    question: str
    options: List[str]
    correct: int
    rationale: str


DIAGNOSTIC_QUESTIONS: List[PlacementQuestion] = [
    PlacementQuestion(
        id="q1_autodiff",
        phase_id="01",
        topic="Math & Autodiff",
        question="Why does PyTorch/LLM training use reverse-mode automatic differentiation rather than forward-mode?",
        options=[
            "Forward mode cannot calculate second-order derivatives",
            "Reverse mode computes gradients for millions of parameters in a single backward pass for a scalar loss",
            "Reverse mode avoids using any GPU memory for intermediate activations",
            "Forward mode is mathematically incompatible with non-linear activation functions",
        ],
        correct=1,
        rationale="Deep networks output a single scalar loss from millions of weight parameters; reverse mode computes all dLoss/dW in O(1) backward passes.",
    ),
    PlacementQuestion(
        id="q2_attention",
        phase_id="07",
        topic="Attention & Transformers",
        question="In Multi-Head Attention, why are the dot products of Q and K divided by sqrt(d_k) before applying softmax?",
        options=[
            "To prevent vanishing gradients during the backward pass",
            "To ensure the dot products don't scale with sqrt(d_k), preventing softmax saturation and near-zero gradients",
            "To normalize the matrix eigenvalues to 1.0",
            "To enforce causality in autoregressive generation",
        ],
        correct=1,
        rationale="For large d_k, the dot products grow large in magnitude, pushing softmax into regions with extremely small gradients. Dividing by sqrt(d_k) stabilizes the variance.",
    ),
    PlacementQuestion(
        id="q3_kvcache",
        phase_id="07",
        topic="Inference & KV-Cache",
        question="During autoregressive LLM decoding, what is the primary benefit of KV-Caching?",
        options=[
            "It avoids recomputing Key and Value vectors for past tokens, turning O(N^2) token generation into O(N) per step",
            "It quantizes the weights from FP16 to INT4 dynamically",
            "It eliminates the need for causal attention masking",
            "It compresses context window length by 50%",
        ],
        correct=0,
        rationale="Without KV-Cache, generating each new token re-computes attention over all previous tokens. KV-Cache stores past keys/values in memory so only the new query is computed.",
    ),
    PlacementQuestion(
        id="q4_lora",
        phase_id="11",
        topic="Fine-Tuning & LoRA",
        question="In Low-Rank Adaptation (LoRA), given a weight matrix W0 of shape (d, k), how is the update delta W represented?",
        options=[
            "As a diagonal sparse matrix with non-zero elements at critical weights",
            "As the product B * A, where B is (d, r) initialized to 0 and A is (r, k) initialized to Gaussian, with r << min(d, k)",
            "As an INT8 quantized delta table stored in flash memory",
            "As a low-pass Fourier transform of the gradients",
        ],
        correct=1,
        rationale="LoRA freezes W0 and decomposes the update into B * A with low rank r, reducing trainable parameters by up to 99%.",
    ),
    PlacementQuestion(
        id="q5_react",
        phase_id="14",
        topic="Agent Engineering & Tool Use",
        question="What core problem does the ReAct (Reasoning + Acting) pattern solve in autonomous AI agents?",
        options=[
            "It eliminates the need for prompt engineering",
            "It allows the model to induce, track, and update action plans while handling exceptions via dynamic reasoning scratchpads",
            "It speeds up inference throughput by bypassing tokenizer lookups",
            "It provides deterministic cryptographic guarantees for tool outputs",
        ],
        correct=1,
        rationale="ReAct interleaves reasoning traces ('Thought') with task-specific actions ('Action' / 'Observation'), improving error recovery and plan adherence.",
    ),
]


class AIScratchTutor:
    """Diagnostic evaluator and personalized curriculum tutor."""

    def __init__(self, registry: Optional[CurriculumRegistry] = None) -> None:
        self.registry = registry or CurriculumRegistry()
        self.registry.build_index()

    def get_diagnostic_questions(self) -> List[Dict[str, Any]]:
        """Return placement test questions."""
        return [
            {
                "id": q.id,
                "phase_id": q.phase_id,
                "topic": q.topic,
                "question": q.question,
                "options": q.options,
            }
            for q in DIAGNOSTIC_QUESTIONS
        ]

    def evaluate_placement(self, answers: Dict[str, int]) -> Dict[str, Any]:
        """
        Evaluate user/agent answers to placement questions.
        answers: {"q1_autodiff": 1, "q2_attention": 1, ...}
        """
        score = 0
        total = len(DIAGNOSTIC_QUESTIONS)
        details = []

        for q in DIAGNOSTIC_QUESTIONS:
            ans = answers.get(q.id)
            is_correct = ans == q.correct
            if is_correct:
                score += 1

            details.append(
                {
                    "id": q.id,
                    "topic": q.topic,
                    "phase_id": q.phase_id,
                    "given_answer": ans,
                    "correct_answer": q.correct,
                    "is_correct": is_correct,
                    "rationale": q.rationale,
                }
            )

        ratio = score / total
        if ratio <= 0.2:
            recommended_phase = "01-math-foundations"
            level = "Novice / Foundations"
        elif ratio <= 0.6:
            recommended_phase = "07-transformers-deep-dive"
            level = "Intermediate / Transformers"
        elif ratio <= 0.8:
            recommended_phase = "11-llm-engineering"
            level = "Advanced / LLM Engineering & SFT"
        else:
            recommended_phase = "14-agent-engineering"
            level = "Expert / Autonomous Multi-Agent Swarms"

        phase_obj = self.registry.get_phase(recommended_phase)
        recommended_lessons = [l.to_dict() for l in phase_obj.lessons[:5]] if phase_obj else []

        return {
            "score": score,
            "total": total,
            "accuracy_percentage": round(ratio * 100, 1),
            "assessed_level": level,
            "recommended_starting_phase": recommended_phase,
            "recommended_lessons": recommended_lessons,
            "question_evaluations": details,
        }

    def generate_learning_plan_markdown(
        self,
        user_name: str,
        evaluation: Dict[str, Any],
        target_path: Optional[Path | str] = None,
    ) -> str:
        """Create or update LEARNING.md study plan."""
        rec_phase = evaluation.get("recommended_starting_phase", "01-math-foundations")
        level = evaluation.get("assessed_level", "Foundations")
        acc = evaluation.get("accuracy_percentage", 0.0)

        lines = [
            f"# LEARNING.md — AI Engineering from Scratch",
            f"",
            f"> **Learner / Agent**: `{user_name}`",
            f"> **Diagnostic Assessment**: {level} ({acc}% score)",
            f"> **Starting Phase**: `{rec_phase}`",
            f"",
            f"## Active Curriculum Plan",
            f"",
            f"| Phase | Title | Status | Goal / First-Principles Artifact |",
            f"| :--- | :--- | :--- | :--- |",
        ]

        phases = self.registry.list_phases()
        for p in phases:
            status = "[x] Completed" if p["slug"] < rec_phase else ("[>] In Progress" if p["slug"] == rec_phase else "[ ] Upcoming")
            lines.append(f"| `Phase {p['phase_id']}` | {p['title']} | {status} | Implement core modules & verify tests |")

        lines.extend([
            f"",
            f"## Next Action Steps",
            f"1. Start with lesson: `{rec_phase}`",
            f"2. Implement core math without frameworks (`build it`)",
            f"3. Verify against production library (`use it`)",
            f"4. Run lesson quiz (`quiz.json`) and pass with >= 80% score.",
        ])

        md_content = "\n".join(lines)
        if target_path:
            p = Path(target_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(md_content, encoding="utf-8")

        return md_content
