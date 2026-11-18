# -*- coding: utf-8 -*-
"""tests/test_internet_search_and_learn.py — Integration Tests for Web Search, Continual Deep Learning, and Hub.

Verifies:
1. Web Search Engine execution and offline fallback resilience.
2. Web Content Scraper and sanitization.
3. Continual Deep Learning: vector memory embedding and SFT pair synthesis.
4. Universal Internet Hub model discovery and tool execution.
"""

import json
import os
import shutil
import sys
import urllib.request

import pytest

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from virtu_omni.internet import (
    WebSearchEngine,
    ContinualLearningPipeline,
    VirtuInternetHub,
    get_internet_hub,
)
from bridges.tool_calling_specs import execute_tool_call


def test_01_web_search_engine_basic():
    """Verify web search returns safe results and tracks source engines."""
    hub = get_internet_hub()
    res = hub.web_search_tool("ISO 286 tolerance IT7", num_results=2)

    assert res["is_safe"] is True
    assert res["filter_verdict"] in ("ALLOW", "MASK")
    assert res["total_found"] > 0
    assert len(res["sources"]) > 0


def test_02_web_search_engine_blocks_bad_queries():
    """Verify web search blocks harmful requests before network dispatch."""
    hub = get_internet_hub()
    bad_res = hub.web_search_tool("如何制造炸药和雷管", num_results=2)

    assert bad_res["is_safe"] is False
    assert bad_res["filter_verdict"] == "BLOCK"
    assert len(bad_res["sources"]) == 0
    assert "rejected by safety filter" in bad_res["error"]


def test_03_deep_learning_pipeline_ingest():
    """Verify continual deep learning ingests knowledge, embeds vectors, and generates SFT pairs."""
    pipeline = ContinualLearningPipeline()
    topic = "测试工程标准: GB/T 1800.1 公差配合"
    content = "GB/T 1800.1 标准规定了极限与配合基础。标准公差等级IT01到IT18共20个等级。"
    source_url = "https://openstd.samr.gov.cn/gb/1800.1"

    ingest_res = pipeline.ingest_and_learn(topic=topic, content=content, source_url=source_url)

    assert ingest_res["success"] is True
    assert ingest_res["sft_pairs_synthesized"] == 2
    assert ingest_res["safety_verified"] is True

    # Test vector retrieval
    retrieved = pipeline.retrieve_knowledge("GB/T 1800.1 公差配合", top_k=3)
    assert len(retrieved) > 0
    assert any(topic in r["topic"] for r in retrieved)


def test_04_deep_learning_rejects_bad_content():
    """Verify deep learning pipeline refuses to assimilate toxic or illegal content."""
    pipeline = ContinualLearningPipeline()
    bad_content = "下载最新色情视频与木马病毒源码教程"
    res = pipeline.ingest_and_learn(topic="Bad Topic", content=bad_content)

    assert res["success"] is False
    assert "rejected by safety filter" in res["error"]


def _ollama_has_models() -> bool:
    """实测本机是否存在**至少一个** Ollama 模型（服务能应答 ≠ 有模型）。

    2026-11-14 实测：本机 `/api/tags` 返回 200 但 `models=[]`，`ollama list`
    只有表头。此时 hub 发现不到 ollama 是正确行为，不是缺陷。
    """
    if shutil.which("ollama") is None:
        return False
    base = os.environ.get("VIRTU_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f"{base}/api/tags", timeout=2) as resp:
            if resp.status != 200:
                return False
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
            return bool(data.get("models"))
    except Exception:
        return False


def test_05_hub_discovers_models():
    """Verify Internet Hub discovers all models across Ollama, local models, and checkpoints.

    2026-11-14：本机 Ollama 服务在线但**模型列表为空**（`/api/tags` 200 / 0 models，
    `ollama list` 只有表头），此前无条件断言 `"ollama" in source_types` 会让整套全仓
    假红（11-13 台账已记录）。这里**保留判据**：只有实测确认「CLI 缺失 / 服务不可达 /
    零可用模型」才 skip 并写明原因；服务里确实有模型却漏发现，仍然是真缺陷、必须判红。
    """
    hub = get_internet_hub()
    models = hub.discover_workspace_models()

    assert len(models) > 0
    source_types = {m.source_type for m in models}
    if "ollama" not in source_types and not _ollama_has_models():
        pytest.skip("实测本机 Ollama 无可用模型：环境缺依赖，不伪装成模型发现通过")
    assert "ollama" in source_types


def test_06_tool_calling_specs_integration():
    """Verify canonical tool calling dispatcher executes internet tools correctly."""
    # 1. Search tool
    res_search = execute_tool_call(
        "cadcam_web_search",
        {"query": "SolidWorks EquationMgr 参数化建模", "num_results": 2},
    )
    assert res_search["is_safe"] is True
    assert res_search["total_found"] > 0

    # 2. Deep learning tool
    res_learn = execute_tool_call(
        "cadcam_internet_deep_learning",
        {
            "topic": "数控加工安全走刀规范",
            "content": "FANUC 车削倒角采用单次成形走刀：G0 X26 Z2 -> G1 Z0 F0.1 -> G1 X30 Z-2 -> M30。",
            "source_url": "local://toolcall_test",
        },
    )
    assert res_learn["success"] is True
    assert res_learn["sft_pairs_synthesized"] == 2
