"""Unit tests for Parameter Alignment Engine."""

import os
import tempfile
import torch
from virtu_omni.config import ModelConfig
from virtu_omni.models.expander import BaseParameterExpander
from virtu_omni.alignment.aligner import AlignmentValidator


def test_layer_alignment_metrics():
    config = ModelConfig(num_layers=2, hidden_dim=64, intermediate_dim=192)
    validator = AlignmentValidator(config=config)

    src_w = torch.randn(32, 32) * 0.02
    expander = BaseParameterExpander(config=config)
    exp_w = expander.expand_matrix_width(src_w, 64, 64)

    metrics = validator.compute_layer_alignment(src_w, exp_w, layer_idx=0, tensor_name="test_proj")
    assert metrics["cosine_similarity"] >= 0.99
    assert metrics["wasserstein_distance"] <= 0.05
    assert metrics["semantic_score"] >= 0.95
    assert metrics["status"] in ["PASS", "FAIL"]


def test_full_model_validation():
    config = ModelConfig(num_layers=2, hidden_dim=768, intermediate_dim=3072, vocab_size=200)
    expander = BaseParameterExpander(config=config)
    src_weights = expander.load_source_weights()
    exp_weights = expander.build_expanded_10b_state_dict()

    validator = AlignmentValidator(config=config, cosine_threshold=0.995, semantic_threshold=0.95)
    report = validator.validate_full_model(src_weights, exp_weights)

    assert "summary" in report
    assert report["summary"]["total_tensors_evaluated"] > 0
    assert report["summary"]["alignment_pass_rate"] >= 99.5

    # Test report export
    with tempfile.TemporaryDirectory() as tmp_dir:
        md_file = os.path.join(tmp_dir, "alignment_report.md")
        saved_md = validator.export_markdown_report(report, md_file)
        assert saved_md == md_file
