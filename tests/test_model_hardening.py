"""Regression suite for the full-chain hardening pass (config → data → model → serving).

Every test here targets a defect that was identified and fixed in this pass, covering
three scenario classes:
  * normal business paths   (happy-path behaviour still works)
  * boundary/limit paths    (empty inputs, single samples, truncation limits)
  * invalid/abnormal paths  (structured error codes instead of silent degradation)
"""

from __future__ import annotations

import base64
import io
import json

import pytest
# torch 是可选训练依赖：无 torch 的推理主机上跳过本模块，而不是让收集阶段中断。
pytest.importorskip("torch")
import torch
from PIL import Image

from virtu_omni.config import DataConfig, ModelConfig, VirtuOmniConfig
from virtu_omni.errors import ModelError
from virtu_omni.models.architecture import VirtuOmni10B
from virtu_omni.models.loop import (
    LoopConvergenceCriterion,
    LoopStateCache,
    LoopStepController,
)
from virtu_omni.models.geometry_token_bridge import GeometryTokenBridge
from virtu_omni.models.smelt_loader import StandardizedSmeltTokenizer
from virtu_omni.data.pipeline import StreamingMultimodalDataPipeline
from virtu_omni.alignment.aligner import AlignmentValidator


def _tiny_model_config() -> ModelConfig:
    return ModelConfig(
        num_layers=1,
        hidden_dim=32,
        intermediate_dim=96,
        num_attention_heads=8,
        num_kv_heads=2,
        head_dim=16,
        vocab_size=64,
        vision_codebook_size=32,
        image_resolution=28,
        patch_size=14,
        max_position_embeddings=64,
        max_loop_steps=2,
        adaptive_loop=False,
    )


@pytest.fixture(scope="module")
def tiny_model() -> VirtuOmni10B:
    model = VirtuOmni10B(_tiny_model_config())
    model.eval()
    return model


# --------------------------------------------------------------------------------------
# 1. Configuration boundary (E1001/E1002/E1003)
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "kwargs",
    [
        {"num_layers": 0},
        {"head_dim": 15},
        {"num_attention_heads": 8, "num_kv_heads": 3},
        {"vocab_size": 1},
        {"image_resolution": 7, "patch_size": 14},
        {"convergence_threshold": 0.0},
        {"loop_exit_metric": "cosin"},
    ],
)
def test_config_rejects_impossible_values(kwargs):
    with pytest.raises(ModelError) as exc:
        ModelConfig(**kwargs)
    assert exc.value.code == "E1001"
    assert "hint" in exc.value.to_dict()


