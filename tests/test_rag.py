"""Unit tests for Method 4: Local RAG, Dense Vector Store, and Pipeline."""

from __future__ import annotations
import os
import tempfile
import numpy as np

from virtu_edge.rag.vector_store import LightweightEmbedder, DenseVectorStore
from virtu_edge.rag.chunker import CodebaseChunker
from virtu_edge.rag.pipeline import LocalRAGPipeline


def test_embedder_normalization_and_dim() -> None:
    """Test LightweightEmbedder output dimensionality and unit norm."""
    embedder = LightweightEmbedder(dim=64)
    vec1 = embedder.embed_text("def solve_equation(x): return x * 2")
    vec2 = embedder.embed_text("class DatabaseConnection: pass")

    assert vec1.shape == (64,)
    assert abs(np.linalg.norm(vec1) - 1.0) < 1e-4
    assert abs(np.linalg.norm(vec2) - 1.0) < 1e-4

    # Different texts have different representations
    assert np.dot(vec1, vec2) < 0.95


def test_vector_store_persistence_and_search() -> None:
    """Test DenseVectorStore adding, searching, saving and reloading."""
    store = DenseVectorStore(dim=64)
    docs = [
        {"content": "Python asyncio event loop and coroutines", "metadata": {"lang": "python"}},
        {"content": "PostgreSQL relational database schema design", "metadata": {"lang": "sql"}},
        {"content": "FastAPI high performance REST API endpoints", "metadata": {"lang": "python"}},
    ]
    added = store.add_documents(docs)
    assert added == 3

    # Search query
    res = store.search("FastAPI web server routes", top_k=1)
    assert len(res) == 1
    top_doc, score = res[0]
    assert "FastAPI" in top_doc["content"]
    assert score > 0.0

    with tempfile.TemporaryDirectory() as tmp_dir:
        idx_path = os.path.join(tmp_dir, "vector_index.json")
        store.save(idx_path)
        assert os.path.exists(idx_path)

        loaded_store = DenseVectorStore.load(idx_path)
        assert len(loaded_store.documents) == 3
        res_loaded = loaded_store.search("PostgreSQL database", top_k=1)
        assert "PostgreSQL" in res_loaded[0][0]["content"]


def test_codebase_chunker() -> None:
    """Test chunking file with line overlap."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        sample_file = os.path.join(tmp_dir, "sample.py")
        lines = [f"# Line {i}\nx_{i} = {i} * 10\n" for i in range(1, 100)]
        with open(sample_file, "w", encoding="utf-8") as f:
            f.writelines(lines)

        chunker = CodebaseChunker(chunk_size_lines=30, overlap_lines=5)
        chunks = chunker.chunk_file(sample_file)

        assert len(chunks) > 1
        first = chunks[0]
        assert "metadata" in first
        assert first["metadata"]["start_line"] == 1
        assert first["metadata"]["end_line"] == 30
        assert first["metadata"]["filename"] == "sample.py"


def test_rag_pipeline_end_to_end() -> None:
    """Test LocalRAGPipeline directory indexing, query retrieval, and prompt assembly."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create mock source code files
        f1 = os.path.join(tmp_dir, "loop_controller.py")
        with open(f1, "w", encoding="utf-8") as f:
            f.write("class LoopStepController:\n    def get_step(self):\n        return self.max_steps\n")

        f2 = os.path.join(tmp_dir, "database.py")
        with open(f2, "w", encoding="utf-8") as f:
            f.write("def connect_db():\n    return 'connected'\n")

        pipeline = LocalRAGPipeline(dim=64)
        stat = pipeline.index_directory(tmp_dir)
        assert stat["total_chunks"] >= 2

        # Retrieve
        res = pipeline.retrieve("How does LoopStepController get step?", top_k=1)
        assert len(res) == 1
        assert "LoopStepController" in res[0]["content"]

        # Assemble Prompt
        prompt_data = pipeline.assemble_prompt("What does LoopStepController do?", top_k=1)
        assert "LoopStepController" in prompt_data["prompt"]
        assert len(prompt_data["citations"]) == 1

        # Evaluate Groundedness
        grounded = pipeline.evaluate_groundedness(
            answer="LoopStepController has a method get_step that returns max_steps",
            citations=prompt_data["citations"],
        )
        assert grounded["groundedness_score"] > 0.0
        assert grounded["status"] == "PASS"
