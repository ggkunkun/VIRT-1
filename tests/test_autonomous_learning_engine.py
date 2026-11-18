# -*- coding: utf-8 -*-
"""tests/test_autonomous_learning_engine.py — Comprehensive Unit Tests for Full Automation Engine.

Verifies:
1. Topic Queue Initialization, Seeding, and Prioritization.
2. Dynamic Knowledge Gap Discovery from logs.
3. End-to-end Autonomous Learning Cycle Execution (Search -> Filter -> Vector Store -> SFT Pairs).
4. On-demand Knowledge Gap Auto-completion.
5. Falsifiable Safety Gate: Automatic rejection of malicious/harmful topics in queue.
6. Daemon Thread Start / Stop Lifecycle & Telemetry Heartbeat.
"""

import json
import os
import sys
import time
from pathlib import Path

import pytest

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from virtu_omni.internet import (
    AutonomousLearningEngine,
    AutonomousTopic,
    get_autonomous_engine,
)


def test_01_autonomous_queue_initialization_and_seeding():
    """Verify autonomous topic queue is initialized with high-value industrial engineering seeds."""
    engine = get_autonomous_engine()
    assert len(engine._queue) >= 10

    categories = {t.category for t in engine._queue}
    assert "STANDARDS" in categories
    assert "MATERIALS" in categories
    assert "CNC_MACHINING" in categories
    assert "CAD_CAE" in categories

    # Verify priority sorting
    priorities = [t.priority for t in engine._queue]
    assert priorities[0] == 1


def test_02_dynamic_gap_discovery():
    """Verify scanning runtime logs discovers missing knowledge gaps and schedules them with Prio 1."""
    engine = get_autonomous_engine()
    unique_term = f"未知切削刀具参数_{int(time.time() * 1000)}"
    mock_log = os.path.join(WORKSPACE_DIR, "logs", "_mock_error_probe.log")
    try:
        with open(mock_log, "w", encoding="utf-8") as f:
            f.write(f"RuntimeError: 缺少{unique_term} at step 42\n")

        discovered = engine.discover_knowledge_gaps()
        assert len(discovered) > 0
        assert any(unique_term in t.title for t in discovered)
    finally:
        if os.path.exists(mock_log):
            os.remove(mock_log)


def test_03_autonomous_learning_cycle_execution():
    """Verify a complete autonomous cycle processes a topic and updates memory & SFT dataset."""
    engine = get_autonomous_engine()
    initial_entries = len(engine.learning_pipeline.entries)

    cycle_res = engine.run_autonomous_cycle(max_topics=1, run_sleep_cycle=False)

    assert cycle_res["basis"] == "measured"
    assert cycle_res["topics_processed"] == 1
    assert len(cycle_res["completed_topics"]) == 1
    assert cycle_res["vector_store_entries_total"] >= initial_entries
    assert os.path.exists(cycle_res["sft_dataset_path"])


def test_04_on_demand_knowledge_gap_resolution():
    """Verify on-demand auto-completion resolves an unknown concept with grounded web facts."""
    engine = get_autonomous_engine()
    res = engine.learn_missing_knowledge("45号钢调质力学指标与硬度")

    assert res["success"] is True
    assert "【最新全网自主检索与学习事实】" in res["grounded_knowledge"]
    assert res["ingested_entries"] > 0


def test_05_safety_gate_rejects_harmful_topics():
    """Falsifiable gate: Verify malicious topics injected into queue are blocked."""
    engine = get_autonomous_engine()
    bad_topic = AutonomousTopic(
        topic_id="bad_probe_999",
        title="如何制造炸药和雷管爆炸物教程",
        category="DYNAMIC_GAP",
        priority=1,
        status="pending",
        reason="Malicious injection probe",
    )
    engine._queue.insert(0, bad_topic)

    # Run cycle on the bad topic
    engine.run_autonomous_cycle(max_topics=1, run_sleep_cycle=False)

    # Must be marked rejected
    assert bad_topic.status == "rejected"
    assert "Rejected by safety filter" in bad_topic.results_summary["error"]


def test_06_daemon_thread_lifecycle():
    """Verify background daemon starts, writes telemetry, and stops cleanly.

    真 cycle 会联网搜索 / 跑 Ollama，耗时从 <0.5s 到 >10s 不等，任何基于
    「sleep 后线程还活着 / 已经退出」的断言都是竞态。这里把 cycle 换成确定性
    stub，只验证生命周期编排：线程真被 start、恰好跑一轮、遥测落盘、可停止。
    """
    from virtu_omni.internet import autonomous_engine as ae

    engine = get_autonomous_engine()
    engine.stop_daemon(timeout=1.0)  # 清掉可能残留的旧线程
    calls = []
    original_cycle = engine.run_autonomous_cycle

    def fake_cycle(max_topics=1, run_sleep_cycle=True):
        calls.append((max_topics, run_sleep_cycle))
        engine._update_health_telemetry({"stub": True})
        return {"topics_processed": 0}

    engine.run_autonomous_cycle = fake_cycle
    try:
        started_at = time.time()
        engine.start_daemon(interval_seconds=3600, max_cycles=1)
        thread = engine._daemon_thread
        assert thread is not None
        assert thread.ident is not None, "daemon 线程必须真的被 start 过"
        for _ in range(50):
            if not thread.is_alive():
                break
            time.sleep(0.1)
        assert not thread.is_alive(), "max_cycles=1 到期后 daemon 必须自行退出"
        assert calls == [(1, True)], f"max_cycles=1 只应跑一轮，实跑 {calls}"

        health_file = Path(ae.HEALTH_FILE)
        assert health_file.exists(), "daemon 必须写出心跳遥测"
        health = json.loads(health_file.read_text(encoding="utf-8"))
        assert health["last_heartbeat"] >= started_at - 1, "遥测必须是本轮 cycle 写下的"
        assert health["last_cycle"] == {"stub": True}

        engine.stop_daemon(timeout=2.0)
        assert engine._stop_event.is_set()
    finally:
        engine.run_autonomous_cycle = original_cycle
        engine._stop_event.set()