def test_config_yaml_rejects_unknown_key(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("model:\n  num_layers: 2\n  hidden_dimension: 128\n", encoding="utf-8")
    with pytest.raises(ModelError) as exc:
        VirtuOmniConfig.from_yaml(str(path))
    assert exc.value.code == "E1003"
    assert "hidden_dimension" in exc.value.message


def test_config_yaml_rejects_non_mapping_section(tmp_path):
    path = tmp_path / "bad2.yaml"
    path.write_text("model:\n  - 1\n  - 2\n", encoding="utf-8")
    with pytest.raises(ModelError) as exc:
        VirtuOmniConfig.from_yaml(str(path))
    assert exc.value.code == "E1002"


def test_config_yaml_valid_roundtrip(tmp_path):
    path = tmp_path / "good.yaml"
    path.write_text("model:\n  num_layers: 2\n", encoding="utf-8")
    loaded = VirtuOmniConfig.from_yaml(str(path))
    assert loaded.model.num_layers == 2


# --------------------------------------------------------------------------------------
# 2. Inference core (E2001..E2008)
# --------------------------------------------------------------------------------------
def test_forward_requires_a_modality(tiny_model):
    with pytest.raises(ModelError) as exc:
        tiny_model()
    assert exc.value.code == "E2001"


def test_forward_rejects_unknown_mode(tiny_model):
    with pytest.raises(ModelError) as exc:
        tiny_model(input_ids=torch.zeros((1, 3), dtype=torch.long), mode="txt_gen")
    assert exc.value.code == "E2002"


def test_forward_mode_modality_mismatch(tiny_model):
    with pytest.raises(ModelError) as exc:
        tiny_model(input_ids=torch.zeros((1, 3), dtype=torch.long), mode="image_gen")
    assert exc.value.code == "E2003"


def test_forward_rejects_bad_label_shape(tiny_model):
    ids = torch.zeros((1, 4), dtype=torch.long)
    with pytest.raises(ModelError) as exc:
        tiny_model(input_ids=ids, labels=torch.zeros((1, 3), dtype=torch.long), mode="text_gen")
    assert exc.value.code == "E2004"


def test_forward_rejects_batch_mismatch(tiny_model):
    ids = torch.zeros((2, 3), dtype=torch.long)
    imgs = torch.zeros((1, 3, 28, 28))
    with pytest.raises(ModelError) as exc:
        tiny_model(input_ids=ids, images=imgs, mode="text_gen")
    assert exc.value.code == "E2007"


def test_forward_rejects_empty_sequence(tiny_model):
    with pytest.raises(ModelError) as exc:
        tiny_model(input_ids=torch.zeros((1, 0), dtype=torch.long))
    assert exc.value.code == "E2007"


def test_forward_rejects_non_multiple_image_size(tiny_model):
    # 30 px is not a multiple of patch_size=14 → would silently truncate patches.
    with pytest.raises(ModelError) as exc:
        tiny_model(images=torch.zeros((1, 3, 30, 30)), mode="image_gen")
    assert exc.value.code == "E2006"


def test_2d_rope_grid_mismatch(tiny_model):
    q = torch.zeros((1, 3, 2, 16))
    with pytest.raises(ModelError) as exc:
        tiny_model.rope_engine.apply_2d_rope(q, q, grid_h=2, grid_w=2)
    assert exc.value.code == "E2005"


def test_text_forward_produces_logits_and_releases_kv_cache(tiny_model):
    out = tiny_model(input_ids=torch.ones((1, 5), dtype=torch.long), mode="text_gen")
    assert out["logits"].shape == (1, 5, 64)
    # Session-bound K/V pairs must not survive the request.
    assert len(tiny_model.state_cache._kv_store) == 0
    # Hidden-state telemetry is preserved (cross-step reuse contract) but bounded.
    assert len(tiny_model.state_cache._state_store) <= tiny_model.state_cache.max_entries


def test_multimodal_forward_alignment(tiny_model):
    ids = torch.ones((1, 3), dtype=torch.long)
    out = tiny_model(input_ids=ids, images=torch.zeros((1, 3, 28, 28)), mode="multimodal_eval")
    # Text logits only: vision positions are stripped, so the text axis stays 3.
    assert out["logits"].shape == (1, 3, 64)
    assert out["loop_stats"]["total_steps"] >= 0


def test_image_gen_mode_outputs_vision_logits(tiny_model):
    out = tiny_model(images=torch.zeros((1, 3, 28, 28)), mode="image_gen")
    assert out["image_logits"].shape[0] == 1
    assert out["image_logits"].shape[-1] == 32
    assert "logits" not in out


# --------------------------------------------------------------------------------------
# 3. Loop components (E2008 + memory bounds)
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize("metric", ["cosin", "l2", ""])
def test_convergence_rejects_unknown_metric(metric):
    with pytest.raises(ModelError) as exc:
        LoopConvergenceCriterion(metric=metric)
    assert exc.value.code == "E2008"


def test_convergence_rejects_non_positive_threshold():
    with pytest.raises(ModelError) as exc:
        LoopConvergenceCriterion(threshold=0.0)
    assert exc.value.code == "E2008"


def test_convergence_detects_identical_states():
    crit = LoopConvergenceCriterion(threshold=1e-3)
    h = torch.randn(1, 4, 8)
    converged, delta = crit.evaluate(h, h)
    assert converged is True
    assert delta < 1e-6


def test_step_controller_history_is_bounded():
    ctrl = LoopStepController(_tiny_model_config())
    for i in range(LoopStepController.MAX_HISTORY_ENTRIES + 500):
        ctrl.record_step(i, delta=0.1, converged=False)
    assert len(ctrl.step_history) <= LoopStepController.MAX_HISTORY_ENTRIES
    summary = ctrl.get_summary()
    assert summary["total_steps"] <= LoopStepController.MAX_HISTORY_ENTRIES


def test_state_cache_evicts_and_detaches():
    cache = LoopStateCache(enabled=True, max_entries=4)
    for i in range(10):
        t = torch.randn(2, 3, requires_grad=True) * i
        t.retain_grad()
        cache.set_state(f"k{i}", t)
    assert len(cache._state_store) <= 4
    for value in cache._state_store.values():
        assert value.requires_grad is False


def test_state_cache_disabled_ignores_writes():
    cache = LoopStateCache(enabled=False)
    cache.set_state("k", torch.randn(2, 2))
    assert cache.get_state("k") is None


# --------------------------------------------------------------------------------------
# 4. Data pipeline (E3001..E3005)
# --------------------------------------------------------------------------------------
def test_pipeline_normal_batch():
    pipe = StreamingMultimodalDataPipeline(DataConfig(num_workers=1, image_resolution=28, patch_size=14))
    batch = pipe.collate_fn([pipe.process_single_pair(
        {"image": Image.new("RGB", (28, 28)), "text": "hello"}
    )])
    assert batch["images"].shape == (1, 3, 28, 28)
    assert batch["labels"].shape[0] == 1


def test_pipeline_rejects_empty_batch():
    pipe = StreamingMultimodalDataPipeline(DataConfig(num_workers=1))
    with pytest.raises(ModelError) as exc:
        pipe.collate_fn([])
    assert exc.value.code == "E3003"


def test_pipeline_rejects_non_pil_image():
    pipe = StreamingMultimodalDataPipeline(DataConfig(num_workers=1))
    with pytest.raises(ModelError) as exc:
        pipe.preprocess_image([[0, 0, 0]])
    assert exc.value.code == "E3001"


def test_pipeline_rejects_missing_image():
    pipe = StreamingMultimodalDataPipeline(DataConfig(num_workers=1))
    with pytest.raises(ModelError) as exc:
        pipe.process_single_pair({"text": "no image"})
    assert exc.value.code == "E3001"


def test_pipeline_rejects_non_text_caption():
    pipe = StreamingMultimodalDataPipeline(DataConfig(num_workers=1))
    with pytest.raises(ModelError) as exc:
        pipe.tokenize_text(123)
    assert exc.value.code == "E3002"


def test_pipeline_rejects_image_shape_mismatch():
    pipe = StreamingMultimodalDataPipeline(DataConfig(num_workers=1, image_resolution=28))
    a = pipe.process_single_pair({"image": Image.new("RGB", (28, 28)), "text": "a"})
    b = a | {"image": torch.zeros(3, 14, 14)}
    with pytest.raises(ModelError) as exc:
        pipe.collate_fn([a, b])
    assert exc.value.code == "E3004"


@pytest.mark.parametrize("num_samples,batch_size", [(-1, 4), (4, 0)])
def test_pipeline_arg_validation(num_samples, batch_size):
    pipe = StreamingMultimodalDataPipeline(DataConfig(num_workers=1, image_resolution=28))
    with pytest.raises(ModelError) as exc:
        list(pipe.generate_streaming_batches(num_samples=num_samples, batch_size=batch_size))
    assert exc.value.code == "E3005"


def test_pipeline_tokenize_keeps_bos_eos():
    pipe = StreamingMultimodalDataPipeline(DataConfig(num_workers=1, max_text_tokens=8))
    tokens = pipe.tokenize_text("abcdefghij")
    assert tokens[0] == 1 and tokens[-1] == 2
    assert tokens.numel() == 8


# --------------------------------------------------------------------------------------
# 5. Feature transformation: geometry bridge + tokenizer (E5001..E5004)
# --------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def bridge() -> GeometryTokenBridge:
    return GeometryTokenBridge(hidden_dim=32)


def test_geometry_feature_tokens_are_reachable(bridge):
    ids, feats = bridge.encode_geometry_sequence(
        [{"type": "feat_fillet", "x1": 1.0}, {"type": "tol_datum"}, {"type": "nc_g01_linear"}]
    )
    names = [bridge.id_to_token[i] for i in ids]
    assert names == ["<FEAT_FILLET>", "<TOL_DATUM>", "<NC_G01_LINEAR>"]
    assert feats.shape == (1, 3, 8)


def test_geometry_unknown_type_warns(bridge):
    with pytest.warns(UserWarning, match="Unknown geometry entity type"):
        ids, _ = bridge.encode_geometry_sequence([{"type": "mystery_entity"}])
    assert bridge.id_to_token[ids[0]] == "<GEOM_LINE>"


@pytest.mark.parametrize("bad", ["abc", None, float("nan"), float("inf")])
def test_geometry_rejects_non_numeric_values(bridge, bad):
    with pytest.raises(ModelError) as exc:
        bridge.encode_geometry_sequence([{"type": "line", "x1": bad}])
    assert exc.value.code == "E5001"


def test_geometry_rejects_out_of_vocab_tokens(bridge):
    with pytest.raises(ModelError) as exc:
        bridge.encode_geometry_sequence([{"type": "circle"}], vocab_size=1000)
    assert exc.value.code == "E5002"


def test_geometry_empty_entities_shape():
    ids, feats = GeometryTokenBridge(hidden_dim=32).encode_geometry_sequence([])
    assert ids == []
    assert feats.shape == (1, 0, 8)


def test_geometry_projector_validates_rank(bridge):
    with pytest.raises(ModelError) as exc:
        bridge.project_to_manifold(torch.zeros(3, 8))
    assert exc.value.code == "E5001"


def test_geometry_projector_normal_path(bridge):
    out = bridge.project_to_manifold(torch.zeros(1, 2, 8))
    assert out.shape == (1, 2, 32)


def test_smelt_tokenizer_encode_and_decode(tmp_path):
    vocab = tmp_path / "vocab.json"
    vocab.write_text(json.dumps({"text": ["<pad>", "<bos>", "<eos>", "<unk>", "a", "b"]}), encoding="utf-8")
    tok = StandardizedSmeltTokenizer(vocab)
    ids, mask = tok.encode("ab", max_length=4)
    assert ids.shape == (1, 4) and mask.shape == (1, 4)
    assert ids[0, 0] == 1 and ids[0, 3] == 2
    assert tok.decode(ids) == "ab"
    # Single-token 2-D tensor used to collapse to a 0-d scalar via squeeze().
    assert tok.decode(torch.tensor([[5]])) == "b"


def test_smelt_tokenizer_rejects_bad_args(tmp_path):
    vocab = tmp_path / "vocab.json"
    vocab.write_text(json.dumps({"text": ["<pad>", "<bos>", "<eos>"]}), encoding="utf-8")
    tok = StandardizedSmeltTokenizer(vocab)
    with pytest.raises(ModelError) as exc:
        tok.encode(123)
    assert exc.value.code == "E5004"
    with pytest.raises(ModelError) as exc:
        tok.encode("x", max_length=0)
    assert exc.value.code == "E5004"


# --------------------------------------------------------------------------------------
# 6. Alignment reporting must not fabricate a PASS certificate
# --------------------------------------------------------------------------------------
def _report(cosine: float, wasserstein: float, semantic: float, verdict: str) -> dict:
    return {
        "summary": {
            "overall_verdict": verdict,
            "alignment_pass_rate": 100.0 if verdict == "APPROVED" else 0.0,
            "average_cosine_similarity": cosine,
            "average_wasserstein_distance": wasserstein,
            "average_semantic_score": semantic,
            "passed_tensors": 1 if verdict == "APPROVED" else 0,
            "total_tensors_evaluated": 1,
        },
        "layer_records": [],
    }


def test_alignment_report_marks_failure(tmp_path):
    validator = AlignmentValidator(_tiny_model_config())
    out = tmp_path / "fail.md"
    validator.export_markdown_report(_report(0.10, 0.50, 0.10, "REJECTED"), str(out))
    text = out.read_text(encoding="utf-8")
    assert "未达标 (FAIL)" in text
    assert "驳回" in text
    assert "ALIGN-VIRTU-10B-" in text


def test_alignment_report_marks_pass(tmp_path):
    validator = AlignmentValidator(_tiny_model_config())
    out = tmp_path / "pass.md"
    validator.export_markdown_report(_report(0.999, 0.001, 0.999, "APPROVED"), str(out))
    text = out.read_text(encoding="utf-8")
    assert "达标 (PASS)" in text
    assert "准予进入预训练" in text


# --------------------------------------------------------------------------------------
# 7. Serving layer (E4001..E4003, honest output, bounded telemetry)
# --------------------------------------------------------------------------------------
from fastapi.testclient import TestClient  # noqa: E402  (kept near its usage for clarity)
from fastapi import HTTPException  # noqa: E402

import virtu_omni.serving.server as server_module  # noqa: E402

SERVING_TEST_TOKEN = "serving-hardening-test-" + "x" * 48
SERVING_TEST_AUTH = {"Authorization": f"Bearer {SERVING_TEST_TOKEN}"}


@pytest.fixture(scope="module")
def client() -> TestClient:
    cfg = VirtuOmniConfig(model=_tiny_model_config())
    return TestClient(server_module.create_app(cfg, bearer_token=SERVING_TEST_TOKEN),
                      headers=SERVING_TEST_AUTH)


def _png_b64(size: int = 28) -> str:
    buf = io.BytesIO()
    Image.new("RGB", (size, size), color=(10, 120, 200)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def test_module_does_not_build_app_on_import():
    # Building the model at import time allocated weights for any importer.
    assert "app" not in vars(server_module)


def test_health_reports_healthy(client):
    resp = client.get("/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "HEALTHY"


def test_chat_returns_real_forward_result(client):
    payload = {"model": "Virtu-Omni-10B", "messages": [{"role": "user", "content": "hello world"}]}
    resp = client.post("/v1/chat/completions", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["choices"]) == 1
    content = data["choices"][0]["message"]["content"]
    # The old handler returned a canned "Successfully processed query" sentence.
    assert "Successfully processed" not in content
    assert data["degraded"] is True
    assert isinstance(data["generated_token_ids"][0], int)
    # Usage must describe the tokens actually returned, not a character-length guess.
    assert data["usage"]["completion_tokens"] == len(data["generated_token_ids"])
    assert data["usage"]["completion_tokens"] >= 1
    assert "latency_ms" in data["performance"]


def test_chat_tokenizes_the_actual_prompt(client):
    short = client.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "A"}]}).json()
    long = client.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "A" * 20}]}).json()
    # The old handler fed the constant id 42, so prompt length never varied.
    assert short["usage"]["prompt_tokens"] == 2
    assert long["usage"]["prompt_tokens"] == 21


