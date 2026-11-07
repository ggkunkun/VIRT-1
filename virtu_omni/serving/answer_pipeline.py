"""Serving-side answer cleanup: thinking hygiene followed by strict-format compilation."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from virtu_omni.serving.output_compiler import compile_output
from virtu_omni.serving.output_hygiene import hygiene, strip_think


@dataclass(frozen=True)
class CleanResult:
    text: str
    chars_before: int
    chars_after: int
    think_removed: bool
    loop_trimmed: bool
    compiler_applied: bool

    def to_dict(self) -> dict:
        return asdict(self)


def clean_served_answer(prompt: str, text: str, fix_arithmetic: bool = True) -> CleanResult:
    raw = text or ""
    visible = strip_think(raw)
    cleaned = hygiene(raw)
    compiled = compile_output(prompt, cleaned)
    if fix_arithmetic:
        try:
            from virtu_omni.serving.numeric_repair import fix_explicit_equation
            compiled = fix_explicit_equation(compiled)
        except Exception:
            pass
    return CleanResult(
        text=compiled,
        chars_before=len(raw),
        chars_after=len(compiled),
        think_removed=len(visible.strip()) < len(raw.strip()) or "<think>" in raw.lower(),
        loop_trimmed=len(cleaned) < len(visible.strip()),
        compiler_applied=compiled != cleaned,
    )
