"""Codebase and Document Semantic Chunker for Local RAG."""

from __future__ import annotations
import hashlib
import os
from typing import List, Dict, Any


class CodebaseChunker:
    """Splits source code and markdown documents into semantically bounded chunks."""

    def __init__(self, chunk_size_lines: int = 40, overlap_lines: int = 10) -> None:
        self.chunk_size_lines = chunk_size_lines
        self.overlap_lines = overlap_lines

    def chunk_file(self, filepath: str) -> List[Dict[str, Any]]:
        """Split a single file into overlapping line chunks."""
        if not os.path.exists(filepath):
            return []

        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except Exception:
            return []

        if not lines:
            return []

        chunks: List[Dict[str, Any]] = []
        total_lines = len(lines)
        step = max(1, self.chunk_size_lines - self.overlap_lines)

        for start in range(0, total_lines, step):
            end = min(total_lines, start + self.chunk_size_lines)
            chunk_text = "".join(lines[start:end]).strip()

            if len(chunk_text) < 20:  # Skip trivial chunks
                continue

            content_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()[:12]
            chunks.append({
                "id": f"{os.path.basename(filepath)}:L{start + 1}-L{end}",
                "content": chunk_text,
                "metadata": {
                    "filepath": os.path.abspath(filepath),
                    "filename": os.path.basename(filepath),
                    "start_line": start + 1,
                    "end_line": end,
                    "total_lines": total_lines,
                    "hash": content_hash,
                },
            })

            if end >= total_lines:
                break

        return chunks

    def chunk_directory(
        self,
        directory: str,
        extensions: List[str] = [".py", ".md", ".json", ".yaml", ".yml"],
        exclude_dirs: List[str] = [".venv", ".git", "__pycache__", "pytest_cache"],
    ) -> List[Dict[str, Any]]:
        """Recursively scan directory and extract chunks."""
        all_chunks: List[Dict[str, Any]] = []

        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in extensions:
                    file_path = os.path.join(root, file)
                    all_chunks.extend(self.chunk_file(file_path))

        return all_chunks
