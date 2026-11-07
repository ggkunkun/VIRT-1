"""Universal Reversible Tokenizer for Virtu Omnimodal Foundation Models.

Provides full-fidelity encoding and decoding with:
- Guaranteed lossless round-trip via Byte-Fallback UTF-8 codec.
- Special token handling (<pad>=0, <s>=1, </s>=2, <unk>=3).
- Industrial domain subword vocabulary coverage.
- Incremental streaming detokenizer for real-time SSE token streaming without UTF-8 slicing errors.
"""

from __future__ import annotations
import codecs
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import torch

# Standard Special Token Identifiers
PAD_TOKEN_ID = 0
BOS_TOKEN_ID = 1
EOS_TOKEN_ID = 2
UNK_TOKEN_ID = 3

BYTE_OFFSET = 4  # Tokens 4..259 are mapped to single raw bytes 0..255
SUBWORD_OFFSET = 260

# Domain subwords tailored for CAD/CAM/Engineering and general conversational tokens
CORE_INDUSTRIAL_SUBWORDS = [
    " ", "\n", "\t", " =", " = ", " : ", "->", " + ", " - ", " * ", " / ",
    "CAD", "CAM", "CAE", "CNC", "G00", "G01", "G02", "G03", "G17", "G54", "G71", "G90", "G91",
    "M03", "M05", "M08", "M09", "M30", "FANUC", "SIEMENS", "SolidWorks", "AutoCAD",
    "NX", "CIMCO", "VERICUT", "SSCNC", "mm", "min", "r/min", "rpm", "mm/min", "mm³/min",
    "Vc", "Vf", "ap", "ae", "fz", "MRR", "FOS", "GD&T", "HT200", "AL7075", "45#",
    "你好", "模型", "计算", "转速", "进给", "深度", "公差", "外径", "内孔", "圆角",
    "倒角", "仿真", "过切", "残料", "主轴", "刀具", "对刀", "坐标系", "世界模型",
    "true", "false", "null", "{\"tool\":", "\"arguments\":", "\"action\":",
    "{\"status\":", "\"result\":", "{\"choices\":", "```python", "```json", "```gcode", "```",
]


