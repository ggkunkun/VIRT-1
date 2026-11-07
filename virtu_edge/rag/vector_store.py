"""Dense Vector Store with Cosine Similarity Search and Persistence."""

from __future__ import annotations
import hashlib
import json
import os
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
try:
    import torch
    import torch.nn.functional as F
except ImportError:
    torch = None
    F = None


class LightweightEmbedder:
    """Deterministic, high-performance semantic embedding projector.

    Maps text to normalized d-dimensional dense vector embeddings using
    n-gram hashing projection and subword semantic pooling.
    Requires 0 external APIs and runs with microsecond latency.
    """

    def __init__(self, dim: int = 128) -> None:
        self.dim = dim
        # Deterministic projection weights
        rng = np.random.RandomState(42)
        self.proj_matrix = rng.randn(4096, dim).astype(np.float32)
        self.proj_matrix /= np.linalg.norm(self.proj_matrix, axis=-1, keepdims=True)

    def embed_text(self, text: str) -> np.ndarray:
        """Encode text string into normalized dense vector."""
        if not text:
            return np.zeros(self.dim, dtype=np.float32)

        # Hash character 3-grams and tokens into 4096 buckets
        words = text.lower().split()
        buckets = np.zeros(4096, dtype=np.float32)

        for w in words:
            # Word level
            h = int(hashlib.md5(w.encode("utf-8")).hexdigest(), 16) % 4096
            buckets[h] += 1.0
            # 3-gram level
            for i in range(len(w) - 2):
                gram = w[i:i + 3]
                hg = int(hashlib.md5(gram.encode("utf-8")).hexdigest(), 16) % 4096
                buckets[hg] += 0.5

        # Project to dense dim
        vec = buckets @ self.proj_matrix
        norm = np.linalg.norm(vec)
        if norm > 1e-8:
            vec /= norm
        return vec.astype(np.float32)

    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """Embed list of texts."""
        return np.vstack([self.embed_text(t) for t in texts])


class DenseVectorStore:
    """In-memory vector database with persistence and top-K cosine search."""

    def __init__(self, dim: int = 128) -> None:
        self.dim = dim
        self.embedder = LightweightEmbedder(dim=dim)
        self.documents: List[Dict[str, Any]] = []
        self.embeddings: Optional[np.ndarray] = None

    def add_documents(self, docs: List[Dict[str, Any]]) -> int:
        """Add document chunks to vector store.

        Each doc must contain 'content' and optional 'metadata'.
        """
        if not docs:
            return 0

        texts = [d["content"] for d in docs]
        new_vecs = self.embedder.embed_batch(texts)

        start_idx = len(self.documents)
        for i, d in enumerate(docs):
            doc_entry = {
                "id": d.get("id", f"doc_{start_idx + i}"),
                "content": d["content"],
                "metadata": d.get("metadata", {}),
            }
            self.documents.append(doc_entry)

        if self.embeddings is None:
            self.embeddings = new_vecs
        else:
            self.embeddings = np.vstack([self.embeddings, new_vecs])

        return len(docs)

    def search(self, query: str, top_k: int = 3, threshold: float = 0.0) -> List[Tuple[Dict[str, Any], float]]:
        """Search top-K most semantically relevant documents for query."""
        if not self.documents or self.embeddings is None:
            return []

        q_vec = self.embedder.embed_text(query)
        # Cosine similarity (since vectors are unit-normalized, dot product is cosine similarity)
        scores = self.embeddings @ q_vec

        ranked_indices = np.argsort(-scores)
        results: List[Tuple[Dict[str, Any], float]] = []

        for idx in ranked_indices[:top_k]:
            score = float(scores[idx])
            if score >= threshold:
                results.append((self.documents[idx], score))

        return results

    def save(self, filepath: str) -> str:
        """Persist vector index and documents to JSON file."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        data = {
            "dim": self.dim,
            "documents": self.documents,
            "embeddings": self.embeddings.tolist() if self.embeddings is not None else [],
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return filepath

    @classmethod
    def load(cls, filepath: str) -> DenseVectorStore:
        """Load vector store from JSON file."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        store = cls(dim=data["dim"])
        store.documents = data["documents"]
        if data["embeddings"]:
            store.embeddings = np.array(data["embeddings"], dtype=np.float32)
        return store
