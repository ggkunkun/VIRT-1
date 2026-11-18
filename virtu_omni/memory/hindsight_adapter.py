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

import hashlib
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

from virtu_omni.memory.working_memory import _atomic_write_text

try:
    from hindsight_client import Hindsight as UpstreamHindsightClient
except ImportError:
    UpstreamHindsightClient = None


class MemoryType:
    WORLD_FACTS = "world_facts"
    AGENT_EXPERIENCES = "agent_experiences"
    ENTITY_SUMMARIES = "entity_summaries"
    MENTAL_MODELS = "mental_models"


COORDINATE_ISOLATION_RULES: Dict[str, str] = {
    "solidworks": (
        "SOLIDWORKS 2021 坐标系 (Y-up，严禁混入 CNC Z-up)：默认世界 Y 轴朝上；"
        "标准法向必须使用前置正号 +Z / +Y / +X（禁止写成 Z+/Y+/X+）："
        "Front Plane（前视基准面）= XY 平面，法向 +Z (0, 0, 1)；"
        "Top Plane（上视基准面）= XZ 平面，法向 +Y (0, 1, 0)；"
        "Right Plane（右视基准面）= YZ 平面，法向 +X (1, 0, 0)。"
    ),
    "vericut_cnc": (
        "VERICUT 9.6 / Siemens NX 12.0 / CNC 坐标系 (Z-up / G54)：机床默认 Up=Z+（具体以 .vcproject 实测 Setup/Component 坐标树为准）；"
        "G54 为工件编程零点，严禁等价套用 SOLIDWORKS Y-up 默认基准面；XML 中 Unit=\"inch\" 与 \"millimeter\" 必须按工程实测原样匹配，禁止误翻；"
        "Auto-Diff 三色严格按【红色→蓝色→绿色】分条写完即止（三色互禁串词，禁止在绿色末尾续写红色小标题）："
        "红色(Red)=过切(Gouge，刀具侵入实体属致命缺陷，立即停机排查修正刀路；红色条内禁出现‘残料’‘excess’或‘公差’)；"
        "蓝色(Blue)=残料/欠切(Excess material，表面留有未切净余量，补充半精或精加工；蓝色条内禁出现‘过切’‘切入’或‘公差’)；"
        "绿色(Green)=公差内合格(In-tolerance，加工几何达标放行；绿色条内禁出现‘过切’‘切入’或‘残料’)。"
    ),
    "lame": (
        "Lamé 厚壁圆筒闭式解（禁用薄壁公式 Pi*Di/(2t)）："
        "直径比 K = Do / Di（无量纲），平方比 k = K^2 = (Do / Di)^2（无量纲比值，严禁标注 MPa 单位！）；"
        "内壁环向应力 sigma_theta = Pi * (k + 1) / (k - 1)（k 已是平方比，严禁再平方写成 (k^2+1)/(k^2-1)；如 Di=60, Do=120, Pi=20 => K=2, k=4, sigma_theta=33.33 MPa），"
        "内壁径向应力 sigma_r = -Pi（受压为负，如 -20 MPa），"
        "等效应力 sigma_vm = sqrt(sigma_theta^2 - sigma_theta*sigma_r + sigma_r^2)，FOS = Sy / sigma_vm >= 1.5。"
    ),
    "fanuc_g71": (
        "FANUC 车削 G71/G70 安全规范：必须包含 T0101（4位刀补号）、G50 S_ 限速、G96 S_ M03 恒线速正转与 M30；"
        "定位点必须在毛坯外（如 Ø60 棒料用 G0 X62.0 Z2.0），严禁 G00 负向 Z 扎刀（禁止 G0 ... Z-）；"
        "两行复合循环必须均以 G71 开头，格式为 G71 U1.5 R0.5 与 G71 P10 Q20 U0.4 W0.1 F0.25，"
        "紧接 N10 G0 X_ -> G1 Z_ -> X_ -> N20 完整精车轮廓，最后 G70 P10 Q20。"
    ),
}

