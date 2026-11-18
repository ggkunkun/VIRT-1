#!/usr/bin/env python3
"""Antigravity rule-budget guard for D:/Virtu模型.

Simulates the two documented Google Antigravity limits locally:

  1. 24,000 bytes per rule file (after expanding @[label](path) includes).
     A file over the limit is truncated from the tail, silently.
  2. 20,000 tokens aggregate for always-on rules + frontmatter-less
     AGENTS.md / GEMINI.md. Over budget, the largest files are demoted
     to pointers.

It also enforces the local contract added on 2026-11-15: AGENTS.md is
37 KB and therefore truncated by Antigravity, so
.agents/rules/virtu-constitution-tail.md must stay byte-identical to
AGENTS.md from "## 8. " onward, and that start offset must still sit
below the real truncation point with room to spare.

Exit code 0 = PASS, 1 = FAIL. Safe to run in CI or before a commit.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILE_LIMIT_BYTES = 24_000
TOKEN_BUDGET = 20_000
VALID_TRIGGERS = {"always_on", "model_decision", "glob", "manual"}
# Measured on 2026-11-15 (Antigravity 2.32.1): limit 24000 but only ~23842
# bytes survived (truncated by 13794 of 37636), i.e. a ~158-byte reserve.
TRUNCATE_RESERVE_BYTES = 158
SAFETY_MARGIN_BYTES = 512
TAIL_RULE = ROOT / ".agents" / "rules" / "virtu-constitution-tail.md"
TAIL_MARKER = "## 8. "
TAIL_MARKER_RE = re.compile(r"^## 8\. ", re.M)
INCLUDE_RE = re.compile(r"@\[[^\]]*\]\(([^)]+)\)")


def estimate_tokens(text: str) -> int:
    """Rough token estimate: 1 per CJK char, 1 per 4 other chars."""
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    return cjk + (len(text) - cjk) // 4


def expand_includes(text: str, base: Path) -> str:
    def repl(match: re.Match[str]) -> str:
        target = Path(match.group(1))
        if not target.is_absolute():
            target = (base / target).resolve()
        try:
            body = target.read_text(encoding="utf-8")
        except OSError:
            return match.group(0)
        return re.sub(r"\A---\n.*?\n---\n", "", body, flags=re.S)

    return INCLUDE_RE.sub(repl, text)


def parse_frontmatter(text: str) -> dict[str, str] | None:
    m = re.match(r"\A---\n(.*?)\n---\n", text, flags=re.S)
    if not m:
        return None
    data: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            key, _, value = line.partition(":")
            data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def body_after_marker(text: str) -> str | None:
    """Return text from the '## 8. ' heading (line-start only) to EOF."""
    m = TAIL_MARKER_RE.search(text)
    return None if m is None else text[m.start():]


def main() -> int:
    failures: list[str] = []
    warnings: list[str] = []
    rows: list[tuple[str, int, int, str]] = []
    always_on_tokens = 0
    headroom_note = ""

    candidates: list[Path] = []
    for name in ("AGENTS.md", "GEMINI.md"):
        path = ROOT / name
        if path.is_file():
            candidates.append(path)
    rules_dir = ROOT / ".agents" / "rules"
    if rules_dir.is_dir():
        candidates.extend(sorted(p for p in rules_dir.glob("*.md") if p.is_file()))

    if not candidates:
        print("FAIL: no rule files found")
        return 1

    for path in candidates:
        rel = path.relative_to(ROOT).as_posix()
        raw = path.read_text(encoding="utf-8")
        expanded = expand_includes(raw, path.parent)
        size = len(expanded.encode("utf-8"))
        tokens = estimate_tokens(expanded)
        fm = parse_frontmatter(raw)

        if fm is None:
            mode = "always_on (no frontmatter)"
            always_on_tokens += tokens
        else:
            trigger = fm.get("trigger", "")
            if trigger not in VALID_TRIGGERS:
                failures.append(f"{rel}: invalid trigger {trigger!r}; Antigravity drops this rule silently")
                mode = "dropped"
            else:
                mode = trigger
                if trigger == "always_on":
                    always_on_tokens += tokens
                if trigger == "model_decision" and not fm.get("description"):
                    failures.append(f"{rel}: model_decision without description")
                if trigger == "glob" and not fm.get("globs"):
                    failures.append(f"{rel}: glob trigger without globs")

        if rel.startswith(".agents/rules/") and fm is None:
            failures.append(f"{rel}: files under .agents/rules/ must start with YAML frontmatter")

        if size > FILE_LIMIT_BYTES:
            over = size - FILE_LIMIT_BYTES
            if rel == "AGENTS.md" and TAIL_RULE.is_file():
                mode += f" [truncated {over}B, tail covered by {TAIL_RULE.name}]"
            else:
                failures.append(f"{rel}: {size} bytes, {over} bytes will be truncated")
        if "\r\n" in raw:
            warnings.append(f"{rel}: CRLF line endings")
        if raw.startswith("\ufeff"):
            warnings.append(f"{rel}: UTF-8 BOM present")

        rows.append((rel, size, tokens, mode))

    if always_on_tokens > TOKEN_BUDGET:
        failures.append(
            f"always_on total {always_on_tokens} tokens > {TOKEN_BUDGET} budget; "
            "largest files get demoted to pointers"
        )

    if TAIL_RULE.is_file():
        agents_text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        agents_tail = body_after_marker(agents_text)
        rule_tail = body_after_marker(TAIL_RULE.read_text(encoding="utf-8"))
        if agents_tail is None:
            failures.append(f"AGENTS.md: marker {TAIL_MARKER!r} not found; cannot verify tail rule")
        elif rule_tail is None:
            failures.append(f"{TAIL_RULE.name}: marker {TAIL_MARKER!r} not found")
        elif agents_tail != rule_tail:
            failures.append(
                f"{TAIL_RULE.name}: stale — AGENTS.md changed after {TAIL_MARKER!r}, "
                "regenerate the tail rule"
            )

        m = TAIL_MARKER_RE.search((ROOT / "AGENTS.md").read_text(encoding="utf-8"))
        marker_offset = (
            len((ROOT / "AGENTS.md").read_text(encoding="utf-8")[: m.start()].encode("utf-8"))
            if m
            else -1
        )
        safe_ceiling = FILE_LIMIT_BYTES - TRUNCATE_RESERVE_BYTES - SAFETY_MARGIN_BYTES
        if marker_offset < 0:
            pass
        elif marker_offset > safe_ceiling:
            failures.append(
                f"coverage gap risk: tail rule starts at byte {marker_offset} but Antigravity "
                f"keeps only ~{safe_ceiling} bytes; move the start marker earlier"
            )
        else:
            headroom_note = (
                f"tail start      : byte {marker_offset} "
                f"({safe_ceiling - marker_offset} bytes headroom before a coverage gap)"
            )
    else:
        agents_size = (ROOT / "AGENTS.md").stat().st_size if (ROOT / "AGENTS.md").is_file() else 0
        if agents_size > FILE_LIMIT_BYTES:
            failures.append("AGENTS.md exceeds 24,000 bytes and no tail rule exists to cover the cut")

    width = max(len(r[0]) for r in rows)
    print(f"{'file'.ljust(width)}  {'bytes':>7}  {'~tokens':>7}  mode")
    for rel, size, tokens, mode in rows:
        print(f"{rel.ljust(width)}  {size:>7}  {tokens:>7}  {mode}")
    print(f"\nalways_on tokens: {always_on_tokens} / {TOKEN_BUDGET}")
    print(f"per-file limit  : {FILE_LIMIT_BYTES} bytes")
    if headroom_note:
        print(headroom_note)

    for w in warnings:
        print(f"WARN  {w}")
    for f in failures:
        print(f"FAIL  {f}")
    if failures:
        print(f"\nRESULT: FAIL ({len(failures)} issue(s))")
        return 1
    print("\nRESULT: PASS — Antigravity gets the full constitution")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
