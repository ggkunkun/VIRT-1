"""Automated Test Suite for Standardized Smelted Parameter Bundle.

Validates:
1. Bundle file manifest and SHA-256 integrity.
2. Triple verification suite status (Integrity, Validity, Consistency).
3. Official model loader and strict parameter loading (0 missing / 0 unexpected).
4. Total parameter count matches official specifications (1,276,874,193).
5. End-to-end multi-scenario manufacturing inference (subsystem, operation, material, JEV).
"""

import os
import json
import pytest
import torch
from pathlib import Path

from virtu_omni import (
    StandardizedSmeltBundle,
    StandardizedSmeltTokenizer,
    load_standardized_bundle,
)

BUNDLE_DIR = Path(r"D:\Virtu模型\checkpoints\standardized_smelt_bundle")


@pytest.fixture(scope="module")
def bundle():
    """Module-level fixture for the standardized bundle."""
    assert BUNDLE_DIR.exists(), f"Bundle directory does not exist: {BUNDLE_DIR}"
    return StandardizedSmeltBundle(BUNDLE_DIR)


def test_bundle_manifest_and_file_integrity(bundle):
    """Verify package manifest and all file existences."""
    manifest = bundle.load_manifest()
    assert manifest["package_title"] == "Virtu-Omni Standardized Smelted Parameter Bundle"
    assert manifest["parameter_count"] == 1276874193
    assert manifest["tensor_count"] == 1333
    assert len(manifest["files"]) == 24

    ok, errors = bundle.verify_bundle_integrity()
    assert ok, f"Bundle integrity verification failed: {errors}"


def test_triple_verification_approved(bundle):
    """Verify triple verification results."""
    report = bundle.load_verification_report()
    assert report["overall_verdict"] == "APPROVED"
    assert report["pass_rate"] == 100.0

    # Integrity
    assert report["integrity_check"]["status"] == "PASS"
    assert report["integrity_check"]["standardized_parameter_count"] == 1276874193
    assert len(report["integrity_check"]["missing_tensors"]) == 0
    assert len(report["integrity_check"]["unexpected_tensors"]) == 0

    # Validity
    assert report["validity_check"]["status"] == "PASS"
    assert report["validity_check"]["nan_tensor_count"] == 0
    assert report["validity_check"]["inf_tensor_count"] == 0
    assert report["validity_check"]["config_valid"] is True

    # Consistency
    assert report["consistency_check"]["status"] == "PASS"
    assert len(report["consistency_check"]["dimension_mismatches"]) == 0
    assert len(report["consistency_check"]["dtype_mismatches"]) == 0


def test_model_strict_loading(bundle):
    """Verify model instantiation and strict state_dict loading."""
    model = bundle.load_model(device="cpu", strict=True)
    assert model is not None
    assert isinstance(model, torch.nn.Module)

    # Count parameters
    total_params = sum(p.numel() for p in model.parameters())
    assert total_params == 1276874193
    assert len(list(model.parameters())) > 100


def test_tokenizer_encoding_decoding(bundle):
    """Verify tokenizer encodes and decodes properly."""
    tokenizer = bundle.get_tokenizer()
    assert tokenizer.vocab_size == 4096

    text = "G43.4 开启五轴联动刀尖点跟随控制"
    ids, mask = tokenizer.encode(text, max_length=60)
    assert ids.shape == (1, 60)
    assert mask.shape == (1, 60)
    assert mask.sum().item() > 0

    decoded = tokenizer.decode(ids)
    assert len(decoded) > 0


def test_end_to_end_subsystem_prediction(bundle):
    """Verify manufacturing subsystem classification inference."""
    res = bundle.predict_subsystem("G43.4 开启五轴联动刀尖点跟随控制并设置偏置")
    assert "predicted_index" in res
    assert 0 <= res["predicted_index"] < 12
    assert "predicted_key" in res
    assert "predicted_name" in res
    assert res["confidence"] > 0.0
    assert len(res["top_candidates"]) == 3
    assert res["latency_ms"] > 0.0


def test_end_to_end_machining_task_prediction(bundle):
    """Verify joint prediction of subsystem, operation, and material."""
    res = bundle.predict_machining_task("端铣刀快速走刀加工 6061铝合金 平面凹槽")
    assert "subsystem" in res
    assert "operation" in res
    assert "material" in res
    assert res["subsystem"]["index"] in range(12)
    assert len(res["operation"]["name"]) > 0
    assert len(res["material"]["name"]) > 0


def test_end_to_end_action_pair_verification(bundle):
    """Verify JEV pair compatibility verification."""
    context = "主轴高速旋转且冷却液未开启报警"
    action = "M08 开启高压切削液喷淋并降速巡检"
    res = bundle.verify_action_pair(context, action)
    assert "verification_score" in res
    assert 0.0 <= res["verification_score"] <= 1.0
    assert res["verdict"] in ("COMPLIANT", "NON_COMPLIANT")


def test_end_to_end_joint_embedding(bundle):
    """Verify 512-d normalized JEV embedding extraction."""
    text = "高精度数控机床刀位点补偿"
    emb = bundle.extract_joint_embedding(text)
    assert len(emb) == 512
    # Verify vector is L2 normalized
    norm = sum(x * x for x in emb) ** 0.5
    assert abs(norm - 1.0) < 1e-4