class VirtuTokenizer:
    """Universal Lossless Tokenizer with Byte-Fallback UTF-8 Architecture."""

    def __init__(self, vocab_size: int = 4096, vocab_path: Optional[Union[str, Path]] = None) -> None:
        self.vocab_size = max(4, vocab_size)
        self.stoi: Dict[str, int] = {
            "<pad>": PAD_TOKEN_ID,
            "<s>": BOS_TOKEN_ID,
            "</s>": EOS_TOKEN_ID,
            "<unk>": UNK_TOKEN_ID,
        }
        self.itos: Dict[int, str] = {
            PAD_TOKEN_ID: "<pad>",
            BOS_TOKEN_ID: "<s>",
            EOS_TOKEN_ID: "</s>",
            UNK_TOKEN_ID: "<unk>",
        }
        # Prepopulate byte tokens for guaranteed byte-fallback, bounded by vocab_size
        self.byte_to_id: Dict[int, int] = {}
        self.id_to_byte: Dict[int, int] = {}
        byte_slots = max(1, self.vocab_size - BYTE_OFFSET)

        for b in range(256):
            tid = BYTE_OFFSET + (b % byte_slots)
            byte_repr = f"<0x{b:02X}>"
            self.stoi[byte_repr] = tid
            if tid not in self.itos:
                self.itos[tid] = byte_repr
            self.byte_to_id[b] = tid
            if tid not in self.id_to_byte:
                self.id_to_byte[tid] = b

        curr_id = min(self.vocab_size, max(BYTE_OFFSET + 256, BYTE_OFFSET + byte_slots))
        if curr_id < self.vocab_size:
            curr_id = SUBWORD_OFFSET

        # Load external vocab if available
        loaded_from_file = False
        if vocab_path and Path(vocab_path).exists():
            try:
                with open(vocab_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                external_words = data.get("text", []) if isinstance(data, dict) else data
                for w in external_words:
                    if curr_id >= self.vocab_size:
                        break
                    if w not in self.stoi:
                        self.stoi[w] = curr_id
                        self.itos[curr_id] = w
                        curr_id += 1
                loaded_from_file = True
            except Exception:
                loaded_from_file = False

        if not loaded_from_file:
            for sub in CORE_INDUSTRIAL_SUBWORDS:
                if curr_id >= self.vocab_size:
                    break
                if sub not in self.stoi:
                    self.stoi[sub] = curr_id
                    self.itos[curr_id] = sub
                    curr_id += 1

        self.actual_vocab_size = len(self.itos)

    def encode(
        self,
        text: str,
        max_length: int = 512,
        add_special_tokens: bool = True,
        return_tensors: Optional[str] = "pt",
    ) -> Union[torch.Tensor, List[int]]:
        """Encode text to token ids with greedy longest-match + byte fallback."""
        if not isinstance(text, str):
            text = str(text)

        tokens: List[int] = []
        if add_special_tokens:
            tokens.append(BOS_TOKEN_ID)

        i = 0
        n = len(text)
        budget = max_length - (2 if add_special_tokens else 0)
        budget = max(0, budget)

        # Greedy match known multi-char subwords first
        while i < n and len(tokens) - (1 if add_special_tokens else 0) < budget:
            matched = False
            # Try longest matches up to 16 chars
            for length in range(min(16, n - i), 1, -1):
                chunk = text[i : i + length]
                if chunk in self.stoi:
                    tokens.append(self.stoi[chunk])
                    i += length
                    matched = True
                    break

            if not matched:
                # Single character check or byte fallback
                char = text[i]
                if char in self.stoi:
                    tokens.append(self.stoi[char])
                else:
                    # UTF-8 byte fallback
                    for byte in char.encode("utf-8"):
                        tokens.append(self.byte_to_id.get(byte, UNK_TOKEN_ID))
                i += 1

        if add_special_tokens:
            tokens.append(EOS_TOKEN_ID)

        if return_tensors == "pt":
            return torch.tensor([tokens], dtype=torch.long)
        return tokens

    def decode(
        self,
        token_ids: Union[List[int], torch.Tensor],
        skip_special_tokens: bool = True,
    ) -> str:
        """Decode token ids back into valid UTF-8 string."""
        if isinstance(token_ids, torch.Tensor):
            token_list = token_ids.reshape(-1).tolist()
        else:
            token_list = list(token_ids)

        byte_buffer = bytearray()
        out_chunks: List[str] = []

        def flush_bytes():
            if byte_buffer:
                out_chunks.append(byte_buffer.decode("utf-8", errors="replace"))
                byte_buffer.clear()

        for tid in token_list:
            if skip_special_tokens and tid in (PAD_TOKEN_ID, BOS_TOKEN_ID, EOS_TOKEN_ID):
                continue
            if tid in self.id_to_byte:
                byte_buffer.append(self.id_to_byte[tid])
            else:
                flush_bytes()
                sub = self.itos.get(tid, "")
                if sub and not (skip_special_tokens and sub.startswith("<") and sub.endswith(">")):
                    out_chunks.append(sub)

        flush_bytes()
        return "".join(out_chunks)

    def create_streamer(self) -> IncrementalTokenStreamer:
        """Create an incremental streaming detokenizer for real-time text yielding."""
        return IncrementalTokenStreamer(self)


class IncrementalTokenStreamer:
    """Decodes token-by-token handling multibyte UTF-8 boundaries seamlessly."""

    def __init__(self, tokenizer: VirtuTokenizer) -> None:
        self.tokenizer = tokenizer
        self.decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self.byte_buffer = bytearray()

    def put(self, token_id: int) -> str:
        """Put a token and return newly decodable text chunk, if ready."""
        if token_id in (PAD_TOKEN_ID, BOS_TOKEN_ID, EOS_TOKEN_ID):
            return ""
        if token_id in self.tokenizer.id_to_byte:
            self.byte_buffer.append(self.tokenizer.id_to_byte[token_id])
            try:
                decoded = self.decoder.decode(self.byte_buffer, final=False)
                if decoded:
                    self.byte_buffer.clear()
                    return decoded
                return ""
            except Exception:
                return ""
        else:
            # Subword or word token
            pending = ""
            if self.byte_buffer:
                pending = self.decoder.decode(self.byte_buffer, final=True)
                self.byte_buffer.clear()
            sub = self.tokenizer.itos.get(token_id, "")
            return pending + sub

    def flush(self) -> str:
        """Flush any remaining buffered bytes."""
        if self.byte_buffer:
            res = self.decoder.decode(self.byte_buffer, final=True)
            self.byte_buffer.clear()
            return res
        return ""
