"""Chain-of-Thought (CoT) Synthetic Dataset Generator and Formatter."""

from __future__ import annotations
import json
import os
from typing import List, Dict, Any, Iterator
import torch
from torch.utils.data import Dataset, DataLoader


class SyntheticCoTGenerator:
    """Generates structured step-by-step reasoning problems with <think>...</think> traces."""

    COT_TEMPLATES = [
        {
            "problem": "Calculate the factorial of 5 and return the result.",
            "thought": "1. Factorial n! = 1 * 2 * ... * n.\n2. For n=5: 1 * 2 = 2.\n3. 2 * 3 = 6.\n4. 6 * 4 = 24.\n5. 24 * 5 = 120.\nConclusion: 5! = 120.",
            "answer": "120",
        },
        {
            "problem": "Write a Python function to check if a word is a palindrome.",
            "thought": "1. A palindrome reads the same backwards and forwards.\n2. In Python, a string can be reversed via slice s[::-1].\n3. Normalize word to lowercase.\n4. Compare word.lower() == word.lower()[::-1].",
            "answer": "def is_palindrome(s: str) -> bool:\n    s = s.lower()\n    return s == s[::-1]",
        },
        {
            "problem": "Compute the time complexity of binary search on a sorted array of size N.",
            "thought": "1. Binary search divides search interval in half each step.\n2. At step k, remaining size is N / (2^k).\n3. Search terminates when size reaches 1: N / 2^k = 1 -> 2^k = N -> k = log2(N).\n4. Therefore, time complexity is O(log N).",
            "answer": "O(log N)",
        },
        {
            "problem": "Given array [3, 1, 4, 1, 5, 9, 2], find the maximum element.",
            "thought": "1. Initialize max_val = 3.\n2. Compare 1 < 3 -> keep 3.\n3. Compare 4 > 3 -> max_val = 4.\n4. Compare 1 < 4 -> keep 4.\n5. Compare 5 > 4 -> max_val = 5.\n6. Compare 9 > 5 -> max_val = 9.\n7. Compare 2 < 9 -> keep 9.\n8. Maximum is 9.",
            "answer": "9",
        },
        {
            "problem": "Fix the bug in Python: `def add(a, b): return a - b`.",
            "thought": "1. The function is named add, which represents addition.\n2. The implementation uses subtraction operator `-` instead of `+`.\n3. To fix, replace `-` with `+`.",
            "answer": "def add(a, b):\n    return a + b",
        },
        {
            "problem": "Calculate the dot product of vectors [1, 2, 3] and [4, 5, 6].",
            "thought": "1. Dot product = sum(u_i * v_i).\n2. 1*4 = 4.\n3. 2*5 = 10.\n4. 3*6 = 18.\n5. Sum = 4 + 10 + 18 = 32.",
            "answer": "32",
        },
    ]

    @classmethod
    def format_sample(cls, problem: str, thought: str, answer: str) -> str:
        """Format into reasoning token sequence."""
        return (
            f"<problem>\n{problem}\n</problem>\n"
            f"<think>\n{thought}\n</think>\n"
            f"<answer>\n{answer}\n</answer>"
        )

    @classmethod
    def generate_corpus(cls, repeat: int = 10) -> List[Dict[str, str]]:
        """Generate expanded synthetic reasoning samples."""
        corpus: List[Dict[str, str]] = []
        for i in range(repeat):
            for idx, item in enumerate(cls.COT_TEMPLATES):
                corpus.append({
                    "id": f"cot_{idx}_{i}",
                    "problem": item["problem"],
                    "thought": item["thought"],
                    "answer": item["answer"],
                    "formatted_text": cls.format_sample(item["problem"], item["thought"], item["answer"]),
                })
        return corpus

    @classmethod
    def save_corpus(cls, filepath: str, repeat: int = 10) -> str:
        """Save synthetic CoT dataset to JSONL file."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        samples = cls.generate_corpus(repeat=repeat)
        with open(filepath, "w", encoding="utf-8") as f:
            for s in samples:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")
        return filepath


class SimpleCoTDataset(Dataset):
    """PyTorch Dataset for synthetic CoT reasoning tokens."""

    def __init__(self, samples: List[Dict[str, str]], vocab_size: int = 1000, max_seq_len: int = 64) -> None:
        self.samples = samples
        self.vocab_size = vocab_size
        self.max_seq_len = max_seq_len

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        text = self.samples[idx]["formatted_text"]
        # Deterministic character-based token mapping into vocabulary
        tokens = [hash(ch) % (self.vocab_size - 1) + 1 for ch in text[:self.max_seq_len]]
        if len(tokens) < self.max_seq_len:
            tokens = tokens + [0] * (self.max_seq_len - len(tokens))

        input_ids = torch.tensor(tokens, dtype=torch.long)
        labels = input_ids.clone()
        return {"input_ids": input_ids, "labels": labels}