CANONICAL_DOMAIN_INVARIANTS: List[Dict[str, Any]] = [
    {
        "bank_id": "virtu_cad_cam",
        "context": "cad_coordinate_system",
        "memory_type": MemoryType.WORLD_FACTS,
        "tags": ["coordinate_system", "solidworks", "y_up", "plane_normal", "canonical_invariant"],
        "content": COORDINATE_ISOLATION_RULES["solidworks"],
    },
    {
        "bank_id": "virtu_cnc_machining",
        "context": "cnc_coordinate_isolation",
        "memory_type": MemoryType.WORLD_FACTS,
        "tags": ["coordinate_system", "vericut", "nx", "cnc", "z_up", "g54", "autodiff", "canonical_invariant"],
        "content": COORDINATE_ISOLATION_RULES["vericut_cnc"],
    },
    {
        "bank_id": "virtu_quality_audit",
        "context": "cae_lame_theory",
        "memory_type": MemoryType.MENTAL_MODELS,
        "tags": ["lame", "thick_cylinder", "fea", "fos", "stress", "canonical_invariant"],
        "content": COORDINATE_ISOLATION_RULES["lame"],
    },
    {
        "bank_id": "virtu_cnc_machining",
        "context": "fanuc_g71_safety",
        "memory_type": MemoryType.MENTAL_MODELS,
        "tags": ["fanuc", "g71", "g70", "t0101", "zero_plunge", "cnc", "canonical_invariant"],
        "content": COORDINATE_ISOLATION_RULES["fanuc_g71"],
    },
]


