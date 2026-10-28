"""Syntax-aware multi-language code tokenizer.

Preserves:
1. Indentation levels (<|indent:2|>, <|indent:4|>, <|indent:8|>).
2. Multi-character operators (->, =>, ::, !=, ==, etc.).
3. Language boundary markers (<|lang:python|>, <|lang:java|>, etc.).
4. Fill-in-the-Middle (FIM) structural tags (<|fim_prefix|>, <|fim_suffix|>, <|fim_middle|>).
5. Byte-level fallback guaranteeing 0 OOV rate.
"""

from __future__ import annotations
import re
from typing import List, Dict


class SyntaxAwareCodeTokenizer:
    """Production syntax-aware tokenizer for code LLM training."""

    SPECIAL_TOKENS = [
        "<|pad|>",
        "<|bos|>",
        "<|eos|>",
        "<|unk|>",
        "<|fim_prefix|>",
        "<|fim_suffix|>",
        "<|fim_middle|>",
        "<|repo_name|>",
        "<|file_sep|>",
        "<|newline|>",
        "<|indent:2|>",
        "<|indent:4|>",
        "<|indent:8|>",
        "<|lang:python|>",
        "<|lang:java|>",
        "<|lang:cpp|>",
        "<|lang:c|>",
        "<|lang:go|>",
        "<|lang:rust|>",
        "<|lang:typescript|>",
        "<|lang:javascript|>",
    ]

    OPERATORS = [
        "::", "->", "=>", "==", "!=", "<=", ">=", "&&", "||",
        "++", "--", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=",
        "<<", ">>", "...", "/*", "*/", "//",
    ]

    def __init__(self, vocab_size: int = 64000) -> None:
        self.vocab_size = vocab_size
        self.token_to_id: Dict[str, int] = {}
        self.id_to_token: Dict[int, str] = {}

        # 1. Register special tokens
        for idx, token in enumerate(self.SPECIAL_TOKENS):
            self.token_to_id[token] = idx
            self.id_to_token[idx] = token

        # 2. Register multi-character operators
        curr_id = len(self.SPECIAL_TOKENS)
        for op in self.OPERATORS:
            self.token_to_id[op] = curr_id
            self.id_to_token[curr_id] = op
            curr_id += 1

        # 3. Register single ASCII bytes (0 - 255) to guarantee 0 OOV
        self.byte_offset = curr_id
        for b in range(256):
            token_str = f"<|b_{b}|>"
            self.token_to_id[token_str] = self.byte_offset + b
            self.id_to_token[self.byte_offset + b] = token_str

        # Build fast regex splitter
        escaped_ops = [re.escape(op) for op in sorted(self.OPERATORS, key=len, reverse=True)]
        pattern = (
            r"(?P<INDENT>^[ ]+)"
            r"|(?P<NEWLINE>\n)"
            r"|(?P<OP>" + "|".join(escaped_ops) + r")"
            r"|(?P<IDENT>[a-zA-Z_][a-zA-Z0-9_]*)"
            r"|(?P<NUM>[0-9]+)"
            r"|(?P<PUNCT>[^\s\w])"
            r"|(?P<SPACE>[ ]+)"
        )
        self.lexer_re = re.compile(pattern, re.MULTILINE)

    @property
    def pad_token_id(self) -> int:
        return self.token_to_id["<|pad|>"]

    @property
    def bos_token_id(self) -> int:
        return self.token_to_id["<|bos|>"]

    @property
    def eos_token_id(self) -> int:
        return self.token_to_id["<|eos|>"]

    @property
    def fim_prefix_id(self) -> int:
        return self.token_to_id["<|fim_prefix|>"]

    @property
    def fim_suffix_id(self) -> int:
        return self.token_to_id["<|fim_suffix|>"]

    @property
    def fim_middle_id(self) -> int:
        return self.token_to_id["<|fim_middle|>"]

    def encode(self, code: str, language: str = "generic") -> List[int]:
        """Convert source code string to syntax-aware token IDs."""
        tokens: List[int] = [self.bos_token_id]

        # Insert language boundary token if supported
        lang_tag = f"<|lang:{language.lower()}|>"
        if lang_tag in self.token_to_id:
            tokens.append(self.token_to_id[lang_tag])

        for match in self.lexer_re.finditer(code):
            val = match.group(0)

            if match.group("INDENT"):
                spaces = len(val)
                while spaces >= 8:
                    tokens.append(self.token_to_id["<|indent:8|>"])
                    spaces -= 8
                while spaces >= 4:
                    tokens.append(self.token_to_id["<|indent:4|>"])
                    spaces -= 4
                while spaces >= 2:
                    tokens.append(self.token_to_id["<|indent:2|>"])
                    spaces -= 2
                for _ in range(spaces):
                    tokens.append(self.byte_offset + ord(" "))

            elif match.group("NEWLINE"):
                tokens.append(self.token_to_id["<|newline|>"])

            elif match.group("OP") and val in self.token_to_id:
                tokens.append(self.token_to_id[val])

            else:
                # Fast byte fallback
                for b in val.encode("utf-8"):
                    tokens.append(self.byte_offset + b)

        tokens.append(self.eos_token_id)
        return tokens

    def decode(self, token_ids: List[int]) -> str:
        """Convert token IDs back to reconstructed source code."""
        byte_buffer = bytearray()
        parts: List[str] = []

        def flush_bytes() -> None:
            nonlocal byte_buffer
            if byte_buffer:
                parts.append(byte_buffer.decode("utf-8", errors="replace"))
                byte_buffer = bytearray()

        for tid in token_ids:
            if tid in (self.bos_token_id, self.eos_token_id, self.pad_token_id):
                continue
            token_str = self.id_to_token.get(tid, "")

            if token_str.startswith("<|lang:") or token_str in (
                "<|fim_prefix|>", "<|fim_suffix|>", "<|fim_middle|>"
            ):
                continue
            elif token_str == "<|newline|>":
                flush_bytes()
                parts.append("\n")
            elif token_str == "<|indent:8|>":
                flush_bytes()
                parts.append("        ")
            elif token_str == "<|indent:4|>":
                flush_bytes()
                parts.append("    ")
            elif token_str == "<|indent:2|>":
                flush_bytes()
                parts.append("  ")
            elif token_str in self.token_to_id and token_str in self.OPERATORS:
                flush_bytes()
                parts.append(token_str)
            elif token_str.startswith("<|b_") and token_str.endswith("|>"):
                b_val = int(token_str[4:-2])
                byte_buffer.append(b_val)
            else:
                flush_bytes()
                parts.append(token_str)

        flush_bytes()
        return "".join(parts)