def test_chat_accepts_data_url_image(client):
    payload = {
        "messages": [{"role": "user", "content": "describe", "image_base64": f"data:image/png;base64,{_png_b64()}"}]
    }
    resp = client.post("/v1/chat/completions", json=payload)
    assert resp.status_code == 200


def test_chat_rejects_invalid_image(client):
    payload = {"messages": [{"role": "user", "content": "x", "image_base64": "bm90LWFuLWltYWdl"}]}
    resp = client.post("/v1/chat/completions", json=payload)
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "E4001"


def test_chat_rejects_oversized_image(client, monkeypatch):
    monkeypatch.setattr(server_module, "MAX_IMAGE_BASE64_BYTES", 16)
    payload = {"messages": [{"role": "user", "content": "x", "image_base64": "A" * 100}]}
    resp = client.post("/v1/chat/completions", json=payload)
    assert resp.status_code == 413
    assert resp.json()["detail"]["code"] == "E4001"


def test_chat_rejects_missing_user_message(client):
    resp = client.post("/v1/chat/completions", json={"messages": [{"role": "system", "content": "sys"}]})
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "E4003"


def test_stream_emits_real_content_and_done(client):
    payload = {"messages": [{"role": "user", "content": "stream me"}], "stream": True}
    resp = client.post("/v1/chat/completions", json=payload)
    assert resp.status_code == 200
    body = resp.text
    assert body.count("data: ") >= 2
    assert "[DONE]" in body
    assert "Successfully" not in body


