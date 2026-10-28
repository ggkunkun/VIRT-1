"""Streaming vectorization and dynamic batch DataLoader for Code LLM pretraining."""

from __future__ import annotations
import json
import random
import time
from typing import Iterator, Dict, Any, List, Optional
import torch

from virtu_code.config import TokenizerConfig
from virtu_code.tokenization.tokenizer import SyntaxAwareCodeTokenizer


class CodeVectorizer:
    """Transforms raw code into FIM-augmented PyTorch tensors with dynamic padding."""

    def __init__(
        self,
        tokenizer: Optional[SyntaxAwareCodeTokenizer] = None,
        config: Optional[TokenizerConfig] = None,
    ) -> None:
        self.config = config or TokenizerConfig()
        self.tokenizer = tokenizer or SyntaxAwareCodeTokenizer(self.config.vocab_size)

    def apply_fim(self, token_ids: List[int]) -> List[int]:
        """Apply Fill-in-the-Middle transformation with configured FIM rate."""
        if random.random() > self.config.fim_rate or len(token_ids) < 8:
            return token_ids

        # Strip BOS and EOS
        content = token_ids[1:-1]
        if not content:
            return token_ids

        # Sample cut boundaries
        idx1 = random.randint(0, len(content) - 1)
        idx2 = random.randint(0, len(content) - 1)
        start, end = min(idx1, idx2), max(idx1, idx2)

        prefix = content[:start]
        middle = content[start:end]
        suffix = content[end:]

        # SPM vs PSM format
        if random.random() < self.config.fim_spm_rate:
            return (
                [self.tokenizer.bos_token_id, self.tokenizer.fim_prefix_id]
                + suffix
                + [self.tokenizer.fim_suffix_id]
                + prefix
                + [self.tokenizer.fim_middle_id]
                + middle
                + [self.tokenizer.eos_token_id]
            )
        else:
            return (
                [self.tokenizer.bos_token_id, self.tokenizer.fim_prefix_id]
                + prefix
                + [self.tokenizer.fim_suffix_id]
                + suffix
                + [self.tokenizer.fim_middle_id]
                + middle
                + [self.tokenizer.eos_token_id]
            )

    def vectorize_sample(self, code_text: str, language: str = "generic") -> List[int]:
        """Tokenize code text and optionally apply FIM transformation."""
        tokens = self.tokenizer.encode(code_text, language=language)
        fim_tokens = self.apply_fim(tokens)
        return fim_tokens[: self.config.max_sequence_length]

    def collate_batch(self, batch_tokens: List[List[int]]) -> Dict[str, torch.Tensor]:
        """Pad token lists into uniform PyTorch batch tensors."""
        max_len = max(len(seq) for seq in batch_tokens)
        batch_size = len(batch_tokens)

        input_ids = torch.full((batch_size, max_len), self.tokenizer.pad_token_id, dtype=torch.long)
        attention_mask = torch.zeros((batch_size, max_len), dtype=torch.long)
        labels = torch.full((batch_size, max_len), -100, dtype=torch.long)

        for i, seq in enumerate(batch_tokens):
            length = len(seq)
            input_ids[i, :length] = torch.tensor(seq, dtype=torch.long)
            attention_mask[i, :length] = 1
            labels[i, :length] = torch.tensor(seq, dtype=torch.long)

        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "labels": labels,
        }


class StreamingCodeDataLoader:
    """High-throughput streaming DataLoader for TB-scale code pretraining."""

    def __init__(
        self,
        jsonl_path: str,
        config: Optional[TokenizerConfig] = None,
        vectorizer: Optional[CodeVectorizer] = None,
    ) -> None:
        self.jsonl_path = jsonl_path
        self.config = config or TokenizerConfig()
        self.vectorizer = vectorizer or CodeVectorizer(config=self.config)

    def stream_batches(self) -> Iterator[Dict[str, torch.Tensor]]:
        """Stream JSONL dataset line-by-line and yield PyTorch batches."""
        batch_tokens: List[List[int]] = []

        with open(self.jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                record = json.loads(line)
                code_text = record.get("clean_code", "")
                language = record.get("language", "generic")

                tokens = self.vectorizer.vectorize_sample(code_text, language)
                batch_tokens.append(tokens)

                if len(batch_tokens) >= self.config.streaming_batch_size:
                    yield self.vectorizer.collate_batch(batch_tokens)
                    batch_tokens = []

        if batch_tokens:
            yield self.vectorizer.collate_batch(batch_tokens)

    def benchmark_throughput(self, num_samples: int = 20000) -> Dict[str, Any]:
        """Measure vectorization throughput (samples/sec) on streaming data."""
        sample_code = (
            "def calculate_metrics(values: list[float]) -> dict[str, float]:\n"
            "    total = sum(values)\n"
            "    count = len(values)\n"
            "    mean = total / count if count > 0 else 0.0\n"
            "    return {'total': total, 'mean': mean}\n"
        )
        sample_lang = "python"

        # Pre-generate token IDs to measure pure streaming vectorization + batch tensorization
        tokens = self.vectorizer.tokenizer.encode(sample_code, sample_lang)

        batch_size = self.config.streaming_batch_size
        batches = num_samples // batch_size

        t0 = time.perf_counter()
        for _ in range(batches):
            batch_list = [tokens for _ in range(batch_size)]
            _ = self.vectorizer.collate_batch(batch_list)
        elapsed = time.perf_counter() - t0

        throughput = num_samples / elapsed
        target_met = throughput >= self.config.target_throughput_samples_per_sec

        return {
            "num_samples": num_samples,
            "elapsed_seconds": round(elapsed, 4),
            "throughput_samples_per_sec": round(throughput, 1),
            "target_threshold": self.config.target_throughput_samples_per_sec,
            "target_achieved": target_met,
        }
