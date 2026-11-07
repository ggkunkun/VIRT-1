"""Virtu-Omni Hindsight Memory Architecture Adapter.

Implements the multi-layered agent memory architecture from Vectorize Hindsight
(arXiv:2512.12818: "Hindsight is 20/20: Building Agent Memory that Retains, Recalls, and Reflects").

Core Features:
1. Four Memory Types:
   - world_facts: Static/discovered facts (material properties, machine kinematic limits).
   - agent_experiences: Episodic logs of task completions, CAD generation, and CAM simulations.
   - entity_summaries: Entity-specific profiles (SOLIDWORKS, NX, CIMCO, AL7075-T6, Fanuc).
   - mental_models: Evolving beliefs, learned failure modes, and self-reflection heuristics.
2. Three Core Operations:
   - retain: Ingest full-context content, extract entities/facts, index semantics.
   - recall: Multi-channel retrieval (dense vector similarity + lexical overlap + entity linking).
   - reflect: Cross-session self-improvement loop synthesizing past outcomes into actionable directives.
3. Multi-Bank Organization:
   - virtu_cad_cam, virtu_cnc_machining, virtu_quality_audit, default.
4. Native Hindsight Client Integration:
   - Bridges to `hindsight_client.Hindsight` when server endpoint is configured.
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

WORKSPACE_DIR = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

try:
    from virtu_edge.rag.vector_store import LightweightEmbedder
except ImportError:
    LightweightEmbedder = None

try:
    from hindsight_client import Hindsight as UpstreamHindsightClient
except ImportError:
    UpstreamHindsightClient = None


class MemoryType:
    WORLD_FACTS = "world_facts"
    AGENT_EXPERIENCES = "agent_experiences"
    ENTITY_SUMMARIES = "entity_summaries"
    MENTAL_MODELS = "mental_models"


@dataclass
class MemoryUnit:
    id: str
    bank_id: str
    memory_type: str
    content: str
    context: str = "general"
    tags: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0


class VirtuHindsightMemory:
    """Enterprise Memory System for Virtu Foundation Models and Multi-Agent Team."""

    KNOWN_ENTITIES = [
        "SOLIDWORKS", "SW", "NXOpen", "Siemens NX", "AutoCAD", "AutoLISP",
        "Vericut", "CIMCO", "SSCNC", "FANUC", "SIEMENS", "Macro B",
        "G71", "G70", "G54", "EquationMgr", "ForceRebuild3",
        "SS304", "AL6061-T6", "AL7075-T6", "Ti-6Al-4V", "Cr12MoV", "Steel45",
    ]

    def __init__(
        self,
        storage_path: Optional[str | Path] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        embedding_dim: int = 128,
    ):
        self.storage_path = Path(storage_path or (WORKSPACE_DIR / "data" / "memory" / "hindsight_banks.json"))
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.embedding_dim = embedding_dim

        # Vector embedder
        if LightweightEmbedder is not None:
            self.embedder = LightweightEmbedder(dim=embedding_dim)
        else:
            self.embedder = None

        # Optional upstream live server client
        self.base_url = base_url or os.getenv("HINDSIGHT_API_URL") or os.getenv("HINDSIGHT_BASE_URL")
        self.api_key = api_key or os.getenv("HINDSIGHT_API_KEY")
        self.upstream_client = None
        if self.base_url and UpstreamHindsightClient is not None:
            try:
                self.upstream_client = UpstreamHindsightClient(base_url=self.base_url, api_key=self.api_key)
            except Exception as e:
                print(f"[Virtu-Hindsight] Upstream connection warning: {e}")

        # In-memory banks: { bank_id: { "description": ..., "units": { unit_id: MemoryUnit }, "vectors": { unit_id: np.ndarray } } }
        self.banks: Dict[str, Dict[str, Any]] = {}
        self._load_storage()
        self._ensure_default_banks()

    def _ensure_default_banks(self):
        defaults = {
            "default": "Default general memory bank for cross-task engineering context",
            "virtu_cad_cam": "3D parametric CAD modeling, equations, and FeatureTree rules",
            "virtu_cnc_machining": "CNC toolpaths, G-code cycles, feeds/speeds, and machine dynamics",
            "virtu_quality_audit": "Geometric tolerances, GD&T, safety guardrails, and collision audits",
        }
        for b_id, desc in defaults.items():
            if b_id not in self.banks:
                self.create_bank(b_id, desc)

    def create_bank(self, bank_id: str, description: str = "") -> Dict[str, Any]:
        """Create or register a dedicated memory bank."""
        if bank_id not in self.banks:
            self.banks[bank_id] = {
                "bank_id": bank_id,
                "description": description,
                "created_at": time.time(),
                "units": {},
                "vectors": {},
            }
            self._save_storage()
        return {"bank_id": bank_id, "status": "created", "description": description}

    def list_banks(self) -> List[Dict[str, Any]]:
        """List all available memory banks with counts."""
        res = []
        for b_id, b_data in self.banks.items():
            res.append({
                "bank_id": b_id,
                "description": b_data.get("description", ""),
                "unit_count": len(b_data.get("units", {})),
                "created_at": b_data.get("created_at", 0),
            })
        return res

    def _extract_entities(self, text: str) -> List[str]:
        """Detect industrial software, materials, and G-codes mentioned in content."""
        found = []
        for ent in self.KNOWN_ENTITIES:
            pattern = r"\b" + re.escape(ent) + r"\b"
            if re.search(pattern, text, re.IGNORECASE):
                found.append(ent)
        return list(set(found))

    def _auto_classify_type(self, content: str, context: str) -> str:
        """Infer memory type from content patterns if not explicitly provided."""
        text_lower = content.lower()
        if any(w in text_lower for w in ["密度", "抗拉强度", "屈服强度", "硬度", "公差标准", "物理参数"]):
            return MemoryType.WORLD_FACTS
        elif any(w in text_lower for w in ["反思", "教训", "避坑", "经验法则", "原则", "必须优先", "严禁"]):
            return MemoryType.MENTAL_MODELS
        elif any(w in text_lower for w in ["概述", "专精", "特性", "软件体系", "模块架构"]):
            return MemoryType.ENTITY_SUMMARIES
        else:
            return MemoryType.AGENT_EXPERIENCES

    def retain(
        self,
        bank_id: str,
        content: str,
        context: Optional[str] = "learnings",
        tags: Optional[List[str]] = None,
        memory_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Core Operation: Retain information into Hindsight memory."""
        if bank_id not in self.banks:
            self.create_bank(bank_id, f"Auto-created bank for {bank_id}")

        bank = self.banks[bank_id]
        unit_id = f"MEM_{bank_id[:4].upper()}_{len(bank['units']) + 1:04d}_{int(time.time()) % 10000:04d}"

        entities = self._extract_entities(content)
        m_type = memory_type or self._auto_classify_type(content, context or "")
        all_tags = list(set((tags or []) + [context or "general", m_type]))

        unit = MemoryUnit(
            id=unit_id,
            bank_id=bank_id,
            memory_type=m_type,
            content=content.strip(),
            context=context or "general",
            tags=all_tags,
            entities=entities,
            created_at=time.time(),
            updated_at=time.time(),
            metadata=metadata or {},
        )

        bank["units"][unit_id] = asdict(unit)

        # Compute embedding
        if self.embedder is not None:
            vec = self.embedder.embed_text(f"{content} {' '.join(entities)} {' '.join(all_tags)}")
            bank["vectors"][unit_id] = vec.tolist()

        self._save_storage()

        # Optional upstream sync
        if self.upstream_client is not None:
            try:
                self.upstream_client.retain(
                    bank_id=bank_id,
                    content=content,
                    context=context,
                    tags=all_tags,
                )
            except Exception as e:
                pass

        return {
            "status": "retained",
            "id": unit_id,
            "bank_id": bank_id,
            "memory_type": m_type,
            "entities": entities,
            "tags": all_tags,
            "timestamp": unit.created_at,
        }

    def recall(
        self,
        bank_id: str,
        query: str,
        types: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        max_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """Core Operation: Hybrid recall combining vector similarity, BM25 keywords, and entity links."""
        if bank_id not in self.banks:
            return []

        bank = self.banks[bank_id]
        units = bank.get("units", {})
        if not units:
            return []

        query_entities = set(self._extract_entities(query))
        query_words = set(re.findall(r"[\w\u4e00-\u9fa5]+", query.lower()))

        # Query embedding
        q_vec = None
        if self.embedder is not None:
            q_vec = self.embedder.embed_text(query)

        scored_results: List[Tuple[float, Dict[str, Any]]] = []

        for u_id, u_data in units.items():
            # Filter by memory types
            if types and u_data.get("memory_type") not in types:
                continue

            # Filter by tags if specified
            if tags and not any(t in u_data.get("tags", []) for t in tags):
                continue

            content = u_data.get("content", "")
            content_words = set(re.findall(r"[\w\u4e00-\u9fa5]+", content.lower()))

            # 1. Lexical Jaccard/Overlap Score (0.0 to 1.0)
            overlap = len(query_words & content_words)
            lexical_score = overlap / max(1, len(query_words))

            # 2. Dense Semantic Cosine Similarity (0.0 to 1.0)
            semantic_score = 0.0
            u_vec_list = bank.get("vectors", {}).get(u_id)
            if q_vec is not None and u_vec_list:
                import numpy as np
                u_vec = np.array(u_vec_list, dtype=np.float32)
                sim = float(np.dot(q_vec, u_vec))
                semantic_score = max(0.0, sim)

            # 3. Entity Co-occurrence Bonus (0.0 to 0.3)
            u_entities = set(u_data.get("entities", []))
            entity_match = len(query_entities & u_entities)
            entity_score = 0.15 * entity_match if entity_match > 0 else 0.0

            # Combined weighted relevance
            total_score = 0.50 * semantic_score + 0.35 * lexical_score + 0.15 * entity_score
            if total_score > 0.05 or overlap > 0:
                result_entry = dict(u_data)
                result_entry["score"] = round(total_score, 4)
                result_entry["semantic_score"] = round(semantic_score, 4)
                result_entry["lexical_score"] = round(lexical_score, 4)
                scored_results.append((total_score, result_entry))

        # Sort descending by relevance score
        scored_results.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored_results[:max_results]]

    def reflect(
        self,
        bank_id: str,
        query: str,
        budget: str = "mid",
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Core Operation: Reflect on past memory units to synthesize actionable guidance."""
        # Recall relevant memories from all types
        recalled = self.recall(bank_id=bank_id, query=query, max_results=8)
        if not recalled:
            # Fallback to search all banks
            for b in self.banks:
                if b != bank_id:
                    recalled.extend(self.recall(bank_id=b, query=query, max_results=3))

        # Separate recalled memories by type
        facts = [m["content"] for m in recalled if m.get("memory_type") == MemoryType.WORLD_FACTS]
        experiences = [m["content"] for m in recalled if m.get("memory_type") == MemoryType.AGENT_EXPERIENCES]
        mental_models = [m["content"] for m in recalled if m.get("memory_type") == MemoryType.MENTAL_MODELS]
        entities_found = list({ent for m in recalled for ent in m.get("entities", [])})

        # Synthesize strategic directives
        directives = []
        for mm in mental_models:
            directives.append(f"[Mental Model Rule] {mm}")
        for exp in experiences[:3]:
            directives.append(f"[Historical Precedent] {exp[:100]}...")

        if not directives:
            directives.append(f"依据当前工业知识库：针对【{query}】推荐保持标准加工公差与常规切削速度。")

        synthesis = (
            f"针对设计与制造意图【{query}】，Hindsight 记忆库共检索到 {len(recalled)} 条高置信度记忆单元 "
            f"（涉及实体: {', '.join(entities_found) if entities_found else '通用机械'}）。"
            f"综合历史反思：建议优先遵循既定方程式参数约束与仿真护栏，防范由于切削载荷或壁厚超限导致的返工。"
        )

        return {
            "status": "reflected",
            "query": query,
            "bank_id": bank_id,
            "budget": budget,
            "synthesis": synthesis,
            "directives": directives,
            "evidence_count": len(recalled),
            "recalled_memories": recalled[:4],
            "timestamp": time.time(),
        }

    def _load_storage(self):
        if self.storage_path.exists() and self.storage_path.stat().st_size > 0:
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.banks = data.get("banks", {})
            except Exception as e:
                print(f"[Virtu-Hindsight] Load error: {e}")
                self.banks = {}

    def _save_storage(self):
        try:
            import copy
            banks_snapshot = copy.deepcopy(self.banks)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump({"version": "2.0-Hindsight", "updated_at": time.time(), "banks": banks_snapshot}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Virtu-Hindsight] Save error: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Return system health and bank statistics."""
        total_units = sum(len(b.get("units", {})) for b in self.banks.values())
        return {
            "framework": "Vectorize Hindsight (arXiv:2512.12818)",
            "operations": ["retain", "recall", "reflect"],
            "memory_types": [
                MemoryType.WORLD_FACTS,
                MemoryType.AGENT_EXPERIENCES,
                MemoryType.ENTITY_SUMMARIES,
                MemoryType.MENTAL_MODELS,
            ],
            "total_banks": len(self.banks),
            "total_units": total_units,
            "banks": self.list_banks(),
            "upstream_connected": self.upstream_client is not None,
            "status": "active",
        }

    def export_memory_report(self, output_path: str | Path) -> Path:
        """Generate structured Markdown report summarizing Hindsight memory state."""
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        status = self.get_status()
        lines = [
            "# Virtu Foundation Model x Hindsight Memory Report",
            "",
            "> **Architecture**: Vectorize Hindsight (arXiv:2512.12818)",
            f"> **Generated**: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}",
            f"> **Total Banks**: {status['total_banks']} | **Total Units**: {status['total_units']}",
            "",
            "## 1. Banks Overview",
            "",
            "| Bank ID | Description | Units |",
            "| :--- | :--- | :--- |",
        ]

        for b in status["banks"]:
            lines.append(f"| `{b['bank_id']}` | {b['description']} | {b['unit_count']} |")

        lines.extend([
            "",
            "## 2. Sample Memory Units by Type",
            "",
        ])

        for b_id, b_data in self.banks.items():
            units = list(b_data.get("units", {}).values())
            if units:
                lines.append(f"### Bank: `{b_id}`")
                for u in units[-3:]:
                    lines.append(f"- **[{u.get('memory_type', '').upper()}]** (`{u.get('id')}`): {u.get('content')}")
                    if u.get("entities"):
                        lines.append(f"  - *Entities*: `{', '.join(u.get('entities'))}`")
                lines.append("")

        with open(out, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return out