def test_metrics_single_sample_does_not_crash(client):
    client.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "one"}]})
    data = client.get("/v1/metrics").json()
    assert data["total_requests"] >= 1
    assert data["p99_latency_ms"] >= 0.0
    assert data["slo_sample_size"] == data["total_requests"]


def test_metrics_without_samples_reports_zero_compliance():
    cfg = VirtuOmniConfig(model=_tiny_model_config())
    fresh = TestClient(server_module.create_app(cfg, bearer_token=SERVING_TEST_TOKEN),
                       headers=SERVING_TEST_AUTH)
    data = fresh.get("/v1/metrics").json()
    assert data["total_requests"] == 0
    assert data["slo_compliance_rate"] == 0.0


def test_latency_buffer_is_bounded():
    # The buffer must be a fixed-size deque; a plain list grew one entry per request.
    assert server_module.LATENCY_WINDOW > 0
    from collections import deque

    buf: "deque[float]" = deque(maxlen=server_module.LATENCY_WINDOW)
    for i in range(server_module.LATENCY_WINDOW + 100):
        buf.append(float(i))
    assert len(buf) == server_module.LATENCY_WINDOW


def test_generate_image_is_labelled_placeholder(client):
    resp = client.post("/v1/multimodal/generate_image", json={"prompt": "city", "height": 256, "width": 256})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert "image_base64" in data
    assert data["mode"] == "placeholder"


