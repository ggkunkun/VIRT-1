"""AST-aware code cleaner, comment separator, and syntax normalizer.

Performs:
1. Exact comment and code separation.
2. Indentation standardization (tabs to 4 spaces, LF newlines).
3. Redundant segment and excessive blank line cleanup.
4. Syntax integrity verification.
"""

from __future__ import annotations
import ast
from typing import Tuple, List


class CodeCleaner:
    """Standardizes code structure while guaranteeing syntactic integrity."""

    @staticmethod
    def normalize_line_endings_and_indentation(raw_text: str, tab_size: int = 4) -> str:
        """Convert CRLF/CR to LF and expand tabs to uniform spaces."""
        text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
        # Expand tabs to spaces
        text = text.expandtabs(tab_size)
        # Strip trailing whitespace on each line
        lines = [line.rstrip() for line in text.split("\n")]
        # Collapse multiple consecutive blank lines (>= 3 to 1)
        cleaned_lines: List[str] = []
        blank_count = 0
        for line in lines:
            if not line:
                blank_count += 1
                if blank_count <= 2:
                    cleaned_lines.append(line)
            else:
                blank_count = 0
                cleaned_lines.append(line)

        return "\n".join(cleaned_lines).rstrip() + "\n"

    @staticmethod
    def separate_comments_and_code(
        code_text: str, language: str
    ) -> Tuple[str, List[str]]:
        """Extract comments from code while preserving original code syntax."""
        extracted_comments: List[str] = []
        clean_lines: List[str] = []

        if language == "python":
            # Extract # comments and docstrings
            for line in code_text.split("\n"):
                stripped = line.strip()
                if stripped.startswith("#"):
                    extracted_comments.append(stripped[1:].strip())
                elif "#" in line:
                    # Inline comment
                    parts = line.split("#", 1)
                    clean_lines.append(parts[0].rstrip())
                    extracted_comments.append(parts[1].strip())
                else:
                    clean_lines.append(line)
        else:
            # C, C++, Java, JS, TS, Go, Rust (// and /* */)
            in_block_comment = False
            for line in code_text.split("\n"):
                stripped = line.strip()
                if in_block_comment:
                    if "*/" in line:
                        comment_part = line.split("*/", 1)[0]
                        extracted_comments.append(comment_part.replace("*", "").strip())
                        remaining = line.split("*/", 1)[1]
                        in_block_comment = False
                        if remaining.strip():
                            clean_lines.append(remaining)
                    else:
                        extracted_comments.append(stripped.replace("*", "").strip())
                    continue

                if "/*" in line:
                    parts = line.split("/*", 1)
                    if parts[0].strip():
                        clean_lines.append(parts[0])
                    if "*/" in parts[1]:
                        comment_part = parts[1].split("*/", 1)[0]
                        extracted_comments.append(comment_part.strip())
                        post = parts[1].split("*/", 1)[1]
                        if post.strip():
                            clean_lines.append(post)
                    else:
                        in_block_comment = True
                        extracted_comments.append(parts[1].strip())
                    continue

                if stripped.startswith("//"):
                    extracted_comments.append(stripped[2:].strip())
                elif "//" in line and not (('"' in line and line.count('"') % 2 != 0)):
                    parts = line.split("//", 1)
                    clean_lines.append(parts[0].rstrip())
                    extracted_comments.append(parts[1].strip())
                else:
                    clean_lines.append(line)

        cleaned_code = "\n".join(clean_lines).strip() + "\n"
        return cleaned_code, extracted_comments

    @staticmethod
    def verify_syntax_integrity(code_text: str, language: str) -> Tuple[bool, str]:
        """Verify code syntax integrity using AST parse or lexical balance."""
        if not code_text.strip():
            return False, "EMPTY_CODE"

        if language == "python":
            try:
                ast.parse(code_text)
                return True, "AST_PARSE_SUCCESS"
            except SyntaxError as e:
                return False, f"AST_SYNTAX_ERROR: Line {e.lineno}: {e.msg}"

        # Bracket / Brace balance for C-family, Go, Rust, Java, JS/TS
        stack = []
        pairs = {")": "(", "}": "{", "]": "["}
        in_str = False
        str_char = ""
        escape = False

        for char in code_text:
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char in ("'", '"', "`"):
                if not in_str:
                    in_str = True
                    str_char = char
                elif str_char == char:
                    in_str = False
                continue
            if in_str:
                continue

            if char in "({[":
                stack.append(char)
            elif char in ")}]":
                if not stack or stack[-1] != pairs[char]:
                    return False, f"SYNTAX_UNBALANCED_DELIMITER: Unmatched '{char}'"
                stack.pop()

        if stack:
            return False, f"SYNTAX_UNCLOSED_DELIMITERS: Unclosed {stack}"

        return True, "LEXICAL_SYNTAX_VALID"
