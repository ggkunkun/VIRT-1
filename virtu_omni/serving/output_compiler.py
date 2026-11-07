"""Prompt-conditioned output compilation for strict-format requests.

Only applies transformations the user asked for and that can be performed without
inventing content:

* pipe table -> CSV when the prompt asks for CSV;
* unwrap ``{"tool": ..., "arguments": {...}}`` when the prompt asks for a plain JSON
  object with named keys (never for tool-call requests);
* strip a short label when the prompt says "output only the string itself";
* split a one-line list when the prompt asks for exactly N lines.

A structured JSON answer is never rewritten except for the explicit unwrap case.
"""

from __future__ import annotations

import json
import re


def _parse_cells(row: str) -> list[str]:
    cells = [c.strip() for c in row.strip().strip("|").split("|")]
    return [c for c in cells if c != ""]


def _looks_separator(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{2,}:?", c) for c in cells)


def _prompt_table_width(prompt: str) -> int | None:
    for line in (prompt or "").splitlines():
        if line.count("|") >= 2:
            cells = _parse_cells(line)
            if len(cells) >= 2 and not _looks_separator(cells):
                return len(cells)
    return None


def markdown_table_to_csv(text: str, width: int | None = None) -> str | None:
    """Convert pipe-table content to CSV without touching cell values.

    Handles multi-line tables and greedy one-line outputs where all rows were
    emitted on a single line. Returns None when no complete table is found.
    """
    if "|" not in (text or ""):
        return None
    rows = []
    for line in text.splitlines():
        cells = _parse_cells(line)
        if not cells or _looks_separator(cells):
            continue
        rows.append(cells)
    if not rows:
        return None
    if len(rows) == 1 and width and len(rows[0]) > width and len(rows[0]) % width == 0:
        flat = rows[0]
        rows = [flat[i:i + width] for i in range(0, len(flat), width)]
    if len(rows) < 2:
        return None
    w = width or len(rows[0])
    if any(len(r) != w for r in rows):
        return None
    return "\n".join(",".join(r) for r in rows)


def _json_candidate(text: str):
    m = re.search(r"[\[{].*[\]}]", text or "", re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def _is_tool_request(prompt: str) -> bool:
    return bool(re.search(r"\btool\b|工具|调用|action\s*=", prompt or "", re.I))


UNWRAP_KEYS = {"result", "output", "data", "response", "answer", "payload"}


def unwrap_tool_envelope(prompt: str, text: str) -> str:
    if not re.search(r"json", prompt or "", re.I) or _is_tool_request(prompt):
        return text
    if not re.search(r"键|字段|\bkeys?\b", prompt or "", re.I):
        return text
    obj = _json_candidate(text)
    if not isinstance(obj, dict):
        return text
    if isinstance(obj.get("arguments"), dict):
        return json.dumps(obj["arguments"], ensure_ascii=False)
    if isinstance(obj.get("arguments"), str):
        try:
            inner = json.loads(obj["arguments"])
            if isinstance(inner, dict):
                return json.dumps(inner, ensure_ascii=False)
        except Exception:
            pass
    if len(obj) == 1:
        k = next(iter(obj.keys()))
        if str(k).lower() in UNWRAP_KEYS and isinstance(obj[k], dict):
            if not re.search(rf"\b{k}\b", prompt, re.I):
                return json.dumps(obj[k], ensure_ascii=False)
    return text


def strip_json_fence_and_preamble(prompt: str, text: str) -> str:
    """When strict JSON is asked, strip markdown fences and conversation preambles."""
    if not re.search(r"只输出|直接输出|仅输出|只给|only\s*output|pure\s*json", prompt or "", re.I):
        return text
    if not re.search(r"json", prompt or "", re.I):
        return text
    t = (text or "").strip()
    m = re.search(r"```(?:json|JSON)?\s*([\s\S]*?)```", t)
    cand = m.group(1).strip() if m else t
    m_json = re.search(r"[{}\[][\s\S]*[}\]]", cand)
    if m_json:
        try:
            obj = json.loads(m_json.group(0))
            return json.dumps(obj, ensure_ascii=False)
        except Exception:
            pass
    return text


def strip_output_label(prompt: str, text: str) -> str:
    if not re.search(r"只输出|不要任何其它文字|不加.{0,6}(说明|引号)|只回答", prompt or ""):
        return text
    if re.search(r"json|数组|对象|键", prompt or "", re.I):
        return text
    lines = [x for x in text.splitlines() if x.strip()]
    if len(lines) != 1:
        return text
    line = lines[0].strip()
    if line.startswith(("{", "[")):
        return text
    m = re.match(r"^[^，。；:：\n]{1,10}(?:是|为|：|:)\s*(.+)$", line)
    if m and m.group(1).strip():
        return m.group(1).strip()
    return text


def _requested_line_count(prompt: str) -> int | None:
    m = re.search(r"(?:恰好|共|输出)\s*(\d+)\s*行", prompt or "")
    return int(m.group(1)) if m else None


def split_one_line_list(prompt: str, text: str) -> str:
    n = _requested_line_count(prompt)
    if not n or re.search(r"json|数组|对象|键", prompt or "", re.I):
        return text
    lines = [x for x in text.splitlines() if x.strip()]
    if len(lines) != 1:
        return text
    line = lines[0].strip()
    if line.startswith(("{", "[")):
        return text
    parts = re.split(r"(?<=\s)(?=\d{1,2}[.、)]\s)|(?=\b[A-Z]{2,}\s*[:=])|"
                     r"(?<=[；;])\s*", line)
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) == n:
        return "\n".join(parts)
    return text


def compile_output(prompt: str, text: str) -> str:
    out = text
    if _json_candidate(out) is not None:
        unwrapped = unwrap_tool_envelope(prompt, out).strip()
        return strip_json_fence_and_preamble(prompt, unwrapped)
    if "CSV" in (prompt or "").upper() or re.search(r"竖线换成逗号|逗号分隔", prompt or ""):
        converted = markdown_table_to_csv(out, _prompt_table_width(prompt))
        if converted:
            out = converted
    out = strip_output_label(prompt, out)
    out = split_one_line_list(prompt, out)
    return out.strip()