def build_swarm_coordinate_contract(task: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build explicit cross-software coordinate isolation contract for multi-agent workflows."""
    task = task or {}
    return {
        "cad_modeling_system": "SOLIDWORKS_2021_Y_UP",
        "cad_plane_normals": {
            "Front": {"plane": "XY", "normal": [0, 0, 1], "label": "+Z"},
            "Top": {"plane": "XZ", "normal": [0, 1, 0], "label": "+Y"},
            "Right": {"plane": "YZ", "normal": [1, 0, 0], "label": "+X"},
        },
        "cam_simulation_system": "VERICUT_9.6_NX_12_CNC_Z_UP",
        "cnc_wcs": task.get("wcs", "G54"),
        "unit_policy": "Preserve XML Unit ('inch' or 'millimeter') and CNC G20/G21 as observed; never assume conversion",
        "autodiff_policy": {"red": "gouge_fatal", "blue": "excess_material", "green": "in_tolerance"},
        "isolation_rule": "Never apply CNC/VERICUT Z-up plane assumptions to SOLIDWORKS Front/Top/Right reference planes.",
    }


# 旧格式 JSON（缺新字段）读回时填充的默认值。expires_at=None 表示永不过期，
# 这样 559 条历史 unit 不会被误判为过期；数值型字段保持 0/1.0 便于排序与衰减计算。
_UNIT_DEFAULTS: Dict[str, Any] = {
    "content_sha256": "",
    "expires_at": None,
    "access_count": 0,
    "last_recalled_at": None,
    "utility_score": 1.0,
}


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
    # --- 记忆生命周期字段（向后兼容：旧 JSON 缺字段时由 _UNIT_DEFAULTS 补齐）---
    content_sha256: str = ""            # 归一化内容指纹，用于入库存重
    expires_at: Optional[float] = None  # Unix 时间戳；None = 永不过期（TTL）
    access_count: int = 0               # recall 命中次数（命中反馈）
    last_recalled_at: Optional[float] = None  # 最近一次被 recall 命中的时间
    utility_score: float = 1.0          # 效用分，命中递增，供 prune/compact 排序


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
        env_storage = os.getenv("VIRTU_HINDSIGHT_PATH")
        self.storage_path = Path(
            storage_path or env_storage or (WORKSPACE_DIR / "data" / "memory" / "hindsight_banks.json")
        )
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
        self._storage_load_failed = False
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
            # ASCII-only boundaries: \b fails between CJK and Latin (both are
            # \w), which silently killed the entity channel for Chinese text.
            pattern = r"(?<![A-Za-z0-9_])" + re.escape(ent) + r"(?![A-Za-z0-9_])"
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

    # ------------------------------------------------------------------
    # 记忆生命周期辅助方法（内容指纹 / 过期 / 效用 / 旧格式归一化）
    # ------------------------------------------------------------------
    @staticmethod
    def _fingerprint(content: str) -> str:
        """归一化内容的 sha256 指纹。旧 unit 无 content_sha256 时按内容现算。"""
        return hashlib.sha256((content or "").strip().encode("utf-8")).hexdigest()

    @staticmethod
    def _is_expired(u_data: Dict[str, Any], now: float) -> bool:
        exp = u_data.get("expires_at")
        return exp is not None and float(exp) <= now

    @staticmethod
    def _is_canonical(u_data: Dict[str, Any]) -> bool:
        """canonical_invariant（坐标系/Lamé/G71 安全规范）永不参与淘汰。"""
        return "canonical_invariant" in (u_data.get("tags") or [])

    @staticmethod
    def _keep_score(u_data: Dict[str, Any], now: float) -> float:
        """效用 + 近因 + 命中反馈的分值，越大越应保留。"""
        utility = float(u_data.get("utility_score", 1.0) or 1.0)
        last = u_data.get("last_recalled_at") or u_data.get("created_at") or 0.0
        recency = 1.0 / (1.0 + max(0.0, now - float(last)) / 86400.0)
        hits = int(u_data.get("access_count", 0) or 0)
        return utility + recency + 0.05 * hits

    def _normalize_unit(self, u_data: Dict[str, Any]) -> Dict[str, Any]:
        """为旧格式 unit 补齐新字段默认值（原地修改，不新增 unit）。"""
        for key, default in _UNIT_DEFAULTS.items():
            if key not in u_data:
                u_data[key] = default
        if not u_data.get("content_sha256"):
            u_data["content_sha256"] = self._fingerprint(u_data.get("content", ""))
        return u_data

    def _normalize_loaded(self):
        for bank in self.banks.values():
            if not isinstance(bank, dict):
                continue
            units = bank.get("units", {})
            if isinstance(units, dict):
                for u in units.values():
                    if isinstance(u, dict):
                        self._normalize_unit(u)
            if not isinstance(bank.get("vectors"), dict):
                bank["vectors"] = {}

    def _evict(self, bank: Dict[str, Any], victim_ids: List[str]) -> int:
        vectors = bank.setdefault("vectors", {})
        removed = 0
        for uid in victim_ids:
            if uid in bank.get("units", {}):
                del bank["units"][uid]
                vectors.pop(uid, None)
                removed += 1
        return removed

    def retain(
        self,
        bank_id: str,
        content: str,
        context: Optional[str] = "learnings",
        tags: Optional[List[str]] = None,
        memory_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ttl_seconds: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Core Operation: Retain information into Hindsight memory.

        入库按内容指纹去重：相同归一化内容不新增 unit，直接返回已有 id
        （status=duplicate）。ttl_seconds 非空时写入 expires_at，recall 会跳过
        已过期 unit。新字段对旧 JSON 向后兼容。
        """
        if bank_id not in self.banks:
            self.create_bank(bank_id, f"Auto-created bank for {bank_id}")

        bank = self.banks[bank_id]
        clean_content = content.strip()
        fingerprint = self._fingerprint(clean_content)

        # 内容指纹去重：覆盖新 unit 与缺 content_sha256 的历史 unit
        for existing_id, existing in bank["units"].items():
            if self._fingerprint(existing.get("content", "")) == fingerprint:
                return {
                    "status": "duplicate",
                    "id": existing_id,
                    "bank_id": bank_id,
                    "memory_type": existing.get("memory_type"),
                    "entities": existing.get("entities", []),
                    "tags": existing.get("tags", []),
                    "timestamp": existing.get("created_at"),
                    "deduplicated": True,
                }

        now = time.time()
        seq = len(bank["units"]) + 1
        unit_id = f"MEM_{bank_id[:4].upper()}_{seq:04d}_{int(now) % 10000:04d}"
        while unit_id in bank["units"]:
            seq += 1
            unit_id = f"MEM_{bank_id[:4].upper()}_{seq:04d}_{int(now) % 10000:04d}"
        expires_at = (now + ttl_seconds) if ttl_seconds is not None else None

        entities = self._extract_entities(clean_content)
        m_type = memory_type or self._auto_classify_type(clean_content, context or "")
        all_tags = list(set((tags or []) + [context or "general", m_type]))

        unit = MemoryUnit(
            id=unit_id,
            bank_id=bank_id,
            memory_type=m_type,
            content=clean_content,
            context=context or "general",
            tags=all_tags,
            entities=entities,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
            content_sha256=fingerprint,
            expires_at=expires_at,
            access_count=0,
            last_recalled_at=None,
            utility_score=1.0,
        )

        bank["units"][unit_id] = asdict(unit)

        # Compute embedding
        if self.embedder is not None:
            vec = self.embedder.embed_text(f"{clean_content} {' '.join(entities)} {' '.join(all_tags)}")
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
                print(f"[Virtu-Hindsight] Upstream retain warning: {e}")

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
        update_stats: bool = True,
    ) -> List[Dict[str, Any]]:
        """Core Operation: Hybrid recall combining vector similarity, BM25 keywords, and entity links.

        跳过已过期 unit；当 update_stats=True 时命中（进入 top-N）的 unit 写回
        access_count / last_recalled_at / utility_score（命中反馈）。只读注入场景可设 update_stats=False。
        """
        if bank_id not in self.banks:
            return []

        bank = self.banks[bank_id]
        units = bank.get("units", {})
        if not units:
            return []

        now = time.time()
        query_entities = set(self._extract_entities(query))
        query_words = set(re.findall(r"[\w\u4e00-\u9fa5]+", query.lower()))

        # Query embedding
        q_vec = None
        if self.embedder is not None:
            q_vec = self.embedder.embed_text(query)

        scored_results: List[Tuple[float, str, Dict[str, Any]]] = []

        for u_id, u_data in units.items():
            # 跳过已过期 unit（TTL）
            if self._is_expired(u_data, now):
                continue

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
                scored_results.append((total_score, u_id, result_entry))

        # Sort descending by relevance score
        scored_results.sort(key=lambda x: x[0], reverse=True)
        top = scored_results[:max_results]

        # 命中反馈：写回访问计数 / 最近召回时间 / 效用分（只读调用时跳过落盘）
        if top and update_stats:
            for _, u_id, _entry in top:
                u = units.get(u_id)
                if u is None:
                    continue
                u["access_count"] = int(u.get("access_count", 0) or 0) + 1
                u["last_recalled_at"] = now
                u["utility_score"] = float(u.get("utility_score", 1.0) or 1.0) + 0.1
            self._save_storage()

        return [item[2] for item in top]

    def recall_all_banks(
        self,
        query: str,
        bank_ids: Optional[List[str]] = None,
        types: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        max_results: int = 5,
        update_stats: bool = True,
    ) -> List[Dict[str, Any]]:
        """Recall across multiple Hindsight banks, deduplicate, and rank by relevance score."""
        target_banks = [b for b in (bank_ids or list(self.banks.keys())) if b in self.banks]
        merged: List[Dict[str, Any]] = []
        seen_keys: set[str] = set()
        per_bank = max(2, max_results)
        for b_id in target_banks:
            hits = self.recall(
                bank_id=b_id,
                query=query,
                types=types,
                tags=tags,
                max_results=per_bank,
                update_stats=update_stats,
            )
            for item in hits:
                dedupe_key = str(item.get("content_sha256") or item.get("id") or "")
                if dedupe_key and dedupe_key in seen_keys:
                    continue
                if dedupe_key:
                    seen_keys.add(dedupe_key)
                if "bank_id" not in item:
                    item["bank_id"] = b_id
                merged.append(item)
        merged.sort(key=lambda x: float(x.get("score", 0.0) or 0.0), reverse=True)
        return merged[:max_results]

    def seed_canonical_invariants(self) -> Dict[str, Any]:
        """Idempotently seed or refresh canonical coordinate-isolation, Lamé, and G71 safety invariants."""
        retained = 0
        updated = 0
        duplicate = 0
        ids: List[str] = []
        now = time.time()
        dirty = False

        for entry in CANONICAL_DOMAIN_INVARIANTS:
            b_id = entry["bank_id"]
            if b_id not in self.banks:
                self.create_bank(b_id, f"Auto-created bank for {b_id}")
            bank = self.banks[b_id]
            clean_content = entry["content"].strip()
            new_fp = self._fingerprint(clean_content)

            # Update existing canonical invariant for same (bank_id, context) if rule text was refined
            matched_id = None
            for uid, u in bank.get("units", {}).items():
                if (
                    u.get("context") == entry["context"]
                    and "canonical_invariant" in (u.get("tags") or [])
                ):
                    matched_id = uid
                    break

            if matched_id is not None:
                u = bank["units"][matched_id]
                if self._fingerprint(u.get("content", "")) == new_fp:
                    duplicate += 1
                else:
                    u["content"] = clean_content
                    u["content_sha256"] = new_fp
                    u["entities"] = self._extract_entities(clean_content)
                    u["tags"] = list(set(entry["tags"] + [entry["context"], entry["memory_type"]]))
                    u["updated_at"] = now
                    if self.embedder is not None:
                        vec = self.embedder.embed_text(
                            f"{clean_content} {' '.join(u['entities'])} {' '.join(u['tags'])}"
                        )
                        bank["vectors"][matched_id] = vec.tolist()
                    updated += 1
                    dirty = True
                ids.append(matched_id)
                continue

            res = self.retain(
                bank_id=b_id,
                content=clean_content,
                context=entry["context"],
                tags=entry["tags"],
                memory_type=entry["memory_type"],
                metadata={"source": "canonical_domain_invariants"},
            )
            ids.append(str(res.get("id", "")))
            if res.get("status") == "retained":
                retained += 1
            else:
                duplicate += 1

        if dirty:
            self._save_storage()
        return {"retained": retained, "updated": updated, "duplicate": duplicate, "ids": ids}

    @staticmethod
    def select_coordinate_invariants(query: str, include_all_if_empty: bool = False) -> List[Tuple[str, str]]:
        """Select applicable coordinate-system / formula invariants without cross-software contamination."""
        q_low = (query or "").lower()
        selected: List[Tuple[str, str]] = []

        def _add(k: str) -> None:
            if k in COORDINATE_ISOLATION_RULES and all(x[0] != k for x in selected):
                selected.append((k, COORDINATE_ISOLATION_RULES[k]))

        wants_coord = any(w in q_low for w in ("坐标系", "基准面", "plane", "y-up", "z-up", "法向", "normal"))
        if any(w in q_low for w in ("solidworks", "基准面", "front", "top", "right", "sw")):
            _add("solidworks")
        if any(w in q_low for w in ("vericut", "vcproject", "autodiff", "auto-diff", "auto diff", "nx", "cnc", "g54", "过切", "残料", "gouge", "excess", "inch", "millimeter")):
            _add("vericut_cnc")
        if wants_coord and not selected:
            _add("solidworks")
            _add("vericut_cnc")
        elif wants_coord and len(selected) == 1:
            # Explicit cross-contrast prevents subtle Y-up / Z-up bleeding when coordinates are discussed
            _add("solidworks")
            _add("vericut_cnc")

        if any(w in q_low for w in ("lam", "厚壁", "环向应力", "径向应力", "sigma_", "σ_θ", "σ_r", "fos", "屈服", "von mises")):
            _add("lame")
        if any(w in q_low for w in ("g71", "g70", "fanuc", "车削", "粗车", "精车", "t0101", "扎刀", "台阶轴")):
            _add("fanuc_g71")

        if include_all_if_empty and not selected:
            for k in ("solidworks", "vericut_cnc", "lame", "fanuc_g71"):
                _add(k)
        return selected

    def build_domain_memory_context(
        self,
        query: str,
        *,
        bank_ids: Optional[List[str]] = None,
        max_items: int = 4,
        update_stats: bool = False,
        include_invariants: bool = True,
        include_all_invariants_if_unmatched: bool = False,
        working_memory_block: str = "",
        extra_sections: Optional[List[str]] = None,
        max_chars: int = 2400,
    ) -> str:
        """Build a concise, software-isolated engineering memory block for runtime prompts."""
        sections: List[str] = []
        shown_invariants: List[str] = []

        if include_invariants:
            invs = self.select_coordinate_invariants(
                query, include_all_if_empty=include_all_invariants_if_unmatched
            )
            if invs:
                inv_lines = [f"- [{k}] {txt}" for k, txt in invs]
                shown_invariants = [txt for _, txt in invs]
                sections.append("[跨软件坐标系与工程规范锚点]\n" + "\n".join(inv_lines))

        hits = self.recall_all_banks(
            query=query,
            bank_ids=bank_ids,
            max_results=max_items * 2 if include_invariants else max_items,
            update_stats=update_stats,
        )
        if hits:
            hit_lines = []
            for h in hits:
                raw_content = str(h.get("content", "")).strip()
                if include_invariants and (
                    "canonical_invariant" in (h.get("tags") or [])
                    or any(raw_content == inv_txt for inv_txt in shown_invariants)
                ):
                    continue
                content = re.sub(r"\s+", " ", raw_content)[:220]
                if content:
                    hit_lines.append(
                        f"- [{h.get('bank_id', 'default')}/{h.get('memory_type', 'fact')}] {content}"
                    )
                if len(hit_lines) >= max_items:
                    break
            if hit_lines:
                sections.append("[Hindsight 跨库检索]\n" + "\n".join(hit_lines))

        if working_memory_block and working_memory_block.strip():
            sections.append(working_memory_block.strip())

        for extra in extra_sections or []:
            if extra and str(extra).strip():
                sections.append(str(extra).strip())

        combined = "\n\n".join(sections).strip()
        if max_chars > 0 and len(combined) > max_chars:
            combined = combined[: max_chars - 3].rstrip() + "..."
        return combined

    def reflect(
        self,
        bank_id: str,
        query: str,
        budget: str = "mid",
        context: Optional[str] = None,
        update_stats: bool = True,
    ) -> Dict[str, Any]:
        """Core Operation: Reflect on past memory units to synthesize actionable guidance."""
        # Recall relevant memories from primary bank, then enrich across all banks
        recalled = self.recall(
            bank_id=bank_id, query=query, max_results=6, update_stats=update_stats
        )
        seen = {m.get("id") for m in recalled if m.get("id")}
        for extra in self.recall_all_banks(
            query=query,
            bank_ids=[b for b in self.banks if b != bank_id],
            max_results=4,
            update_stats=update_stats,
        ):
            if extra.get("id") not in seen:
                recalled.append(extra)
                seen.add(extra.get("id"))

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
                # 向后兼容：旧 JSON 缺新字段时补齐默认值（内存态，不立即回写文件）
                self._normalize_loaded()
            except Exception as e:
                print(f"[Virtu-Hindsight] Load error: {e}")
                self.banks = {}
                # 读失败后禁止回写：否则一次损坏的 JSON 会被空 banks 永久抹掉
                self._storage_load_failed = True

    def _save_storage(self):
        if self._storage_load_failed:
            print("[Virtu-Hindsight] Refusing to save: storage load failed, original file left untouched")
            return
        try:
            import copy
            banks_snapshot = copy.deepcopy(self.banks)
            payload = json.dumps(
                {"version": "2.0-Hindsight", "updated_at": time.time(), "banks": banks_snapshot},
                ensure_ascii=False,
                indent=2,
            )
            _atomic_write_text(self.storage_path, payload)
        except Exception as e:
            print(f"[Virtu-Hindsight] Save error: {e}")

    def prune(self, max_units: int = 2000, bank_id: Optional[str] = None) -> int:
        """按 utility+recency 淘汰到容量上限，返回淘汰数量。

        bank_id 为 None 时对全部 bank 做全局容量约束；否则只约束该 bank。
        """
        now = time.time()
        if bank_id is not None:
            bank = self.banks.get(bank_id)
            if bank is None:
                return 0
            units = bank.get("units", {})
            overflow = len(units) - max_units
            if overflow <= 0:
                return 0
            evictable = [(uid, u) for uid, u in units.items() if not self._is_canonical(u)]
            ranked = sorted(evictable, key=lambda kv: self._keep_score(kv[1], now))
            removed = self._evict(bank, [uid for uid, _ in ranked[:overflow]])
            if removed:
                self._save_storage()
            return removed

        total_units = sum(len(b.get("units", {})) for b in self.banks.values())
        overflow = total_units - max_units
        if overflow <= 0:
            return 0
        all_items = []
        for bank in self.banks.values():
            for uid, u in bank.get("units", {}).items():
                if not self._is_canonical(u):
                    all_items.append((bank, uid, u))
        all_items.sort(key=lambda t: self._keep_score(t[2], now))
        removed = 0
        for bank, uid, _ in all_items[:overflow]:
            removed += self._evict(bank, [uid])
        if removed:
            self._save_storage()
        return removed

    def compact(self, bank_id: Optional[str] = None) -> int:
        """清理过期 unit 与重复内容 unit（按 utility+recency 保留最优者），返回淘汰数量。"""
        now = time.time()
        banks = ([self.banks[bank_id]] if bank_id and bank_id in self.banks
                 else list(self.banks.values()))
        removed = 0
        for bank in banks:
            units = bank.get("units", {})
            best: Dict[str, Tuple[float, str, bool]] = {}
            for uid, u in units.items():
                fp = self._fingerprint(u.get("content", ""))
                expired = self._is_expired(u, now)
                score = -1.0 if expired else self._keep_score(u, now)
                cur = best.get(fp)
                if cur is None or score > cur[0]:
                    best[fp] = (score, uid, expired)
            keep_ids = {uid for _score, uid, expired in best.values() if not expired}
            # canonical 安全不变量即使被标过期/重复也不淘汰
            keep_ids.update(uid for uid, u in units.items() if self._is_canonical(u))
            victims = [uid for uid in units if uid not in keep_ids]
            removed += self._evict(bank, victims)
        if removed:
            self._save_storage()
        return removed

    @staticmethod
    def is_sleep_debug_noise(unit: Dict[str, Any]) -> bool:
        """Identify raw Sleep telemetry / debug JSON dumps that pollute semantic recall.

        Never flags verified canonical invariants or genuine engineering rules.
        """
        tags = {str(t) for t in (unit.get("tags") or [])}
        if "canonical_invariant" in tags:
            return False
        content = str(unit.get("content") or "")
        if "【Sleep固化心智模型-task_verified_facts】" in content:
            return True
        noise_markers = (
            "DYNAMIC_GAP",
            "缺少未知切削刀具参数",
            '"facets_engaged"',
            "'facets_engaged'",
        )
        return any(marker in content for marker in noise_markers)

    def purge_sleep_debug_noise(
        self,
        *,
        bank_id: Optional[str] = None,
        save: bool = True,
    ) -> int:
        """Remove noisy Sleep debug/telemetry JSON blobs from memory banks and rebuild storage."""
        banks = (
            [self.banks[bank_id]]
            if bank_id and bank_id in self.banks
            else list(self.banks.values())
        )
        removed = 0
        for bank in banks:
            units = bank.get("units", {})
            victims = [uid for uid, u in units.items() if self.is_sleep_debug_noise(u)]
            if victims:
                removed += self._evict(bank, victims)
        if removed and save:
            self._save_storage()
        return removed

    def get_status(self) -> Dict[str, Any]:
        """Return system health and bank statistics."""
        total_units = sum(len(b.get("units", {})) for b in self.banks.values())
        return {
            "framework": "Vectorize Hindsight (arXiv:2512.12818)",
            "operations": ["retain", "recall", "reflect", "prune", "compact"],
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
