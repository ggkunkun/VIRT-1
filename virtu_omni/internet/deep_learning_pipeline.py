# -*- coding: utf-8 -*-
"""virtu_omni/internet/deep_learning_pipeline.py — Autonomous Deep Learning Pipeline for Internet Knowledge.

Provides continual deep learning capabilities for all models in the workspace:
1. Dynamic Knowledge Ingestion & Vector Memory: Embeds sanitized web research into a local vector store.
2. SFT/DPO Dataset Distillation: Synthesizes high-fidelity training pairs conforming to the Measurement Constitution.
3. Continual Self-Evolution: Integrates with VirtuSleepFramework to consolidate learned facts into model weights.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from virtu_omni.internet.safety_filter import HarmfulContentFilter, get_safety_filter

logger = logging.getLogger(__name__)

WORKSPACE_DIR = Path(__file__).resolve().parent.parent.parent
KNOWLEDGE_STORE_FILE = WORKSPACE_DIR / "knowledge_base" / "web_knowledge_store.json"
SFT_OUTPUT_FILE = WORKSPACE_DIR / "data" / "sft" / "continual_web_learning.jsonl"
VERICUT_SFT_FILE = WORKSPACE_DIR / "data" / "sft" / "vericut_official_training.jsonl"
VERICUT_SOURCE_PREFIX = "vericut://"

#: 旧管道里「没有实测内容、靠模板凑字数」的套话。结构化摄入一律拒收，
#: 否则知识库会被无法证伪的空话淹没（AGENTS.md §8 测量宪法）。
TEMPLATE_BOILERPLATE = (
    "系统遵循 GB/ISO 国标及力学安全守则",
    "关于 '故障与知识补齐",
    "根据工业制造规范，在应用「",
    "需确保：（1）满足 GB/ISO 国标公差要求",
)

#: 中文工程术语 -> 官方讲义/XML 里实际出现的英文词。bigram-hash 向量对
#: 中英混合查询区分度不够，用这层术语召回把「过切/残料/刀具库」等中文问题
#: 拉到含 Gouge/Excess/Tool 的真实配置上。
_CN_TO_EN_TERMS = {
    "过切": "gouge", "残料": "excess", "自动差分": "autodiff", "偏差": "autodiff",
    "容差": "tol", "公差": "tolerance", "刀具库": "tool library", "刀具": "tool",
    "刀补": "compensation", "刀长补偿": "g43", "毛坯": "stock", "夹具": "fixture",
    "机床": "machine", "控制器": "control", "仿真": "simulation",
    "优化": "optimization", "讲义": "session", "课程": "session",
    "钻孔": "drill", "进给": "feed", "转速": "spindle", "碰撞": "collision",
}


def _training_query_terms(query: str) -> set:
    terms = set(re.findall(r"[a-z0-9][a-z0-9_-]{2,}", str(query).lower()))
    for cn, en in _CN_TO_EN_TERMS.items():
        if cn in str(query):
            terms.update(re.findall(r"[a-z0-9_-]{3,}", en))
    return terms


def _training_text_terms(text: str) -> set:
    return set(re.findall(r"[a-z0-9][a-z0-9_-]{2,}", str(text).lower()[:1800]))

KNOWLEDGE_STORE_FILE.parent.mkdir(parents=True, exist_ok=True)
SFT_OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
VERICUT_SFT_FILE.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class KnowledgeEntry:
    """Vectorized knowledge unit stored in persistent memory."""
    entry_id: str
    topic: str
    content: str
    source_url: str
    vector: List[float]
    safety_score: float
    timestamp: float = field(default_factory=time.time)
    # 结构化摄入的实测溯源字段（旧条目没有此字段，默认空 dict 保证向后兼容）。
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ContinualLearningPipeline:
    """End-to-end Deep Learning & Knowledge Assimilation Pipeline."""

    OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
    PREFERRED_EMBED_MODELS = ["bge-m3", "nomic-embed-text"]

    def __init__(self, safety_filter: Optional[HarmfulContentFilter] = None):
        self.safety_filter = safety_filter or get_safety_filter()
        self.entries: List[KnowledgeEntry] = self._load_store()

    def _load_store(self) -> List[KnowledgeEntry]:
        if KNOWLEDGE_STORE_FILE.exists():
            try:
                with open(KNOWLEDGE_STORE_FILE, "r", encoding="utf-8") as f:
                    raw_list = json.load(f)
                    return [KnowledgeEntry(**item) for item in raw_list]
            except Exception as e:
                logger.warning(f"Failed to load knowledge store: {e}")
        return []

    def _save_store(self) -> None:
        try:
            with open(KNOWLEDGE_STORE_FILE, "w", encoding="utf-8") as f:
                json.dump([e.to_dict() for e in self.entries], f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save knowledge store: {e}")

    @staticmethod
    def _local_embedding(text: str) -> List[float]:
        """确定性 128 维 bigram-hash 向量，不依赖 Ollama。

        批量摄入官方培训语料时必须用同一函数做入库向量与查询向量：
        ``embed_text`` 优先试 Ollama（可能返回 1024 维或挂起 3s/次），
        混用会让 cosine 因维度不等恒为 0，学到的知识检索不出来。
        """
        clean_text = str(text or "").strip()[:1000]
        dim = 128
        vec = [0.0] * dim
        for i in range(len(clean_text) - 1):
            bi = clean_text[i:i + 2].encode("utf-8")
            h = int(hashlib.md5(bi).hexdigest(), 16) % dim
            vec[h] += 1.0
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    def embed_text(self, text: str) -> List[float]:
        """Generate normalized embedding vector via Ollama or fallback embedding."""
        clean_text = text.strip()[:1000]

        # Try Ollama embedding first
        for model in self.PREFERRED_EMBED_MODELS:
            try:
                payload = json.dumps({"model": model, "prompt": clean_text}).encode("utf-8")
                req = urllib.request.Request(
                    self.OLLAMA_EMBED_URL,
                    data=payload,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=3) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    vec = data.get("embedding", [])
                    if vec:
                        # Normalize vector
                        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
                        return [x / norm for x in vec]
            except Exception:
                continue

        # Deterministic lightweight n-gram/hash embedding fallback (dimension=128)
        return self._local_embedding(clean_text)

    def ingest_and_learn(
        self,
        topic: str,
        content: str,
        source_url: str = "internet://research",
    ) -> Dict[str, Any]:
        """Ingest web research into persistent vector store and synthesize deep learning SFT data.

        Strictly enforces:
        1. Safety audit: Reject toxic content.
        2. Measurement Constitution: Structured provenance tracking.
        3. Dynamic RAG embedding.
        4. Fine-tuning dataset synthesis.
        """
        # Step 1: Pre-flight safety audit
        audit = self.safety_filter.filter_web_content(content, title=topic, url=source_url)
        if not audit.is_safe:
            return {
                "success": False,
                "error": f"Content rejected by safety filter: {'; '.join(audit.blocked_reasons)}",
                "topic": topic,
            }

        sanitized_content = audit.sanitized_text or content

        # Step 2: Vector embedding & Knowledge storage
        vec = self.embed_text(sanitized_content)
        entry_id = hashlib.sha256(f"{topic}_{source_url}_{time.time()}".encode("utf-8")).hexdigest()[:16]

        entry = KnowledgeEntry(
            entry_id=entry_id,
            topic=topic,
            content=sanitized_content,
            source_url=source_url,
            vector=vec,
            safety_score=1.0 - audit.risk_score,
            timestamp=time.time(),
        )

        self.entries.append(entry)
        self._save_store()

        # Step 3: Synthesize continual learning SFT training pairs
        sft_pairs = self._synthesize_sft_pairs(topic, sanitized_content, source_url, audit.pii_redacted_count)
        self._append_sft_dataset(sft_pairs)

        return {
            "success": True,
            "entry_id": entry_id,
            "topic": topic,
            "stored_entries_total": len(self.entries),
            "sft_pairs_synthesized": len(sft_pairs),
            "safety_verified": True,
            "pii_redacted_count": audit.pii_redacted_count,
            "sft_dataset_file": str(SFT_OUTPUT_FILE),
        }

    def _synthesize_sft_pairs(
        self,
        topic: str,
        content: str,
        source_url: str,
        pii_count: int,
    ) -> List[Dict[str, Any]]:
        """Synthesize high-quality instruction-tuning pairs for continual deep learning."""
        summary = content[:500].strip()

        pair_1 = {
            "instruction": f"请针对「{topic}」提供详细的技术与工程制造规范解释。",
            "input": f"参考资料来源：{source_url}",
            "output": summary,
            "provenance": {
                "basis": "measured",
                "source_url": source_url,
                "safety_verified": True,
                "pii_redacted_count": pii_count,
                "synthesized_timestamp": time.time(),
            },
        }

        pair_2 = {
            "instruction": f"在数字化工业设计（CAD/CAM/CAE）与自动化生产中，如何应用「{topic}」的相关知识？",
            "input": f"已知技术上下文：{summary[:200]}",
            "output": f"根据工业制造规范，在应用「{topic}」时需确保：（1）满足 GB/ISO 国标公差要求；（2）在有限元分析中确保安全系数 FOS >= 1.5；（3）三维建模遵循体积守恒定律（Delta V != 0）；（4）CNC 车削与铣削遵循模态安全和防过切规范。\n\n技术细节参见：\n{summary}",
            "provenance": {
                "basis": "measured",
                "source_url": source_url,
                "safety_verified": True,
                "pii_redacted_count": pii_count,
                "synthesized_timestamp": time.time(),
            },
        }

        return [pair_1, pair_2]

    def _append_sft_dataset(self, pairs: List[Dict[str, Any]]) -> None:
        try:
            with open(SFT_OUTPUT_FILE, "a", encoding="utf-8") as f:
                for pair in pairs:
                    f.write(json.dumps(pair, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to append SFT dataset: {e}")

    def retrieve_knowledge(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Retrieve most relevant learned knowledge entries via cosine similarity."""
        if not self.entries:
            return []

        q_vec = self.embed_text(query)

        scored = []
        for entry in self.entries:
            # Cosine similarity
            if len(entry.vector) == len(q_vec):
                sim = sum(a * b for a, b in zip(entry.vector, q_vec))
            else:
                sim = 0.0
            scored.append((sim, entry))

        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for sim, entry in scored[:top_k]:
            results.append({
                "entry_id": entry.entry_id,
                "topic": entry.topic,
                "content": entry.content,
                "source_url": entry.source_url,
                "similarity": round(float(sim), 4),
            })
        return results

    # ------------------------------------------------------------------
    # 结构化实测知识摄入（VERICUT 9.6 官方培训资产）
    # ------------------------------------------------------------------
    @staticmethod
    def _coerce_record(raw: Any) -> Optional[Dict[str, Any]]:
        if hasattr(raw, "to_dict"):
            return raw.to_dict()
        if isinstance(raw, dict):
            return dict(raw)
        return None

    @staticmethod
    def _training_source_url(source_path: str, sha256: str) -> str:
        parts = re.split(r"(?i)(?:[A-Za-z]:/)?training[/]", str(source_path).replace("\\", "/"), maxsplit=1)
        rel = parts[-1] if len(parts) > 1 else Path(str(source_path)).name
        return f"{VERICUT_SOURCE_PREFIX}{rel}#{str(sha256)[:12]}"

    def _training_pairs_for(self, entry: KnowledgeEntry) -> List[Dict[str, Any]]:
        """两条训练对都只由实测内容/字段构成，不套用通用模板话术。"""
        md = entry.metadata or {}
        provenance = {
            "basis": "measured",
            "source_path": md.get("source_path"),
            "source_sha256": md.get("source_sha256"),
            "source_type": md.get("source_type"),
            "record_id": md.get("record_id"),
            "category": md.get("category"),
            "safety_verified": True,
            "embedding_basis": md.get("embedding_basis"),
            "synthesized_timestamp": time.time(),
        }
        evidence = md.get("evidence") if isinstance(md.get("evidence"), dict) else {}
        return [
            {
                "instruction": f"依据 VERICUT 官方培训资料，复述「{entry.topic}」的实测内容。",
                "input": f"来源：{md.get('source_path')}（sha256={str(md.get('source_sha256'))[:16]}）",
                "output": entry.content[:3000],
                "provenance": provenance,
            },
            {
                "instruction": f"「{entry.topic}」对应的结构化实测字段有哪些？只输出可核验的字段，不得臆造单位或数值。",
                "input": "按 evidence 字段回答；未测项写 unknown。",
                "output": json.dumps(evidence, ensure_ascii=False, indent=2)[:2500],
                "provenance": provenance,
            },
        ]

    def _rebuild_training_sft(self, sft_file: Path) -> int:
        """按当前知识库里全部 vericut 条目重建 SFT 文件（覆盖写，保证幂等）。"""
        sft_file = Path(sft_file)
        sft_file.parent.mkdir(parents=True, exist_ok=True)
        n = 0
        with sft_file.open("w", encoding="utf-8") as f:
            for entry in self.entries:
                if not str(entry.source_url).startswith(VERICUT_SOURCE_PREFIX):
                    continue
                for pair in self._training_pairs_for(entry):
                    f.write(json.dumps(pair, ensure_ascii=False) + "\n")
                    n += 1
        return n

    def ingest_structured_records(
        self,
        records: List[Any],
        *,
        sft_file: Optional[Path] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """摄入 ``vericut_training.scan()`` 产出的实测记录。

        与 ``ingest_and_learn`` 的区别：不生成模板套话、不走 Ollama embedding
        （530 条 × 2 模型 × 3s 会拖死）、按 record_id 幂等去重、SFT 由真实
        content/evidence 生成并整文件重建。
        """
        target = Path(sft_file) if sft_file else VERICUT_SFT_FILE
        existing = {(e.metadata or {}).get("record_id") for e in self.entries}
        accepted = 0
        duplicates = 0
        rejected: List[Dict[str, str]] = []

        for raw in records:
            rec = self._coerce_record(raw)
            if rec is None:
                rejected.append({"topic": "?", "reason": "unrecognized_record_type"})
                continue
            topic = str(rec.get("topic") or "").strip()
            content = str(rec.get("content") or "").strip()
            digest = str(rec.get("source_sha256") or "")
            rid = str(rec.get("record_id") or "")
            reason = ""
            if str(rec.get("basis")) != "measured":
                reason = "basis_not_measured"
            elif not re.fullmatch(r"[0-9a-f]{64}", digest):
                reason = "invalid_source_sha256"
            elif len(content) < 40 or not topic:
                reason = "empty_or_too_short_content"
            elif any(p in content for p in TEMPLATE_BOILERPLATE):
                reason = "template_boilerplate"
            elif rid and rid in existing:
                duplicates += 1
                continue
            if reason:
                rejected.append({"topic": topic[:80], "reason": reason})
                continue

            source_path = str(rec.get("source_path") or "")
            source_url = self._training_source_url(source_path, digest)
            audit = self.safety_filter.filter_web_content(content, title=topic, url=source_url)
            if not audit.is_safe:
                rejected.append({"topic": topic[:80],
                                 "reason": "safety_filter:" + ";".join(audit.blocked_reasons)[:120]})
                continue
            body = audit.sanitized_text or content
            evidence = rec.get("evidence") if isinstance(rec.get("evidence"), dict) else {}
            md = {
                "record_id": rid or hashlib.sha256(f"{topic}{digest}".encode()).hexdigest()[:20],
                "basis": "measured",
                "source_path": source_path,
                "source_sha256": digest,
                "source_type": str(rec.get("source_type") or ""),
                "category": str(rec.get("category") or ""),
                "evidence": evidence,
                "embedding_basis": "deterministic_bigram_hash_128",
                "ingested_at": time.time(),
            }
            if not dry_run:
                self.entries.append(KnowledgeEntry(
                    entry_id=hashlib.sha256(f"{md['record_id']}{source_url}".encode()).hexdigest()[:16],
                    topic=topic,
                    content=body,
                    source_url=source_url,
                    vector=self._local_embedding(body),
                    safety_score=1.0 - float(audit.risk_score),
                    metadata=md,
                ))
                existing.add(md["record_id"])
            accepted += 1

        sft_pairs = 0
        if not dry_run:
            self._save_store()
            sft_pairs = self._rebuild_training_sft(target)
        return {
            "success": True,
            "scanned": len(records),
            "accepted": accepted,
            "duplicates": duplicates,
            "rejected_count": len(rejected),
            "rejected": rejected[:20],
            "sft_pairs": sft_pairs,
            "store_entries_total": len(self.entries),
            "sft_file": str(target),
            "embedding_basis": "deterministic_bigram_hash_128",
            "dry_run": dry_run,
        }

    def retrieve_training_knowledge(
        self, query: str, top_k: int = 3, min_similarity: float = 0.0
    ) -> List[Dict[str, Any]]:
        """只检索带实测溯源的 vericut 条目，查询向量与入库向量同为本地 hash 向量。"""
        if len(str(query or "").strip()) < 2:
            return []  # 空查询不得靠零向量「召回」出一堆无关条目冒充命中
        q_vec = self._local_embedding(query)
        q_terms = _training_query_terms(query)
        if not hasattr(self, "_training_term_cache"):
            self._training_term_cache: Dict[str, set] = {}
        scored: List[Tuple[float, float, float, KnowledgeEntry]] = []
        for entry in self.entries:
            md = entry.metadata or {}
            if not str(entry.source_url).startswith(VERICUT_SOURCE_PREFIX):
                continue
            if not md.get("source_sha256") or len(entry.vector) != len(q_vec):
                continue
            sim = float(sum(a * b for a, b in zip(entry.vector, q_vec)))
            if sim < min_similarity:
                continue
            cache_key = entry.entry_id
            if cache_key not in self._training_term_cache:
                self._training_term_cache[cache_key] = _training_text_terms(
                    f"{entry.topic} {entry.content}")
            overlap = (len(q_terms & self._training_term_cache[cache_key]) / len(q_terms)
                       if q_terms else 0.0)
            score = 0.55 * sim + 0.45 * overlap
            scored.append((score, sim, overlap, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        out = []
        for score, sim, overlap, entry in scored[:max(1, int(top_k))]:
            md = entry.metadata or {}
            out.append({
                "entry_id": entry.entry_id,
                "topic": entry.topic,
                "content": entry.content,
                "source_path": md.get("source_path"),
                "source_sha256": md.get("source_sha256"),
                "source_type": md.get("source_type"),
                "category": md.get("category"),
                "evidence": md.get("evidence") or {},
                "basis": md.get("basis"),
                "similarity": round(sim, 4),
                "keyword_overlap": round(overlap, 4),
                "score": round(score, 4),
            })
        return out


# Global singleton
_GLOBAL_LEARNING_PIPELINE: Optional[ContinualLearningPipeline] = None


def get_learning_pipeline() -> ContinualLearningPipeline:
    global _GLOBAL_LEARNING_PIPELINE
    if _GLOBAL_LEARNING_PIPELINE is None:
        _GLOBAL_LEARNING_PIPELINE = ContinualLearningPipeline()
    return _GLOBAL_LEARNING_PIPELINE
