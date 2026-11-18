# -*- coding: utf-8 -*-
"""virtu_omni/internet/autonomous_engine.py — Fully Autonomous Internet Learning & Evolution Engine.

Enables end-to-end full automation:
1. Autonomous Knowledge Gap & Topic Discovery: Scans missing standards, material parameters, and machining rules.
2. Automated Multi-Tier Safety Guard: Filters bad/harmful queries and web pages, redacts PII.
3. Automated Continual Deep Learning: Vectorizes knowledge into RAG memory and distills SFT training pairs.
4. Autonomous Sleep Consolidation: Bridges with VirtuSleepFramework for dream synthesis and homeostasis.
5. All-Weather Daemon Service: Runs background scheduler with health telemetry, auto-recovery, and self-monitoring.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

WORKSPACE_DIR = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from virtu_omni.internet.safety_filter import HarmfulContentFilter, get_safety_filter
from virtu_omni.internet.search_engine import WebSearchEngine, get_search_engine
from virtu_omni.internet.deep_learning_pipeline import ContinualLearningPipeline, get_learning_pipeline

logger = logging.getLogger("virtu_omni.internet.autonomous")

QUEUE_FILE = WORKSPACE_DIR / "knowledge_base" / "autonomous_topic_queue.json"
HEALTH_FILE = WORKSPACE_DIR / "reports" / "autonomous_daemon_health.json"
SFT_FILE = WORKSPACE_DIR / "data" / "sft" / "continual_web_learning.jsonl"

QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
HEALTH_FILE.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class AutonomousTopic:
    """A topic in the autonomous queue."""
    topic_id: str
    title: str
    category: str  # STANDARDS, MATERIALS, CNC_MACHINING, CAD_CAE, DYNAMIC_GAP
    priority: int  # 1 (highest) to 10 (lowest)
    status: str  # "pending", "in_progress", "completed", "rejected", "failed"
    reason: str
    added_timestamp: float = field(default_factory=time.time)
    completed_timestamp: Optional[float] = None
    results_summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AutonomousLearningEngine:
    """Full-cycle autonomous learning orchestrator."""

    # Curated knowledge discovery seed bank for autonomous continuous exploration
    CURATED_TOPIC_BANK = [
        # 1. Engineering Standards
        ("GB/T 1800.1-2020 极限与配合基础公差等级与偏差", "STANDARDS", 1, "核心国家标准基础规范"),
        ("ISO 286-1 线性尺寸公差代号体系与孔轴配合选择", "STANDARDS", 1, "国际标准化组织基础标准"),
        ("GB/T 8129 工业自动化系统与数控机床术语规范", "STANDARDS", 2, "CNC 与自动化术语统一"),
        ("ASME Y14.5-2018 几何尺寸与公差 (GD&T) 标注基准", "STANDARDS", 2, "精密机械形位公差基准体系"),
        ("DIN 76 螺纹收尾退刀槽与倒角标准参数", "STANDARDS", 3, "标准件螺纹连接退刀槽设计"),

        # 2. Materials & CAE Elasticity
        ("6061-T6 铝合金弹性模量泊松比与屈服强度机械性能", "MATERIALS", 1, "航空与常规工业法兰常用材料参数"),
        ("45号钢调质处理抗拉强度与硬度力学指标", "MATERIALS", 2, "轴类核心材料力学性能"),
        ("TC4 钛合金高温强度与数控加工切削参数推荐", "MATERIALS", 2, "航空高温钛合金切削热与转速"),
        ("304不锈钢屈服极限与拉伸成型材料参数", "MATERIALS", 2, "耐腐蚀薄板冲压材料特性"),
        ("厚壁圆筒 Lamé 弹性力学方程与内压应力分布解析解", "CAD_CAE", 1, "CAE 闭环强度校核理论依据"),

        # 3. CNC Machining & Toolpaths
        ("FANUC 0i-TF 车削宏程序 #100 #500 变量编程与逻辑控制", "CNC_MACHINING", 1, "数控机床宏程序核心语法"),
        ("铣削切削线速度 Vc 与主轴转速 S 计算公式与 MRR 计算", "CNC_MACHINING", 1, "切削参数与材料去除率核心公式"),
        ("FANUC G71 复合粗车循环与 G70 精车走刀编程格式", "CNC_MACHINING", 2, "外圆粗精车模态指令规范"),
        ("五轴联动 CNC 叶轮与叶片加工防干涉刀轴控制策略", "CNC_MACHINING", 3, "复杂曲面多轴加工安全规程"),

        # 4. Parametric CAD & Digital Manufacturing
        ("SolidWorks 2021 COM Automation EquationMgr 参数化尺寸约束驱动", "CAD_CAE", 1, "三维特征树参数化方程式绑定"),
        ("OpenCASCADE B-Rep 实体拓扑缝合与非流形几何自愈算法", "CAD_CAE", 2, "B-Rep 几何核修补核心原理"),
        ("Google SayCan 工业软件可供性与防死锁断言机制", "CAD_CAE", 3, "大模型操作工业软件防崩溃机制"),
    ]

    def __init__(
        self,
        safety_filter: Optional[HarmfulContentFilter] = None,
        search_engine: Optional[WebSearchEngine] = None,
        learning_pipeline: Optional[ContinualLearningPipeline] = None,
    ):
        self.safety_filter = safety_filter or get_safety_filter()
        self.search_engine = search_engine or get_search_engine()
        self.learning_pipeline = learning_pipeline or get_learning_pipeline()
        self._daemon_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._queue: List[AutonomousTopic] = self._load_queue()
        self._ensure_seed_topics()

    def _load_queue(self) -> List[AutonomousTopic]:
        if QUEUE_FILE.exists():
            try:
                with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    return [AutonomousTopic(**item) for item in raw]
            except Exception as e:
                logger.warning(f"Failed to load autonomous topic queue: {e}")
        return []

    def _save_queue(self) -> None:
        try:
            with open(QUEUE_FILE, "w", encoding="utf-8") as f:
                json.dump([t.to_dict() for t in self._queue], f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save autonomous topic queue: {e}")

    def _ensure_seed_topics(self) -> None:
        """Seed initial high-value industrial engineering topics if queue is empty."""
        existing_titles = {t.title for t in self._queue}
        added = False
        for title, cat, prio, reason in self.CURATED_TOPIC_BANK:
            if title not in existing_titles:
                t_id = hashlib.sha256(title.encode("utf-8")).hexdigest()[:12]
                self._queue.append(
                    AutonomousTopic(
                        topic_id=t_id,
                        title=title,
                        category=cat,
                        priority=prio,
                        status="pending",
                        reason=reason,
                    )
                )
                added = True
        if added:
            # Sort queue by priority (1 is highest)
            self._queue.sort(key=lambda x: x.priority)
            self._save_queue()

    def discover_knowledge_gaps(self) -> List[AutonomousTopic]:
        """Scan logs and recent failed executions to discover real-time knowledge gaps."""
        discovered = []
        logs_dir = WORKSPACE_DIR / "logs"
        if logs_dir.exists():
            for log_f in logs_dir.glob("*.log"):
                try:
                    with open(log_f, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        # Search for error clues or missing parameters
                        matches = re.findall(r"(?:缺少|未知|未定义|不支持的|Error:)\s*([A-Za-z0-9_\-\u4e00-\u9fa5]{4,25})", content)
                        existing_titles = {t.title for t in self._queue}
                        for m in set(matches[:3]):
                            t_title = f"故障与知识补齐: {m}"
                            if t_title not in existing_titles and len(m) > 4:
                                t_id = hashlib.sha256(m.encode("utf-8")).hexdigest()[:12]
                                topic = AutonomousTopic(
                                    topic_id=t_id,
                                    title=t_title,
                                    category="DYNAMIC_GAP",
                                    priority=1,
                                    status="pending",
                                    reason=f"在运行日志 {log_f.name} 中检测到不明确或报错实体",
                                )
                                self._queue.insert(0, topic)
                                existing_titles.add(t_title)
                                discovered.append(topic)
                except Exception:
                    pass

        if discovered:
            self._save_queue()
        return discovered

    def run_autonomous_cycle(self, max_topics: int = 1, run_sleep_cycle: bool = True) -> Dict[str, Any]:
        """Execute one complete autonomous learning cycle:

        1. Select next pending topics from queue.
        2. Audit topic via HarmfulContentFilter.
        3. Perform multi-source Web Search.
        4. Scrape & sanitize web pages.
        5. Ingest into Vector RAG Store.
        6. Synthesize continual SFT training pairs with provenance.
        7. Record into VirtuSleepFramework WakeBuffer and optionally trigger Sleep Consolidation.
        8. Update health telemetry and cycle report.
        """
        cycle_start_t = time.time()
        logger.info(f"Starting autonomous learning cycle (budget: {max_topics} topics)...")

        # Refresh queue with dynamic gaps if any
        self.discover_knowledge_gaps()

        pending_topics = [t for t in self._queue if t.status == "pending"]
        if not pending_topics:
            logger.info("No pending topics in queue. Resetting completed topics to maintain continuous learning.")
            for t in self._queue:
                t.status = "pending"
            pending_topics = self._queue
            self._save_queue()

        topics_to_process = pending_topics[:max_topics]
        processed_reports = []

        for topic in topics_to_process:
            topic.status = "in_progress"
            self._save_queue()
            logger.info(f" -> Processing topic [{topic.category}] '{topic.title}' (prio={topic.priority})")

            # Step 1: Pre-flight safety audit
            audit = self.safety_filter.audit_query(topic.title)
            if not audit.is_safe:
                topic.status = "rejected"
                topic.results_summary = {
                    "error": "Rejected by safety filter",
                    "reasons": audit.blocked_reasons,
                }
                self._save_queue()
                logger.warning(f"    [REJECTED] Topic failed safety audit: {audit.blocked_reasons}")
                continue

            # Step 2: Web Search
            search_res = self.search_engine.search(topic.title, num_results=3)
            if not search_res.is_safe or not search_res.results:
                topic.status = "failed"
                topic.results_summary = {"error": search_res.error_message or "No results found"}
                self._save_queue()
                logger.warning(f"    [FAILED] Web search yielded zero results: {search_res.error_message}")
                continue

            # Step 3: Deep Extraction & Ingestion
            learned_snippets = []
            for item in search_res.results:
                # Ingest snippet into vector store & SFT dataset
                ingest_res = self.learning_pipeline.ingest_and_learn(
                    topic=f"{topic.title} - {item.title}",
                    content=item.snippet,
                    source_url=item.url,
                )
                if ingest_res.get("success"):
                    learned_snippets.append({
                        "entry_id": ingest_res.get("entry_id"),
                        "title": item.title,
                        "url": item.url,
                        "pairs_count": ingest_res.get("sft_pairs_synthesized", 0),
                    })

                # Try scraping page content if URL is external
                if item.url.startswith("http") and not "samr.gov.cn" in item.url:
                    content_res = self.search_engine.fetch_web_content(item.url, max_chars=1200)
                    if content_res["success"] and content_res["text"]:
                        deep_ingest = self.learning_pipeline.ingest_and_learn(
                            topic=f"{topic.title} (Deep Excerpt)",
                            content=content_res["text"][:600],
                            source_url=item.url,
                        )
                        if deep_ingest.get("success"):
                            learned_snippets.append({
                                "entry_id": deep_ingest.get("entry_id"),
                                "title": f"{item.title} (Page Excerpt)",
                                "url": item.url,
                                "pairs_count": deep_ingest.get("sft_pairs_synthesized", 0),
                            })

            topic.status = "completed"
            topic.completed_timestamp = time.time()
            topic.results_summary = {
                "sources_found": len(search_res.results),
                "learned_snippets_count": len(learned_snippets),
                "learned_snippets": learned_snippets,
                "engines_used": search_res.source_engines_used,
            }
            self._save_queue()

            # Step 4: Record into VirtuSleepFramework WakeBuffer
            try:
                from virtu_omni.memory import get_sleep_framework
                sf = get_sleep_framework()
                wake_prompt = f"自主学习主题: {topic.title}"
                wake_completion = f"从全网检索提炼工业制造知识：\n" + "\n".join(f"- {s['title']}: {s['url']}" for s in learned_snippets)
                sf.record_wake_step(
                    prompt=wake_prompt,
                    completion=wake_completion,
                    verified_facts={"topic": topic.title, "category": topic.category, "sources": len(learned_snippets)},
                    tool_calls=[{"name": "cadcam_web_search", "args": {"query": topic.title}}],
                )
            except Exception as e:
                logger.debug(f"Sleep framework record step skipped: {e}")

            processed_reports.append(topic.to_dict())
            logger.info(f"    [COMPLETED] Successfully ingested {len(learned_snippets)} items into memory & SFT dataset.")

        # Step 5: Optional Sleep Phase Consolidation
        sleep_report = None
        if run_sleep_cycle and processed_reports:
            try:
                from virtu_omni.memory import get_sleep_framework, build_ollama_model_caller
                caller, label = build_ollama_model_caller()
                sf = get_sleep_framework(model_caller=caller, model_caller_label=label)
                logger.info(f"Triggering VirtuSleepFramework memory consolidation (caller={label})...")
                sleep_report = sf.run_sleep_cycle(run_id=f"auto_cycle_{int(cycle_start_t)}")
                logger.info(
                    "Sleep consolidation completed: gate=%s valid=%s basis=%s",
                    sleep_report["homeostasis_gate_passed"],
                    sleep_report["measurement_valid"],
                    sleep_report["basis"],
                )
            except Exception as e:
                logger.warning(f"Sleep consolidation phase encountered exception: {e}")
                sleep_report = {"status": "skipped", "reason": str(e)}

        elapsed = time.time() - cycle_start_t

        cycle_summary = {
            "timestamp": time.time(),
            "runtime_seconds": round(elapsed, 2),
            "topics_processed": len(processed_reports),
            "completed_topics": [p["title"] for p in processed_reports if p["status"] == "completed"],
            "vector_store_entries_total": len(self.learning_pipeline.entries),
            "sft_dataset_path": str(SFT_FILE),
            "sleep_consolidation": sleep_report,
            "basis": "measured",
        }

        # Update health telemetry
        self._update_health_telemetry(cycle_summary)
        return cycle_summary

    def learn_missing_knowledge(self, concept_or_question: str) -> Dict[str, Any]:
        """On-demand auto-completion: Model hits unknown concept -> autonomously learns it online in real-time."""
        logger.info(f"On-demand autonomous knowledge acquisition triggered for: '{concept_or_question}'")

        # 1. Audit
        audit = self.safety_filter.audit_query(concept_or_question)
        if not audit.is_safe:
            return {
                "success": False,
                "error": f"Rejected by safety filter: {'; '.join(audit.blocked_reasons)}",
                "concept": concept_or_question,
            }

        # 2. Safe Web Search
        search_res = self.search_engine.search(audit.sanitized_text or concept_or_question, num_results=3)
        if not search_res.is_safe or not search_res.results:
            return {
                "success": False,
                "error": search_res.error_message or "No web results found",
                "concept": concept_or_question,
            }

        # 3. Ingest into Vector Store and SFT
        ingested = []
        for item in search_res.results[:2]:
            res = self.learning_pipeline.ingest_and_learn(
                topic=item.title,
                content=item.snippet,
                source_url=item.url,
            )
            if res.get("success"):
                ingested.append(res)

        # 4. Formulate grounded answer
        top_snippet = search_res.results[0]
        grounded_knowledge = (
            f"【最新全网自主检索与学习事实】\n"
            f"主题: {top_snippet.title}\n"
            f"核心内容: {top_snippet.snippet}\n"
            f"数据来源: {top_snippet.url}\n"
            f"已自动向量化存入本地知识库并生成持续学习微调数据对。"
        )

        return {
            "success": True,
            "concept": concept_or_question,
            "grounded_knowledge": grounded_knowledge,
            "sources_count": len(search_res.results),
            "ingested_entries": len(ingested),
            "vector_store_total": len(self.learning_pipeline.entries),
        }

    def _update_health_telemetry(self, last_cycle_summary: Dict[str, Any]) -> None:
        """Write continuous daemon status telemetry for external monitoring."""
        pending_count = sum(1 for t in self._queue if t.status == "pending")
        completed_count = sum(1 for t in self._queue if t.status == "completed")
        rejected_count = sum(1 for t in self._queue if t.status == "rejected")

        health = {
            "daemon_status": "RUNNING" if self._daemon_thread and self._daemon_thread.is_alive() else "STANDBY",
            "last_heartbeat": time.time(),
            "last_heartbeat_human": time.strftime("%Y-%m-%d %H:%M:%S"),
            "queue_stats": {
                "total_topics": len(self._queue),
                "pending": pending_count,
                "completed": completed_count,
                "rejected": rejected_count,
            },
            "knowledge_stats": {
                "vector_store_entries": len(self.learning_pipeline.entries),
                "sft_pairs_file": str(SFT_FILE),
                "sft_file_exists": SFT_FILE.exists(),
                "sft_file_size_bytes": SFT_FILE.stat().st_size if SFT_FILE.exists() else 0,
            },
            "last_cycle": last_cycle_summary,
        }

        try:
            with open(HEALTH_FILE, "w", encoding="utf-8") as f:
                json.dump(health, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to write health telemetry: {e}")

    def start_daemon(self, interval_seconds: int = 1800, max_cycles: Optional[int] = None) -> None:
        """Start the continuous background autonomous learning daemon."""
        if self._daemon_thread and self._daemon_thread.is_alive():
            logger.info("Autonomous learning daemon is already running.")
            return

        self._stop_event.clear()

        def _daemon_loop():
            logger.info(f"Autonomous Learning Daemon started. Sleep interval: {interval_seconds}s")
            cycles = 0
            while not self._stop_event.is_set():
                try:
                    self.run_autonomous_cycle(max_topics=1, run_sleep_cycle=True)
                    cycles += 1
                    if max_cycles and cycles >= max_cycles:
                        logger.info(f"Reached max_cycles ({max_cycles}). Daemon stopping.")
                        break
                except Exception as e:
                    logger.error(f"Error during autonomous cycle: {e}", exc_info=True)

                # Sleep in increments of 1 second so shutdown is responsive
                for _ in range(interval_seconds):
                    if self._stop_event.is_set():
                        break
                    time.sleep(1)

            logger.info("Autonomous Learning Daemon stopped gracefully.")

        self._daemon_thread = threading.Thread(target=_daemon_loop, daemon=True, name="VirtuAutoLearningDaemon")
        self._daemon_thread.start()

    def stop_daemon(self, timeout: float = 5.0) -> None:
        """Stop the running background daemon."""
        self._stop_event.set()
        if self._daemon_thread:
            self._daemon_thread.join(timeout=timeout)
            logger.info("Autonomous Learning Daemon terminated.")


# Global singleton
_GLOBAL_AUTONOMOUS_ENGINE: Optional[AutonomousLearningEngine] = None


def get_autonomous_engine() -> AutonomousLearningEngine:
    global _GLOBAL_AUTONOMOUS_ENGINE
    if _GLOBAL_AUTONOMOUS_ENGINE is None:
        _GLOBAL_AUTONOMOUS_ENGINE = AutonomousLearningEngine()
    return _GLOBAL_AUTONOMOUS_ENGINE
