"""Curriculum Registry for AI Engineering from Scratch.

Indexes, parses, and resolves 542+ lessons across 20 phases from the local
repository clone at `external/ai-engineering-from-scratch/`.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("virtu_omni.ai_scratch.curriculum")

DEFAULT_REPO_PATH = Path(__file__).resolve().parent.parent.parent / "external" / "ai-engineering-from-scratch"


@dataclass
class QuizQuestion:
    stage: str
    question: str
    options: List[str]
    correct: int
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LessonMetadata:
    phase_id: str
    phase_title: str
    lesson_id: str
    lesson_title: str
    rel_path: str
    has_docs: bool = False
    has_code: bool = False
    has_quiz: bool = False
    has_outputs: bool = False
    code_files: List[str] = field(default_factory=list)
    output_files: List[str] = field(default_factory=list)
    quiz_questions: List[QuizQuestion] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["quiz_questions"] = [q.to_dict() for q in self.quiz_questions]
        return res


@dataclass
class PhaseSummary:
    phase_id: str
    slug: str
    title: str
    lesson_count: int
    lessons: List[LessonMetadata] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase_id": self.phase_id,
            "slug": self.slug,
            "title": self.title,
            "lesson_count": self.lesson_count,
            "lessons": [l.to_dict() for l in self.lessons],
        }


class CurriculumRegistry:
    """Discovers, parses, and caches curriculum data across all 20 phases."""

    def __init__(self, repo_dir: Optional[Path | str] = None) -> None:
        if repo_dir:
            self.repo_dir = Path(repo_dir)
        else:
            self.repo_dir = DEFAULT_REPO_PATH

        self.phases_dir = self.repo_dir / "phases"
        self._phases_cache: Dict[str, PhaseSummary] = {}
        self._lessons_cache: Dict[str, LessonMetadata] = {}
        self._is_indexed = False

    def is_available(self) -> bool:
        """Check if local cloned phases directory exists."""
        return self.phases_dir.exists() and self.phases_dir.is_dir()

    def build_index(self, force: bool = False) -> None:
        """Scan phases directory and build in-memory lookup index."""
        if self._is_indexed and not force:
            return

        self._phases_cache.clear()
        self._lessons_cache.clear()

        if not self.is_available():
            logger.warning("Curriculum phases directory not found at: %s", self.phases_dir)
            self._is_indexed = True
            return

        phase_dirs = sorted([d for d in self.phases_dir.iterdir() if d.is_dir() and re.match(r"^\d{2}-", d.name)])

        for p_dir in phase_dirs:
            slug = p_dir.name
            phase_num = slug.split("-")[0]
            title = slug[len(phase_num) + 1 :].replace("-", " ").title()

            phase_lessons: List[LessonMetadata] = []

            lesson_dirs = sorted([d for d in p_dir.iterdir() if d.is_dir() and re.match(r"^\d{2}-", d.name)])
            for l_dir in lesson_dirs:
                l_slug = l_dir.name
                l_num = l_slug.split("-")[0]
                l_title = l_slug[len(l_num) + 1 :].replace("-", " ").title()

                docs_path = l_dir / "docs" / "en.md"
                code_dir = l_dir / "code"
                outputs_dir = l_dir / "outputs"
                quiz_path = l_dir / "quiz.json"

                code_files = [f.name for f in code_dir.iterdir() if f.is_file()] if code_dir.exists() else []
                output_files = [f.name for f in outputs_dir.iterdir() if f.is_file()] if outputs_dir.exists() else []

                quiz_questions: List[QuizQuestion] = []
                if quiz_path.exists():
                    try:
                        with open(quiz_path, "r", encoding="utf-8") as qf:
                            q_data = json.load(qf)
                            for item in q_data.get("questions", []):
                                quiz_questions.append(
                                    QuizQuestion(
                                        stage=item.get("stage", "post"),
                                        question=item.get("question", ""),
                                        options=item.get("options", []),
                                        correct=item.get("correct", 0),
                                        explanation=item.get("explanation", ""),
                                    )
                                )
                    except Exception as err:
                        logger.debug("Failed parsing quiz for %s: %s", l_slug, err)

                rel_path = f"phases/{slug}/{l_slug}"
                meta = LessonMetadata(
                    phase_id=phase_num,
                    phase_title=title,
                    lesson_id=l_num,
                    lesson_title=l_title,
                    rel_path=rel_path,
                    has_docs=docs_path.exists(),
                    has_code=bool(code_files),
                    has_quiz=bool(quiz_questions),
                    has_outputs=bool(output_files),
                    code_files=code_files,
                    output_files=output_files,
                    quiz_questions=quiz_questions,
                )

                phase_lessons.append(meta)
                # Store by full key: "01/05" or "01-math-foundations/05-chain-rule-and-autodiff"
                self._lessons_cache[f"{phase_num}/{l_num}"] = meta
                self._lessons_cache[f"{slug}/{l_slug}"] = meta
                self._lessons_cache[l_slug] = meta

            summary = PhaseSummary(
                phase_id=phase_num,
                slug=slug,
                title=title,
                lesson_count=len(phase_lessons),
                lessons=phase_lessons,
            )
            self._phases_cache[phase_num] = summary
            self._phases_cache[slug] = summary

        self._is_indexed = True
        unique_phase_count = len({p.phase_id for p in self._phases_cache.values()})
        unique_lesson_count = len({l.rel_path for l in self._lessons_cache.values()})
        logger.info(
            "Indexed Curriculum: %d phases, %d total lessons",
            unique_phase_count,
            unique_lesson_count,
        )

    def list_phases(self) -> List[Dict[str, Any]]:
        """List all phases with summary metrics."""
        self.build_index()
        seen = set()
        res = []
        for phase in self._phases_cache.values():
            if phase.phase_id not in seen:
                seen.add(phase.phase_id)
                res.append(
                    {
                        "phase_id": phase.phase_id,
                        "slug": phase.slug,
                        "title": phase.title,
                        "lesson_count": phase.lesson_count,
                    }
                )
        return sorted(res, key=lambda x: int(x["phase_id"]))

    def get_phase(self, phase_identifier: str) -> Optional[PhaseSummary]:
        """Fetch phase by ID ('01') or slug ('01-math-foundations')."""
        self.build_index()
        return self._phases_cache.get(phase_identifier)

    def get_lesson(self, phase_identifier: str, lesson_identifier: str) -> Optional[LessonMetadata]:
        """Fetch lesson metadata by phase and lesson identifier."""
        self.build_index()
        key1 = f"{phase_identifier}/{lesson_identifier}"
        if key1 in self._lessons_cache:
            return self._lessons_cache[key1]

        # Try numeric matching
        p_num = phase_identifier.split("-")[0].zfill(2)
        l_num = lesson_identifier.split("-")[0].zfill(2)
        key2 = f"{p_num}/{l_num}"
        if key2 in self._lessons_cache:
            return self._lessons_cache[key2]

        return self._lessons_cache.get(lesson_identifier)

    def get_lesson_doc(self, phase_identifier: str, lesson_identifier: str) -> Optional[str]:
        """Read the markdown documentation for a specific lesson."""
        lesson = self.get_lesson(phase_identifier, lesson_identifier)
        if not lesson:
            return None
        doc_path = self.repo_dir / lesson.rel_path / "docs" / "en.md"
        if doc_path.exists():
            return doc_path.read_text(encoding="utf-8")
        return None

    def get_lesson_code(self, phase_identifier: str, lesson_identifier: str, filename: Optional[str] = None) -> Dict[str, str]:
        """Read implementation code files for a specific lesson."""
        lesson = self.get_lesson(phase_identifier, lesson_identifier)
        if not lesson:
            return {}
        code_dir = self.repo_dir / lesson.rel_path / "code"
        if not code_dir.exists():
            return {}

        results: Dict[str, str] = {}
        for f in code_dir.iterdir():
            if f.is_file() and (filename is None or f.name == filename):
                try:
                    results[f.name] = f.read_text(encoding="utf-8")
                except Exception as err:
                    logger.debug("Failed reading %s: %s", f.name, err)
        return results

    def search_lessons(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search across all lessons by title, slug, or topics."""
        self.build_index()
        q = query.lower()
        matches = []
        seen = set()

        for lesson in self._lessons_cache.values():
            if lesson.rel_path in seen:
                continue
            score = 0
            if q in lesson.lesson_title.lower():
                score += 10
            if q in lesson.rel_path.lower():
                score += 5
            if q in lesson.phase_title.lower():
                score += 2

            if score > 0:
                seen.add(lesson.rel_path)
                matches.append((score, lesson.to_dict()))

        matches.sort(key=lambda x: x[0], reverse=True)
        return [m[1] for m in matches[:limit]]

    def get_total_counts(self) -> Dict[str, int]:
        """Return total phases, lessons, quizzes, and code implementations."""
        self.build_index()
        unique_phases = len({p.phase_id for p in self._phases_cache.values()})
        unique_lessons = len({l.rel_path for l in self._lessons_cache.values()})
        total_quizzes = sum(len(l.quiz_questions) for l in {l.rel_path: l for l in self._lessons_cache.values()}.values())
        return {
            "total_phases": unique_phases,
            "total_lessons": unique_lessons,
            "total_quiz_questions": total_quizzes,
        }
