"""Local RAG Pipeline: Ingest, Retrieve, Assemble Context, and Evaluate."""

from __future__ import annotations
import os
import time
from typing import Dict, List, Any, Optional, Tuple

from virtu_edge.rag.chunker import CodebaseChunker
from virtu_edge.rag.vector_store import DenseVectorStore


class LocalRAGPipeline:
    """Retrieval-Augmented Generation pipeline running entirely on local CPU/GPU."""

    def __init__(self, vector_store: Optional[DenseVectorStore] = None, dim: int = 128) -> None:
        self.vector_store = vector_store or DenseVectorStore(dim=dim)
        self.chunker = CodebaseChunker()

    def index_directory(
        self,
        directory: str,
        index_save_path: Optional[str] = None,
        extensions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Index all relevant source files in directory."""
        start_time = time.time()
        exts = extensions or [".py", ".md", ".json", ".yaml"]
        chunks = self.chunker.chunk_directory(directory, extensions=exts)

        num_indexed = self.vector_store.add_documents(chunks)
        duration = time.time() - start_time

        if index_save_path:
            self.vector_store.save(index_save_path)

        return {
            "indexed_directory": directory,
            "total_chunks": num_indexed,
            "duration_sec": round(duration, 3),
            "index_path": index_save_path,
        }

    def retrieve(self, query: str, top_k: int = 3, threshold: float = 0.0) -> List[Dict[str, Any]]:
        """Retrieve most relevant context chunks with similarity scores."""
        results = self.vector_store.search(query, top_k=top_k, threshold=threshold)
        retrieved: List[Dict[str, Any]] = []

        for doc, score in results:
            retrieved.append({
                "id": doc["id"],
                "content": doc["content"],
                "metadata": doc["metadata"],
                "similarity_score": round(score, 4),
            })

        return retrieved

    def assemble_prompt(self, query: str, top_k: int = 3) -> Dict[str, Any]:
        """Assemble retrieval-augmented prompt with provenance citations."""
        retrieved = self.retrieve(query, top_k=top_k)

        context_blocks: List[str] = []
        for i, r in enumerate(retrieved, start=1):
            meta = r["metadata"]
            citation = f"[{i}] {meta.get('filename', 'doc')} (L{meta.get('start_line', 1)}-L{meta.get('end_line', 1)})"
            context_blocks.append(f"--- Document {citation} (Relevance: {r['similarity_score']}) ---\n{r['content']}")

        full_context = "\n\n".join(context_blocks)

        prompt = (
            f"You are a verified code intelligence assistant. "
            f"Answer the user query strictly based on the following retrieved codebase context. "
            f"If the answer cannot be deduced from the context, state that clearly.\n\n"
            f"[RETRIEVED CODEBASE CONTEXT]\n"
            f"{full_context}\n\n"
            f"[USER QUERY]\n"
            f"{query}\n\n"
            f"[INSTRUCTION]\n"
            f"Provide a concise, accurate response with code symbol citations."
        )

        return {
            "query": query,
            "prompt": prompt,
            "retrieved_count": len(retrieved),
            "citations": [r["id"] for r in retrieved],
            "top_similarity": retrieved[0]["similarity_score"] if retrieved else 0.0,
            "context_tokens_approx": len(prompt.split()),
        }

    def evaluate_groundedness(self, answer: str, citations: List[str]) -> Dict[str, Any]:
        """Verify that answer references factual codebase symbols without hallucinations."""
        # Simple lexical overlap between answer tokens and retrieved chunk content
        import re

        all_cited_content = ""
        for doc in self.vector_store.documents:
            if doc["id"] in citations:
                all_cited_content += " " + doc["content"].lower()

        answer_tokens = set(re.findall(r"\w+", answer.lower()))
        cited_tokens = set(re.findall(r"\w+", all_cited_content.lower()))

        intersection = answer_tokens.intersection(cited_tokens)
        groundedness = len(intersection) / max(1, len(answer_tokens))

        return {
            "groundedness_score": round(groundedness, 4),
            "overlapping_tokens": len(intersection),
            "status": "PASS" if groundedness > 0.3 else "FLAGGED",
        }
