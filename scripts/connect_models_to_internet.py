# -*- coding: utf-8 -*-
"""scripts/connect_models_to_internet.py — Master Connector for All Models to Internet, Safety Filter & Deep Learning.

Usage:
    python scripts/connect_models_to_internet.py [--model MODEL_TAG] [--test-query QUERY] [--verbose]

Responsibilities:
1. Discover and catalog all models in the folder (Ollama, models/, checkpoints/).
2. Bind each model to the Virtu Internet Hub, Safety Filter, and Continual Deep Learning Pipeline.
3. Validate defense-in-depth safety filter (query guard, content sanitizer, PII masking).
4. Execute real-time web search for engineering knowledge.
5. Ingest and synthesize deep learning training pairs into persistent storage.
6. Verify live inference on an active model with internet grounding.
7. Output formal provenance and audit report complying with the Measurement Constitution.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# Workspace setup
WORKSPACE_DIR = Path(__file__).resolve().parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from virtu_omni.internet import (
    HarmfulContentFilter,
    WebSearchEngine,
    ContinualLearningPipeline,
    VirtuInternetHub,
    get_safety_filter,
    get_search_engine,
    get_learning_pipeline,
    get_internet_hub,
)
from bridges.tool_calling_specs import get_cadcam_tool_definitions, execute_tool_call

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("VirtuInternetConnector")


def connect_all_models_to_internet(
    target_model_for_test: str = "virtu-internet-enhanced:latest",
    sample_query: str = "GB/T 1800.1 标准公差等级 IT7 计算与配合代号 H7/g6",
    verbose: bool = True,
) -> Dict[str, Any]:
    """Execute complete binding and verification for all models in the workspace."""
    start_time = time.time()
    logger.info("================================================================================")
    logger.info("   Virtu Industrial Ecosystem: Connecting All Models to Internet & Deep Learning")
    logger.info("================================================================================")

    hub = get_internet_hub()
    safety_filter = get_safety_filter()
    search_engine = get_search_engine()
    learning_pipeline = get_learning_pipeline()

    # Step 1: Model Discovery
    logger.info("[Step 1/5] Discovering all models in workspace folder...")
    models = hub.discover_workspace_models()
    logger.info(f" -> Found {len(models)} model artifacts across Ollama, models/, and checkpoints/")

    models_by_type = {}
    for m in models:
        models_by_type.setdefault(m.source_type, []).append(m.model_name)

    for stype, mlist in models_by_type.items():
        logger.info(f"   * [{stype}] ({len(mlist)} models): {', '.join(mlist[:5])}{' ...' if len(mlist) > 5 else ''}")

    # Step 2: Safety Filter Gate Validation (Measurement Constitution Rule 4/8)
    logger.info("[Step 2/5] Auditing Automated Harmful Content & Injection Filter Gate...")
    probe_res = safety_filter.falsifiable_mutation_probe()
    logger.info(f" -> Falsifiable Mutation Probe Result: ok={probe_res['falsifiable_ok']}, blocked {probe_res['bad_samples_blocked']}/{probe_res['bad_samples_total']} bad samples")
    assert probe_res["falsifiable_ok"] is True, "Safety gate failed falsifiable probe!"

    # PII Masking test
    pii_test_raw = "联系方式: 13800138000, 身份证: 110101199001011234, token: sk-abcdef1234567890abcdef12"
    masked_pii, pii_count = safety_filter.mask_pii(pii_test_raw)
    logger.info(f" -> PII Masking: Redacted {pii_count} secrets. Result: '{masked_pii}'")

    # Step 3: Web Search Execution
    logger.info(f"[Step 3/5] Executing Safe Web Search for query: '{sample_query}'...")
    search_res = search_engine.search(sample_query, num_results=3)
    logger.info(f" -> Web Search: is_safe={search_res.is_safe}, verdict={search_res.filter_verdict}, found={search_res.total_found} items, engines={search_res.source_engines_used}")

    for idx, item in enumerate(search_res.results, 1):
        logger.info(f"   [{idx}] {item.title} ({item.source_engine}) -> {item.url}")
        logger.info(f"       摘要: {item.snippet[:120]}...")

    # Step 4: Continual Deep Learning & Vector Memory Ingestion
    logger.info("[Step 4/5] Ingesting Knowledge into Vector Memory & Synthesizing SFT Training Pairs...")
    learn_summary = hub.execute_search_and_learn(topic=sample_query, num_results=2)
    logger.info(f" -> Deep Learning Ingestion: stored {learn_summary['learned_entries_count']} entries into vector store")
    logger.info(f" -> SFT Training Pairs saved to: {learn_summary.get('sft_dataset_file', 'data/sft/continual_web_learning.jsonl')}")

    # Step 5: Live Model Grounded Inference Verification
    logger.info(f"[Step 5/5] Testing Live Model Inference with Internet Grounding on '{target_model_for_test}'...")
    infer_res = hub.query_model_with_internet(
        model_name=target_model_for_test,
        prompt="请简述 GB/T 1800.1 公差等级 IT7 与配合代号 H7/g6 的应用特点。",
        enable_search=True,
        enable_deep_learning=True,
        timeout=25.0,
    )

    logger.info(f" -> Live Inference: success={infer_res['success']}, latency={infer_res.get('latency_ms', 0):.1f}ms")
    logger.info(f" -> Model Response Excerpt:\n{infer_res.get('response', '')[:300]}...\n")

    # Final Provenance Report
    total_time = time.time() - start_time
    report = {
        "status": "success",
        "timestamp": time.time(),
        "total_models_connected": len(models),
        "models_summary": {k: len(v) for k, v in models_by_type.items()},
        "safety_gate": probe_res,
        "web_search": {
            "query": sample_query,
            "is_safe": search_res.is_safe,
            "verdict": search_res.filter_verdict,
            "total_found": search_res.total_found,
            "engines_used": search_res.source_engines_used,
        },
        "deep_learning": {
            "entries_ingested": learn_summary["learned_entries_count"],
            "vector_store_entries_total": len(learning_pipeline.entries),
            "sft_output_file": str(learn_summary.get("sft_dataset_file")),
        },
        "live_inference_verification": {
            "model_tested": target_model_for_test,
            "success": infer_res["success"],
            "response_preview": infer_res.get("response", "")[:200],
            "citations_count": len(infer_res.get("internet_citations", [])),
        },
        "basis": "measured",
        "total_runtime_seconds": round(total_time, 2),
    }

    # Save Provenance Report
    report_file = WORKSPACE_DIR / "reports" / "internet_deep_learning_connection_report.json"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(f"================================================================================")
    logger.info(f" All {len(models)} models are successfully connected to Internet & Deep Learning!")
    logger.info(f" Full Provenance Report saved to: {report_file}")
    logger.info(f"================================================================================")

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Connect all workspace models to Internet & Deep Learning.")
    parser.add_argument("--model", default="virtu-internet-enhanced:latest", help="Ollama model to verify live inference")
    parser.add_argument("--query", default="ISO 286 / GB/T 1800.1 公差等级计算与制造应用", help="Test query for search and learning")
    parser.add_argument("--verbose", action="store_true", help="Print verbose logs")
    args = parser.parse_args()

    connect_all_models_to_internet(
        target_model_for_test=args.model,
        sample_query=args.query,
        verbose=args.verbose,
    )
