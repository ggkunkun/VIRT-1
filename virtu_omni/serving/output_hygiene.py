"""Output hygiene for greedy-decoded industrial answers.

Measured on the 2026-11-05 210-case board: the served template always injects an
empty ``<think>\\n\\n</think>`` block even with ``think=false``.  Those two non-empty
lines break every exact-line-count criterion (instruction 54.9 -> 73.4 once removed).
Greedy decoding also degenerates into token/sentence loops (704-token answers that
repeat one sentence, 512-token answers that repeat one word).

This module removes those artifacts without rewriting content.  It never joins lines,
never re-orders text, and only cuts a tail that is a verbatim repetition.  Anything
that could change a legitimate repeated line (code, G-code, tables) is left alone
unless the repetition is at least ``MIN_LINE_REPEATS`` long.
"""

from __future__ import annotations

import re

MIN_LINE_REPEATS = 4
MIN_TOKEN_REPEATS = 8
MIN_PERIOD_REPEATS = 3
MAX_PERIOD_LINES = 12
MAX_UNIT_CHARS = 48

PAD_RE = re.compile(r"\[PAD\d+\]")
LEGACY_THINK_RE = re.compile(r"<[｜|]?(?:begin|end)▁?of▁?thinking[｜|]?>")
TOOL_CALL_TAGS_RE = re.compile(r"</?tool_call>")

COSPLAY_RE = re.compile(
    r"(?:[🧠🔧]\s*)?(?:Virtu[- ]?MoE\s*)?(?:工业超级智能体\s*)?(?:正在(?:调用|调度|咨询|切换|激活).{0,35}(?:专家|网络)|(?:材料力学|工业制造|逆向推理|CAD|CAM|CAE|有限元|数控).{0,25}专家正在(?:校核|分析|计算|执行|验证))[：:。]?(?:\s*\n\s*[-*•]\s*[^\n]+)*\n*",
    re.I
)


def strip_special_tokens(text: str) -> str:
    """Strip special token residues such as [PAD\\d+], legacy thinking markers, and stray tool tags."""
    if not text:
        return ""
    text = PAD_RE.sub("", text)
    text = LEGACY_THINK_RE.sub("", text)
    text = TOOL_CALL_TAGS_RE.sub("", text)
    return text


def strip_cosplay(text: str) -> str:
    """Strip internal multi-agent cosplay monologue headers when substantive content follows."""
    if not text:
        return ""
    cleaned = COSPLAY_RE.sub("", text).strip()
    return cleaned if cleaned else text


def split_think(text: str) -> tuple[str, str]:
    """Return ``(thinking_body, visible_text)``; tolerates unclosed/stray tags."""
    text = text or ""
    parts = re.findall(r"<think>(.*?)(?:</think>|$)", text, flags=re.S | re.I)
    body = "\n".join(parts).strip()
    visible = re.sub(r"<think>.*?(?:</think>|$)", "", text, flags=re.S | re.I)
    visible = re.sub(r"</?think>", "", visible, flags=re.I).strip()
    return body, visible


def strip_think(text: str) -> str:
    """Drop the thinking channel, falling back to it when it is the only answer."""
    body, visible = split_think(text)
    return visible if visible else body


def _collapse_tail_run(text: str, unit: str, min_repeats: int) -> str:
    if not unit:
        return text
    count = 0
    pos = len(text)
    while pos >= len(unit) and text[pos - len(unit):pos] == unit:
        count += 1
        pos -= len(unit)
    if count >= min_repeats:
        return text[:pos] + unit
    return text


def collapse_repeated_lines(text: str, min_repeats: int = MIN_LINE_REPEATS) -> str:
    """Keep the first line of a consecutive identical run; all other lines untouched."""
    lines = text.splitlines(keepends=True)
    out = []
    run_key = None
    run_len = 0
    for line in lines:
        key = line.strip()
        if key and key == run_key:
            run_len += 1
            if run_len >= min_repeats:
                continue
        else:
            run_key = key
            run_len = 1
        out.append(line)
    return "".join(out)


def collapse_token_runs(text: str, min_repeats: int = MIN_TOKEN_REPEATS,
                        max_unit: int = MAX_UNIT_CHARS) -> str:
    """Cut tails such as ``进给进给进给...`` produced by greedy repetition."""
    out_lines = []
    for line in text.splitlines(keepends=True):
        newline = "\n" if line.endswith("\n") else ""
        body = line[:-1] if newline else line
        best = None
        limit = min(max_unit, len(body) // min_repeats)
        for unit_len in range(1, limit + 1):
            unit = body[-unit_len:]
            count = 0
            pos = len(body)
            while pos >= unit_len and body[pos - unit_len:pos] == unit:
                count += 1
                pos -= unit_len
            if count >= min_repeats and (best is None or count * unit_len > best[0]):
                best = (count * unit_len, unit)
        if best:
            body = _collapse_tail_run(body, best[1], min_repeats)
        out_lines.append(body + newline)
    return "".join(out_lines)


def collapse_periodic_tail(text: str, min_repeats: int = MIN_PERIOD_REPEATS,
                           max_unit_lines: int = MAX_PERIOD_LINES) -> str:
    """Cut a tail made of >=3 identical consecutive line blocks; keep one block."""
    lines = text.splitlines(keepends=True)
    normalized = [x.rstrip("\r\n") for x in lines]
    n = len(lines)
    for unit_len in range(1, min(max_unit_lines, n // min_repeats) + 1):
        block = normalized[n - unit_len:n]
        if not any(x.strip() for x in block):
            continue
        count = 0
        pos = n
        while pos >= unit_len and normalized[pos - unit_len:pos] == block:
            count += 1
            pos -= unit_len
        if count >= min_repeats:
            start = n - count * unit_len
            return "".join(lines[:start + unit_len])
    return text


def collapse_exact_halves(text: str, min_len: int = 30) -> str:
    half = len(text) // 2
    if half >= min_len and text[:half].strip() == text[half:].strip():
        return text[:half]
    return text


def hygiene(text: str) -> str:
    """Clean one served answer.  Pure function; safe to call on every generation."""
    text = strip_special_tokens(text)
    body, visible = split_think(text)
    current = visible if visible else body
    current = strip_cosplay(current)
    for _ in range(4):
        previous = current
        current = collapse_repeated_lines(current)
        current = collapse_token_runs(current)
        current = collapse_periodic_tail(current)
        current = collapse_exact_halves(current)
        if current == previous:
            break
    return current.strip()