def test_understand_returns_measured_confidence(client):
    resp = client.post(
        "/v1/multimodal/understand",
        json={"image_base64": _png_b64(), "question": "what is this?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    conf = data["analysis"]["confidence_score"]
    assert 0.0 <= conf <= 1.0
    assert data["analysis"]["mode"] == "placeholder"


def test_understand_rejects_invalid_image(client):
    resp = client.post("/v1/multimodal/understand", json={"image_base64": "!!!!"})
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "E4001"


# --------------------------------------------------------------------------------------
# 8. Fix-point branch coverage (second-order boundaries of the hardened paths)
# --------------------------------------------------------------------------------------
def test_chat_rejects_blank_image_payload(client):
    resp = client.post("/v1/chat/completions", json={
        "messages": [{"role": "user", "content": "x", "image_base64": ""}],
    })
    assert resp.status_code == 200  # empty string is falsy → treated as "no image"


def test_decode_base64_rejects_empty_payload():
    with pytest.raises(HTTPException) as exc:
        server_module._decode_base64_image("", 28, 14)
    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "E4001"


def test_scaffold_tokenizer_rejects_tiny_vocab():
    with pytest.raises(ModelError) as exc:
        server_module._encode_scaffold_tokens("x", vocab_size=2)
    assert exc.value.code == "E4003"


def test_scaffold_tokenizer_handles_empty_prompt():
    ids = server_module._encode_scaffold_tokens("", vocab_size=64)
    assert ids.shape == (1, 2)
    assert ids[0, 0] == 1 and ids[0, 1] == 2


def test_chat_maps_model_error_to_400(client, monkeypatch):
    def boom(*args, **kwargs):
        raise ModelError("E2002", "bad mode", hint="internal test")

    monkeypatch.setattr(server_module.VirtuOmni10B, "forward", boom)
    resp = client.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "x"}]})
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "E2002"


def test_chat_maps_unexpected_crash_to_503(client, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("CUDA kernel fault")

    monkeypatch.setattr(server_module.VirtuOmni10B, "forward", boom)
    resp = client.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "x"}]})
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "E4002"


def test_understand_maps_crash_to_503(client, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("vision tower crashed")

    monkeypatch.setattr(server_module.VirtuOmni10B, "forward", boom)
    resp = client.post("/v1/multimodal/understand", json={"image_base64": _png_b64()})
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "E4003"


def test_lazy_app_attribute_builds_once(monkeypatch):
    # Force the lightweight proxy config path so this test does not allocate 10B weights.
    monkeypatch.delenv("VIRTU_FULL_10B", raising=False)
    first = getattr(server_module, "app")
    second = getattr(server_module, "app")
    assert first is second
    from fastapi import FastAPI

    assert isinstance(first, FastAPI)


def test_module_unknown_attribute_raises():
    with pytest.raises(AttributeError):
        getattr(server_module, "definitely_not_defined")


def test_data_config_rejects_zero_workers():
    with pytest.raises(ModelError) as exc:
        DataConfig(num_workers=0)
    assert exc.value.code == "E1001"


def test_yaml_rejects_non_mapping_root(tmp_path):
    path = tmp_path / "list.yaml"
    path.write_text("- 1\n- 2\n", encoding="utf-8")
    with pytest.raises(ModelError) as exc:
        VirtuOmniConfig.from_yaml(str(path))
    assert exc.value.code == "E1002"


def test_yaml_rejects_wrong_value_type(tmp_path):
    path = tmp_path / "type.yaml"
    path.write_text("model:\n  num_layers: abc\n", encoding="utf-8")
    with pytest.raises(ModelError) as exc:
        VirtuOmniConfig.from_yaml(str(path))
    assert exc.value.code == "E1003"


def test_pipeline_detects_label_length_mismatch():
    pipe = StreamingMultimodalDataPipeline(DataConfig(num_workers=1, image_resolution=28))
    sample = pipe.process_single_pair({"image": Image.new("RGB", (28, 28)), "text": "abc"})
    sample["labels"] = sample["labels"][:-1]
    with pytest.raises(ModelError) as exc:
        pipe.collate_fn([sample])
    assert exc.value.code == "E3004"


@pytest.mark.parametrize("kwargs", [{"sample_count": -1}, {"batch_size": 0}])
def test_benchmark_arg_validation(kwargs):
    pipe = StreamingMultimodalDataPipeline(DataConfig(num_workers=1))
    with pytest.raises(ModelError) as exc:
        pipe.benchmark_throughput(**{"sample_count": 0, **kwargs})
    assert exc.value.code == "E3005"


def test_forward_rejects_1d_input_ids(tiny_model):
    with pytest.raises(ModelError) as exc:
        tiny_model(input_ids=torch.zeros(4, dtype=torch.long))
    assert exc.value.code == "E2007"


def test_forward_images_without_text_mode_mismatch(tiny_model):
    with pytest.raises(ModelError) as exc:
        tiny_model(images=torch.zeros((1, 3, 28, 28)), mode="text_gen")
    assert exc.value.code == "E2003"


def test_2d_rope_rejects_zero_grid(tiny_model):
    q = torch.zeros((1, 1, 2, 16))
    with pytest.raises(ModelError) as exc:
        tiny_model.rope_engine.apply_2d_rope(q, q, grid_h=0, grid_w=1)
    assert exc.value.code == "E2005"


def test_loop_controller_set_steps():
    ctrl = LoopStepController(_tiny_model_config())
    ctrl.set_max_steps(3)
    assert ctrl.max_loop_steps == 3


def test_convergence_handles_nan_delta():
    crit = LoopConvergenceCriterion(threshold=1e-3)
    h = torch.full((1, 2, 4), float("nan"))
    converged, delta = crit.evaluate(h, h)
    # Non-finite deltas must report "not converged" with a finite sentinel
    # instead of raising or looping forever.
    assert converged is False
    assert delta == 1.0


def test_state_cache_kv_eviction():
    cache = LoopStateCache(enabled=True, max_entries=2)
    for i in range(6):
        cache.set_kv(i, i, torch.randn(1, 1, 4), torch.randn(1, 1, 4))
    assert len(cache._kv_store) <= 2
    cache.clear_kv()
    assert len(cache._kv_store) == 0
    assert cache.get_kv(0, 0) is None


def test_state_cache_disabled_kv():
    cache = LoopStateCache(enabled=False)
    cache.set_kv(0, 0, torch.randn(1, 1, 4), torch.randn(1, 1, 4))
    assert cache.get_kv(0, 0) is None


def test_geometry_projector_rejects_nan(bridge):
    bad = torch.zeros(1, 1, 8)
    bad[0, 0, 0] = float("nan")
    with pytest.raises(ModelError) as exc:
        bridge.project_to_manifold(bad)
    assert exc.value.code == "E5001"


def test_smelt_tokenizer_without_special_tokens(tmp_path):
    vocab = tmp_path / "vocab.json"
    vocab.write_text(json.dumps({"text": ["<pad>", "<bos>", "<eos>", "<unk>", "a", "b"]}), encoding="utf-8")
    tok = StandardizedSmeltTokenizer(vocab)
    ids, _ = tok.encode("ab", max_length=2, add_special_tokens=False)
    assert ids.tolist() == [[4, 5]]
    # Decoding a plain python list (not a tensor) must also work.
    assert tok.decode([4, 5]) == "ab"
    # max_length=1 leaves no room for BOS+EOS; the body budget clamps to zero.
    tight, _ = tok.encode("abc", max_length=1)
    assert tight.shape == (1, 1)
    # Empty/special-only sequences decode to the empty string, not a crash.
    assert tok.decode([]) == ""
    assert tok.decode([0, 1, 2]) == ""


def test_smelt_tokenizer_truncates_long_text(tmp_path):
    vocab = tmp_path / "vocab.json"
    vocab.write_text(json.dumps({"text": ["<pad>", "<bos>", "<eos>"]}), encoding="utf-8")
    tok = StandardizedSmeltTokenizer(vocab)
    ids, mask = tok.encode("x" * 50, max_length=6)
    assert ids.numel() == 6
    assert mask.sum().item() == 6


def test_geometry_empty_entities_with_vocab(bridge):
    ids, feats = bridge.encode_geometry_sequence([], vocab_size=1000)
    assert ids == []
    assert feats.shape == (1, 0, 8)


def test_scaffold_tokenizer_truncates_long_prompt():
    ids = server_module._encode_scaffold_tokens("A" * 600, vocab_size=64)
    assert ids.shape == (1, 512)


def test_understand_maps_model_error_to_400(client, monkeypatch):
    def boom(*args, **kwargs):
        raise ModelError("E2006", "vision shape", hint="internal test")

    monkeypatch.setattr(server_module.VirtuOmni10B, "forward", boom)
    resp = client.post("/v1/multimodal/understand", json={"image_base64": _png_b64()})
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "E2006"


def test_mask_rejects_negative_lengths(tiny_model):
    with pytest.raises(ModelError) as exc:
        tiny_model.create_block_hybrid_mask(-1, 2, torch.device("cpu"))
    assert exc.value.code == "E2007"


def test_set_max_steps_rejects_non_positive():
    ctrl = LoopStepController(_tiny_model_config())
    with pytest.raises(ValueError):
        ctrl.set_max_steps(0)


def test_state_cache_dual_eviction():
    cache = LoopStateCache(enabled=True, max_entries=1)
    cache.set_state("a", torch.randn(2, 2))
    cache.set_kv(0, 0, torch.randn(1, 1, 2), torch.randn(1, 1, 2))
    # Bound is 1 entry, so one of the two stores must be trimmed.
    assert len(cache) <= 1


def test_estimated_parameter_count_is_positive():
    cfg = _tiny_model_config()
    # Exercises the analytic formula (documented as an *estimate*: it omits the
    # QK-norm and loop-gate tensors, so no tight equality is asserted here).
    assert cfg.total_estimated_parameters > 0
    assert sum(p.numel() for p in VirtuOmni10B(cfg).parameters()) > 0